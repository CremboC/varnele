//! The keyboard's language model: P(word | two previous words) from corpus word triples,
//! interpolated with P(word | previous word) from the pairs and that with the word's frequency
//! (absolute discounting). Words are lowercase, as typed with their
//! diacritics; "<s>" is the start of a sentence. Keyboard only, like key-shift: the checker
//! does not use it.

use crate::data::Data;
use crate::text::*;

pub const START: &str = "<s>";
/// discount on every pair count; the mass taken goes to the word's own frequency
const D: f64 = 0.75;
/// predictions before any letter is typed come from the followers of the previous word, then these
const TOP_WORDS: usize = 2000;

/// The previous word of a context as the model knows it: the last word, lowercased, or the
/// sentence start when there is none or a sentence just ended.
pub fn previous_word(context: &str) -> String {
    let t = context.trim_end();
    if t.is_empty() || t.ends_with(['.', '!', '?']) {
        return START.into();
    }
    let word: String = t
        .chars()
        .rev()
        .skip_while(|c| !c.is_alphabetic())
        .take_while(|c| c.is_alphabetic())
        .collect::<Vec<_>>()
        .into_iter()
        .rev()
        .collect();
    if word.is_empty() { START.into() } else { lower(&word) }
}

/// The two previous words of a context: the word before [`previous_word`] ("<s>" when that one
/// starts the sentence), "" when the previous word is itself the sentence start.
pub fn previous_words(context: &str) -> (String, String) {
    let prev = previous_word(context);
    if prev == START {
        return (String::new(), prev);
    }
    // commas don't part the words: the counts run across them (sakė, kad)
    let rest = context.trim_end_matches(|c: char| !c.is_alphabetic()).trim_end_matches(|c: char| c.is_alphabetic());
    (previous_word(rest), prev)
}

impl Data {
    /// How often the word occurs, smoothed: an unseen word counts as half an occurrence.
    pub fn p_word(&self, w: &str) -> f64 {
        (self.words.get(w) as f64).max(0.5) / (self.words_total.max(1) as f64)
    }

    /// P(w | prev), both lowercase.
    pub fn p_next(&self, prev: &str, w: &str) -> f64 {
        let Some(packed) = self.pairs.value(&format!("{prev} ")) else { return self.p_word(w) };
        let (total, distinct) = ((packed >> 32) as f64, (packed & 0xFFFF_FFFF) as f64);
        let c = self.pairs.get(&format!("{prev} {w}")) as f64;
        (c - D).max(0.0) / total + D * distinct / total * self.p_word(w)
    }

    /// P(w | prev2 prev): the triples' counts, backing off to [`Self::p_next`]; just that when
    /// `prev2` is "" or the triples don't have the two words.
    pub fn p_next3(&self, prev2: &str, prev: &str, w: &str) -> f64 {
        let lower_order = self.p_next(prev, w);
        if prev2.is_empty() {
            return lower_order;
        }
        let Some(packed) = self.triples.value(&format!("{prev2} {prev} ")) else { return lower_order };
        let (total, distinct) = ((packed >> 32) as f64, (packed & 0xFFFF_FFFF) as f64);
        let c = self.triples.get(&format!("{prev2} {prev} {w}")) as f64;
        (c - D).max(0.0) / total + D * distinct / total * lower_order
    }

    /// The words seen after "prev2 prev" (the listed triples) that start with `prefix`, compared
    /// without diacritics, most frequent first.
    pub fn followers3(&self, prev2: &str, prev: &str, prefix: &str, n: usize) -> Vec<String> {
        if prev2.is_empty() {
            return vec![];
        }
        self.followers(&self.triples, &format!("{prev2} {prev} "), prefix, n, |_| true).into_iter().map(|(w, _)| w).collect()
    }

    /// The `n` words after `head` ("PREV " in the pairs, "A B " in the triples, "" in the words)
    /// that start with `prefix` (compared without diacritics) and pass `keep`, most frequent
    /// first, ties in alphabetical order: from the ranked lists made at export when they have them
    /// (the words seen after a sentence start, `ir`, `buvo`…), else by listing the table.
    fn followers(&self, table: &crate::counts::Counts, head: &str, prefix: &str, n: usize, keep: impl Fn(&str) -> bool + Copy) -> Vec<(String, u64)> {
        let fp = fold(&lower(prefix));
        if let Some(list) = self.ranked.ranked(head, &fp) {
            // the list holds the most frequent ones: enough unless `keep` drops too many
            let out: Vec<(String, u64)> = list.into_iter().filter(|(w, _)| keep(w)).take(n).collect();
            if out.len() == n {
                return out;
            }
        }
        table.top_folded(head, prefix, n, keep)
    }

