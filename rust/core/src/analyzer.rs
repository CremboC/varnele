//! Morphological analysis: prefix grammar + index lookup + spoken-register layer.

use std::collections::BTreeSet;

use crate::data::{Data, Kind};
use crate::derivation;
use crate::text::*;

pub const NEGS: [&str; 6] = ["", "ne", "nebe", "be", "te", "tebe"];
pub const PREFIXES: [&str; 12] = ["ap", "at", "į", "iš", "nu", "pa", "par", "per", "pra", "pri", "su", "už"];
const PLAIN_PREFIX_FLAGS: &[u8; 12] = b"abcdefghijkl";
const REFL_PREFIX_FLAGS: &[u8; 12] = b"mnopqrstuvwx";

/// Spoken shortening rules: (colloquial ending, formal ending, tag test)
#[derive(Clone, Copy)]
pub enum TagTest {
    Inf,
    EndsWith(&'static str),
}

impl TagTest {
    pub fn ok(self, tag: &str) -> bool {
        match self {
            TagTest::Inf => tag == "V.inf",
            TagTest::EndsWith(s) => tag.ends_with(s),
        }
    }
}

pub const COLLOQUIAL: [(&str, &str, TagTest); 17] = [
    ("t", "ti", TagTest::Inf),                  // valgyt -> valgyti
    ("m", "me", TagTest::EndsWith(".1pl")),     // buvom -> buvome
    ("t", "te", TagTest::EndsWith(".2pl")),     // buvot -> buvote
    ("s", "si", TagTest::EndsWith(".refl")),    // jaučias -> jaučiasi
    ("oj", "oje", TagTest::EndsWith(".loc")),   // mokykloj -> mokykloje
    ("ėj", "ėje", TagTest::EndsWith(".loc")),
    ("uj", "uje", TagTest::EndsWith(".loc")),
    ("y", "yje", TagTest::EndsWith(".loc")),
    ("uos", "uose", TagTest::EndsWith(".loc")),
    ("am", "ame", TagTest::EndsWith(".loc")),
    ("om", "oms", TagTest::EndsWith(".pl.dat")),
    ("om", "omis", TagTest::EndsWith(".pl.ins")),
    ("ėm", "ėms", TagTest::EndsWith(".pl.dat")),
    ("ėm", "ėmis", TagTest::EndsWith(".pl.ins")),
    ("am", "ams", TagTest::EndsWith(".pl.dat")),
    ("im", "ims", TagTest::EndsWith(".pl.dat")),
    ("im", "imis", TagTest::EndsWith(".pl.ins")),
];

/// Spoken words that are no shortening of an ending: (word, its standard form)
pub const SPOKEN_WORDS: [(&str, &str); 1] = [
    ("eime", "eikime"), // let's go: imperative of eiti without -ki-
];

#[derive(Clone, Debug)]
pub struct Analysis {
    pub lemma: String,
    pub kind: Kind,
    pub tag: u16,
    pub prefix: String,
    pub entry: u32,
}

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Status {
    Ok,
    Derived,
    Compound,
    Colloquial,
    Unknown,
}

pub struct CheckResult {
    pub status: Status,
    pub analyses: Vec<Analysis>,
    pub formal: Vec<String>,
}

struct Split<'a> {
    neg: &'static str,
    vi: i32,
    vs: String,
    si: &'static str,
    core: &'a str,
}

