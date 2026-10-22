//! Loads the compiled data file written by `python3 -m varnele export`.

use std::collections::BTreeSet;
use std::sync::OnceLock;

use crate::analyzer::COLLOQUIAL;
use crate::counts::Counts;
use crate::fx::{FxMap, FxSet};
use crate::text::{fold, lower, FOLDED_ALPHABET};

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Kind {
    Noun,
    Adj,
    Pron,
    Num,
    Inf,
    Prs,
    Pst,
    Word,
}

impl Kind {
    fn from_u8(x: u8) -> Kind {
        match x {
            0 => Kind::Noun,
            1 => Kind::Adj,
            2 => Kind::Pron,
            3 => Kind::Num,
            4 => Kind::Inf,
            5 => Kind::Prs,
            6 => Kind::Pst,
            _ => Kind::Word,
        }
    }
    pub fn is_verb(self) -> bool {
        matches!(self, Kind::Inf | Kind::Prs | Kind::Pst)
    }
}

pub struct Entry {
    pub lemma: String,
    pub kind: Kind,
    pub flags: String,
}

/// A morphological tag such as "N.m.sg.acc" split into its dotted parts.
pub struct Tag {
    pub s: String,
    pub parts: Vec<String>,
}

pub struct Signature {
    /// (suffix, tag ids) in export order
    pub suffixes: Vec<(String, Vec<u16>)>,
    pub by_suffix: FxMap<String, usize>,
}

struct Folded {
    stems: FxMap<String, Vec<u32>>,         // folded stem -> stem indices
    sigs: Vec<FxMap<String, Vec<usize>>>,   // folded suffix -> suffix indices
    spoken: Vec<Vec<(String, Vec<String>)>>, // folded spoken suffix -> its real spellings (einam: me -> m)
}

/// The callbacks of [`Data::walk_forms`].
struct Walk<'a, S> {
    step: &'a dyn Fn(S, char) -> Option<S>,
    end: &'a dyn Fn(S) -> bool,
    entry_ok: &'a dyn Fn(u32) -> bool,
    last_ok: &'a dyn Fn(char) -> bool,
    prefixes: &'a FxSet<String>,
}

pub struct Data {
    pub tags: Vec<Tag>,
    pub tag_ids: FxMap<String, u16>,
    pub entries: Vec<Entry>,
    pub sigs: Vec<Signature>,
    pub stem_list: Vec<String>,
    pub stems: FxMap<String, Vec<(u16, u32)>>,
    pub blacklist: FxSet<String>,
    pub freq: Counts,
    pub lemma_freq: Counts,
    pub abbrev: FxSet<String>,
    pub deriv_stems: FxSet<String>,
    pub suffix_rests: FxMap<String, String>,
    pub head_rests: FxSet<String>,
    /// word counts for the language model (tokenised like the keyboard, unlike `freq`)
    pub words: Counts,
    pub words_total: u64,
    /// word pairs: "PREV WORD" -> count; "PREV " -> all pairs starting with PREV << 32 | how many
    /// different second words (before pruning). PREV "<s>" is the sentence start.
    pub pairs: Counts,
    /// word triples, the same for two previous words: "A B WORD" -> count, "A B " -> total << 32 |
    /// distinct; empty in a data file without them
    pub triples: Counts,
    /// the most frequent words after the pairs' and triples' heads that have many
    /// ([`Counts::ranked_lists`]); empty in a data file without them
    pub ranked: Counts,
    folded: OnceLock<Folded>,
    entry_stems: OnceLock<Vec<Vec<(u32, u16)>>>,
    stem_prefixes: OnceLock<FxSet<String>>,
    verb_stem_prefixes: OnceLock<FxSet<String>>,
    pub(crate) top_words: OnceLock<Vec<String>>,
}

struct Reader<'a> {
    b: &'a [u8],
    p: usize,
}

impl<'a> Reader<'a> {
    fn take(&mut self, n: usize) -> Result<&'a [u8], String> {
        let s = self.b.get(self.p..self.p + n).ok_or("truncated data file")?;
        self.p += n;
        Ok(s)
    }
    fn u8(&mut self) -> Result<u8, String> {
        Ok(self.take(1)?[0])
    }
    fn u16(&mut self) -> Result<u16, String> {
        Ok(u16::from_le_bytes(self.take(2)?.try_into().unwrap()))
    }
    fn u32(&mut self) -> Result<u32, String> {
        Ok(u32::from_le_bytes(self.take(4)?.try_into().unwrap()))
    }
    fn str(&mut self) -> Result<String, String> {
        let n = self.u16()? as usize;
        String::from_utf8(self.take(n)?.to_vec()).map_err(|e| e.to_string())
    }
    fn strs(&mut self) -> Result<Vec<String>, String> {
        let n = self.u32()?;
        (0..n).map(|_| self.str()).collect()
    }
    /// A table of counts: u32 byte length + FST bytes.
    fn counts(&mut self) -> Result<Counts, String> {
        let n = self.u32()? as usize;
        Counts::from_bytes(self.take(n)?.to_vec())
    }
}

