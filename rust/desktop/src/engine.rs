//! What the desktop app does with the keys typed, whatever the operating system: keeps its own copy
//! of the text being typed and, when whitespace finishes a word, says how to change that word. The
//! same decisions as the keyboard (VarneleDictionary.kt), which eval/keyboard_sim.py mirrors.

use std::collections::HashSet;

use varnele::text::lower;
use varnele::{Checker, KeyboardWord, WordStatus};

/// context rules whose first fix may change letters, not only diacritics
const SURE_RULES: [&str; 4] = ["subject", "rare", "formal", "phrase"];
/// a fix may cost this much ignoring diacritics: one typo
const MAX_TYPO_COST: f64 = 1.0;
/// no word is this long, and text is dropped from the front beyond the second limit
const MAX_TOKEN: usize = 40;
const MAX_TEXT: usize = 400;
/// the words of the sentence the grammar sees, as on the keyboard
const CONTEXT_WORDS: usize = 3;
/// How far the text can lean to one language. One English word is enough to stop (a wrong fix of
/// English is worse than a Lithuanian word left as typed); this many Lithuanian words start again.
const MAX_LEAN: i32 = 2;

/// A key as the app sees it, after the platform layer has decoded it.
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Key {
    /// a character typed (whitespace included)
    Char(char),
    Backspace,
    /// enter or tab: finishes the word, and what is typed next is somewhere else
    Enter,
    /// arrows, home, delete, a dead key, a shortcut: the cursor may be inside a word now
    Moved,
    /// a click or another app: the text is not ours any more, but the next word is a word
    Reset,
}

/// Change the text before the cursor: delete characters, then type some.
#[derive(Clone, Debug, PartialEq)]
pub struct Edit {
    pub delete: usize,
    pub insert: String,
}

#[derive(Clone, Debug, PartialEq)]
pub enum Action {
    /// let the key through
    Pass,
    /// apply the edit, then let the key through
    Before(Edit),
    /// apply the edit instead of the key
    Instead(Edit),
}

/// The last fix, while backspace can still undo it.
struct LastFix {
    typed: String,
    fixed: String,
    /// what followed the word and stays: trailing punctuation and the space
    tail: String,
}

#[derive(Default)]
pub struct Engine {
    /// the sentence as it stands, up to the cursor
    text: String,
    /// the cursor may be inside a word we didn't see all of: leave the current word alone
    dirty: bool,
    /// > 0: the last words were English, which is left alone
    lean: i32,
    last: Option<LastFix>,
    /// the last word, fixed although it is English too (is -> iš): the next word may take that back
    doubtful: Option<LastFix>,
    /// words whose fix backspace undid: leave them alone from now on (lowercase)
    kept: HashSet<String>,
    pub formal: bool,
    /// the system's English dictionary; the desktop has one keyboard for every language
    pub english: Option<Box<dyn Fn(&str) -> bool>>,
}

/// The fix to apply without asking, as VarneleDictionary.getSuggestions marks them.
pub fn autocorrect(r: &KeyboardWord) -> Option<&str> {
    if r.status != WordStatus::Unknown {
        let first = r.context_fixes.first()?;
        if first.2 == 0.0 || SURE_RULES.contains(&r.context_rule.as_str()) {
            return Some(&first.0);
        }
        return r.context_fixes.iter().find(|c| c.2 == 0.0).map(|c| c.0.as_str());
    }
    let top = r.suggestions.first()?;
    (top.2 <= MAX_TYPO_COST).then_some(top.0.as_str())
}

/// The change from one word to another, keeping what they share at the start, so an app sees as
/// few keys as possible. Counted in characters.
pub fn diff(from: &str, to: &str) -> Edit {
    let same = from.chars().zip(to.chars()).take_while(|(a, b)| a == b).count();
    Edit { delete: from.chars().count() - same, insert: to.chars().skip(same).collect() }
}

