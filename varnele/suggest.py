"""Correction suggestions.

Two candidate sources, both verified by the analyzer:
  1. Diacritic-blind lookup: "sviesa" -> "šviesa", "ivikis" -> "įvykis".
     Handles the most common Lithuanian errors (ą/a, ė/e/ę, į/i/y, ū/u/ų, š/s ...).
  2. One ordinary typo (insert/delete/replace/swap) on top of that.
Candidates are ranked by a weighted edit distance where swapping letters
inside a diacritic class is cheap and anything else costs a full edit.
"""

import math
from pathlib import Path

from .analyzer import COLLOQUIAL
from .phonology import LT_ALPHABET, fold

FOLDED_ALPHABET = sorted(set(fold(LT_ALPHABET)))


KEYBOARD = ["qwertyuiop", "asdfghjkl", "zxcvbnm"]
_POS = {c: (r, i) for r, row in enumerate(KEYBOARD) for i, c in enumerate(row)}


def _near(a, b):
    """Adjacent keys on a QWERTY-based Lithuanian layout (diacritics share their base key)."""
    pa, pb = _POS.get(fold(a)), _POS.get(fold(b))
    return bool(pa and pb) and abs(pa[0] - pb[0]) <= 1 and abs(pa[1] - pb[1]) <= 1


def _cost(a, b):
    """Damerau-Levenshtein with cheap same-class substitutions."""
    n, m = len(a), len(b)
    d = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        d[i][0] = float(i)
    for j in range(m + 1):
        d[0][j] = float(j)
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            ca, cb = a[i - 1], b[j - 1]
            sub = (0.0 if ca == cb else 0.6 if {ca.lower(), cb.lower()} == {"i", "y"}   # y is its own key
                   else 0.3 if fold(ca) == fold(cb) else 0.8 if _near(ca, cb) else 1.0)
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + sub)
            if i > 1 and j > 1 and ca == b[j - 2] and a[i - 2] == cb:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)
    return d[n][m]


def _diacritic_cost(word, cand):
    """Cost of a same-length fix that only changes diacritics (and i/y). If nothing was
    typed with diacritics, how many are missing says nothing: one counts like many,
    and frequency decides (turetu -> turėtų, not the rare turėtu)."""
    if any(c in "ąčęėįšųūž" for c in word):
        return _cost(word, cand)
    diacritics = sum(1 for a, b in zip(word, cand) if a != b and {a, b} != {"i", "y"})
    swaps = sum(1 for a, b in zip(word, cand) if {a, b} == {"i", "y"})
    return (0.3 if diacritics else 0.0) + 0.6 * swaps


def _edits1(w, alphabet):
    splits = [(w[:i], w[i:]) for i in range(len(w) + 1)]
    out = set()
    for l, r in splits:
        if r:
            out.add(l + r[1:])
            for c in alphabet:
                out.add(l + c + r[1:])
        if len(r) > 1:
            out.add(l + r[1] + r[0] + r[2:])
        for c in alphabet:
            out.add(l + c + r)
    out.discard(w)
    return out


DATA = Path(__file__).resolve().parent.parent / "data"


def _load_freq(name):
    freq = {}
    path = DATA / name
    if path.exists():
        for line in path.read_text("utf-8").splitlines():
            w, _, n = line.partition("\t")
            freq[w] = int(n)
    return freq


class Suggester:
    def __init__(self, analyzer):
        self.an = analyzer
        self.idx = analyzer.index
        self.freq = _load_freq("freq.tsv")
        self.lemma_freq = _load_freq("lemma_freq.tsv")

    def _score(self, word, cand):
        """Lower is better. Diacritic-only fixes always beat real edits; among
        equally plausible candidates, frequent words win."""
        lf = max((self.lemma_freq.get(a.lemma.lower(), 0) for a in self.an._analyze_exact(cand)), default=0)
        cl = cand.lower()
        # a negated form is as common as the plain one: neturėtų counts like turėtų
        f = self.freq.get(cl, 0) or (self.freq.get(cl[2:], 0) if cl.startswith("ne") else 0)
        bonus = 0.12 * math.log10(1 + f) + 0.1 * math.log10(1 + lf)
        if fold(cand.lower()) == fold(word):
            return 0.1 + 0.5 * _diacritic_cost(word, cand.lower()) - bonus
        return _cost(word, cand.lower()) - bonus

    def _folded_forms(self, fw):
        return self.an.folded_forms(fw)

    def suggest(self, word, n=5):
        lower = word.lower()
        cands = set()
        fw = fold(lower)
        cands |= self._folded_forms(fw)
        if len(fw) <= 25:
            for e in _edits1(fw, FOLDED_ALPHABET):
                cands |= self._folded_forms(e)
        # spoken shortening + missing diacritics at once: rasyt -> rašyti
        spoken = {}
        for short, full, _ in COLLOQUIAL:
            if fw.endswith(fold(short)) and len(fw) > len(short) + 1:
                for c in self._folded_forms(fw[: len(fw) - len(short)] + fold(full)):
                    spoken[c] = lower[: len(lower) - len(short)] + full
                    cands.add(c)
        # Only keep candidates the full analyzer accepts (prefix flags etc.)
        good = [c for c in cands if c != lower and (len(c) > 1 or len(lower) <= 2)
                and self.an._analyze_exact(c)]
        cap = word[:1].isupper()
        def score(c):
            base = spoken.get(c)
            sc = self._score(lower, c)
            sc = min(sc, self._score(base, c) + 0.05) if base else sc
            # a lowercase word is rarely a misspelt name: dvara -> dvarą, not Dvarą
            # 0.3: a name can share a lemma key with a verb (Klausė / klausė, past of klausti)
            return sc + (0.3 if c[:1].isupper() and word[:1].islower() else 0)
        ranked = sorted(good, key=lambda c: (score(c), c))
        return [c[0].upper() + c[1:] if cap else c for c in ranked[:n]]
