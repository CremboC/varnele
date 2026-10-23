//! Checking words and whole texts: the public entry point.

use std::collections::BTreeMap;

use crate::analyzer::{Analyzer, Status};
use crate::data::Data;
use crate::grammar::{Fit, Grammar, Issue};
use crate::text::*;

pub type Finding = Issue;

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum WordStatus {
    Ok,
    Colloquial,
    Unknown,
    Skip,
}

/// Result of [`Checker::keyboard_word`].
pub struct KeyboardWord {
    pub status: WordStatus,
    /// corrections for an unknown word: (word, cost, typo cost ignoring diacritics;
    /// 0 = only diacritics differ)
    pub suggestions: Vec<(String, f64, f64)>,
    /// a grammar rule that says this (valid) word must change, and its fixes
    pub context_rule: String,
    pub context_fixes: Vec<(String, f64, f64)>,
    /// the first suggestions come from the key-shift search
    pub key_shift: bool,
}

pub struct Checker {
    pub an: Analyzer,
    grammar: Grammar,
}

/// The ghost adds the next word from this probability. When the ghost is tapped, the next word is
/// the one that follows (or follows a comma the sentence fixer adds: `maniau, kad`) 71 / 72 / 73% of
/// the time on subtitles / Tatoeba / Wikipedia, appended on 2.5 / 4.8 / 6.4% of the taps; at 0.5
/// 57 / 66 / 67%, lower is worse still (eval/predict_sim.py --ghost). A wrong word costs a
/// backspace-word and a right one saves a few letters (kad, į, su), so precision first.
const GHOST_NEXT_P: f64 = 0.6;
/// A prediction the grammar rules out (a genitive after `į`) keeps this share of its probability.
const MISFIT: f64 = 0.01;
/// A genitive after a preposition that takes another case keeps this share: it may modify the
/// object to come (į Lietuvos sostinę).
const MODIFIER: f64 = 0.3;
/// Candidates the grammar re-ranks when the words before require a case.
const GRAMMAR_CANDIDATES: usize = 30;

const TLDS: &[&str] = &["lt", "com", "org", "net", "eu", "gov", "edu", "info"];

/// Blank out URLs and e-mail addresses (same positions, spaces instead).
fn blank_urls(chars: &mut [char]) {
    let n = chars.len();
    let mut i = 0;
    while i < n {
        if chars[i].is_whitespace() {
            i += 1;
            continue;
        }
        let start = i;
        while i < n && !chars[i].is_whitespace() {
            i += 1;
        }
        let run: String = chars[start..i].iter().collect();
        let mut from = None;
        // \S+\.(tld)\b\S*  -> the whole run
        for (k, _) in run.match_indices('.') {
            if k == 0 {
                continue;
            }
            let after = &run[k + 1..];
            if TLDS.iter().any(|t| {
                after.starts_with(t)
                    && after[t.len()..].chars().next().map_or(true, |c| !(c.is_alphanumeric() || c == '_'))
            }) {
                from = Some(0);
                break;
            }
        }
        // \S+@\S+
        if from.is_none() {
            if let Some(k) = run.find('@') {
                if k > 0 && k + 1 < run.len() {
                    from = Some(0);
                }
            }
        }
        // https?://\S+
        if from.is_none() {
            for pat in ["https://", "http://"] {
                if let Some(k) = run.find(pat) {
                    if run.len() > k + pat.len() {
                        from = Some(run[..k].chars().count());
                        break;
                    }
                }
            }
        }
        if let Some(f) = from {
            for c in &mut chars[start + f..i] {
                *c = ' ';
            }
        }
    }
}

/// (word, offset). Skips URLs/e-mails and ordinal tails like 1-ojo; a word followed
/// directly by "." is returned with the dot so abbreviations can be recognised.
pub fn tokens(text: &str) -> Vec<(String, usize)> {
    let mut chars: Vec<char> = text.chars().collect();
    blank_urls(&mut chars);
    let mut out = Vec::new();
    for (a, b) in word_spans(&chars) {
        if a >= 2 && (chars[a - 1] == '-' || chars[a - 1] == '‑') && chars[a - 2].is_numeric() {
            continue;
        }
        let mut w = substr(&chars, a, b);
        if chars.get(b) == Some(&'.') {
            w.push('.');
        }
        out.push((w, a));
    }
    out
}

