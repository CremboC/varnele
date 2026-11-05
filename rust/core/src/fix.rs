//! What Varnelė changes without asking, for every app that types: the keyboard, the desktop app, the
//! simulations. An app says what was typed and applies the edit it gets back.

use std::collections::BTreeMap;

use crate::checker::{Checker, KeyboardWord, WordStatus};
use crate::text::*;

/// context rules whose first fix may change letters, not only diacritics
const SURE_RULES: [&str; 4] = ["subject", "rare", "formal", "phrase"];
/// rules the sentence fixer applies, by diacritics only
const SAFE_RULES: [&str; 9] = ["case", "agreement", "quantity", "negation", "relative", "object", "subject", "phrase", "valency"];
/// rules whose fixes of earlier words may change letters too
const LETTER_RULES: [&str; 1] = ["phrase"];
/// the top suggestion wins by this much: only then are diacritics chosen without asking
const CLEAR_MARGIN: f64 = 0.08;
/// a fix may cost this much ignoring diacritics: one typo
const MAX_TYPO_COST: f64 = 1.0;
/// the last words of the sentence whose autocorrected diacritics may change
const SOFT_WINDOW: usize = 6;
/// the words of the sentence the grammar sees for a word just finished
const CONTEXT_WORDS: usize = 3;

/// the letters only Lithuanian writes here
const LETTERS: &str = "ąčęėįšųūž";
/// fewer words than this say nothing of the language, unless one has those letters
const MIN_WORDS: usize = 3;
/// the share of words Lithuanian could have written: subtitle lines keep 97-98%, English 1-2%
const MIN_LITHUANIAN: f64 = 0.7;

fn lower_char(c: char) -> char {
    c.to_lowercase().next().unwrap_or(c)
}

/// A word as keys: lowercase, no diacritics; y stays, it is its own key (šita, not syta).
fn keys(s: &str) -> String {
    lower(s).chars().map(|c| if c == 'y' { c } else { fold_char(c) }).collect()
}

/// The same keys pressed: only diacritics differ.
fn same_keys(a: &str, b: &str) -> bool {
    keys(a) == keys(b)
}

/// Runs of letters in `chars`: (start, end).
fn letter_runs(chars: &[char]) -> Vec<(usize, usize)> {
    let mut out = Vec::new();
    let mut i = 0;
    while i < chars.len() {
        if chars[i].is_alphabetic() {
            let a = i;
            while i < chars.len() && chars[i].is_alphabetic() {
                i += 1;
            }
            out.push((a, i));
        } else {
            i += 1;
        }
    }
    out
}

/// Where the sentence before the cursor starts: after the last sentence end, not counting the last
/// character (`sakinys.` is still that sentence).
fn sentence_start(chars: &[char]) -> usize {
    let mut i = chars.len().saturating_sub(1);
    while i > 0 {
        i -= 1;
        if ".!?\n".contains(chars[i]) {
            return i + 1;
        }
    }
    0
}

/// How much of a text speaks for Lithuanian, for apps that see every language (add up a field's
/// paragraphs): its words, not counting names; the ones Lithuanian can't have written; whether one
/// has Lithuanian letters.
#[derive(Clone, Copy, Debug, Default)]
pub struct Tally {
    pub words: usize,
    pub foreign: usize,
    pub marked: bool,
}

impl Tally {
    /// `found`: what [`Checker::check_text`] found in `text`. A word is foreign when it is unknown and
    /// not a Lithuanian word short of its diacritics; a capital inside a sentence is a name.
    pub fn of(text: &str, found: &[crate::checker::Finding]) -> Tally {
        let chars: Vec<char> = text.chars().collect();
        let runs = letter_runs(&chars);
        let mut t = Tally { words: runs.len(), foreign: 0, marked: chars.iter().any(|c| LETTERS.contains(lower_char(*c))) };
        for f in found.iter().filter(|f| f.rule == "unknown") {
            let opener = chars[..f.start].iter().rev().find(|c| !c.is_whitespace());
            if f.start > 0 && first_upper(&f.word) && !opener.is_some_and(|c| ".!?\n".contains(*c)) {
                t.words = t.words.saturating_sub(1);
            } else if f.suggestions.first().is_none_or(|s| fold(&lower(s)) != fold(&lower(&f.word))) {
                t.foreign += 1;
            }
        }
        t
    }

