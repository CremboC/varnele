//! Gesture (swipe) typing: which words a finger path over the keyboard spells.
//!
//! Candidates come from a walk over the folded stems (as the key-shift search does) in which
//! every letter's key must lie near the path, in order, the first near its start and the last
//! near its end. Each candidate is scored as in SHARK2's location channel: the mean distance
//! between the finger's path and the word's ideal path (straight lines through its key
//! centres), both resampled to the same number of points, plus the usual frequency bonus.
//! The result is the keys swiped (no diacritics, `y` kept: it is its own key); choosing the
//! diacritics is left to the keyboard's normal checks of a word typed without them.

use std::collections::HashMap;

use crate::analyzer::{Analyzer, NEGS, PREFIXES};
use crate::text::*;

/// Distances are in key widths.
const STEP: f32 = 0.2; // path resampling for the "passes near" test
const MIN_RATIO: f32 = 0.6; // ideal path so far >= this × finger path so far − 1 (0.75: 2× faster, −0.3 points)
const NEAR: f32 = 1.0; // a key the path passes within this is a letter it may spell
const ENDS: f32 = 1.2; // first and last letter: this near the path's start and end
const POINTS: usize = 32; // path and template resampled to this many points for scoring
const WARPED: f32 = 0.8; // share of the time-warped distance in the shape distance
const SHAPE_WEIGHT: f64 = 4.0; // cost per squared key width of shape distance
const UNSEEN_PREFIXED: f64 = 0.3; // a prefixed form only the prefix rules allow, never seen
const CONTEXT_WEIGHT: f64 = 0.3; // cost per log10 of how much likelier the language model finds the word here
const WARP: usize = 300; // best point-by-point shapes compared again with time warping
const KEEP: usize = 40; // best shapes whose frequency and analysis are looked up
const THREADS: usize = 4; // prefix chains searched at once

/// Key centres of the letter keys.
pub struct Layout {
    keys: Vec<(char, f32, f32)>,
}

impl Layout {
    /// HeliBoard's Lithuanian QWERTY on a phone: keys 1 wide and 1.4 high, the bottom row
    /// starting after a 1.5 wide shift key (diacritics are long-press popups of their base key).
    pub fn qwerty() -> Layout {
        let mut keys = Vec::new();
        for (r, (row, x0)) in [("qwertyuiop", 0.5), ("asdfghjkl", 1.0), ("zxcvbnm", 2.0)].iter().enumerate() {
            for (i, c) in row.chars().enumerate() {
                keys.push((c, x0 + i as f32, 0.7 + 1.4 * r as f32));
            }
        }
        Layout { keys }
    }

    /// Keys as (letter, centre x, centre y), coordinates divided by the key width.
    pub fn new(keys: Vec<(char, f32, f32)>) -> Layout {
        Layout { keys }
    }

    /// Centre of a letter's key.
    pub fn centre(&self, c: char) -> Option<(f32, f32)> {
        self.keys.iter().find(|k| k.0 == c).map(|k| (k.1, k.2))
    }

    fn id(&self, c: char) -> Option<usize> {
        self.keys.iter().position(|k| k.0 == c)
    }
}

/// The key a letter is typed with: its base letter, but y is a key of its own.
pub fn key_char(c: char) -> char {
    if c == 'y' { c } else { fold_char(c) }
}

/// The keys swiped for a word: lowercase, no diacritics, y kept.
pub fn key_word(w: &str) -> String {
    lower(w).chars().map(key_char).collect()
}

pub struct GestureCandidate {
    /// keys swiped (diacritic-free spelling), capitalised if the gesture was
    pub word: String,
    /// total cost, lower is better
    pub cost: f64,
    /// mean distance from the ideal path, in key widths
    pub shape: f64,
    /// the most likely real form spelt by these keys
    pub best: String,
}