    /// The most frequent words, most frequent first.
    fn top_words(&self) -> &[String] {
        self.top_words.get_or_init(|| {
            let mut all = self.words.with_prefix("");
            all.sort_by(|a, b| b.1.cmp(&a.1).then_with(|| a.0.cmp(&b.0)));
            all.into_iter().take(TOP_WORDS).map(|(w, _)| w).collect()
        })
    }

    /// log10 of how much likelier the word is after `prev` than anywhere: > 0 when the pair
    /// is common (tuo metu), < 0 when `prev` is usually followed by other words (taip pat).
    pub fn association(&self, prev: &str, w: &str) -> f64 {
        (self.p_next(prev, w) / self.p_word(w)).log10()
    }

    /// The most likely next words after `prev` (lowercase) that start with `prefix` (compared
    /// without diacritics, so a prefix typed without them matches), with their probability.
    pub fn predict(&self, prev: &str, prefix: &str, n: usize) -> Vec<(String, f64)> {
        let longer = |w: &str| clen(w) > clen(prefix) || prefix.is_empty();
        // the words seen after `prev`, most frequent first
        let next = self.followers(&self.pairs, &format!("{prev} "), prefix, n, longer);
        let mut out: Vec<(String, f64)> = next.into_iter().take(n).map(|(w, _)| { let p = self.p_next(prev, &w); (w, p) }).collect();
        if out.len() == n {
            return out;
        }
        // then frequent words (the pairs list is pruned): by P(w | prev) too, which for an
        // unlisted pair is the backed-off word frequency
        let cands: Vec<String> = if prefix.is_empty() {
            self.top_words().to_vec() // all of them would be a scan of every word
        } else {
            // an unlisted pair backs off to the word's frequency, so the most frequent words are
            // the ones that can win: scoring all of them took 30+ ms on the phone after one letter
            // (listing every ka- word and sorting them took 1 ms on the Mac: ranked lists now)
            self.followers(&self.words, "", prefix, 4 * n, |_| true).into_iter().map(|(w, _)| w).collect()
        };
        let mut rest: Vec<(String, f64)> = cands
            .into_iter()
            .filter(|w| longer(w) && !out.iter().any(|o| &o.0 == w))
            .map(|w| { let p = self.p_next(prev, &w); (w, p) })
            .collect();
        rest.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap().then_with(|| a.0.cmp(&b.0)));
        out.extend(rest.into_iter().take(n - out.len()));
        out
    }
}

/// How many words before the current one the topic cache looks at (about a paragraph).
const CACHE_WORDS: usize = 150;
/// The topic cache's share of the probability when there is text before the word: the
/// prediction strip gains from more (top 3 after one letter 24.7 → 26.3% at 0.3), swipe ranking
/// loses (77.0 → 76.5% top-1).
pub const CACHE_PREDICT: f64 = 0.3;
pub const CACHE_SWIPE: f64 = 0.1;
/// Predictions take the cache's share in as the context grows: words / (words + this) of it.
/// A few words are no topic, and at the full share `Aš vakar buvau` predicted `aš`, `vakar`.
/// Top 3 before typing / after one letter, 0 → 300: Tatoeba (one sentence) 13.0 / 44.9 →
/// 18.5 / 46.9%, subtitles 11.8 / 31.3 → 12.4 / 32.9%, Wikipedia 16.0 / 31.2 → 16.1 / 30.4%.
const CACHE_RAMP: f64 = 300.0;
/// Candidates from the previous word's followers and the frequent words, before the paragraph
/// re-ranks them: 20 gives the same top 3 as 200 on all three test sets, 5× faster (0.5 ms).
const CANDIDATES: usize = 20;

/// What the model knows of the text before a word: the previous word, and the lemmas used
/// earlier (a topic cache: `Vilnius` in the paragraph makes `Vilniaus` likely).
pub struct LmContext {
    pub prev: String,
    /// the word before `prev` ("" if none, see [`previous_words`])
    pub prev2: String,
    lemmas: crate::fx::FxMap<String, u32>,
    words: u32,
}