impl Data {
    pub fn load(bytes: &[u8]) -> Result<Data, String> {
        let mut r = Reader { b: bytes, p: 0 };
        if r.take(4)? != b"VRNL" {
            return Err("not a varnele data file".into());
        }
        let version = r.u32()?;
        if version != 3 {
            return Err(format!("unsupported data version {version}"));
        }
        let tags: Vec<Tag> = r
            .strs()?
            .into_iter()
            .map(|s| Tag { parts: s.split('.').map(String::from).collect(), s })
            .collect();
        let tag_ids = tags.iter().enumerate().map(|(i, t)| (t.s.clone(), i as u16)).collect();

        let n = r.u32()?;
        let mut entries = Vec::with_capacity(n as usize);
        for _ in 0..n {
            let lemma = r.str()?;
            let kind = Kind::from_u8(r.u8()?);
            let flags = r.str()?;
            entries.push(Entry { lemma, kind, flags });
        }

        let n = r.u32()?;
        let mut sigs = Vec::with_capacity(n as usize);
        for _ in 0..n {
            let m = r.u16()?;
            let mut suffixes = Vec::with_capacity(m as usize);
            let mut by_suffix = FxMap::default();
            for k in 0..m as usize {
                let suf = r.str()?;
                let nt = r.u8()?;
                let ts = (0..nt).map(|_| r.u16()).collect::<Result<Vec<_>, _>>()?;
                by_suffix.insert(suf.clone(), k);
                suffixes.push((suf, ts));
            }
            sigs.push(Signature { suffixes, by_suffix });
        }

        let n = r.u32()?;
        let mut stem_list = Vec::with_capacity(n as usize);
        let mut stems = FxMap::default();
        stems.reserve(n as usize);
        for _ in 0..n {
            let st = r.str()?;
            let m = r.u16()?;
            let mut hits = Vec::with_capacity(m as usize);
            for _ in 0..m {
                let sid = r.u16()?;
                hits.push((sid, r.u32()?));
            }
            stem_list.push(st.clone());
            stems.insert(st, hits);
        }

        let blacklist = r.strs()?.into_iter().collect();
        let freq = r.counts()?;
        let lemma_freq = r.counts()?;
        let abbrev = r.strs()?.into_iter().collect();
        let deriv_stems = r.strs()?.into_iter().collect();
        let n = r.u32()?;
        let mut suffix_rests = FxMap::default();
        for _ in 0..n {
            let k = r.str()?;
            suffix_rests.insert(k, r.str()?);
        }
        let head_rests = r.strs()?.into_iter().collect();
        let words = r.counts()?;
        let pairs = r.counts()?;
        let triples = if r.p < r.b.len() { r.counts()? } else { Counts::empty() };
        let ranked = if r.p < r.b.len() { r.counts()? } else { Counts::empty() };

        Ok(Data {
            tags,
            tag_ids,
            entries,
            sigs,
            stem_list,
            stems,
            blacklist,
            freq,
            lemma_freq,
            abbrev,
            deriv_stems,
            suffix_rests,
            head_rests,
            words_total: words.total(),
            words,
            pairs,
            triples,
            ranked,
            folded: OnceLock::new(),
            entry_stems: OnceLock::new(),
            stem_prefixes: OnceLock::new(),
            verb_stem_prefixes: OnceLock::new(),
            top_words: OnceLock::new(),
        })
    }

    pub fn tag(&self, id: u16) -> &Tag {
        &self.tags[id as usize]
    }

    /// Exact lookup of an unprefixed form -> (entry, tag) pairs.
    pub fn lookup(&self, word: &str) -> Vec<(u32, u16)> {
        let mut out = Vec::new();
        if self.blacklist.contains(word) {
            return out;
        }
        let mut cuts: Vec<usize> = word.char_indices().map(|(i, _)| i).skip(1).collect();
        cuts.push(word.len());
        for &i in cuts.iter().rev() {
            if let Some(hits) = self.stems.get(&word[..i]) {
                let suf = &word[i..];
                for &(sid, eid) in hits {
                    let sig = &self.sigs[sid as usize];
                    if let Some(&k) = sig.by_suffix.get(suf) {
                        out.extend(sig.suffixes[k].1.iter().map(|&t| (eid, t)));
                    }
                }
            }
        }
        out
    }