fn is_roman(s: &str) -> bool {
    !s.is_empty() && s.chars().all(|c| "IVXLCDM".contains(c))
}

/// Letters Lithuanian doesn't use and the keys touching them (staggered rows: w is above a and s, not d).
const SLIP_KEYS: [(char, &str); 3] = [('w', "qeas"), ('q', "wa"), ('x', "zsdc")];
/// What may stand between a sentence's end and its first word.
const OPENERS: &str = " \t\"'„“”«»‘’([-–—";

/// Only spaces, quotes and brackets between the start of the text or a sentence end and `pos`.
fn sentence_start(chars: &[char], pos: usize) -> bool {
    let mut i = pos;
    while i > 0 && OPENERS.contains(chars[i - 1]) {
        i -= 1;
    }
    i == 0 || ".!?…\n".contains(chars[i - 1])
}

impl Checker {
    pub fn new(data: Data) -> Checker {
        Checker { an: Analyzer::new(data), grammar: Grammar::default() }
    }

    pub fn from_bytes(bytes: &[u8]) -> Result<Checker, String> {
        Ok(Checker::new(Data::load(bytes)?))
    }

    /// Status and suggestions for one word.
    pub fn check_word(&self, word: &str) -> (WordStatus, Vec<String>) {
        self.check_word_at(word, false)
    }

    /// [`Checker::check_word`]; `sentence_start`: a capital may be the keyboard's own (Ziwma is ziwma).
    pub fn check_word_at(&self, word: &str, sentence_start: bool) -> (WordStatus, Vec<String>) {
        let mut w = word;
        if let Some(stripped) = w.strip_suffix('.') {
            if self.an.data.abbrev.contains(&lower(w)) || clen(w) == 2 {
                return (WordStatus::Ok, vec![]);
            }
            w = stripped;
        }
        if is_foreign(w) || (is_upper(w) && clen(w) > 1) {
            let fix = self.slip_fixes(w, sentence_start);
            return if fix.is_empty() { (WordStatus::Skip, vec![]) } else { (WordStatus::Unknown, fix) };
        }
        let r = self.an.check(w);
        if r.status == Status::Unknown {
            if clen(w) == 1 {
                let lw = lower(w);
                let mut fix: Vec<(f64, String)> = self
                    .an
                    .folded_forms(&lw)
                    .into_iter()
                    .filter(|f| *f != lw)
                    .map(|f| (self.an.score(&lw, &f), f))
                    .collect();
                fix.sort_by(|a, b| a.0.partial_cmp(&b.0).unwrap().then_with(|| a.1.cmp(&b.1)));
                return if fix.is_empty() {
                    (WordStatus::Skip, vec![])
                } else {
                    (WordStatus::Unknown, fix.into_iter().map(|x| x.1).collect())
                };
            }
            if w.contains('-') || w.contains('‑') {
                let parts: Vec<&str> = w.split(['-', '‑']).filter(|p| !p.is_empty()).collect();
                if parts.len() == 2 && is_roman(parts[0]) {
                    return (WordStatus::Ok, vec![]);
                }
                if parts.iter().all(|p| is_foreign(p) || self.an.check(p).status != Status::Unknown) {
                    return (WordStatus::Ok, vec![]);
                }
            }
        }
        match r.status {
            Status::Colloquial => (WordStatus::Colloquial, r.formal),
            Status::Unknown => (WordStatus::Unknown, self.an.suggest(w, 5)),
            _ => (WordStatus::Ok, vec![]),
        }
    }

