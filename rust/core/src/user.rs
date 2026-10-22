//! The user's own language model: words and word pairs learned on the phone from the text as it
//! ends up (after autocorrect and the sentence fixer), mixed into the corpus model's
//! P(word | context) by [`crate::analyzer::Analyzer::p_context`]. Keyboard only.
//!
//! The keyboard shows it the text before the cursor after every finished word
//! ([`UserLm::observe`]); a sentence is learned once the next one is begun (so a word backspaced
//! and retyped is learned as it ends up), the last one when the message is done
//! ([`UserLm::commit`]: send, field cleared or left). Counts halve when the tables are full, so
//! old habits fade and the file stays small.

use std::collections::VecDeque;
use std::hash::{Hash, Hasher};

use crate::fx::{FxHasher, FxMap, FxSet};
use crate::lm::START;
use crate::text::*;

/// The user's share of the probability after a word the user wrote n times (followed by another):
/// USER_SHARE · n / (n + USER_RAMP). On the test sets learned in order (predict_sim.py --learn) the
/// top 3 moved within ±0.3 points for shares 0.3–0.7 and ramps 10–100; a share for the user's word
/// frequency regardless of the previous word added nothing.
const USER_SHARE: f64 = 0.5;
const USER_RAMP: f64 = 50.0;
/// discount on every user pair count (absolute discounting, as the corpus model)
const D: f32 = 0.5;
/// table sizes: past them every count halves and what drops below MIN_COUNT goes
const MAX_WORDS: usize = 10_000;
const MAX_PAIRS: usize = 40_000;
const MIN_COUNT: f32 = 0.4;
/// a word Varnelė doesn't know is predicted once the user has written it this often (a typo left
/// once is not a word)
pub const UNKNOWN_MIN: f32 = 2.0;
/// sentences remembered as learned (a refocused field is not learned twice)
const REMEMBER: usize = 1000;
const HEADER: &str = "varnele-user 1";

#[derive(Default)]
struct Word {
    count: f32,
    /// as the user writes it, when not all lowercase (TSR, Freiburg); empty otherwise
    written: String,
}

#[derive(Default)]
pub struct UserLm {
    /// off: neither learned nor used (the setting)
    pub enabled: bool,
    words: FxMap<String, Word>,
    total: f32,
    /// previous word -> followers
    pairs: FxMap<String, FxMap<String, f32>>,
    n_pairs: usize,
    /// the text before the cursor when last shown: its last sentence is not learned yet
    pending: String,
    learned: VecDeque<u64>,
    learned_set: FxSet<u64>,
    pub dirty: bool,
}

/// Sentences of a text as the corpus counts split them: after . ! ? and a space, or at a line end.
fn sentences(text: &str) -> Vec<&str> {
    let mut out = Vec::new();
    let mut start = 0;
    let mut prev_end = false;
    for (i, c) in text.char_indices() {
        if c == '\n' || (c.is_whitespace() && prev_end) {
            out.push(&text[start..i]);
            start = i + c.len_utf8();
        }
        prev_end = matches!(c, '.' | '!' | '?');
    }
    out.push(&text[start..]);
    out.into_iter().filter(|s| s.chars().any(char::is_alphabetic)).collect()
}

fn words_of(s: &str) -> impl Iterator<Item = &str> {
    s.split(|c: char| !c.is_alphabetic()).filter(|w| !w.is_empty())
}

/// A sentence's words: the same sentence with or without its full stop is learned once.
fn hash(s: &str) -> u64 {
    let mut h = FxHasher::default();
    for w in words_of(s) {
        w.hash(&mut h);
    }
    h.finish()
}

impl UserLm {
    /// Words the user has written, all occurrences counted.
    pub fn total(&self) -> f32 {
        self.total
    }

    /// The user's share of P(word | context) after `prev`: grows with how often the user wrote
    /// `prev` followed by a word, [`USER_SHARE`] · n / (n + [`USER_RAMP`]).
    pub fn share(&self, prev: &str) -> f64 {
        if !self.enabled {
            return 0.0;
        }
        let n = self.pairs.get(prev).map_or(0.0, |next| next.values().sum::<f32>()) as f64;
        USER_SHARE * n / (n + USER_RAMP)
    }

    /// P(w | prev) from the user's text alone, both lowercase (0 for a word never written).
    pub fn p_next(&self, prev: &str, w: &str) -> f64 {
        let pw = self.words.get(w).map_or(0.0, |x| x.count / self.total.max(1.0)) as f64;
        let Some(next) = self.pairs.get(prev) else { return pw };
        let total: f32 = next.values().sum();
        let c = next.get(w).copied().unwrap_or(0.0);
        ((c - D).max(0.0) / total) as f64 + (D * next.len() as f32 / total) as f64 * pw
    }