    fn folded(&self) -> &Folded {
        self.folded.get_or_init(|| {
            let mut stems: FxMap<String, Vec<u32>> = FxMap::default();
            for (i, st) in self.stem_list.iter().enumerate() {
                stems.entry(fold(&lower(st))).or_default().push(i as u32);
            }
            let sigs = self
                .sigs
                .iter()
                .map(|sig| {
                    let mut m: FxMap<String, Vec<usize>> = FxMap::default();
                    for (k, (suf, _)) in sig.suffixes.iter().enumerate() {
                        m.entry(fold(suf)).or_default().push(k);
                    }
                    m
                })
                .collect();
            // a suffix with a spoken shortening for one of its tags: valgy|ti -> valgy|t
            let spoken = self
                .sigs
                .iter()
                .map(|sig| {
                    let mut m: Vec<(String, Vec<String>)> = Vec::new();
                    for (suf, tags) in &sig.suffixes {
                        for (short, full, test) in COLLOQUIAL {
                            let Some(head) = suf.strip_suffix(full) else { continue };
                            if !tags.iter().any(|&t| test.ok(&self.tags[t as usize].s)) {
                                continue;
                            }
                            let real = format!("{head}{short}");
                            let fs = fold(&real);
                            match m.iter_mut().find(|e| e.0 == fs) {
                                Some(e) if e.1.contains(&real) => {}
                                Some(e) => e.1.push(real),
                                None => m.push((fs, vec![real])),
                            }
                        }
                    }
                    m
                })
                .collect();
            Folded { stems, sigs, spoken }
        })
    }

    /// All real unprefixed forms whose folded spelling equals `fword`.
    pub fn lookup_folded(&self, fword: &str, out: &mut BTreeSet<String>) {
        let f = self.folded();
        let mut cuts: Vec<usize> = fword.char_indices().map(|(i, _)| i).skip(1).collect();
        cuts.push(fword.len());
        for &i in cuts.iter().rev() {
            if let Some(idxs) = f.stems.get(&fword[..i]) {
                let fsuf = &fword[i..];
                for &si in idxs {
                    let st = &self.stem_list[si as usize];
                    for &(sid, _) in &self.stems[st] {
                        if let Some(ks) = f.sigs[sid as usize].get(fsuf) {
                            for &k in ks {
                                out.insert(format!("{st}{}", self.sigs[sid as usize].suffixes[k].0));
                            }
                        }
                    }
                }
            }
        }
    }

    /// Every beginning of every folded stem: prunes the key-shift search.
    fn stem_prefixes(&self) -> &FxSet<String> {
        self.stem_prefixes.get_or_init(|| self.prefixes_of(|_| true))
    }

    /// The same for the stems of verbs only: a verbal prefix (pa-, nu-…) goes only on verbs.
    fn verb_stem_prefixes(&self) -> &FxSet<String> {
        self.verb_stem_prefixes.get_or_init(|| {
            self.prefixes_of(|si| self.stems[&self.stem_list[si as usize]].iter().any(|&(_, e)| self.entries[e as usize].kind.is_verb()))
        })
    }

    fn prefixes_of(&self, keep: impl Fn(u32) -> bool) -> FxSet<String> {
        let mut set = FxSet::default();
        for (st, idxs) in &self.folded().stems {
            if !idxs.iter().any(|&si| keep(si)) {
                continue;
            }
            for (i, _) in st.char_indices().skip(1) {
                set.insert(st[..i].to_string());
            }
            set.insert(st.clone());
        }
        set
    }

    /// Unprefixed forms where every letter is the typed letter or one of `options(typed letter)`
    /// (e.g. its neighbours on the keyboard): fofrkua -> didelis. `typed` is folded.
    pub fn neighbour_forms(&self, typed: &[char], options: &dyn Fn(char) -> Vec<char>, out: &mut BTreeSet<String>) {
        let f = self.folded();
        let prefixes = self.stem_prefixes();
        let opts: Vec<Vec<char>> = typed.iter().map(|&c| options(c)).collect();
        let mut cur = String::new();
        let mut budget = 200_000usize; // search steps: bounds the worst case on a phone
        self.neighbour_dfs(&opts, 0, &mut cur, f, prefixes, out, &mut budget);
    }

    #[allow(clippy::too_many_arguments)]
    fn neighbour_dfs(&self, opts: &[Vec<char>], pos: usize, cur: &mut String, f: &Folded,
                     prefixes: &FxSet<String>, out: &mut BTreeSet<String>, budget: &mut usize) {
        if *budget == 0 {
            return;
        }
        *budget -= 1;
        if let Some(idxs) = f.stems.get(cur.as_str()) {
            let rest = &opts[pos..];
            for &si in idxs {
                let st = &self.stem_list[si as usize];
                for &(sid, _) in &self.stems[st] {
                    for (fsuf, ks) in &f.sigs[sid as usize] {
                        if fsuf.chars().count() == rest.len() && fsuf.chars().zip(rest).all(|(c, o)| o.contains(&c)) {
                            for &k in ks {
                                out.insert(format!("{st}{}", self.sigs[sid as usize].suffixes[k].0));
                            }
                        }
                    }
                }
            }
        }
        if pos == opts.len() {
            return;
        }
        for &c in &opts[pos] {
            cur.push(c);
            if prefixes.contains(cur.as_str()) {
                self.neighbour_dfs(opts, pos + 1, cur, f, prefixes, out, budget);
            }
            cur.pop();
        }
    }