    /// A Lithuanian word with one finger slip onto w, q or x: the seen words it was meant to be,
    /// else none. The slip hit that key instead of one touching it (ziwma -> žiema, xiūrėti ->
    /// žiūrėti) or as well as a letter next to it that it touches (ziewma -> žiema). A foreign word
    /// stays foreign: one the corpus has (news, wifi), a name (a capital other than at a
    /// sentence start: Wiley), a word of 3 letters or fewer (tax, wp).
    fn slip_fixes(&self, w: &str, sentence_start: bool) -> Vec<String> {
        let mut cs = w.chars();
        if sentence_start && cs.next().is_some_and(char::is_uppercase) && cs.as_str() == lower(cs.as_str()) && !cs.as_str().is_empty() {
            // not the capital itself: Westu, Xanderis are names
            let first = lower(w).chars().next();
            if SLIP_KEYS.iter().any(|(k, _)| Some(*k) == first) {
                return vec![];
            }
            return self.slip_fixes(&lower(w), false).iter().map(|c| upper_first(c)).collect();
        }
        let lw = lower(w);
        let chars: Vec<char> = lw.chars().collect();
        let odd: Vec<usize> = (0..chars.len()).filter(|&i| !LT_ALPHABET.contains(chars[i])).collect();
        if w != lw || chars.len() < 4 || odd.len() != 1 || self.an.data.freq.get(&lw) > 0 {
            return vec![];
        }
        let i = odd[0];
        let keys = match SLIP_KEYS.iter().find(|(k, _)| *k == chars[i]) {
            Some((_, keys)) => *keys,
            None => return vec![],
        };
        let without = |c: &[char]| fold(&c[..i].iter().chain(&c[i + 1..]).collect::<String>());
        let rest = without(&chars);
        let touches = |j: usize| j < chars.len() && keys.contains(fold(&chars[j].to_string()).as_str());
        let extra = (i > 0 && touches(i - 1)) || touches(i + 1);
        self.an
            .suggest(w, 20)
            .into_iter()
            .filter(|c| {
                let cc: Vec<char> = c.chars().collect();
                let meant = if cc.len() == chars.len() {
                    keys.contains(fold(&cc[i].to_string()).as_str()) && without(&cc) == rest
                } else {
                    extra && cc.len() + 1 == chars.len() && fold(c) == rest
                };
                meant && self.an.data.freq.get(c) > 0
            })
            .take(5)
            .collect()
    }

    /// What a keyboard needs for the word being typed: is it valid, and the ranked
    /// corrections (word, cost, differs-only-in-diacritics). `context` is the text
    /// before the word (a few previous words); grammar rules can use it to fix a
    /// valid word ("prieš pora" -> "porą") or re-rank corrections. `formal`: a spoken form
    /// gets its standard form as a fix (valgyt -> valgyti, rule "formal").
    pub fn keyboard_word(&self, word: &str, context: &str, key_shift: bool, formal: bool) -> KeyboardWord {
        self.keyboard_word_in(word, context, "", key_shift, formal)
    }