    /// How often the user wrote the word (lowercase), and how (empty: lowercase).
    pub fn word(&self, w: &str) -> Option<(f32, &str)> {
        self.words.get(w).map(|x| (x.count, x.written.as_str()))
    }

    /// Candidates for the next word after `prev` beginning with `prefix` (folded comparison,
    /// longer than it): the user's followers of `prev`, then the user's most frequent words.
    pub fn candidates(&self, prev: &str, prefix: &str, n: usize) -> Vec<String> {
        if !self.enabled {
            return Vec::new();
        }
        let fp = fold(prefix);
        let fits = |w: &str| clen(w) > clen(prefix) && fold(w).starts_with(&fp);
        let mut out: Vec<(String, f32)> = match self.pairs.get(prev) {
            Some(next) => next.iter().filter(|(w, _)| fits(w)).map(|(w, &c)| (w.clone(), c)).collect(),
            None => Vec::new(),
        };
        out.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap().then_with(|| a.0.cmp(&b.0)));
        out.truncate(n);
        let mut top: Vec<(&String, f32)> =
            self.words.iter().filter(|(w, _)| fits(w)).map(|(w, x)| (w, x.count)).collect();
        top.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap().then_with(|| a.0.cmp(b.0)));
        for (w, c) in top.into_iter().take(n) {
            if !out.iter().any(|o| &o.0 == w) {
                out.push((w.clone(), c));
            }
        }
        out.into_iter().map(|(w, _)| w).collect()
    }

    /// Learn one sentence (words of letters; the first follows the sentence start).
    pub fn learn_sentence(&mut self, s: &str) {
        let mut prev = START.to_string();
        for (i, w) in words_of(s).enumerate() {
            let lw = lower(w);
            let e = self.words.entry(lw.clone()).or_default();
            e.count += 1.0;
            // the first word's capital is the sentence's; a lowercase one mid-sentence says it is not a name
            if i > 0 || w != capitalize(&lw) {
                e.written = if w == lw { String::new() } else { w.to_string() };
            }
            self.total += 1.0;
            let next = self.pairs.entry(prev).or_default();
            let c = next.entry(lw.clone()).or_insert(0.0);
            if *c == 0.0 {
                self.n_pairs += 1;
            }
            *c += 1.0;
            prev = lw;
        }
        self.dirty = true;
        if self.words.len() > MAX_WORDS || self.n_pairs > MAX_PAIRS {
            self.halve();
        }
    }

    /// Learn every sentence of a text (the evaluations' shortcut for a user who wrote it).
    pub fn learn_text(&mut self, text: &str) {
        for s in sentences(text) {
            self.learn_sentence(s);
        }
    }

    /// Halve every count and drop the ones that fall below [`MIN_COUNT`]: recent and frequent
    /// words stay, a word seen once long ago goes.
    fn halve(&mut self) {
        while self.words.len() > MAX_WORDS * 9 / 10 || self.n_pairs > MAX_PAIRS * 9 / 10 {
            self.words.retain(|_, x| {
                x.count /= 2.0;
                x.count >= MIN_COUNT
            });
            self.total = self.words.values().map(|x| x.count).sum();
            self.n_pairs = 0;
            for next in self.pairs.values_mut() {
                next.retain(|_, c| {
                    *c /= 2.0;
                    *c >= MIN_COUNT
                });
                self.n_pairs += next.len();
            }
            self.pairs.retain(|_, next| !next.is_empty());
        }
    }

    fn learn_once(&mut self, s: &str) {
        let h = hash(s);
        if !self.learned_set.insert(h) {
            return;
        }
        self.learned.push_back(h);
        if self.learned.len() > REMEMBER {
            let old = self.learned.pop_front().unwrap();
            self.learned_set.remove(&old);
        }
        self.learn_sentence(s);
    }

    /// The text before the cursor after a finished word, as it ends up. Sentences followed by
    /// the start of another are learned (once each); the last one waits.
    pub fn observe(&mut self, text: &str) {
        if !self.enabled {
            return;
        }
        let ss = sentences(text);
        if let Some((_, done)) = ss.split_last() {
            for s in done {
                self.learn_once(s);
            }
        }
        self.pending = text.to_string();
    }

    /// The message is done (sent, field cleared or left): learn the last sentence too.
    pub fn commit(&mut self) {
        let text = std::mem::take(&mut self.pending);
        if !self.enabled {
            return;
        }
        for s in sentences(&text) {
            self.learn_once(s);
        }
    }

    /// Forget everything learned.
    pub fn clear(&mut self) {
        let enabled = self.enabled;
        *self = UserLm { enabled, dirty: true, ..Default::default() };
    }

    /// The counts as text: a header line, then `1 TAB word TAB count [TAB written]` and
    /// `2 TAB prev TAB word TAB count`.
    pub fn to_text(&self) -> String {
        let mut out = String::from(HEADER);
        out.push('\n');
        let mut ws: Vec<_> = self.words.iter().collect();
        ws.sort_by(|a, b| a.0.cmp(b.0));
        for (w, x) in ws {
            out += &format!("1\t{w}\t{}", x.count);
            if !x.written.is_empty() {
                out += &format!("\t{}", x.written);
            }
            out.push('\n');
        }
        let mut ps: Vec<_> = self.pairs.iter().flat_map(|(p, next)| next.iter().map(move |(w, c)| (p, w, c))).collect();
        ps.sort_by(|a, b| (a.0, a.1).cmp(&(b.0, b.1)));
        for (p, w, c) in ps {
            out += &format!("2\t{p}\t{w}\t{c}\n");
        }
        out
    }

    /// Counts written by [`Self::to_text`]; nothing (an empty model) if the text is not one.
    pub fn from_text(text: &str) -> UserLm {
        let mut u = UserLm::default();
        let mut lines = text.lines();
        if lines.next() != Some(HEADER) {
            return u;
        }
        for line in lines {
            let f: Vec<&str> = line.split('\t').collect();
            match f.as_slice() {
                ["1", w, c, rest @ ..] => {
                    let Ok(c) = c.parse::<f32>() else { continue };
                    u.total += c;
                    u.words.insert(w.to_string(), Word { count: c, written: rest.first().unwrap_or(&"").to_string() });
                }
                ["2", p, w, c] => {
                    let Ok(c) = c.parse::<f32>() else { continue };
                    u.pairs.entry(p.to_string()).or_default().insert(w.to_string(), c);
                    u.n_pairs += 1;
                }
                _ => {}
            }
        }
        u
    }

    /// Load the counts from a file (keeping `enabled`); a missing or broken file is an empty model.
    pub fn load(&mut self, path: &str) {
        let enabled = self.enabled;
        *self = UserLm::from_text(&std::fs::read_to_string(path).unwrap_or_default());
        self.enabled = enabled;
    }

    /// Write the counts to a file if they changed (through a temporary file, so a crash
    /// leaves the old one).
    pub fn save(&mut self, path: &str) -> std::io::Result<()> {
        if !self.dirty {
            return Ok(());
        }
        let tmp = format!("{path}.tmp");
        std::fs::write(&tmp, self.to_text())?;
        std::fs::rename(&tmp, path)?;
        self.dirty = false;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn user() -> UserLm {
        UserLm { enabled: true, ..Default::default() }
    }

    #[test]
    fn learns_finished_sentences_once() {
        let mut u = user();
        u.observe("Labas, kaip ");
        assert_eq!(u.total(), 0.0); // the sentence is not finished
        u.observe("Labas, kaip sekasi? Gerai ");
        assert_eq!(u.total(), 3.0);
        u.observe("Labas, kaip sekasi? Gerai, ačiū. Tu ");
        assert_eq!(u.total(), 5.0); // the first sentence is not learned again
        u.commit();
        assert_eq!(u.total(), 6.0);
        assert!(u.p_next("kaip", "sekasi") > 0.3);
        assert!(u.p_next(START, "labas") > 0.0);
    }

    #[test]
    fn backspaced_words_are_not_learned() {
        let mut u = user();
        u.observe("Mes einam i ");
        u.observe("Mes einame į ");
        u.observe("Mes einame į parką. ");
        assert_eq!(u.total(), 0.0); // the last sentence waits for the message to be done
        u.commit();
        u.observe("Mes einame į parką");
        u.commit(); // the same sentence again (field refocused)
        assert_eq!(u.total(), 4.0);
        assert!(u.word("einame").is_some() && u.word("einam").is_none() && u.word("i").is_none());
    }

    #[test]
    fn names_keep_their_capital() {
        let mut u = user();
        u.learn_text("Rytoj su Freiburg. Freiburg laimės.");
        assert_eq!(u.word("freiburg").unwrap().1, "Freiburg");
        u.learn_text("Labas.");
        assert_eq!(u.word("labas").unwrap().1, ""); // a sentence start says nothing
    }

    #[test]
    fn halving_bounds_the_tables_and_text_round_trips() {
        let mut u = user();
        for i in 0..(MAX_WORDS + 10) {
            u.learn_sentence(&format!("žodis {}", "a".repeat(i % 50 + 1) + &"b".repeat(i / 50)));
        }
        assert!(u.words.len() <= MAX_WORDS && u.n_pairs <= MAX_PAIRS);
        assert!(u.word("žodis").is_some());
        let v = UserLm::from_text(&u.to_text());
        assert_eq!(v.words.len(), u.words.len());
        assert_eq!(v.n_pairs, u.n_pairs);
        assert!((v.total() - u.total()).abs() < 1.0);
    }

    #[test]
    fn disabled_learns_nothing() {
        let mut u = UserLm::default();
        u.observe("Labas. Kaip ");
        u.commit();
        assert_eq!(u.total(), 0.0);
        assert_eq!(u.share(START), 0.0);
    }
}
