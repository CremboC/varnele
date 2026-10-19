"""Productive word formation: derived words and compounds not in the lexicon.

Lithuanian makes new words freely, so no word list is ever complete:
    Kamčiatka -> kamčiatkinis, siena -> sienutė, pavasaris -> pavasarininkas,
    stogas + stulpas -> stogastulpis.
A word is accepted here if it splits into a known stem plus a productive
suffix (with a valid inflectional ending), or into two known stems.
"""

from . import paradigms as P
from .phonology import underlying

# derivational suffix -> (generator, flags) used to build its ending templates
SUFFIXES = {
    # adjectives from nouns
    "inis": (P.adjective, "B"), "iškas": (P.adjective, "BQ"), "ingas": (P.adjective, "BQ"),
    "uotas": (P.adjective, "B"), "otas": (P.adjective, "B"), "ėtas": (P.adjective, "B"),
    # persons, inhabitants, abstract nouns
    "ininkas": (P.noun, "D"), "ininkė": (P.noun, "D"), "ietis": (P.noun, "D"), "ietė": (P.noun, "D"),
    "ystė": (P.noun, "D"), "umas": (P.noun, "D"), "izmas": (P.noun, "D"), "istas": (P.noun, "D"),
    "istė": (P.noun, "D"), "ynas": (P.noun, "D"), "ija": (P.noun, "D"),
    # diminutives
    "elis": (P.noun, "D"), "ėlis": (P.noun, "D"), "ukas": (P.noun, "D"), "iukas": (P.noun, "D"),
    "utis": (P.noun, "D"), "ytis": (P.noun, "D"), "elė": (P.noun, "D"), "ėlė": (P.noun, "D"),
    "utė": (P.noun, "D"), "ytė": (P.noun, "D"), "aitė": (P.noun, "D"), "iukė": (P.noun, "D"),
    "ukė": (P.noun, "D"), "aitis": (P.noun, "D"),
}
# templates for the second part of a compound: any noun/adjective paradigm
COMPOUND_HEADS = {"as": (P.noun, "D"), "is": (P.noun, "D"), "ys": (P.noun, "D"), "a": (P.noun, "D"),
                  "ė": (P.noun, "D"), "us": (P.noun, "D"), "ias": (P.noun, "D"), "ai": (P.noun, "D"),
                  "iai": (P.noun, "D"), "os": (P.noun, "D"), "ės": (P.noun, "D"),
                  "adj_as": (P.adjective, "B"), "adj_is": (P.adjective, "B"), "adj_us": (P.adjective, "B")}
# International and native prefixoids that attach to whole nouns/adjectives
PREFIXOIDS = ("anti", "auto", "bio", "eko", "geo", "hidro", "kontr", "makro", "mikro", "mono",
              "multi", "neo", "poli", "post", "pseudo", "super", "tele", "termo", "ultra", "vice",
              "tarp", "archi", "hiper", "infra", "inter", "kvazi", "meta", "mini",
              "foto", "kino", "radio", "video", "aero", "agro", "astro", "avia", "elektro", "etno",
              "priešs", "pusiau",
              "psicho", "socio", "trans", "proto", "nano",
              "mega", "giga", "kilo", "euro", "audio", "kardio", "neuro", "fito", "zoo", "paleo")
LINKS = ("", "a", "i", "o", "ia", "io", "u", "ė", "y")
NOMINAL_ENDINGS = ("iai", "ias", "ius", "ios", "ija", "ai", "as", "is", "ys", "us", "ūs", "ia",
                   "a", "ė", "ės", "os", "uo", "i")
MIN_STEM = 4
MIN_COMPOUND_PART = 4


def _templates(table):
    """{rest-of-word: tag} for every form of every template lemma."""
    out = {}
    for suf, (gen, flags) in table.items():
        lemma = "Ø" + suf.replace("adj_", "")
        for form, tag in gen(lemma, flags):
            out.setdefault(form[1:], set()).add(f"+{suf} {tag}")
    return out


def stems_of(lemma, kind):
    """Bare stems a lemma contributes for derivation (lower case)."""
    lw = lemma.lower()
    out = set()
    if kind in ("noun", "adj", "num", "pron"):
        for end in NOMINAL_ENDINGS:
            if lw.endswith(end) and len(lw) - len(end) >= MIN_STEM:
                st = lw[: -len(end)]
                out.add(st)
                out.add(underlying(st))
                if end == "uo":
                    out |= {st + "en", st + "er"}
                break
        if lw.endswith("ija") and len(lw) > 5:
            out.add(lw[:-3])               # repeticija -> repeticinis
    elif kind == "inf" and lw.endswith("ti") and len(lw) > 4:
        out.add(lw[:-2])
    return out


class Derivation:
    def __init__(self, index):
        self.stems = set()
        for lemma, kind, _ in index.entries:
            self.stems |= stems_of(lemma, kind)
        self.suffix_rests = _templates(SUFFIXES)
        self.head_rests = _templates(COMPOUND_HEADS)
        self.index = index

    def _base(self, s):
        return len(s) >= MIN_STEM and (s in self.stems or underlying(s) in self.stems)

    def derived(self, word):
        lw = word.lower()
        for i in range(MIN_STEM, len(lw) - 1):
            if self._base(lw[:i]):
                tags = self.suffix_rests.get(lw[i:])
                if tags:
                    return f"{lw[:i]}+{sorted(tags)[0]}"
        return None

    def prefixed(self, word, analyze):
        """geo+informacinė, neo+kantininkų, anti+vėžinis"""
        lw = word.lower()
        for p in PREFIXOIDS:
            rest = lw[len(p):]
            if lw.startswith(p) and len(rest) >= 4:
                rest = rest[1:] if rest[0] == "-" else rest
                if analyze(rest) or self.derived(rest) or self.compound(rest):
                    return f"{p}+{rest}"
        return None

    def compound(self, word):
        lw = word.lower()
        for i in range(MIN_COMPOUND_PART, len(lw) - 4):
            if not self._base(lw[:i]):
                continue
            for link in LINKS:
                if not lw.startswith(link, i):
                    continue
                rest = lw[i + len(link):]
                if len(rest) < 5:
                    continue
                for eid, tag in self.index.lookup(rest):
                    if self.index.entries[eid][1] in ("noun", "adj"):
                        return f"{lw[:i]}+{link}+{rest} {tag}"
                for j in range(MIN_COMPOUND_PART, len(rest)):
                    if self._base(rest[:j]) and rest[j:] in self.head_rests:
                        return f"{lw[:i]}+{link}+{rest[:j]}+{rest[j:]}"
                d = self.derived(rest)
                if d:
                    return f"{lw[:i]}+{link}+{d}"
        return None
