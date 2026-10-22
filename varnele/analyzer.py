"""Morphological analysis: prefix grammar + index lookup + spoken-register layer."""

from dataclasses import dataclass, field

from .derivation import Derivation
from .index import Index
from .lexicon import PREFIXES, PLAIN_PREFIX_FLAGS, REFL_PREFIX_FLAGS
from .phonology import fold

NEGS = ("", "ne", "nebe", "be", "te", "tebe")
# folded verbal prefix -> real spelling (iš, į, už carry diacritics)
VP_FOLDED = {}
for _p in PREFIXES:
    VP_FOLDED[fold(_p)] = _p
    if _p in ("ap", "at"):
        VP_FOLDED[_p + "i"] = _p + "i"
VERB_KINDS = {"inf", "prs", "pst"}

# Spoken shortenings: (colloquial ending, formal ending, tag test)
COLLOQUIAL = [
    ("t", "ti", lambda t: t == "V.inf"),               # valgyt -> valgyti
    ("m", "me", lambda t: t.endswith(".1pl")),         # buvom -> buvome, dirbkim, būtumėm
    ("t", "te", lambda t: t.endswith(".2pl")),         # buvot -> buvote, dirbkit
    ("s", "si", lambda t: t.endswith(".refl")),        # jaučias -> jaučiasi, džiaugiuos
    ("oj", "oje", lambda t: t.endswith(".loc")),       # mokykloj -> mokykloje
    ("ėj", "ėje", lambda t: t.endswith(".loc")),       # gatvėj -> gatvėje
    ("uj", "uje", lambda t: t.endswith(".loc")),       # turguj -> turguje
    ("y", "yje", lambda t: t.endswith(".loc")),        # kely -> kelyje
    ("uos", "uose", lambda t: t.endswith(".loc")),     # namuos -> namuose
    ("am", "ame", lambda t: t.endswith(".loc")),       # tam name -> tame
    ("om", "oms", lambda t: t.endswith(".pl.dat")),    # kategorijom -> kategorijoms
    ("om", "omis", lambda t: t.endswith(".pl.ins")),   # įgulom -> įgulomis
    ("ėm", "ėms", lambda t: t.endswith(".pl.dat")),
    ("ėm", "ėmis", lambda t: t.endswith(".pl.ins")),
    ("am", "ams", lambda t: t.endswith(".pl.dat")),    # vaikam -> vaikams
    ("im", "ims", lambda t: t.endswith(".pl.dat")),
    ("im", "imis", lambda t: t.endswith(".pl.ins")),
]
# Spoken words that are no shortening of an ending: word -> its standard form
SPOKEN_WORDS = {
    "eime": "eikime",     # let's go: imperative of eiti without -ki-
}


@dataclass
class Analysis:
    form: str
    lemma: str
    kind: str
    tag: str
    prefix: str = ""
    entry: int = -1          # index entry the form was generated from (for re-inflecting)


@dataclass
class Result:
    word: str
    status: str                      # ok | derived | compound | colloquial | unknown
    analyses: list = field(default_factory=list)
    formal: list = field(default_factory=list)


def _prefix_splits(word):
    """Yield (neg, vp_index, vp_surface, si, core) for every possible prefix chain."""
    for neg in NEGS:
        if not word.startswith(neg):
            continue
        r1 = word[len(neg):]
        options = [(-1, "")]
        for i, p in enumerate(PREFIXES):
            options.append((i, p))
            if p in ("ap", "at"):
                options.append((i, p + "i"))
        for vi, vs in options:
            if not r1.startswith(vs):
                continue
            r2 = r1[len(vs):]
            for si in ("", "si"):
                if not r2.startswith(si):
                    continue
                if si and not (neg or vs):
                    continue
                core = r2[len(si):]
                if len(core) < 2 and (neg or vs or si):
                    continue
                nxt = (si or core)[0]
                if vs == "api" and (si or nxt not in "pb"):
                    continue
                if vs == "ati" and (si or nxt not in "td"):
                    continue
                if vs == "ap" and nxt in "pb" or vs == "at" and nxt in "td":
                    continue
                yield neg, vi, vs, si, core