/// Mean distance along the best monotone alignment of two point sequences (dynamic time warping).
fn dtw(a: &[(f32, f32)], b: &[(f32, f32)]) -> f32 {
    // rows of (summed distance, steps); a row only needs the one before it
    let m = b.len();
    let mut prev = vec![(f32::INFINITY, 0u32); m];
    let mut cur = vec![(f32::INFINITY, 0u32); m];
    for (i, &p) in a.iter().enumerate() {
        for j in 0..m {
            let c = dist(p, b[j]);
            let mut best = if i == 0 && j == 0 { (0.0, 0) } else { (f32::INFINITY, 0) };
            for cand in [if i > 0 { prev[j] } else { best }, if j > 0 { cur[j - 1] } else { best }, if i > 0 && j > 0 { prev[j - 1] } else { best }] {
                if cand.0 < best.0 {
                    best = cand;
                }
            }
            cur[j] = (best.0 + c, best.1 + 1);
        }
        std::mem::swap(&mut prev, &mut cur);
    }
    prev[m - 1].0 / prev[m - 1].1 as f32
}

fn dist(a: (f32, f32), b: (f32, f32)) -> f32 {
    ((a.0 - b.0).powi(2) + (a.1 - b.1).powi(2)).sqrt()
}

fn length(pts: &[(f32, f32)]) -> f32 {
    pts.windows(2).map(|w| dist(w[0], w[1])).sum()
}

/// `n` points evenly spaced along a polyline (n >= 2).
fn resample(pts: &[(f32, f32)], n: usize) -> Vec<(f32, f32)> {
    let total = length(pts);
    if pts.len() < 2 || total == 0.0 {
        return vec![pts[0]; n];
    }
    let step = total / (n - 1) as f32;
    let mut out = vec![pts[0]];
    let (mut seg, mut done) = (0usize, 0.0f32); // current segment, path length before it
    for k in 1..n - 1 {
        let want = step * k as f32;
        while seg + 2 < pts.len() && done + dist(pts[seg], pts[seg + 1]) < want {
            done += dist(pts[seg], pts[seg + 1]);
            seg += 1;
        }
        let (a, b) = (pts[seg], pts[seg + 1]);
        let t = ((want - done) / dist(a, b).max(1e-6)).clamp(0.0, 1.0);
        out.push((a.0 + t * (b.0 - a.0), a.1 + t * (b.1 - a.1)));
    }
    out.push(*pts.last().unwrap());
    out
}

/// Search state: the sample the last letter was matched at, its key, the template's length so far.
#[derive(Clone, Copy)]
struct St {
    j: usize,
    key: usize,
    tlen: f32,
}

const NONE: usize = usize::MAX;

impl Analyzer {
    /// Words the path (finger positions, in key widths, in order) may spell, best first.
    /// `cap`: the gesture was made with shift on; `context`: the text before the word.
    pub fn gesture(&self, path: &[(f32, f32)], layout: &Layout, cap: bool, context: &str, n: usize) -> Vec<GestureCandidate> {
        let ctx = self.lm_context(context);
        let out = self.gesture_within(path, layout, cap, &ctx, n, 1.0, 600_000);
        if out.is_empty() {
            // a key missed by more than usual (off the keyboard's edge): look wider, briefly
            return self.gesture_within(path, layout, cap, &ctx, n, 1.5, 120_000);
        }
        out
    }

