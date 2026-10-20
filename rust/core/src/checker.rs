//! Checking words and whole texts: the public entry point.

use std::collections::BTreeMap;

use crate::analyzer::{Analyzer, Status};
use crate::data::Data;
use crate::grammar::{Grammar, Issue};
use crate::text::*;

pub type Finding = Issue;

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum WordStatus {
    Ok,
    Colloquial,
    Unknown,
    Skip,
}

pub struct Checker {
    pub an: Analyzer,
    grammar: Grammar,
}

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

impl Checker {
    pub fn new(data: Data) -> Checker {
        Checker { an: Analyzer::new(data), grammar: Grammar::default() }
    }

    pub fn from_bytes(bytes: &[u8]) -> Result<Checker, String> {
        Ok(Checker::new(Data::load(bytes)?))
    }

    /// Status and suggestions for one word.
    pub fn check_word(&self, word: &str) -> (WordStatus, Vec<String>) {
        let mut w = word;
        if let Some(stripped) = w.strip_suffix('.') {
            if self.an.data.abbrev.contains(&lower(w)) || clen(w) == 2 {
                return (WordStatus::Ok, vec![]);
            }
            w = stripped;
        }
        if is_foreign(w) || (is_upper(w) && clen(w) > 1) {
            return (WordStatus::Skip, vec![]);
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

    /// All findings in a text, in order: misspellings, spoken forms, grammar.
    /// Offsets are in characters.
    pub fn check_text(&self, text: &str, formal: bool, grammar: bool) -> Vec<Finding> {
        let mut found: BTreeMap<usize, Finding> = BTreeMap::new();
        let mut seen: BTreeMap<String, (WordStatus, Vec<String>)> = BTreeMap::new();
        for (word, pos) in tokens(text) {
            let word = if self.an.data.abbrev.contains(&lower(&word)) {
                word
            } else {
                word.trim_end_matches('.').to_string()
            };
            let (st, sugg) = seen.entry(word.clone()).or_insert_with(|| self.check_word(&word)).clone();
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