def _allowed(kind, flags, tag, neg, vi, si):
    refl = tag.endswith(".refl")
    if kind not in VERB_KINDS:
        if vi >= 0 or si:
            return False
        return not neg or (neg == "ne" and "N" in flags)
    if refl and (neg or vi >= 0 or si):
        return False   # *nedžiaugiasi -> nesidžiaugia; *nusipraustis
    if vi >= 0:
        if neg not in ("", "ne", "nebe"):
            return False
        if not any(c.islower() for c in flags):
            # ispell-lt lists some principal parts without prefix data
            # (kristi/krito have it, krinta does not): allow any prefix.
            return not si or bool(set(flags) & set("ROS"))
        return (REFL_PREFIX_FLAGS if si else PLAIN_PREFIX_FLAGS)[vi] in flags
    if si:
        return neg in ("ne", "nebe", "be", "tebe") and "S" in flags
    if neg in ("ne", "nebe"):
        return "N" in flags or "S" in flags
    if neg:
        return "X" in flags
    return True


class Analyzer:
    def __init__(self, index=None):
        self.index = index or Index.load()
        self._deriv = None

    @property
    def deriv(self):
        if self._deriv is None:
            self._deriv = Derivation(self.index)
        return self._deriv

    def _analyze_exact(self, word):
        out, idx = [], self.index
        for neg, vi, vs, si, core in _prefix_splits(word):
            for eid, tag in idx.lookup(core):
                lemma, kind, flags = idx.entries[eid]
                if _allowed(kind, flags, tag, neg, vi, si):
                    out.append(Analysis(word, lemma, kind, tag, neg + vs + si, eid))
        return out

    def analyze(self, word):
        """All analyses of a word, trying sensible case variants."""
        variants = [word]
        if word[:1].isupper():
            if word.isupper() and len(word) > 1:
                variants += [word.capitalize(), word.lower()]
            else:
                variants.append(word[0].lower() + word[1:])
        for v in variants:
            res = self._analyze_exact(v)
            if res:
                return res
        return []

    def folded_forms(self, fw):
        """Real words (with any prefix chain) whose diacritic-free spelling is fw."""
        out = set()
        for neg in NEGS:
            if not fw.startswith(neg):
                continue
            r1 = fw[len(neg):]
            for fvp, vp in [("", "")] + list(VP_FOLDED.items()):
                if not r1.startswith(fvp):
                    continue
                r2 = r1[len(fvp):]
                for si in ("", "si"):
                    if not r2.startswith(si) or (si and not (neg or vp)):
                        continue
                    core = r2[len(si):]
                    if len(core) < 2 and (neg or vp or si):
                        continue
                    for real in self.index.lookup_folded(core):
                        out.add(neg + vp + si + real)
        return out

    def blocked(self, word):
        """A known word within one slip of this one blocks productive analyses:
        'temperaturos' is a misspelling of 'temperatūros' and 'pulininkai' of
        'pulkininkai', not new derived words or compounds."""
        from .suggest import FOLDED_ALPHABET, _edits1
        lw = word.lower()
        fw = fold(lw)
        for probe in [fw, *_edits1(fw, FOLDED_ALPHABET)]:
            for cand in self.folded_forms(probe):
                if cand.lower() != lw and self._analyze_exact(cand):
                    return True
        return False

    def colloquial(self, word):
        """Formal forms this word could be a spoken shortening of."""
        found = []
        full = SPOKEN_WORDS.get(word.lower())
        if full:
            found.append(full if word[:1].islower() else full.capitalize())
        for short, full, test in COLLOQUIAL:
            if word.endswith(short) and len(word) > len(short) + 1:
                cand = word[: len(word) - len(short)] + full
                if cand == word:
                    continue
                if any(test(a.tag) for a in self.analyze(cand)):
                    if cand not in found:
                        found.append(cand)
        return found

    def check(self, word):
        an = self.analyze(word)
        if an:
            return Result(word, "ok", an)
        formal = self.colloquial(word)
        if formal:
            return Result(word, "colloquial", [], formal)
        # Productive analyses are guesses: a known word one slip away wins.
        for status, fn in (("derived", self.deriv.derived), ("compound", self.deriv.compound),
                           ("derived", lambda w: self.deriv.prefixed(w, self._analyze_exact))):
            how = fn(word)
            if how:
                if self.blocked(word):
                    break
                return Result(word, status, [Analysis(word, how, status, status)])
        return Result(word, "unknown")