const OPENING: &[char] = &['(', '[', '{', '„', '“', '"', '\'', '«'];
const CLOSING: &[char] = &['.', ',', ';', ':', '!', '?', ')', ']', '}', '”', '“', '"', '\'', '»', '…'];
const SENTENCE_ENDS: &[char] = &['.', '!', '?', '…'];

/// The word inside a token (what is between two spaces), with what comes after it, if it is only
/// letters: `(sakini?` -> `sakini`, `?`; not `www.google.com`, `a1`, `x@y`.
fn word_of(token: &str) -> Option<(&str, &str)> {
    let t = token.trim_start_matches(OPENING);
    let word = t.trim_end_matches(CLOSING);
    let ok = !word.is_empty() && word.chars().count() <= MAX_TOKEN && word.chars().all(char::is_alphabetic);
    ok.then(|| (word, &t[word.len()..]))
}

impl Engine {
    pub fn new() -> Engine {
        Engine::default()
    }

    pub fn key(&mut self, ck: &Checker, key: Key) -> Action {
        match key {
            Key::Char(c) if c.is_whitespace() => {
                let edit = self.finish_word(ck);
                self.text.push(c);
                self.trim();
                if let Some(l) = &mut self.last {
                    l.tail.push(c);
                }
                edit.map_or(Action::Pass, Action::Before)
            }
            Key::Char(c) => {
                self.last = None;
                self.text.push(c);
                self.trim();
                Action::Pass
            }
            Key::Backspace => self.backspace(),
            Key::Enter => {
                let edit = self.finish_word(ck);
                self.reset();
                edit.map_or(Action::Pass, Action::Before)
            }
            Key::Moved => {
                self.reset();
                self.dirty = true;
                Action::Pass
            }
            Key::Reset => {
                self.reset();
                Action::Pass
            }
        }
    }

    /// Another app: its text may be in another language.
    pub fn new_app(&mut self) {
        self.reset();
        self.lean = 0;
    }

    pub fn is_english(&self) -> bool {
        self.lean > 0
    }

    /// The fix just made, while backspace can undo it: typed, fixed.
    pub fn last_fix(&self) -> Option<(&str, &str)> {
        self.last.as_ref().map(|l| (l.typed.as_str(), l.fixed.as_str()))
    }

    fn reset(&mut self) {
        self.text.clear();
        self.dirty = false;
        self.last = None;
        self.doubtful = None;
    }

    fn trim(&mut self) {
        let n = self.text.chars().count();
        if n > MAX_TEXT {
            self.text = self.text.chars().skip(n - MAX_TEXT).collect();
        }
    }

    fn backspace(&mut self) -> Action {
        if let Some(l) = self.last.take() {
            self.doubtful = None;
            // right after a fix: the word goes back as typed, what followed it stays
            self.kept.insert(lower(&l.typed));
            let end = format!("{}{}", l.fixed, l.tail);
            if let Some(before) = self.text.strip_suffix(end.as_str()) {
                self.text = format!("{before}{}{}", l.typed, l.tail);
                let d = diff(&l.fixed, &l.typed);
                return Action::Instead(Edit { delete: d.delete + l.tail.chars().count(), insert: d.insert + &l.tail });
            }
        }
        if self.text.pop().is_none() {
            self.dirty = true;   // into text we never saw
        }
        Action::Pass
    }