    /// `widen`: key radii times this; `budget`: search steps (stem prefixes and suffixes tried)
    /// without a prefix, a quarter of it for each prefix chain.
    #[allow(clippy::too_many_arguments)]
    fn gesture_within(&self, path: &[(f32, f32)], layout: &Layout, cap: bool, ctx: &crate::lm::LmContext, n: usize, widen: f32,
                      budget: usize) -> Vec<GestureCandidate> {
        let (near_r, ends_r) = (NEAR * widen, ENDS * widen);
        let path_len = length(path);
        if path.len() < 2 || path_len < 0.5 {
            return vec![];
        }
        let pts = resample(path, ((path_len / STEP) as usize + 1).clamp(2, 400));
        let last = pts.len() - 1;
        let h = path_len / last as f32; // path length per sample
        // near[k][j]: the first sample from j on that passes near key k
        let near: Vec<Vec<usize>> = layout
            .keys
            .iter()
            .map(|&(_, x, y)| {
                let mut v = vec![NONE; pts.len() + 1];
                for j in (0..pts.len()).rev() {
                    v[j] = if dist(pts[j], (x, y)) < near_r { j } else { v[j + 1] };
                }
                v
            })
            .collect();
        let centre = |k: usize| (layout.keys[k].1, layout.keys[k].2);
        // the keys of each folded letter (i is also y), by letter - 'a'
        let ids: Vec<Vec<usize>> = ('a'..='z')
            .map(|c| {
                let ks = if c == 'i' { vec!['i', 'y'] } else { vec![c] };
                ks.into_iter().filter_map(|k| layout.id(k)).collect()
            })
            .collect();
        let keys_of = |c: char| -> &[usize] { if c.is_ascii_lowercase() { &ids[c as usize - 'a' as usize] } else { &[] } };
        let ends_near: Vec<bool> = ids.iter().map(|ks| ks.iter().any(|&k| dist(pts[last], centre(k)) < ends_r)).collect();
        let last_ok = |c: char| c.is_ascii_lowercase() && ends_near[c as usize - 'a' as usize];
        // the template can't be much longer than the path (corners are cut, not added)
        let max_len = path_len * 1.3 + 1.0;
        let step = |s: St, c: char| -> Option<St> {
            let mut best: Option<St> = None;
            for &k in keys_of(c) {
                let (j, tlen) = if s.key == NONE {
                    if dist(pts[0], centre(k)) >= ends_r {
                        continue;
                    }
                    (0, 0.0)
                } else if k == s.key {
                    (s.j, s.tlen) // a doubled letter is one key
                } else {
                    (near[k][s.j + 1], s.tlen + dist(centre(s.key), centre(k)))
                };
                // a letter skipped makes the ideal path too short for the finger's so far
                if j == NONE || tlen > max_len || tlen < j as f32 * h * MIN_RATIO - 1.0 {
                    continue;
                }
                if best.is_none_or(|b| j < b.j) {
                    best = Some(St { j, key: k, tlen });
                }
            }
            best
        };
        let end = |s: St| -> bool { s.key != NONE && s.tlen >= path_len * MIN_RATIO - 1.0 };

        // prefix chains as in the analyzer: (ne-|nebe-|be-|te-|tebe-)? (verbal prefix)? (si)?
        let mut chains: Vec<(String, &str, i32, &str)> = Vec::new(); // chain, negation, verbal prefix index, si
        for neg in NEGS {
            let mut verbal: Vec<(i32, String)> = vec![(-1, String::new())];
            for (i, p) in PREFIXES.iter().enumerate() {
                verbal.push((i as i32, p.to_string()));
                if *p == "ap" || *p == "at" {
                    verbal.push((i as i32, format!("{p}i")));
                }
            }
            for (vi, vp) in verbal {
                for si in ["", "si"] {
                    if !si.is_empty() && neg.is_empty() && vp.is_empty() {
                        continue;
                    }
                    chains.push((format!("{neg}{vp}{si}"), neg, vi, si));
                }
            }
        }
        let start = St { j: 0, key: NONE, tlen: 0.0 };
        let walk = |(chain, neg, vi, si): &(String, &str, i32, &str)| -> Vec<String> {
            let mut s = Some(start);
            for c in fold(chain).chars() {
                s = s.and_then(|s| step(s, c));
            }
            let Some(s) = s else { return Vec::new() };
            // only entries that can take the chain, by the analyzer's prefix rules (prefix flags);
            // the analysis of the whole word checks the rest (reflexive forms)
            let entry_ok = |eid: u32| {
                let e = &self.data.entries[eid as usize];
                chain.is_empty() || crate::analyzer::allowed(e.kind, &e.flags, "", neg, *vi, si)
            };
            let mut budget = if chain.is_empty() { budget } else { budget / 4 };
            let mut found = Vec::new();
            self.data.walk_forms(s, &step, &end, &entry_ok, &last_ok, *vi >= 0 || !si.is_empty(), &mut found, &mut budget);
            found
        };
        // the chains are independent searches, so a few threads share them; each chain has its
        // own budget, so the result does not depend on the threads' timing
        let next = std::sync::atomic::AtomicUsize::new(0);
        let threads = std::thread::available_parallelism().map_or(1, |n| n.get()).min(THREADS);
        let mut results: Vec<Vec<String>> = vec![Vec::new(); chains.len()];
        std::thread::scope(|sc| {
            let handles: Vec<_> = (0..threads)
                .map(|_| {
                    sc.spawn(|| {
                        let mut mine = Vec::new();
                        loop {
                            let i = next.fetch_add(1, std::sync::atomic::Ordering::Relaxed);
                            if i >= chains.len() {
                                break;
                            }
                            mine.push((i, walk(&chains[i])));
                        }
                        mine
                    })
                })
                .collect();
            for h in handles {
                for (i, found) in h.join().unwrap() {
                    results[i] = found;
                }
            }
        });
        let mut forms: Vec<String> = Vec::new();
        let mut prefixed: std::collections::HashSet<String> = Default::default();
        for ((chain, ..), found) in chains.iter().zip(results) {
            for f in found {
                if chain.is_empty() {
                    forms.push(f);
                } else if clen(&f) >= 2 {
                    prefixed.insert(format!("{chain}{f}"));
                    forms.push(format!("{chain}{f}"));
                }
            }
        }

        // score the shape of each distinct key sequence: first by the distance between
        // corresponding points, then the best of those also with time warping
        let fpath = resample(path, POINTS);
        struct Shape {
            dist: f32,
            template: Vec<(f32, f32)>,
            forms: Vec<String>,
        }
        let mut by_keys: HashMap<String, Shape> = HashMap::new();
        for f in forms {
            let kw = key_word(&f);
            if let Some(e) = by_keys.get_mut(&kw) {
                e.forms.push(f);
                continue;
            }
            let mut tpl: Vec<(f32, f32)> = Vec::new();
            let mut prev = ' ';
            let mut ok = true;
            for c in kw.chars() {
                if c == prev {
                    continue;
                }
                prev = c;
                match layout.id(c) {
                    Some(k) => tpl.push(centre(k)),
                    None => ok = false,
                }
            }
            if !ok || tpl.len() < 2 {
                continue;
            }
            let template = resample(&tpl, POINTS);
            let dist = fpath.iter().zip(&template).map(|(a, b)| dist(*a, *b)).sum::<f32>() / POINTS as f32;
            by_keys.insert(kw, Shape { dist, template, forms: vec![f] });
        }
        let mut pre: Vec<(String, Shape)> = by_keys.into_iter().collect();
        pre.sort_by(|a, b| a.1.dist.partial_cmp(&b.1.dist).unwrap().then_with(|| a.0.cmp(&b.0)));
        pre.truncate(WARP);
        let mut shapes: Vec<(f64, String, Vec<String>)> = pre
            .into_iter()
            .map(|(k, sh)| (((1.0 - WARPED) * sh.dist + WARPED * dtw(&fpath, &sh.template)) as f64, k, sh.forms))
            .collect();
        shapes.sort_by(|a, b| a.0.partial_cmp(&b.0).unwrap().then_with(|| a.1.cmp(&b.1)));

        // then, for the best KEEP shapes spelt by a real word (a prefix chain + form may not be),
        // the lexical cost of its best real form (frequency, the previous word and the paragraph,
        // a capitalised name for lowercase)
        let mut out: Vec<GestureCandidate> = Vec::new();
        for (d, kw, mut fs) in shapes {
            if out.len() == KEEP {
                break;
            }
            fs.sort();
            fs.dedup();
            let mut best: Option<(f64, String)> = None;
            for f in fs {
                if self.analyze_exact(&f).is_empty() {
                    continue;
                }
                let mut c = self.score(&kw, &lower(&f)) - CONTEXT_WEIGHT * self.context_score(ctx, &lower(&f), crate::lm::CACHE_SWIPE);
                if prefixed.contains(&f) && self.data.freq.get(&lower(&f)) == 0 {
                    c += UNSEEN_PREFIXED; // only the prefix rules say so: įįvykdyte
                }
                if first_upper(&f) && !cap {
                    c += 0.3;
                }
                if best.as_ref().is_none_or(|b| c < b.0) {
                    best = Some((c, f));
                }
            }
            let Some((lex, f)) = best else { continue };
            out.push(GestureCandidate {
                word: if cap { upper_first(&kw) } else { kw },
                cost: SHAPE_WEIGHT * d * d + lex,
                shape: d,
                best: if cap { upper_first(&f) } else { f },
            });
        }
        out.sort_by(|a, b| a.cost.partial_cmp(&b.cost).unwrap().then_with(|| a.word.cmp(&b.word)));
        out.truncate(n);
        out
    }
}
