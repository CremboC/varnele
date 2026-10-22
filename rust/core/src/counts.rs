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
        let mut s = self.map.search(FoldedPrefix { want: &want }).into_stream();
        collect(&mut s)
    }
}

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

/// Keys whose characters, folded, begin with `want`. Walks UTF-8 bytes: a state is the number
/// of characters matched so far and the bytes of the character being read.
struct FoldedPrefix<'a> {
    want: &'a [char],
}

#[derive(Clone, Copy)]
enum St {
    Reading { matched: usize, buf: [u8; 4], have: u8 },
    Done,
    Dead,
}

impl Automaton for FoldedPrefix<'_> {
    type State = St;

    fn start(&self) -> St {
        if self.want.is_empty() { St::Done } else { St::Reading { matched: 0, buf: [0; 4], have: 0 } }
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