    /// The fix of the word before the cursor, now finished.
    fn finish_word(&mut self, ck: &Checker) -> Option<Edit> {
        self.last = None;
        let doubtful = self.doubtful.take();
        let dirty = std::mem::take(&mut self.dirty);
        let start = self.text.char_indices().rev().find(|(_, c)| c.is_whitespace()).map_or(0, |(i, c)| i + c.len_utf8());
        let (before, token) = self.text.split_at(start);
        let (word, tail) = word_of(token)?;
        let r = ck.keyboard_word(word, &context(before), false, self.formal);
        // English and valid (man, to) or a word short of its diacritics (is, as) says nothing
        let english = word.is_ascii() && self.english.as_ref().is_some_and(|f| f(word));
        let lithuanian = matches!(r.status, WordStatus::Ok | WordStatus::Colloquial)
            || r.suggestions.first().is_some_and(|s| s.2 == 0.0);
        if english && !lithuanian {
            self.lean = (self.lean.max(0) + 1).min(MAX_LEAN);
            return doubtful.and_then(|d| self.take_back(d, start));
        }
        if lithuanian && !english {
            self.lean = (self.lean - 1).max(-MAX_LEAN);
        }
        if self.lean > 0 || (english && !lithuanian) || dirty || self.kept.contains(&lower(word)) {
            return None;
        }
        let fix = autocorrect(&r).filter(|f| *f != word)?.to_string();
        let d = diff(word, &fix);
        let edit = Edit { delete: d.delete + tail.chars().count(), insert: d.insert + tail };
        let last = LastFix { typed: word.to_string(), fixed: fix.clone(), tail: tail.to_string() };
        let head = &self.text[..self.text.len() - word.len() - tail.len()];
        self.text = format!("{head}{fix}{tail}");
        if english {
            self.doubtful = Some(LastFix { typed: last.typed.clone(), fixed: last.fixed.clone(), tail: last.tail.clone() });
        }
        self.last = Some(last);
        Some(edit)
    }

    /// The word before the one that starts at `start` goes back as typed: it was English after all.
    fn take_back(&mut self, d: LastFix, start: usize) -> Option<Edit> {
        let (before, token) = self.text.split_at(start);
        let spaces = before.chars().rev().take_while(|c| c.is_whitespace()).count();
        let rest: String = before.chars().skip(before.chars().count() - spaces).collect();
        let head = before.strip_suffix(rest.as_str())?.strip_suffix(d.tail.as_str())?.strip_suffix(d.fixed.as_str())?;
        let diff = diff(&d.fixed, &d.typed);
        let after = format!("{}{rest}{token}", d.tail);
        let edit = Edit { delete: diff.delete + after.chars().count(), insert: diff.insert + &after };
        self.text = format!("{head}{}{after}", d.typed);
        Some(edit)
    }
}

/// The last words of the sentence, for the grammar.
fn context(before: &str) -> String {
    let sentence = before.rfind(SENTENCE_ENDS).map_or(before, |i| &before[i..]);
    let words: Vec<&str> = sentence.split(|c: char| !c.is_alphabetic()).filter(|w| !w.is_empty()).collect();
    words[words.len().saturating_sub(CONTEXT_WORDS)..].join(" ")
}