    /// [`Checker::keyboard_word`] for a word inside a sentence: `after` is the rest of the sentence
    /// after it (the cursor was put back into the text), so the words after it decide too:
    /// "kad žiema žymiai rimtesne| negu" -> rimtesnė, "kad ziema| žymiai rimtesne" -> žiema (not the
    /// more frequent žiemą). `context` should then be the sentence before the word: the rules see a
    /// whole sentence, not one that ends at the word.
    pub fn keyboard_word_in(&self, word: &str, context: &str, after: &str, key_shift: bool, formal: bool) -> KeyboardWord {
        // no words before it in the sentence: the keyboard may have capitalised it
        let (status, formal_forms) = self.check_word_at(word, context.trim().is_empty());
        let lw = lower(word);
        let fw = fold(&lw);
        let entry = |w: String, cost: f64| {
            let fc = crate::suggest::cost(&fw, &fold(&lower(&w)));
            (w, cost, fc)
        };
        let mut suggestions: Vec<(String, f64, f64)> = Vec::new();
        if status == WordStatus::Unknown {
            suggestions = self.an.suggest_scored(word, 5).into_iter().map(|(w, c)| entry(w, c)).collect();
        }
        let mut context_rule = String::new();
        let mut context_fixes: Vec<(String, f64, f64)> = Vec::new();
        let partial = !after.chars().any(char::is_alphabetic);
        if !context.trim().is_empty() || !partial {
            let head = if context.trim().is_empty() { String::new() } else { format!("{} ", context.trim_end()) };
            let start = clen(&head);
            let text = format!("{head}{word}{after}");
            if let Some(f) = self.grammar.check_opts(&self.an, &text, partial).into_iter().find(|f| f.start == start) {
                if f.rule == "context" && status == WordStatus::Unknown {
                    // unknown word: context decides the order
                    let mut ordered: Vec<(String, f64, f64)> = Vec::new();
                    for s in &f.suggestions {
                        ordered.push(entry(s.clone(), self.an.score(&lw, &lower(s))));
                    }
                    for s in suggestions.drain(..) {
                        if !ordered.iter().any(|o| o.0 == s.0) {
                            ordered.push(s);
                        }
                    }
                    ordered.truncate(5);
                    suggestions = ordered;
                    context_rule = "context".into();
                } else if f.rule != "comma" && f.rule != "context" {
                    context_rule = f.rule.to_string();
                    context_fixes = f.suggestions.iter().map(|s| entry(s.clone(), 0.0)).collect();
                }
            }
        }
        if formal && status == WordStatus::Colloquial && !formal_forms.is_empty() {
            context_rule = "formal".into();
            context_fixes = formal_forms.into_iter().map(|w| entry(w, 0.0)).collect();
        }
        // A valid but rare form whose diacritic twin is common was almost certainly typed
        // without diacritics: sakini (rare verb form) -> sakinį. Keyboard only; frequencies
        // come from the small corpus, so the bar is "never seen" vs "seen".
        if status == WordStatus::Ok && context_fixes.is_empty() {
            if let Some(twin) = self.common_twin(word) {
                context_rule = "rare".into();
                context_fixes.push(entry(twin, 0.0));
            }
        }
        // A short valid word never seen in the corpus, one neighbouring key from a common
        // word, is that word mistyped: kak (imperative of the dialect verb kakti) -> kai.
        if status == WordStatus::Ok && context_fixes.is_empty() {
            if let Some(common) = self.common_neighbour(word) {
                context_rule = "rare".into();
                let c = self.an.score(&lw, &lower(&common));
                context_fixes.push(entry(common, c));
            }
        }
        // completely unrecognised and nothing close: maybe the hand was one key off
        let mut shifted = false;
        if key_shift && status == WordStatus::Unknown && suggestions.iter().all(|s| s.2 > 1.0) {
            let ks = self.an.key_shift(word, 3);
            if !ks.is_empty() {
                shifted = true;
                let mut v: Vec<(String, f64, f64)> =
                    ks.into_iter().map(|w| { let c = self.an.score(&lw, &lower(&w)); entry(w, c) }).collect();
                v.extend(suggestions.drain(..));
                v.truncate(5);
                suggestions = v;
            }
        }
        KeyboardWord { status, suggestions, context_rule, context_fixes, key_shift: shifted }
    }

    /// The most frequent word (seen at least COMMON times) that differs from a short (2-4 letters), never
    /// seen valid word in one letter typed with a neighbouring key: kak -> kai.
    fn common_neighbour(&self, word: &str) -> Option<String> {
        const COMMON: u32 = 50;
        let d = &self.an.data;
        let lw = lower(word);
        let chars: Vec<char> = lw.chars().collect();
        if chars.len() < 2 || chars.len() > 4 || !first_lower(word) || d.freq.get(&lw) > 0 {
            return None;
        }
        if self.an.analyze(word).iter().any(|a| d.lemma_freq.get(&lower(&a.lemma)) > 0) {
            return None;
        }
        let mut best: Option<(u32, String)> = None;
        for (i, &c) in chars.iter().enumerate() {
            for k in crate::suggest::key_and_neighbours(c).into_iter().skip(1) {
                let mut v = chars.clone();
                v[i] = k;
                let cand: String = v.into_iter().collect();
                let f = d.freq.get(&cand);
                if f >= COMMON && best.as_ref().map_or(true, |b| f > b.0) && !self.an.analyze_exact(&cand).is_empty() {
                    best = Some((f, cand));
                }
            }
        }
        best.map(|(_, c)| c)
    }

