//! Productive word formation: derived words, compounds and international prefixes.
//! The ending templates are compiled by the Python side (see derivation.py).

use crate::analyzer::Analyzer;
use crate::data::{Data, Kind};
use crate::text::{chead, clen, ctail, lower, underlying};

const PREFIXOIDS: &[&str] = &[
    "anti", "auto", "bio", "eko", "geo", "hidro", "kontr", "makro", "mikro", "mono", "multi", "neo",
    "poli", "post", "pseudo", "super", "tele", "termo", "ultra", "vice", "tarp", "archi", "hiper",
    "infra", "inter", "kvazi", "meta", "mini", "foto", "kino", "radio", "video", "aero", "agro",
    "astro", "avia", "elektro", "etno", "priešs", "pusiau", "psicho", "socio", "trans", "proto",
    "nano", "mega", "giga", "kilo", "euro", "audio", "kardio", "neuro", "fito", "zoo", "paleo",
];
const LINKS: [&str; 9] = ["", "a", "i", "o", "ia", "io", "u", "ė", "y"];
const MIN_STEM: usize = 4;
const MIN_COMPOUND_PART: usize = 4;

fn base(d: &Data, s: &str) -> bool {
    clen(s) >= MIN_STEM && (d.deriv_stems.contains(s) || d.deriv_stems.contains(&underlying(s)))
}

/// known stem + productive suffix: kamčiatk+inio, sien+utėmis
pub fn derived(d: &Data, word: &str) -> Option<String> {
    let lw = lower(word);
    let n = clen(&lw);
    for i in MIN_STEM..n.saturating_sub(1) {
        let (b, rest) = (chead(&lw, i), ctail(&lw, i));
        if base(d, b) {
            if let Some(label) = d.suffix_rests.get(rest) {
                return Some(format!("{b}+{label}"));
            }
        }
    }
    None
}

/// geo+informacinė, neo+kantininkų
pub fn prefixed(an: &Analyzer, word: &str) -> bool {
    let lw = lower(word);
    for p in PREFIXOIDS {
        if let Some(rest) = lw.strip_prefix(p) {
            if clen(rest) >= 4 {
                let rest = rest.strip_prefix('-').unwrap_or(rest);
                if !an.analyze_exact(rest).is_empty()
                    || derived(&an.data, rest).is_some()
                    || compound(&an.data, rest).is_some()
                {
                    return true;
                }
            }
        }
    }
    false
}

/// stem + linking vowel + stem: stog+a+stulpiai, ketur+stygiai
pub fn compound(d: &Data, word: &str) -> Option<String> {
    let lw = lower(word);
    let n = clen(&lw);
    for i in MIN_COMPOUND_PART..n.saturating_sub(4) {
        let b = chead(&lw, i);
        if !base(d, b) {
            continue;
        }
        let after = ctail(&lw, i);
        for link in LINKS {
            let Some(rest) = after.strip_prefix(link) else { continue };
            if clen(rest) < 5 {
                continue;
            }
            for (eid, _) in d.lookup(rest) {
                if matches!(d.entries[eid as usize].kind, Kind::Noun | Kind::Adj) {
                    return Some(format!("{b}+{link}+{rest}"));
                }
            }
            for j in MIN_COMPOUND_PART..clen(rest) {
                if base(d, chead(rest, j)) && d.head_rests.contains(ctail(rest, j)) {
                    return Some(format!("{b}+{link}+{rest}"));
                }
            }
            if let Some(x) = derived(d, rest) {
                return Some(format!("{b}+{link}+{x}"));
            }
        }
    }
    None
}