/// Type `text` through the engine, as if into an empty field; what the field ends up holding.
pub fn simulate(engine: &mut Engine, ck: &Checker, text: &str) -> String {
    let mut field: Vec<char> = Vec::new();
    for c in text.chars() {
        let key = if c == '\n' { Key::Enter } else { Key::Char(c) };
        let action = engine.key(ck, key);
        if let Action::Before(e) | Action::Instead(e) = &action {
            field.truncate(field.len() - e.delete);
            field.extend(e.insert.chars());
        }
        if !matches!(action, Action::Instead(_)) {
            field.push(c);
        }
    }
    field.into_iter().collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn checker() -> &'static std::sync::Mutex<Checker> {
        crate::checker()
    }

    fn typed(text: &str) -> String {
        let ck = checker().lock().unwrap();
        simulate(&mut Engine::new(), &ck, text)
    }

    fn with_english(text: &str, words: &'static [&'static str]) -> String {
        let ck = checker().lock().unwrap();
        let mut e = Engine::new();
        e.english = Some(Box::new(move |w| words.contains(&lower(w).as_str())));
        simulate(&mut e, &ck, text)
    }

    #[test]
    fn fixes_a_word_when_whitespace_finishes_it() {
        assert_eq!(typed("maciau "), "mačiau ");
        assert_eq!(typed("Maciau "), "Mačiau ");
        assert_eq!(typed("maciau\n"), "mačiau\n");
        assert_eq!(typed("maciau"), "maciau");
    }

    #[test]
    fn keeps_punctuation_around_the_word() {
        assert_eq!(typed("(del sakini?) "), "(dėl sakinį?) ");
    }

    #[test]
    fn uses_the_words_before_it() {
        assert_eq!(typed("as buvo "), "aš buvau ");
    }

    #[test]
    fn leaves_addresses_and_code_alone() {
        assert_eq!(typed("www.maciau.lt maciau1 x@maciau.lt "), "www.maciau.lt maciau1 x@maciau.lt ");
    }

    #[test]
    fn diff_keeps_the_shared_start() {
        assert_eq!(diff("maciau", "mačiau"), Edit { delete: 4, insert: "čiau".into() });
        assert_eq!(diff("as", "as"), Edit { delete: 0, insert: "".into() });
    }

    #[test]
    fn backspace_undoes_a_fix_for_good() {
        let ck = checker().lock().unwrap();
        let mut e = Engine::new();
        for c in "maciau".chars() {
            assert_eq!(e.key(&ck, Key::Char(c)), Action::Pass);
        }
        assert_eq!(e.key(&ck, Key::Char(' ')), Action::Before(Edit { delete: 4, insert: "čiau".into() }));
        assert_eq!(e.key(&ck, Key::Backspace), Action::Instead(Edit { delete: 5, insert: "ciau ".into() }));
        for c in "maciau".chars() {
            e.key(&ck, Key::Char(c));
        }
        assert_eq!(e.key(&ck, Key::Char(' ')), Action::Pass);
    }

    #[test]
    fn a_second_backspace_is_a_backspace() {
        let ck = checker().lock().unwrap();
        let mut e = Engine::new();
        for c in "maciau ".chars() {
            e.key(&ck, Key::Char(c));
        }
        assert!(matches!(e.key(&ck, Key::Backspace), Action::Instead(_)));
        assert_eq!(e.key(&ck, Key::Backspace), Action::Pass);
    }

    #[test]
    fn a_moved_cursor_leaves_the_next_word_alone() {
        let ck = checker().lock().unwrap();
        let mut e = Engine::new();
        e.key(&ck, Key::Moved);
        for c in "maciau".chars() {
            e.key(&ck, Key::Char(c));
        }
        assert_eq!(e.key(&ck, Key::Char(' ')), Action::Pass);
        for c in "maciau".chars() {
            e.key(&ck, Key::Char(c));
        }
        assert!(matches!(e.key(&ck, Key::Char(' ')), Action::Before(_)));
    }

    #[test]
    fn backspacing_into_unseen_text_leaves_the_word_alone() {
        let ck = checker().lock().unwrap();
        let mut e = Engine::new();
        e.key(&ck, Key::Backspace);
        for c in "maciau".chars() {
            e.key(&ck, Key::Char(c));
        }
        assert_eq!(e.key(&ck, Key::Char(' ')), Action::Pass);
    }

    #[test]
    fn english_is_left_alone_and_lithuanian_takes_over_again() {
        const EN: &[&str] = &["the", "is", "as", "in", "and", "man", "this"];
        assert_eq!(with_english("the man is in ", EN), "the man is in ");
        assert_eq!(with_english("as maciau ", EN), "aš mačiau ");
        assert_eq!(with_english("as maciau the man is in the house, ", EN), "aš mačiau the man is in the house, ");
        assert_eq!(with_english("is this the house? ", EN), "is this the house? ");
        assert_eq!(with_english("(is this the house? ", EN), "(is this the house? ");
        assert_eq!(with_english("the and maciau maciau maciau ", EN), "the and maciau mačiau mačiau ");
    }
}
