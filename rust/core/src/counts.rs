//! String -> count tables stored as finite-state transducers (the `fst` crate). Sorted keys share
//! their beginnings and endings, so an inflected word list takes a few bytes per word, and a
//! table is read in place: no hash map of hundreds of thousands of strings on the heap.

use fst::{Automaton, IntoStreamer, Map, MapBuilder, Streamer};

use crate::text::{fold, fold_char, lower};

pub struct Counts {
    map: Map<Vec<u8>>,
}

impl Counts {
    pub fn from_bytes(bytes: Vec<u8>) -> Result<Counts, String> {
        Ok(Counts { map: Map::new(bytes).map_err(|e| e.to_string())? })
    }

    pub fn empty() -> Counts {
        Counts::from_bytes(build(Vec::new())).unwrap()
    }

    /// The count of a key, 0 if it is not there.
    pub fn get(&self, key: &str) -> u32 {
        self.value(key).unwrap_or(0) as u32
    }

    pub fn value(&self, key: &str) -> Option<u64> {
        self.map.get(key)
    }

    pub fn len(&self) -> usize {
        self.map.len()
    }

    pub fn is_empty(&self) -> bool {
        self.map.is_empty()
    }

    /// The sum of all values.
    pub fn total(&self) -> u64 {
        let mut s = self.map.stream();
        let mut t = 0;
        while let Some((_, v)) = s.next() {
            t += v;
        }
        t
    }

    /// Every key starting with `prefix`, with its value, in key order.
    pub fn with_prefix(&self, prefix: &str) -> Vec<(String, u64)> {
        let mut s = self.map.search(fst::automaton::Str::new(prefix).starts_with()).into_stream();
        collect(&mut s)
    }

    /// Every key whose folded spelling (no diacritics) starts with the folded `prefix`, so a
    /// prefix typed without diacritics finds the words with them.
    pub fn with_folded_prefix(&self, prefix: &str) -> Vec<(String, u64)> {
        let want: Vec<char> = fold(&lower(prefix)).chars().collect();
        let mut s = self.map.search(FoldedPrefix { skip: 0, want: &want }).into_stream();
        collect(&mut s)
    }

    /// The `n` keys that begin with `head` and whose rest after it, folded, begins with the folded
    /// `prefix`, the rest non-empty and passing `keep`: the highest values first, ties in key
    /// order, as the rests with their values. The same as sorting [`Self::with_folded_prefix`]'s
    /// list, without a string for every key listed (the fst stream itself still takes 0.08 µs a
    /// key: 3 ms for the 41,000 words after a sentence start, see [`Self::ranked_lists`]).
    pub fn top_folded(&self, head: &str, prefix: &str, n: usize, keep: impl Fn(&str) -> bool) -> Vec<(String, u64)> {
        let mut top: Vec<(String, u64)> = Vec::with_capacity(n + 1);
        if n == 0 {
            return top;
        }
        let want: Vec<char> = fold(&lower(prefix)).chars().collect();
        let aut = fst::automaton::Str::new(head).starts_with().intersection(FoldedPrefix { skip: head.len(), want: &want });
        let mut s = self.map.search(aut).into_stream();
        while let Some((k, v)) = s.next() {
            // keys come in order, so a key with the last one's value comes after it
            if top.len() == n && v <= top[n - 1].1 {
                continue;
            }
            let Some(rest) = k.strip_prefix(head.as_bytes()).and_then(|r| std::str::from_utf8(r).ok()) else { continue };
            if rest.is_empty() || !keep(rest) {
                continue;
            }
            let at = top.partition_point(|(w, c)| *c > v || (*c == v && w.as_str() < rest));
            top.insert(at, (rest.to_string(), v));
            top.truncate(n);
        }
        top
    }

    /// For a table of "HEAD WORD" keys (word pairs, triples; in a table of words the head is ""),
    /// the ranked lists that [`Self::ranked`] reads: for every head and every folded beginning of
    /// its words of up to [`RANKED_PREFIX`] letters ("" included) that at least [`RANKED_MIN`]
    /// words have, the `keep` (at most 100) words with the highest counts, as
    /// [`Self::top_folded`] ranks them, keyed "HEAD" + beginning + tab + two-digit rank + word.
    /// Built at export, so the runtime never lists the 41,000 words seen after a sentence start
    /// to take the first 20 (3 ms on the Mac, seconds on the emulator).
    pub fn ranked_lists(&self, keep: usize) -> Vec<(String, u64)> {
        let mut many: crate::fx::FxMap<(String, String), usize> = Default::default();
        let mut s = self.map.stream();
        while let Some((k, _)) = s.next() {
            let Ok(k) = std::str::from_utf8(k) else { continue };
            let (head, rest) = k.split_at(k.rfind(' ').map_or(0, |sp| sp + 1));
            if rest.is_empty() {
                continue;
            }
            let folded: Vec<char> = fold(rest).chars().collect();
            for len in 0..=folded.len().min(RANKED_PREFIX) {
                *many.entry((head.to_string(), folded[..len].iter().collect())).or_insert(0) += 1;
            }
        }
        let mut out = Vec::new();
        for ((head, p), count) in many {
            if count < RANKED_MIN {
                continue;
            }
            for (rank, (w, c)) in self.top_folded(&head, &p, keep.min(100), |_| true).into_iter().enumerate() {
                out.push((format!("{head}{p}\t{rank:02}{w}"), c));
            }
        }
        out
    }