    /// Diacritic-only twin of a valid word when the word itself is never seen in the
    /// frequency corpus (neither the form nor its lemma) and the twin's lemma is.
    fn common_twin(&self, word: &str) -> Option<String> {
        const CASE_PARTS: &[&str] = &["nom", "gen", "dat", "acc", "ins", "loc", "voc"];
        let d = &self.an.data;
        let lemma_freq = |w: &str| {
            self.an.analyze(w).iter().map(|a| d.lemma_freq.get(&lower(&a.lemma))).max().unwrap_or(0)
        };
        let lw = lower(word);
        // a capitalised word is also its lowercase self: Kuriu is the name Kurys, but also kuriu (I create)
        if d.freq.get(&lw) > 0 || lemma_freq(word) > 0 || lemma_freq(&lw) > 0 {
            return None;
        }
        let lowercase = first_lower(word);
        self.an
            .folded_forms(&fold(&lw))
            .into_iter()
            .filter(|c| *c != lw && (!lowercase || first_lower(c)) && !self.an.analyze_exact(c).is_empty())
            // a twin that can only be a vocative (sakiny, "O sentence!") or a participle
            // (tęstuoju for testuoju) is rarely meant
            .filter(|c| {
                self.an.analyze_exact(c).iter().any(|a| {
                    let t = self.an.tag_str(a);
                    let participle = t.starts_with("V.") && t.split('.').any(|p| CASE_PARTS.contains(&p));
                    !t.ends_with(".voc") && !participle
                })
            })
            .map(|c| {
                let f = d.freq.get(&lower(&c));
                (lemma_freq(&c) + f, c)
            })
            .filter(|(score, _)| *score >= 3)
            .max_by(|a, b| a.0.cmp(&b.0).then_with(|| b.1.cmp(&a.1)))
            .map(|(_, c)| cap_like(word, &c))
    }

    /// The keyboard's next words (or completions of `prefix`, typed with or without diacritics)
    /// after `context`, the text before the cursor: the language model's words as they are
    /// written, a name with its capital (lietuvos -> Lietuvos). A word Varnelė doesn't know is
    /// kept only if the context has it (TSR, Freiburg: the user's own words, as written there) or
    /// the user has written it [`crate::user::UNKNOWN_MIN`] times, not from the corpus alone
    /// (foreign words, typos). `formal`: a spoken form (einam) is given
    /// as its standard form (einame), once, as swipe does.
    pub fn keyboard_predict(&self, context: &str, prefix: &str, n: usize, formal: bool) -> Vec<(String, f64)> {
        self.predict_in(&self.an.lm_context(context), context, prefix, n, formal)
    }