    /// Unprefixed forms whose folded spelling can be walked letter by letter: `step(state, letter)`
    /// is the state after one more letter (None: no word goes on this way), `end(state)` whether a
    /// word may stop there. Only entries `entry_ok` accepts, only words whose last folded letter
    /// `last_ok` accepts; `verbs_only`: walk only the stems of verbs (faster for a verbal prefix).
    /// A form with a spoken shortening (`einame` → `einam`, `valgyti` → `valgyt`) also yields the
    /// short form. Drives the gesture search; `budget` bounds the stem prefixes visited and suffixes tried.
    #[allow(clippy::too_many_arguments)]
    pub fn walk_forms<S: Copy>(&self, start: S, step: &dyn Fn(S, char) -> Option<S>, end: &dyn Fn(S) -> bool,
                               entry_ok: &dyn Fn(u32) -> bool, last_ok: &dyn Fn(char) -> bool, verbs_only: bool,
                               out: &mut Vec<String>, budget: &mut usize) {
        let mut cur = String::new();
        let prefixes = if verbs_only { self.verb_stem_prefixes() } else { self.stem_prefixes() };
        let w = Walk { step, end, entry_ok, last_ok, prefixes };
        self.walk_dfs(start, &mut cur, &w, out, budget);
    }

    fn walk_dfs<S: Copy>(&self, state: S, cur: &mut String, w: &Walk<S>, out: &mut Vec<String>, budget: &mut usize) {
        if *budget == 0 {
            return;
        }
        *budget -= 1;
        let f = self.folded();
        if let Some(idxs) = f.stems.get(cur.as_str()) {
            let stem_last = cur.chars().last();
            for &si in idxs {
                let st = &self.stem_list[si as usize];
                for &(sid, eid) in &self.stems[st] {
                    if !(w.entry_ok)(eid) {
                        continue;
                    }
                    let sig = &self.sigs[sid as usize];
                    for (fsuf, ks) in &f.sigs[sid as usize] {
                        if *budget == 0 {
                            return;
                        }
                        if fsuf.chars().last().or(stem_last).is_some_and(w.last_ok) {
                            *budget -= 1;
                            if Self::walk_suffix(state, fsuf, w) {
                                for &k in ks {
                                    out.push(format!("{st}{}", sig.suffixes[k].0));
                                }
                            }
                        }
                    }
                    for (fsuf, reals) in &f.spoken[sid as usize] {
                        if !fsuf.chars().last().or(stem_last).is_some_and(w.last_ok) {
                            continue;
                        }
                        if *budget == 0 {
                            return;
                        }
                        *budget -= 1;
                        if Self::walk_suffix(state, fsuf, w) {
                            for r in reals {
                                out.push(format!("{st}{r}"));
                            }
                        }
                    }
                }
            }
        }
        for c in FOLDED_ALPHABET {
            cur.push(c);
            if w.prefixes.contains(cur.as_str()) {
                if let Some(s) = (w.step)(state, c) {
                    self.walk_dfs(s, cur, w, out, budget);
                }
            }
            cur.pop();
        }
    }

    /// Whether the walk can go on from `state` through `fsuf` and stop there.
    fn walk_suffix<S: Copy>(state: S, fsuf: &str, w: &Walk<S>) -> bool {
        let mut s = Some(state);
        for c in fsuf.chars() {
            s = s.and_then(|s| (w.step)(s, c));
        }
        s.is_some_and(w.end)
    }

    /// Every (form, tag) of one entry, read back from the index.
    pub fn entry_forms(&self, eid: u32) -> Vec<(String, u16)> {
        let es = self.entry_stems.get_or_init(|| {
            let mut v: Vec<Vec<(u32, u16)>> = (0..self.entries.len()).map(|_| Vec::new()).collect();
            for (i, st) in self.stem_list.iter().enumerate() {
                for &(sid, e) in &self.stems[st] {
                    v[e as usize].push((i as u32, sid));
                }
            }
            v
        });
        let mut out = Vec::new();
        for &(si, sid) in &es[eid as usize] {
            let st = &self.stem_list[si as usize];
            for (suf, ts) in &self.sigs[sid as usize].suffixes {
                for &t in ts {
                    out.push((format!("{st}{suf}"), t));
                }
            }
        }
        out
    }
}