    pub fn add(&mut self, o: Tally) {
        self.words += o.words;
        self.foreign += o.foreign;
        self.marked |= o.marked;
    }

    /// Is this Lithuanian? None: too little to tell.
    pub fn is_lithuanian(&self) -> Option<bool> {
        if self.words == 0 || (self.words < MIN_WORDS && !self.marked) {
            return None;
        }
        Some((self.words - self.foreign.min(self.words)) as f64 / self.words as f64 >= MIN_LITHUANIAN)
    }
}

/// The last words of the sentence, for the word that follows them.
pub fn word_context(before: &str) -> String {
    let chars: Vec<char> = before.chars().collect();
    let start = chars.iter().rposition(|c| ".!?…\n".contains(*c)).map_or(0, |i| i + 1);
    let runs = letter_runs(&chars[start..]);
    let words: Vec<String> = runs.iter().map(|&(a, b)| chars[start + a..start + b].iter().collect()).collect();
    words[words.len().saturating_sub(CONTEXT_WORDS)..].join(" ")
}

impl KeyboardWord {
    pub fn is_valid(&self) -> bool {
        self.status != WordStatus::Unknown
    }

    /// Context fix `i` of a valid word is applied without asking: it only changes diacritics, or its
    /// rule is one of the sure ones (aš buvo -> buvau, kak -> kai, valgyt -> valgyti in formal mode,
    /// viena nukritusią sagutė -> nukritusi).
    pub fn is_sure(&self, i: usize) -> bool {
        self.context_fixes.get(i).is_some_and(|c| c.2 == 0.0 || (i == 0 && SURE_RULES.contains(&self.context_rule.as_str())))
    }

    /// Context (a grammar rule) already chose the order, or the top suggestion clearly wins.
    fn clearly_best(&self) -> bool {
        let s = &self.suggestions;
        !s.is_empty() && (self.context_rule == "context" || s.len() == 1 || s[1].1 - s[0].1 >= CLEAR_MARGIN)
    }

    /// How far context fix `i` may go: 2 applied without asking, 0 only offered.
    pub fn fix_level(&self, i: usize) -> u8 {
        if self.is_sure(i) { 2 } else { 0 }
    }

    /// How far suggestion `i` may go: 2 applied without asking, 1 autocorrect may take it, 0 only
    /// offered. The first of a key-shift search is the likely word, if nothing else matched.
    /// A name (a capital inside a sentence: Basteris) only becomes a name with diacritics added
    /// (Siauliuose -> Šiauliuose; not Šantarų -> Santarų, Bresto -> Bręsto).
    pub fn suggestion_level(&self, i: usize) -> u8 {
        let Some(s) = self.suggestions.get(i) else { return 0 };
        if self.name && !self.name_fixes.contains(&s.0) {
            0
        } else if self.key_shift && i == 0 {
            1
        } else if i == 0 && self.clearly_best() && s.2 == 0.0 {
            2
        } else if s.2 <= MAX_TYPO_COST {
            1
        } else {
            0
        }
    }

    /// The fix that is safe to apply to a word already committed: only diacritics change and it is
    /// the clear choice, or a sure rule's.
    pub fn confident_fix(&self) -> Option<&str> {
        if self.is_valid() {
            return if self.is_sure(0) { self.context_fixes.first().map(|c| c.0.as_str()) } else { None };
        }
        (self.clearly_best() && self.suggestions[0].2 == 0.0 && !self.key_shift).then(|| self.suggestions[0].0.as_str())
    }