/// Every possible prefix chain: (ne-|nebe-|be-|te-|tebe-)? (verbal prefix)? (si)? core
fn prefix_splits(word: &str) -> Vec<Split<'_>> {
    let mut out = Vec::new();
    for neg in NEGS {
        let Some(r1) = word.strip_prefix(neg) else { continue };
        let mut options: Vec<(i32, String)> = vec![(-1, String::new())];
        for (i, p) in PREFIXES.iter().enumerate() {
            options.push((i as i32, p.to_string()));
            if *p == "ap" || *p == "at" {
                options.push((i as i32, format!("{p}i")));
            }
        }
        for (vi, vs) in options {
            let Some(r2) = r1.strip_prefix(vs.as_str()) else { continue };
            for si in ["", "si"] {
                let Some(core) = r2.strip_prefix(si) else { continue };
                if !si.is_empty() && neg.is_empty() && vs.is_empty() {
                    continue;
                }
                if clen(core) < 2 && !(neg.is_empty() && vs.is_empty() && si.is_empty()) {
                    continue;
                }
                let nxt = if si.is_empty() { core.chars().next() } else { Some('s') };
                let Some(nxt) = nxt else { continue };
                let pb = nxt == 'p' || nxt == 'b';
                let td = nxt == 't' || nxt == 'd';
                if vs == "api" && (!si.is_empty() || !pb) {
                    continue;
                }
                if vs == "ati" && (!si.is_empty() || !td) {
                    continue;
                }
                if (vs == "ap" && pb) || (vs == "at" && td) {
                    continue;
                }
                out.push(Split { neg, vi, vs: vs.clone(), si, core });
            }
        }
    }
    out
}

pub(crate) fn allowed(kind: Kind, flags: &str, tag: &str, neg: &str, vi: i32, si: &str) -> bool {
    let refl = tag.ends_with(".refl");
    if !kind.is_verb() {
        if vi >= 0 || !si.is_empty() {
            return false;
        }
        return neg.is_empty() || (neg == "ne" && flags.contains('N'));
    }
    if refl && (!neg.is_empty() || vi >= 0 || !si.is_empty()) {
        return false;
    }
    if vi >= 0 {
        if !matches!(neg, "" | "ne" | "nebe") {
            return false;
        }
        if !flags.chars().any(|c| c.is_lowercase()) {
            // ispell-lt lists some principal parts without prefix data: allow any prefix
            return si.is_empty() || flags.chars().any(|c| "ROS".contains(c));
        }
        let table = if si.is_empty() { PLAIN_PREFIX_FLAGS } else { REFL_PREFIX_FLAGS };
        return flags.as_bytes().contains(&table[vi as usize]);
    }
    if !si.is_empty() {
        return matches!(neg, "ne" | "nebe" | "be" | "tebe") && flags.contains('S');
    }
    if neg == "ne" || neg == "nebe" {
        return flags.contains('N') || flags.contains('S');
    }
    if !neg.is_empty() {
        return flags.contains('X');
    }
    true
}

pub struct Analyzer {
    pub data: Data,
    /// the user's own words, learned on the phone (keyboard only)
    pub user: std::sync::RwLock<crate::user::UserLm>,
}

impl Analyzer {
    pub fn new(data: Data) -> Analyzer {
        Analyzer { data, user: Default::default() }
    }

    pub fn tag_str(&self, a: &Analysis) -> &str {
        &self.data.tag(a.tag).s
    }

    pub fn analyze_exact(&self, word: &str) -> Vec<Analysis> {
        let mut out = Vec::new();
        for sp in prefix_splits(word) {
            for (eid, tag) in self.data.lookup(sp.core) {
                let e = &self.data.entries[eid as usize];
                if allowed(e.kind, &e.flags, &self.data.tag(tag).s, sp.neg, sp.vi, sp.si) {
                    out.push(Analysis {
                        lemma: e.lemma.clone(),
                        kind: e.kind,
                        tag,
                        prefix: format!("{}{}{}", sp.neg, sp.vs, sp.si),
                        entry: eid,
                    });
                }
            }
        }
        out
    }

    /// All analyses of a word, trying sensible case variants.
    pub fn analyze(&self, word: &str) -> Vec<Analysis> {
        let mut variants = vec![word.to_string()];
        if first_upper(word) {
            if is_upper(word) && clen(word) > 1 {
                variants.push(capitalize(word));
                variants.push(lower(word));
            } else {
                variants.push(lower_first(word));
            }
        }
        for v in variants {
            let res = self.analyze_exact(&v);
            if !res.is_empty() {
                return res;
            }
        }
        Vec::new()
    }

