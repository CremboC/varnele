//! Correction suggestions: diacritic-blind lookup plus one typo, ranked by a
//! weighted edit distance and word/lemma frequency.

use std::collections::{BTreeSet, HashMap};

use crate::analyzer::{Analyzer, COLLOQUIAL};
use crate::text::*;

const KEYBOARD: [&str; 3] = ["qwertyuiop", "asdfghjkl", "zxcvbnm"];

fn key_pos(c: char) -> Option<(i32, i32)> {
    let c = fold_char(c);
    KEYBOARD
        .iter()
        .enumerate()
        .find_map(|(r, row)| row.chars().position(|k| k == c).map(|i| (r as i32, i as i32)))
}

/// The typed letter and its neighbouring keys, within the (folded) Lithuanian alphabet.
pub fn key_and_neighbours(c: char) -> Vec<char> {
    let mut v = vec![c];
    for &k in FOLDED_ALPHABET.iter() {
        if k != c && near(c, k) {
            v.push(k);
        }
    }
    v
}

/// Adjacent keys on a QWERTY-based Lithuanian layout (diacritics share their base key).
fn near(a: char, b: char) -> bool {
    match (key_pos(a), key_pos(b)) {
        (Some(pa), Some(pb)) => (pa.0 - pb.0).abs() <= 1 && (pa.1 - pb.1).abs() <= 1,
        _ => false,
    }
}

/// Damerau-Levenshtein with cheap same-class substitutions.
/// Cost of a same-length fix that only changes diacritics (and i/y). If nothing was typed
/// with diacritics, how many are missing says nothing: one counts like many, and frequency
/// decides (turetu -> turėtų, not the rare turėtu).
fn diacritic_cost(word: &str, cand: &str) -> f64 {
    if word.chars().any(|c| "ąčęėįšųūž".contains(c)) {
        return cost(word, cand);
    }
    let iy = |a: char, b: char| (a == 'i' && b == 'y') || (a == 'y' && b == 'i');
    let pairs = || word.chars().zip(cand.chars());
    let diacritics = pairs().filter(|&(a, b)| a != b && !iy(a, b)).count();
    let swaps = pairs().filter(|&(a, b)| iy(a, b)).count();
    (if diacritics > 0 { 0.3 } else { 0.0 }) + 0.6 * swaps as f64
}

pub fn cost(a: &str, b: &str) -> f64 {
    let a: Vec<char> = a.chars().collect();
    let b: Vec<char> = b.chars().collect();
    let (n, m) = (a.len(), b.len());
    let mut d = vec![vec![0.0f64; m + 1]; n + 1];
    for (i, row) in d.iter_mut().enumerate() {
        row[0] = i as f64;
    }
    for j in 0..=m {
        d[0][j] = j as f64;
    }
    for i in 1..=n {
        for j in 1..=m {
            let (ca, cb) = (a[i - 1], b[j - 1]);
            let iy = |c: char| matches!(c, 'i' | 'I' | 'y' | 'Y');
            let sub = if ca == cb {
                0.0
            } else if iy(ca) && iy(cb) && ca.to_ascii_lowercase() != cb.to_ascii_lowercase() {
                0.6 // y is its own key: sita means šita, not syta
            } else if fold_char(ca) == fold_char(cb) {
                0.3
            } else if near(ca, cb) {
                0.8
            } else {
                1.0
            };
            let mut v = (d[i - 1][j] + 1.0).min(d[i][j - 1] + 1.0).min(d[i - 1][j - 1] + sub);
            if i > 1 && j > 1 && ca == b[j - 2] && a[i - 2] == cb {
                v = v.min(d[i - 2][j - 2] + 1.0);
            }
            d[i][j] = v;
        }
    }
    d[n][m]
}