    /// What autocorrect commits when the word is finished, if it isn't the word as typed.
    pub fn autocorrection(&self) -> Option<&str> {
        if self.is_valid() {
            let first = self.context_fixes.first()?;
            if self.is_sure(0) {
                return Some(&first.0);
            }
            return self.context_fixes.iter().find(|c| c.2 == 0.0).map(|c| c.0.as_str());
        }
        let top = self.suggestions.first()?;
        (top.2 <= MAX_TYPO_COST && !(self.name && self.suggestion_level(0) == 0)).then_some(top.0.as_str())
    }
}

#[derive(Clone, Copy, Debug)]
pub struct FixOptions {
    /// the last word was picked from a list: the user chose it, only earlier words and commas change
    pub picked: bool,
    /// fix words before the one just finished
    pub earlier: bool,
    pub commas: bool,
    pub formal: bool,
}

/// Change the text before the cursor: delete characters, then type some.
#[derive(Clone, Debug, Default, PartialEq)]
pub struct Edit {
    pub delete: usize,
    pub insert: String,
}

/// The sentence fixer's edit around the cursor: `before` as [`Edit`]; after the cursor, leave `skip`
/// characters, delete `after.delete` more and put `after.insert` there. The cursor stays where it is,
/// after `before.insert`.
#[derive(Clone, Debug, Default, PartialEq)]
pub struct AroundEdit {
    pub before: Edit,
    pub skip: usize,
    pub after: Edit,
}

/// Runs after each finished word, on the sentence before the cursor: fixes the word just finished, if
/// the app committed it as typed (punctuation, a learned word), earlier words by the words after them
/// (visu … žodžių -> visų) and missing commas; diacritics only, except the phrase rule's.
///
/// Diacritics the app gave a word itself (autocorrect chose žiemą for "ziema", the more frequent
/// twin) are not trusted like typed ones: once later words are typed, the sentence is checked with
/// that word as typed and it may get other diacritics (kad žiemą žymiai rimtesne -> žiema). A word
/// whose autocorrection was undone stays as it is.
#[derive(Default)]
pub struct SentenceFixer {
    /// words of the current sentence that got their diacritics from the app: index -> as typed
    soft: BTreeMap<usize, String>,
    /// where that sentence starts in the field
    sentence: Option<usize>,
}

impl SentenceFixer {
    fn enter(&mut self, at: usize) {
        if self.sentence != Some(at) {
            self.soft.clear();
            self.sentence = Some(at);
        }
    }

    /// Autocorrect committed `committed` for `typed`; `before` is the text before the cursor, which
    /// ends with it, and `base` where that text starts in the field.
    pub fn autocorrected(&mut self, before: &str, base: usize, typed: &str, committed: &str) {
        if typed == committed || !same_keys(typed, committed) {
            return;
        }
        let chars: Vec<char> = before.chars().collect();
        let start = sentence_start(&chars);
        self.enter(base + start);
        let words = letter_runs(&chars[start..]).len();
        if words > 0 {
            self.soft.insert(words - 1, typed.to_string());
        }
    }

    /// The last autocorrection was undone: its word stays as typed.
    pub fn undone(&mut self) {
        self.soft.pop_last();
    }

    /// The edit for the text before the cursor, after a finished word. See [`SentenceFixer`].
    pub fn apply(&mut self, ck: &Checker, before: &str, base: usize, o: FixOptions) -> Option<Edit> {
        self.apply_around(ck, before, "", base, o).map(|e| e.before)
    }