impl crate::analyzer::Analyzer {
    pub fn lm_context(&self, context: &str) -> LmContext {
        let all: Vec<&str> = context.split(|c: char| !c.is_alphabetic()).filter(|w| !w.is_empty()).collect();
        let mut lemmas = crate::fx::FxMap::default();
        let recent = &all[all.len().saturating_sub(CACHE_WORDS)..];
        for w in recent {
            let mut ls: Vec<String> = self.analyze(w).into_iter().map(|a| lower(&a.lemma)).collect();
            ls.sort();
            ls.dedup();
            for l in ls {
                *lemmas.entry(l).or_insert(0) += 1;
            }
        }
        let (prev2, prev) = previous_words(context);
        LmContext { prev, prev2, lemmas, words: recent.len() as u32 }
    }

    /// log10 of how much likelier the word (lowercase) is here than anywhere: the previous
    /// word (tuo metu, taip pat) and the paragraph's lemmas.
    pub fn context_score(&self, ctx: &LmContext, w: &str, cache_share: f64) -> f64 {
        (self.p_context(ctx, w, cache_share) / self.data.p_word(w)).log10()
    }

    /// P(w | two previous words, paragraph), w lowercase; `cache_share` of it from the paragraph.
    pub fn p_context(&self, ctx: &LmContext, w: &str, cache_share: f64) -> f64 {
        let d = &self.data;
        let mut p = d.p_next3(&ctx.prev2, &ctx.prev, w);
        if ctx.words > 0 {
            // the lemma's share of the paragraph, times this form's share of the lemma
            let mut pc: f64 = 0.0;
            for a in self.analyze_exact(w) {
                let l = lower(&a.lemma);
                if let Some(&k) = ctx.lemmas.get(&l) {
                    let form = d.freq.get(w) as f64 + 0.5;
                    let lemma = d.lemma_freq.get(&l) as f64 + 1.0;
                    pc = pc.max(k as f64 / ctx.words as f64 * (form / lemma).min(1.0));
                }
            }
            p = (1.0 - cache_share) * p + cache_share * pc;
        }
        let user = self.user.read().unwrap();
        let share = user.share(&ctx.prev);
        if share > 0.0 {
            p = (1.0 - share) * p + share * user.p_next(&ctx.prev, w);
        }
        p
    }

    /// P(w | context) as predictions rank it (w lowercase): the paragraph's share grows with its length.
    pub fn p_predict(&self, ctx: &LmContext, w: &str) -> f64 {
        self.p_context(ctx, w, CACHE_PREDICT * ctx.words as f64 / (ctx.words as f64 + CACHE_RAMP))
    }

    /// The most likely next words that start with `prefix` (compared without diacritics, so a
    /// prefix typed without them matches): candidates are the words seen after the two previous
    /// ones and after the previous one, the paragraph's own words and the frequent ones, ranked
    /// by [`Self::p_context`].
    pub fn predict_words(&self, ctx: &LmContext, context: &str, prefix: &str, n: usize) -> Vec<(String, f64)> {
        let mut cands: crate::fx::FxSet<String> = Default::default();
        for (w, _) in self.data.predict(&ctx.prev, prefix, CANDIDATES) {
            cands.insert(w);
        }
        for w in self.user.read().unwrap().candidates(&ctx.prev, prefix, CANDIDATES) {
            cands.insert(w);
        }
        let fp = fold(&lower(prefix));
        for w in self.data.followers3(&ctx.prev2, &ctx.prev, &fp, CANDIDATES) {
            if clen(&w) > clen(prefix) {
                cands.insert(w);
            }
        }
        for w in context.split(|c: char| !c.is_alphabetic()).filter(|w| !w.is_empty()) {
            let lw = lower(w);
            if fold(&lw).starts_with(&fp) && clen(&lw) > clen(prefix) {
                cands.insert(lw);
            }
        }
        let mut out: Vec<(String, f64)> = cands.into_iter().map(|w| { let p = self.p_predict(ctx, &w); (w, p) }).collect();
        out.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap().then_with(|| a.0.cmp(&b.0)));
        out.truncate(n);
        out
    }
}