    /// The language model's candidates, re-ranked by what the words before require (see
    /// [`Grammar::next_word`]): a word that can't fit is demoted below the ones that can, and its
    /// forms that fit join in (eiti į šiaurės -> šiaurę).
    fn grammar_rerank(&self, ctx: &crate::lm::LmContext, context: &str, prefix: &str, n: usize) -> Vec<(String, f64)> {
        let Some(nw) = Grammar::next_word(&self.an, context) else {
            return self.an.predict_words(ctx, context, &lower(prefix), n * 3);
        };
        let fp = fold(&lower(prefix));
        let mut out: Vec<(String, f64)> = Vec::new();
        for (w, p) in self.an.predict_words(ctx, context, &lower(prefix), GRAMMAR_CANDIDATES) {
            let fit = Grammar::fits_next(&self.an, &nw, &w);
            if matches!(fit, None | Some(Fit::Yes)) {
                out.push((w, p));
                continue;
            }
            for f in Grammar::refit_next(&self.an, &nw, &w) {
                if fold(&f).starts_with(&fp) && clen(&f) > clen(prefix) && !out.iter().any(|o| o.0 == f) {
                    let pf = self.an.p_predict(ctx, &f);
                    out.push((f, pf));
                }
            }
            out.push((w, p * if fit == Some(Fit::Modifier) { MODIFIER } else { MISFIT }));
        }
        // a form can come twice: as a candidate and refitted from another
        out.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap().then_with(|| a.0.cmp(&b.0)));
        let mut seen = crate::fx::FxSet::default();
        out.retain(|(w, _)| seen.insert(w.clone()));
        out.truncate(n * 3);
        out
    }

    fn predict_in(&self, ctx: &crate::lm::LmContext, context: &str, prefix: &str, n: usize, formal: bool) -> Vec<(String, f64)> {
        let written: crate::fx::FxMap<String, &str> =
            context.split(|c: char| !c.is_alphabetic()).filter(|w| !w.is_empty()).map(|w| (lower(w), w)).collect();
        let fp = fold(&lower(prefix));
        let mut out: Vec<(String, f64)> = Vec::new();
        for (w, p) in self.grammar_rerank(ctx, context, prefix, n) {
            let known = |w: &str| self.an.check(w).status != Status::Unknown;
            let w = match self.an.check(&w) {
                // the completion must still begin with what was typed
                r if formal && r.status == Status::Colloquial => match r.formal.into_iter().find(|f| fold(f).starts_with(&fp)) {
                    Some(f) => f,
                    None => continue,
                },
                _ => w,
            };
            if out.iter().any(|(o, _)| *o == w) {
                continue;
            }
            // the counts drop numbers and full stops, so `1990 m.` left a lone `m` (top prediction
            // at a sentence start)
            let w = if clen(&w) == 1 && w != "į" && w != "o" {
                continue;
            } else if w != "kai" && self.an.data.abbrev.contains(&format!("{w}.")) {
                continue; // pr, kun: written with a full stop, the counts drop it
            } else if known(&w) {
                w
            } else if known(&capitalize(&w)) {
                capitalize(&w)
            } else if let Some(as_written) = written.get(&w) {
                as_written.to_string()
            } else if let Some(as_written) = self.user_word(&w) {
                as_written
            } else {
                continue;
            };
            out.push((w, p));
            if out.len() == n {
                break;
            }
        }
        out
    }

    /// A word Varnelė doesn't know that the user writes (lowercase in), as the user writes it.
    fn user_word(&self, w: &str) -> Option<String> {
        let user = self.an.user.read().unwrap();
        if !user.enabled {
            return None;
        }
        match user.word(w)? {
            (c, written) if c >= crate::user::UNKNOWN_MIN => Some(if written.is_empty() { w.to_string() } else { written.to_string() }),
            _ => None,
        }
    }

    /// The keyboard's ghost for the word being typed: its likeliest completion (kod -> kodėl), and
    /// the next word too when the model gives it [`GHOST_NEXT_P`] or more. None when nothing
    /// completes it or the word as typed is likelier than the completion (tau, not tautos).
    /// `formal` as for [`Self::keyboard_predict`].
    /// The keyboard's own diacritics, decided again once the words after them are typed (keyboard
    /// only). `committed` is the sentence as it stands, `typed` the same with each word the keyboard
    /// gave diacritics (autocorrect, not the user) as it was typed: `kad žiemą žymiai rimtesne` /
    /// `kad ziema žymiai rimtesne`. Each such word is checked as typed; a word whose twins the grammar
    /// narrows to ones that leave out its committed spelling takes the first of them (`žiema`: the
    /// predicate rimtesnė needs a nominative subject). A committed spelling the grammar still allows
    /// stays (`sąlyginė taika`: sąlygine would agree too). Returns (start, end, replacement), char
    /// offsets; the two texts must have the same length.
    pub fn keyboard_soft(&self, committed: &str, typed: &str) -> Vec<(usize, usize, String)> {
        let c: Vec<char> = committed.chars().collect();
        let t: Vec<char> = typed.chars().collect();
        if c.len() != t.len() || c == t {
            return Vec::new();
        }
        let mut out = Vec::new();
        for (a, b) in word_spans(&t) {
            if c[a..b] == t[a..b] {
                continue;
            }
            // one word as typed at a time: the others keep what they show (pačių įdomiausių nuotykių;
            // all of them as typed, paciu idomiausiu nuotykiu, is a sentence of unknown words)
            let word: String = t[a..b].iter().collect();
            let now: String = c[a..b].iter().collect();
            let text: String = c[..a].iter().chain(t[a..b].iter()).chain(c[b..].iter()).collect();
            let issues = self.grammar.check(&self.an, &text);
            let Some(f) = issues.iter().find(|f| f.start == a && f.end == b && f.rule != "comma") else { continue };
            let twins: Vec<&String> = f.suggestions.iter()
                .filter(|s| clen(s) == b - a && fold(&lower(s)) == fold(&lower(&word)))
                .collect();
            if twins.is_empty() || twins.iter().any(|s| **s == now) {
                continue;
            }
            out.push((a, b, twins[0].clone()));
        }
        out
    }

    pub fn keyboard_ghost(&self, context: &str, typed: &str, formal: bool) -> Option<String> {
        let (word, next) = self.ghost_parts(context, typed, formal)?;
        Some(match next {
            Some((n, pn)) if pn >= GHOST_NEXT_P => format!("{word} {n}"),
            _ => word,
        })
    }

    /// The ghost's completion and the likeliest next word after it with its probability, whatever
    /// that is (eval/predict_sim.py --ghost weighs thresholds with it).
    pub fn ghost_parts(&self, context: &str, typed: &str, formal: bool) -> Option<(String, Option<(String, f64)>)> {
        let mut ctx = self.an.lm_context(context);
        let (word, p) = self.predict_in(&ctx, context, typed, 1, formal).into_iter().next()?;
        // a dictionary lookup: check() would also guess derivations and compounds, 35 ms for `se`
        if !self.an.analyze(typed).is_empty() && self.an.p_predict(&ctx, &lower(typed)) >= p {
            return None;
        }
        ctx.prev2 = std::mem::replace(&mut ctx.prev, lower(&word)); // the paragraph's lemmas stay: one word more changes little
        let next = self.predict_in(&ctx, &format!("{context} {word}"), "", 1, formal).into_iter().next();
        Some((word, next))
    }

    /// All findings in a text, in order: misspellings, spoken forms, grammar.
    /// Offsets are in characters.
    pub fn check_text(&self, text: &str, formal: bool, grammar: bool) -> Vec<Finding> {
        let mut found: BTreeMap<usize, Finding> = BTreeMap::new();
        let mut seen: BTreeMap<(String, bool), (WordStatus, Vec<String>)> = BTreeMap::new();
        let chars: Vec<char> = text.chars().collect();
        for (word, pos) in tokens(text) {
            let word = if self.an.data.abbrev.contains(&lower(&word)) {
                word
            } else {
                word.trim_end_matches('.').to_string()
            };
            let start = sentence_start(&chars, pos);
            let (st, sugg) = seen.entry((word.clone(), start)).or_insert_with(|| self.check_word_at(&word, start)).clone();
            if st == WordStatus::Unknown || (st == WordStatus::Colloquial && formal) {
                let rule = if st == WordStatus::Unknown { "unknown" } else { "colloquial" };
                found.insert(pos, Finding {
                    start: pos,
                    end: pos + clen(&word),
                    word,
                    rule,
                    message: String::new(),
                    suggestions: sugg,
                });
            }
        }
        if grammar {
            for g in self.grammar.check(&self.an, text) {
                if g.rule == "context" {
                    if let Some(f) = found.get_mut(&g.start) {
                        let mut s = g.suggestions.clone();
                        s.extend(f.suggestions.iter().filter(|x| !g.suggestions.contains(x)).cloned());
                        s.truncate(5);
                        f.suggestions = s;
                        f.message = g.message;
                    }
                } else {
                    found.entry(g.start).or_insert(g);
                }
            }
        }
        found.into_values().collect()
    }
}