    /// In a table of [`Self::ranked_lists`]: the words after `head` beginning with the folded
    /// `p`, most frequent first, if the list is there.
    pub fn ranked(&self, head: &str, p: &str) -> Option<Vec<(String, u64)>> {
        let key = format!("{head}{p}\t");
        let list: Vec<(String, u64)> = self.with_prefix(&key).into_iter().map(|(k, c)| (k[key.len() + 2..].to_string(), c)).collect();
        if list.is_empty() { None } else { Some(list) }
    }
}

/// Ranked lists ([`Counts::ranked_lists`]) are kept for beginnings of up to this many letters
pub const RANKED_PREFIX: usize = 3;
/// that at least this many words have (listing fewer takes under 0.05 ms on the Mac).
pub const RANKED_MIN: usize = 500;
/// Words kept in a ranked list of followers (pairs, triples): the 20 a prediction takes, after
/// dropping words no longer than what was typed;
pub const RANKED_FOLLOWERS: usize = 50;
/// and of frequent words, of which a prediction takes 80.
pub const RANKED_WORDS: usize = 100;

fn collect<S: for<'a> Streamer<'a, Item = (&'a [u8], u64)>>(s: &mut S) -> Vec<(String, u64)> {
    let mut out = Vec::new();
    while let Some((k, v)) = s.next() {
        out.push((String::from_utf8_lossy(k).into_owned(), v));
    }
    out
}

/// FST bytes for (key, value) pairs in any order (a repeated key keeps its last value).
pub fn build(mut pairs: Vec<(String, u64)>) -> Vec<u8> {
    pairs.sort_by(|a, b| a.0.as_bytes().cmp(b.0.as_bytes()));
    pairs.dedup_by(|later, earlier| {
        let same = later.0 == earlier.0;
        if same {
            earlier.1 = later.1;
        }
        same
    });
    let mut b = MapBuilder::memory();
    for (k, v) in pairs {
        b.insert(k, v).unwrap();
    }
    b.into_inner().unwrap()
}

/// Keys whose characters after the first `skip` bytes, folded, begin with `want`. Walks UTF-8
/// bytes: a state is the number of bytes skipped, or the number of characters matched so far and
/// the bytes of the character being read.
struct FoldedPrefix<'a> {
    skip: usize,
    want: &'a [char],
}

#[derive(Clone, Copy)]
enum St {
    Skip(usize),
    Reading { matched: usize, buf: [u8; 4], have: u8 },
    Done,
    Dead,
}

impl FoldedPrefix<'_> {
    fn reading(&self) -> St {
        if self.want.is_empty() { St::Done } else { St::Reading { matched: 0, buf: [0; 4], have: 0 } }
    }
}

impl Automaton for FoldedPrefix<'_> {
    type State = St;

    fn start(&self) -> St {
        if self.skip > 0 { St::Skip(0) } else { self.reading() }
    }

    fn is_match(&self, s: &St) -> bool {
        matches!(s, St::Done)
    }

    fn can_match(&self, s: &St) -> bool {
        !matches!(s, St::Dead)
    }

    fn will_always_match(&self, s: &St) -> bool {
        matches!(s, St::Done)
    }

    fn accept(&self, s: &St, byte: u8) -> St {
        if let St::Skip(k) = *s {
            return if k + 1 < self.skip { St::Skip(k + 1) } else { self.reading() };
        }
        let St::Reading { matched, mut buf, have } = *s else { return *s };
        buf[have as usize] = byte;
        let have = have + 1;
        let need = match buf[0] {
            b if b < 0x80 => 1,
            b if b >= 0xF0 => 4,
            b if b >= 0xE0 => 3,
            _ => 2,
        };
        if have < need {
            return St::Reading { matched, buf, have };
        }
        let Some(c) = std::str::from_utf8(&buf[..have as usize]).ok().and_then(|t| t.chars().next()) else {
            return St::Dead;
        };
        if fold_char(c) != self.want[matched] {
            return St::Dead;
        }
        if matched + 1 == self.want.len() { St::Done } else { St::Reading { matched: matched + 1, buf: [0; 4], have: 0 } }
    }
}