    /// The same with the text after the cursor (`after`, as much as the app has): the whole sentence
    /// the cursor is in is checked, and its words after the cursor are fixed too, as earlier words are
    /// (a word typed into the middle of a sentence: kad ziema | zymiai rimtesne -> žiema, rimtesnė).
    pub fn apply_around(&mut self, ck: &Checker, before: &str, after: &str, base: usize, o: FixOptions) -> Option<AroundEdit> {
        let chars: Vec<char> = before.chars().collect();
        let start = sentence_start(&chars);
        let sentence = &chars[start..];
        if sentence.iter().all(|c| c.is_whitespace()) {
            return None;
        }
        let after: Vec<char> = after.chars().collect();
        let tail = &after[..sentence_end(&after)];
        self.enter(base + start);
        let last = letter_runs(sentence).last().copied();
        let (last_start, last_end) = last.unwrap_or((sentence.len(), sentence.len()));

        let mut fixed: Vec<char> = sentence.to_vec();
        if let (false, Some((a, b))) = (o.picked, last) {
            let rest: String = tail.iter().collect();
            if let Some(word) = last_word_fix(ck, sentence, a, b, &rest, o.formal) {
                let typed: String = sentence[a..b].iter().collect();
                fixed.splice(a..b, word.chars());
                let new_end = a + clen(&word);
                let committed: String = fixed[a..new_end].iter().collect();
                if same_keys(&typed, &committed) {
                    self.soft.insert(letter_runs(&fixed).len() - 1, typed);
                }
            }
        }
        let words_before = letter_runs(&fixed).len();
        let mut cursor = fixed.len();
        let last_end = last_end + cursor - sentence.len();
        fixed.extend_from_slice(tail);
        if o.earlier {
            self.fix_soft(ck, &mut fixed, words_before);
        }
        // the words after the cursor were checked when they were typed: only what the word just finished
        // changes there is fixed (į | didele kavine), not what was there without it (a fix the user undid)
        let old: Vec<(usize, usize, String)> = if tail.iter().any(|c| c.is_alphabetic()) {
            let without: String = sentence[..last_start].iter().chain(tail.iter()).collect();
            ck.check_text(&without, false, true).into_iter().filter(|f| f.start >= last_start)
                .map(|f| (f.start - last_start, f.end - last_start, f.suggestions.first().cloned().unwrap_or_default()))
                .collect()
        } else {
            Vec::new()
        };
        // a second pass catches what the first fix reveals: kuriu -> kurių then needs a comma
        for _ in 0..2 {
            fixed = fix_pass(ck, fixed, (last_start, last_end), &mut cursor, &old, o);
        }
        let (head, rest) = fixed.split_at(cursor);
        if head == sentence && rest == tail {
            return None;
        }
        let same = head.iter().zip(sentence).take_while(|(a, b)| a == b).count();
        let before_edit = Edit { delete: sentence.len() - same, insert: head[same..].iter().collect() };
        let skip = rest.iter().zip(tail).take_while(|(a, b)| a == b).count();
        let same = rest[skip..].iter().rev().zip(tail[skip..].iter().rev()).take_while(|(a, b)| a == b).count();
        let after_edit = Edit { delete: tail.len() - skip - same, insert: rest[skip..rest.len() - same].iter().collect() };
        Some(AroundEdit { before: before_edit, skip, after: after_edit })
    }

    /// The words that got diacritics from the app, among the last [`SOFT_WINDOW`] before the cursor (`n`
    /// words), checked as typed; one with nothing after it yet in the sentence (the word just finished at
    /// its end) waits. A word that no longer looks like the one typed (edited) is forgotten.
    fn fix_soft(&mut self, ck: &Checker, sentence: &mut Vec<char>, n: usize) {
        if self.soft.is_empty() {
            return;
        }
        let words = letter_runs(sentence);
        let mut typed = sentence.clone();
        self.soft.retain(|&k, t| {
            let Some(&(a, b)) = words.get(k) else { return false };
            let now: String = sentence[a..b].iter().collect();
            if !same_keys(&now, t) {
                return false;
            }
            if k + SOFT_WINDOW >= n && k + 1 < words.len() {
                typed.splice(a..b, t.chars());
            }
            true
        });
        if typed == *sentence {
            return;
        }
        let (committed, as_typed): (String, String) = (sentence.iter().collect(), typed.iter().collect());
        for (a, b, w) in ck.keyboard_soft(&committed, &as_typed).into_iter().rev() {
            sentence.splice(a..b, w.chars());
        }
    }
}

