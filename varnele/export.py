"""Compile everything the runtime needs into one binary file (for the Rust port).

The paradigms, sound rules and ispell-lt parsing run here, once. The phone only
loads the result: stems, ending signatures, frequencies and derivation tables.

Format (little-endian). str = u16 byte length + UTF-8 bytes. Sections in order:
  magic "VRNL", u32 version
  tags          u32 n, str*n
  entries       u32 n, (str lemma, u8 kind, str flags)*n
  signatures    u32 n, (u16 m, (str suffix, u8 k, u16 tag*k)*m)*n
  stems         u32 n, (str stem, u16 m, (u16 sig, u32 entry)*m)*n     in index order
  blacklist     u32 n, str*n
  freq          table     word -> count
  lemma_freq    table     lemma -> count
  abbreviations u32 n, str*n
  deriv_stems   u32 n, str*n
  suffix_rests  u32 n, (str rest, str label)*n
  head_rests    u32 n, str*n
  words         table     word -> count, for the language model
  pairs         table     "PREV WORD" -> count; "PREV " -> total << 32 | distinct followers
                (both from data/bigrams.tsv, eval/build_ngrams.py; "<s>" = sentence start)
  triples       table     "A B WORD" -> count; "A B " -> total << 32 | distinct (data/trigrams.tsv;
                optional: the runtime reads it only when bytes are left)
  ranked        table     "HEAD" + folded beginning + tab + rank + word -> count: the 50 most
                frequent words after a pairs or triples head ("PREV ", "A B "; the 100 most
                frequent words: head "") that start with the beginning ("", or 1-3 letters
                without diacritics), where 500+ words do (Rust `fst-ranked`; optional like triples)
  valency       table     "VERB	CLASS	after|before	CASE" -> count (data/valency.tsv,
                eval/build_valency.py; optional like triples)
table = u32 byte length + a finite-state transducer (Rust `fst` crate), built by the Rust
binary's `fst` subcommand: build it first (cargo build --release --manifest-path rust/Cargo.toml).
"""

import struct
import subprocess

from .derivation import Derivation
from .index import Index
from .lexicon import ROOT
from .suggest import _load_freq

VERSION = 3
RUST = ROOT / "rust" / "target" / "release" / "varnele"
KINDS = ["noun", "adj", "pron", "num", "inf", "prs", "pst", "word"]
OUT = ROOT / "data" / "varnele.bin"


class Writer:
    def __init__(self):
        self.buf = bytearray(b"VRNL") + struct.pack("<I", VERSION)

    def u8(self, x):
        self.buf += struct.pack("<B", x)

    def u16(self, x):
        self.buf += struct.pack("<H", x)

    def u32(self, x):
        self.buf += struct.pack("<I", x)

    def table(self, items):
        """(key, count) pairs as an FST, built by the Rust binary."""
        if not RUST.exists():
            raise SystemExit(f"{RUST} not found: cargo build --release --manifest-path rust/Cargo.toml")
        data = "".join(f"{k}\t{v}\n" for k, v in items).encode()
        out = subprocess.run([str(RUST), "fst"], input=data, capture_output=True, check=True).stdout
        self.u32(len(out))
        self.buf += out
        return out

    def ranked(self, tables):
        """The ranked lists of FST tables of words or followers (word pairs, triples): (kind, table)
        with kind "words" or "followers", as one table."""
        data = b"".join(struct.pack("<I", len(t)) + t for _, t in tables)
        kinds = [k for k, _ in tables]
        out = subprocess.run([str(RUST), "fst-ranked", *kinds], input=data, capture_output=True, check=True).stdout
        self.u32(len(out))
        self.buf += out

    def str(self, s):
        b = s.encode("utf-8")
        self.u16(len(b))
        self.buf += b

    def strs(self, items):
        items = list(items)
        self.u32(len(items))
        for s in items:
            self.str(s)


def export(path=OUT):
    idx = Index.load()
    deriv = Derivation(idx)
    abbrev = (ROOT / "data" / "abbreviations.txt").read_text("utf-8").split()

    tags = sorted({t for sig in idx.sigs for ts in sig.values() for t in ts})
    tag_id = {t: i for i, t in enumerate(tags)}
    w = Writer()
    w.strs(tags)

    w.u32(len(idx.entries))
    for lemma, kind, flags in idx.entries:
        w.str(lemma)
        w.u8(KINDS.index(kind))
        w.str(flags)

    w.u32(len(idx.sigs))
    for sig in idx.sigs:
        w.u16(len(sig))
        for suf, ts in sig.items():
            w.str(suf)
            w.u8(len(ts))
            for t in ts:
                w.u16(tag_id[t])

    w.u32(len(idx.stems))
    for st, hits in idx.stems.items():
        w.str(st)
        w.u16(len(hits))
        for sid, eid in hits:
            w.u16(sid)
            w.u32(eid)

    w.strs(sorted(idx.blacklist))
    for name in ("freq.tsv", "lemma_freq.tsv"):
        w.table(_load_freq(name).items())
    w.strs(abbrev)
    w.strs(sorted(deriv.stems))
    w.u32(len(deriv.suffix_rests))
    for rest, labels in sorted(deriv.suffix_rests.items()):
        w.str(rest)
        w.str(sorted(labels)[0])
    w.strs(sorted(deriv.head_rests))

    words, pairs = {}, {}   # word -> count; "PREV WORD" -> count, "PREV " -> total << 32 | distinct
    path_bg = ROOT / "data" / "bigrams.tsv"
    if path_bg.exists():
        for line in path_bg.read_text("utf-8").splitlines():
            v, word, a, *b = line.split("\t")
            if not v:
                words[word] = int(a)
            elif not word:
                pairs[f"{v} "] = int(a) << 32 | int(b[0])
            else:
                pairs[f"{v} {word}"] = int(a)
    word_fst = w.table(words.items())
    pair_fst = w.table(pairs.items())
    triples = {}
    path_tg = ROOT / "data" / "trigrams.tsv"
    if path_tg.exists():
        for line in path_tg.read_text("utf-8").splitlines():
            v, word, a, *b = line.split("\t")
            triples[f"{v} {word}"] = int(a) << 32 | int(b[0]) if not word else int(a)
    w.ranked([("words", word_fst), ("followers", pair_fst), ("followers", w.table(triples.items()))])
    path_val = ROOT / "data" / "valency.tsv"
    valency = {}
    if path_val.exists():
        for line in path_val.read_text("utf-8").splitlines():
            *k, n = line.split("	")
            valency["	".join(k)] = int(n)
    w.table(valency.items())

    path.write_bytes(bytes(w.buf))
    return path, len(w.buf)