    /// Real words (with any prefix chain) whose diacritic-free spelling is `fw`.
    pub fn folded_forms(&self, fw: &str) -> BTreeSet<String> {
        let mut out = BTreeSet::new();
        let mut vp_folded: Vec<(String, String)> = vec![(String::new(), String::new())];
        for p in PREFIXES {
            vp_folded.push((fold(p), p.to_string()));
            if p == "ap" || p == "at" {
                vp_folded.push((format!("{p}i"), format!("{p}i")));
            }
        }
        for neg in NEGS {
            let Some(r1) = fw.strip_prefix(neg) else { continue };
            for (fvp, vp) in &vp_folded {
                let Some(r2) = r1.strip_prefix(fvp.as_str()) else { continue };
                for si in ["", "si"] {
                    let Some(core) = r2.strip_prefix(si) else { continue };
                    if !si.is_empty() && neg.is_empty() && vp.is_empty() {
                        continue;
                    }
                    if clen(core) < 2 && !(neg.is_empty() && vp.is_empty() && si.is_empty()) {
                        continue;
                    }
                    let mut reals = BTreeSet::new();
                    self.data.lookup_folded(core, &mut reals);
                    for real in reals {
                        out.insert(format!("{neg}{vp}{si}{real}"));
                    }
                }
            }
        }
        out
    }

    /// A known word within one slip of this one blocks productive analyses.
    pub fn blocked(&self, word: &str) -> bool {
        let lw = lower(word);
        let fw = fold(&lw);
        let mut probes = vec![fw.clone()];
        probes.extend(edits1(&fw, &FOLDED_ALPHABET));
        for probe in probes {
            for cand in self.folded_forms(&probe) {
                if lower(&cand) != lw && !self.analyze_exact(&cand).is_empty() {
                    return true;
                }
            }
        }
        false
    }

    /// Formal forms this word could be a spoken shortening of.
    pub fn colloquial(&self, word: &str) -> Vec<String> {
        let mut found: Vec<String> = Vec::new();
        let lw = lower(word);
        if let Some((_, full)) = SPOKEN_WORDS.iter().find(|(w, _)| *w == lw) {
            found.push(if first_lower(word) { full.to_string() } else { capitalize(full) });
        }
        for (short, full, test) in COLLOQUIAL {
            if word.ends_with(short) && clen(word) > clen(short) + 1 {
                let cand = format!("{}{}", &word[..word.len() - short.len()], full);
                if cand == word {
                    continue;
                }
                if self.analyze(&cand).iter().any(|a| test.ok(self.tag_str(a))) && !found.contains(&cand) {
                    found.push(cand);
                }
            }
        }
        found
    }

    pub fn check(&self, word: &str) -> CheckResult {
        let an = self.analyze(word);
        if !an.is_empty() {
            return CheckResult { status: Status::Ok, analyses: an, formal: vec![] };
        }
        let formal = self.colloquial(word);
        if !formal.is_empty() {
            return CheckResult { status: Status::Colloquial, analyses: vec![], formal };
        }
        // Productive analyses are guesses: a known word one slip away wins.
        let tries: [(Status, &dyn Fn(&str) -> bool); 3] = [
            (Status::Derived, &|w| derivation::derived(&self.data, w).is_some()),
            (Status::Compound, &|w| derivation::compound(&self.data, w).is_some()),
            (Status::Derived, &|w| derivation::prefixed(self, w)),
        ];
        for (status, f) in tries {
            if f(word) {
                if self.blocked(word) {
                    break;
                }
                return CheckResult { status, analyses: vec![], formal: vec![] };
            }
        }
        CheckResult { status: Status::Unknown, analyses: vec![], formal: vec![] }
    }
}
