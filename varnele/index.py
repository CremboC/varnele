"""Compact form index.

Fully expanding every lexeme gives millions of forms. Instead each lexeme is
stored as (stem, signature): the stem is the longest prefix shared by all its
forms, and the signature is the set of endings (with tags) hanging off it.
Thousands of lexemes share one signature, so the index stays small.
"""

import os
import pickle
import sys
import time

from . import lexicon, paradigms as P
from .phonology import fold

CACHE = lexicon.ROOT / "data" / "index.pkl"

GENERATORS = {
    "noun": P.noun, "adj": P.adjective, "pron": P.pronoun, "num": P.numeral,
    "inf": P.verb_infinitive, "prs": P.verb_present, "pst": P.verb_past,
}


def generate(lemma, kind, flags):
    gen = GENERATORS.get(kind)
    if gen is None:
        return [(lemma, "W")]
    return gen(lemma, flags)


def _lcp(words):
    a, b = min(words), max(words)
    i = 0
    while i < len(a) and a[i] == b[i]:
        i += 1
    return a[:i]


class Index:
    def __init__(self, entries, stems, sigs, blacklist):
        self.entries = entries      # [(lemma, kind, flags)]
        self.stems = stems          # stem -> [(sig_id, entry_id)]
        self.sigs = sigs            # [ {suffix: (tag, ...)} ]
        self.blacklist = blacklist
        self._folded = None

    @classmethod
    def build(cls, verbose=True):
        t0 = time.time()
        entries, blacklist = lexicon.load()
        stems, sigs, sig_ids, nforms = {}, [], {}, 0
        for eid, (lemma, kind, flags) in enumerate(entries):
            forms = {}
            for form, tag in generate(lemma, kind, flags):
                forms.setdefault(form, set()).add(sys.intern(tag))
            nforms += len(forms)
            stem = _lcp(list(forms))
            groups = ({stem: forms} if len(stem) >= 2 else
                      {f: {f: t} for f, t in forms.items()})
            for st, fs in groups.items():
                sig = tuple(sorted((f[len(st):], tuple(sorted(t))) for f, t in fs.items()))
                sid = sig_ids.get(sig)
                if sid is None:
                    sid = sig_ids[sig] = len(sigs)
                    sigs.append(dict(sig))
                stems.setdefault(st, []).append((sid, eid))
        if verbose:
            print(f"built index: {len(entries):,} lexicon entries, {nforms:,} forms, "
                  f"{len(stems):,} stems, {len(sigs):,} signatures in {time.time() - t0:.1f}s",
                  file=sys.stderr)
        return cls(entries, stems, sigs, blacklist)

    def save(self, path=CACHE):
        os.makedirs(path.parent, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump((self.entries, self.stems, self.sigs, self.blacklist), f,
                        protocol=pickle.HIGHEST_PROTOCOL)

    @classmethod
    def load(cls, path=CACHE, rebuild=False):
        src = [lexicon.ROOT / "varnele" / n for n in ("paradigms.py", "phonology.py", "lexicon.py")]
        src.append(lexicon.EXTRA)
        fresh = path.exists() and all(path.stat().st_mtime > p.stat().st_mtime for p in src if p.exists())
        if fresh and not rebuild:
            with open(path, "rb") as f:
                return cls(*pickle.load(f))
        idx = cls.build()
        idx.save(path)
        return idx

    # ------------------------------------------------------------------
    def lookup(self, word):
        """Exact lookup of an unprefixed form -> [(entry_id, tag)]."""
        out = []
        if word in self.blacklist:
            return out
        for i in range(len(word), 0, -1):
            hits = self.stems.get(word[:i])
            if hits:
                suf = word[i:]
                for sid, eid in hits:
                    tags = self.sigs[sid].get(suf)
                    if tags:
                        out.extend((eid, t) for t in tags)
        return out

    def folded(self):
        """Lazily built index keyed by diacritic-free stems and endings."""
        if self._folded is None:
            fstems = {}
            for st, hits in self.stems.items():
                fstems.setdefault(fold(st.lower()), []).append((st, hits))
            fsigs = []
            for sig in self.sigs:
                m = {}
                for suf in sig:
                    m.setdefault(fold(suf), []).append(suf)
                fsigs.append(m)
            self._folded = (fstems, fsigs)
        return self._folded

    def lookup_folded(self, fword):
        """All real unprefixed forms whose folded spelling equals fword."""
        fstems, fsigs = self.folded()
        out = set()
        for i in range(len(fword), 0, -1):
            for st, hits in fstems.get(fword[:i], ()):
                fsuf = fword[i:]
                for sid, _ in hits:
                    for suf in fsigs[sid].get(fsuf, ()):
                        out.add(st + suf)
        return out