impl Analyzer {
    /// Words typed with the hand shifted: every letter may be a neighbouring key
    /// (fofrkua -> didelis). Fewest shifted keys first, then frequency.
    pub fn key_shift(&self, word: &str, n: usize) -> Vec<String> {
        let lw = lower(word);
        let typed: Vec<char> = fold(&lw).chars().collect();
        if typed.len() < 3 || typed.len() > 16 {
            return vec![];
        }
        let mut found = BTreeSet::new();
        self.data.neighbour_forms(&typed, &key_and_neighbours, &mut found);
        // common words first (a whole-word slip is only worth fixing into a likely word),
        // then fewer shifted keys
        let mut ranked: Vec<(i64, usize, String)> = found
            .into_iter()
            .filter_map(|c| {
                let an = self.analyze_exact(&c);
                if !first_lower(&c) || an.is_empty() {
                    return None;
                }
                let lf = an.iter().map(|a| *self.data.lemma_freq.get(&lower(&a.lemma)).unwrap_or(&0)).max().unwrap_or(0);
                let f = *self.data.freq.get(&c).unwrap_or(&0);
                let shifted = fold(&c).chars().zip(&typed).filter(|(a, b)| a != *b).count();
                Some((-((lf + f) as i64), shifted, c))
            })
            .collect();
        ranked.sort();
        let cap = first_upper(word);
        ranked.into_iter().take(n).map(|(_, _, c)| if cap { upper_first(&c) } else { c }).collect()
    }

    /// Lower is better. Diacritic-only fixes always beat real edits; among
    /// equally plausible candidates, frequent words win.
    pub fn score(&self, word: &str, cand: &str) -> f64 {
        let cl = lower(cand);
        let lf = self
            .analyze_exact(cand)
            .iter()
            .map(|a| *self.data.lemma_freq.get(&lower(&a.lemma)).unwrap_or(&0))
            .max()
            .unwrap_or(0);
        let f = *self.data.freq.get(&cl).unwrap_or(&0);
        let bonus = 0.12 * (1.0 + f as f64).log10() + 0.1 * (1.0 + lf as f64).log10();
        if fold(&cl) == fold(word) {
            0.1 + 0.5 * diacritic_cost(word, &cl) - bonus
        } else {
            cost(word, &cl) - bonus
        }
    }

    pub fn suggest(&self, word: &str, n: usize) -> Vec<String> {
        self.suggest_scored(word, n).into_iter().map(|(c, _)| c).collect()
    }

    /// Suggestions with their ranking cost (lower is better).
    pub fn suggest_scored(&self, word: &str, n: usize) -> Vec<(String, f64)> {
        let lw = lower(word);
        let fw = fold(&lw);
        let mut cands: BTreeSet<String> = self.folded_forms(&fw);
        if clen(&fw) <= 25 {
            for e in edits1(&fw, &FOLDED_ALPHABET) {
                cands.extend(self.folded_forms(&e));
            }
        }
        // spoken shortening + missing diacritics at once: rasyt -> rašyti
        let mut spoken: HashMap<String, String> = HashMap::new();
        for (short, full, _) in COLLOQUIAL {
            let fs = fold(short);
            if fw.ends_with(&fs) && clen(&fw) > clen(short) + 1 {
                let base = format!("{}{}", &fw[..fw.len() - fs.len()], fold(full));
                for c in self.folded_forms(&base) {
                    let n_short = clen(short);
                    let typed = format!("{}{}", chead(&lw, clen(&lw) - n_short), full);
                    spoken.insert(c.clone(), typed);
                    cands.insert(c);
                }
            }
        }
        let lw_len = clen(&lw);
        let good: Vec<String> = cands
            .into_iter()
            .filter(|c| *c != lw && (clen(c) > 1 || lw_len <= 2) && !self.analyze_exact(c).is_empty())
            .collect();
        let word_lower_first = first_lower(word);
        let mut scored: Vec<(f64, String)> = good
            .into_iter()
            .map(|c| {
                let mut sc = self.score(&lw, &c);
                if let Some(base) = spoken.get(&c) {
                    sc = sc.min(self.score(base, &c) + 0.05);
                }
                // a lowercase word is rarely a misspelt name: dvara -> dvarą, not Dvarą
                if first_upper(&c) && word_lower_first {
                    sc += 0.15;
                }
                (sc, c)
            })
            .collect();
        scored.sort_by(|a, b| a.0.partial_cmp(&b.0).unwrap().then_with(|| a.1.cmp(&b.1)));
        let cap = first_upper(word);
        scored
            .into_iter()
            .take(n)
            .map(|(sc, c)| (if cap { upper_first(&c) } else { c }, sc))
            .collect()
    }
}