/// The word in `sentence[a..b]`, just finished, if the app left it as typed although its fix is sure;
/// `after`: the rest of the sentence after the cursor.
fn last_word_fix(ck: &Checker, sentence: &[char], a: usize, b: usize, after: &str, formal: bool) -> Option<String> {
    if b - a < 2 {
        return None;
    }
    let word: String = sentence[a..b].iter().collect();
    let r = if after.trim().is_empty() {
        ck.keyboard_word(&word, &word_context(&sentence[..a].iter().collect::<String>()), false, formal)
    } else {
        // the whole sentence: kad ziema | žymiai rimtesnė -> žiema, not the more frequent žiemą
        let after: String = sentence[b..].iter().collect::<String>() + after;
        ck.keyboard_word_in(&word, &sentence[..a].iter().collect::<String>(), &after, false, formal)
    };
    let fix = cap_like(&word, r.confident_fix()?);
    if fix == word {
        return None;
    }
    // a diacritic fix keeps the letters; only a few rules may change them (aš buvo -> buvau)
    (SURE_RULES.contains(&r.context_rule.as_str()) || same_keys(&fix, &word)).then_some(fix)
}

/// Where the sentence after the cursor ends: at its full stop (included) or line break.
fn sentence_end(after: &[char]) -> usize {
    match after.iter().position(|c| ".!?\n".contains(*c)) {
        Some(i) if after[i] == '\n' => i,
        Some(i) => i + 1,
        None => after.len(),
    }
}

/// One pass of grammar fixes over the sentence; `last` is the word just finished, `cursor` where the
/// cursor stands (moved along with the edits before it).
fn fix_pass(ck: &Checker, sentence: Vec<char>, last: (usize, usize), cursor: &mut usize, old: &[(usize, usize, String)],
            o: FixOptions) -> Vec<char> {
    let (last_start, last_end) = last;
    let text: String = sentence.iter().collect();
    let mut out = sentence.clone();
    let mut found = ck.check_text(&text, false, true);
    found.sort_by_key(|f| std::cmp::Reverse(f.start));
    let moved = |at: usize, by: isize, cursor: &mut usize| {
        if at < *cursor {
            *cursor = (*cursor as isize + by) as usize;
        }
    };
    for f in found {
        if o.picked && f.rule != "comma" && f.start < last_end && f.end > last_start {
            continue; // the word picked from the list stays as chosen
        }
        if f.start >= *cursor {
            let first = f.suggestions.first().cloned().unwrap_or_default();
            if old.iter().any(|(a, b, s)| *a == f.start - *cursor && *b == f.end - *cursor && *s == first) {
                continue; // after the cursor and there without the word just finished: seen before
            }
        }
        if f.rule == "comma" {
            // wait for the next word: pirk bet may become pirk bet ką (no comma)
            let next_typed = sentence[f.end..].iter().any(|c| c.is_alphabetic());
            if o.commas && next_typed && f.start >= 2 && sentence[f.start - 1] == ' ' && sentence[f.start - 2].is_alphabetic() {
                out.insert(f.start - 1, ',');
                moved(f.start - 1, 1, cursor);
            }
        } else if SAFE_RULES.contains(&f.rule) && (o.earlier || (f.start >= last_start && f.end <= last_end)) {
            let Some(s) = f.suggestions.first() else { continue };
            if *s != f.word && (LETTER_RULES.contains(&f.rule) || same_keys(s, &f.word)) {
                out.splice(f.start..f.end, s.chars());
                moved(f.start, clen(s) as isize - (f.end - f.start) as isize, cursor);
            }
        }
    }
    out
}
