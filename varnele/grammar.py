"""Context rules: errors a word-by-word checker cannot see.

"prieš pora dienų" is made of valid words, but "prieš" demands the accusative
("porą"). Typing without diacritics produces exactly this kind of error,
because the case endings -ą -ę -į -ų are the letters that get lost.

Case rules only fire when a spelling that differs in diacritics alone would
satisfy them, so a correct but unusual construction is not flagged.
"""

import re
from dataclasses import dataclass, field

from .phonology import fold

WORD = re.compile(r"[^\W\d_]+(?:[-‑][^\W\d_]+)*")
FINITE = {"prs", "pst", "pstf", "fut", "cond", "imp", "inf"}
CASE_NAMES = {"nom": "nominative", "gen": "genitive", "dat": "dative", "acc": "accusative",
              "ins": "instrumental", "loc": "locative", "voc": "vocative"}

# Preposition -> cases it governs. ("po" takes three cases: nothing to check.)
PREPOSITIONS = {
    **dict.fromkeys(["į", "per", "pro", "prieš", "apie", "pagal", "palei", "pas", "aplink"], {"acc"}),
    **dict.fromkeys(["iš", "be", "nuo", "prie", "iki", "ligi", "dėl", "ant", "virš", "tarp",
                     "anot", "pasak", "šalia", "vietoj", "netoli", "anapus", "šiapus", "abipus",
                     "vidury", "vidur"], {"gen"}),
    "už": {"gen", "acc"},
    "su": {"ins"},
    "sulig": {"ins"},
    "ties": {"ins", "gen"},
}
PREP_BY_FOLD = {fold(p): p for p in PREPOSITIONS}

# Words after which a noun phrase must be genitive: daug vaikų, keletas dienų, dešimt metų
QUANTIFIER_WORDS = {"daug", "mažai", "nemažai", "kiek", "tiek", "daugiau", "mažiau", "nedaug",
                    "keletas", "keleto", "keletą", "keletui", "keletu", "daugybė", "daugybę",
                    "daugybės", "dauguma", "daugumą", "daugumos", "pora", "porą", "poros", "porai",
                    "pustrečio", "kelios", "keliolika", "tūkstantis", "tūkstančiai", "tūkstančių",
                    "tūkstantį", "tūkstančius"}
QUANTIFIER_LEMMAS = {"šimtas", "tūkstantis", "milijonas", "milijardas", "dešimtis", "keletas",
                     "pora", "daugybė", "dauguma", "pusė", "trečdalis", "ketvirtadalis", "ketvirtis"}

# Comma rules: these start a clause, so a comma goes before them.
KURIS = {"kuris", "kuri", "kurio", "kurios", "kuriam", "kuriai", "kurį", "kurią", "kuriuo",
         "kuria", "kuriame", "kurioje", "kurie", "kurių", "kuriems", "kurioms", "kuriuos",
         "kurias", "kuriais", "kuriomis", "kuriuose", "kuriose"}
CLAUSE_STARTERS = {"kad", "nes", "jog", "bet", "tačiau", "kadangi", "nors", "jei", "jeigu", "kai",
                   "kol", "nebent", "o"} | KURIS
# ...unless the previous word is part of the same connective ("ir kad", "net jei", "ypač kai")
NO_COMMA_AFTER = {"ir", "ar", "arba", "bei", "o", "bet", "nes", "kad", "jog", "tik", "net", "ypač",
                  "būtent", "nebent", "juk", "negu", "nei", "kaip", "jei", "jeigu", "kai", "nors",
                  "tačiau", "kadangi", "kol", "vos", "lyg", "tarsi", "nebent", "užtat", "taigi"}
INTERROGATIVES = {"kas", "ką", "ko", "kam", "kuo", "kur", "kada", "kaip", "kodėl", "kieno", "kiek",
                  "koks", "kokia", "kokį", "kokią", "kokie", "kokios", "kokių", "kokio",
                  "kokiam", "kokiu", "kokiame", "kokioje", "kokiems", "kokius", "kokias",
                  "kažkas", "kažkur"} | KURIS


@dataclass
class Issue:
    start: int
    end: int
    word: str
    rule: str                      # case | agreement | quantity | comma | context
    message: str
    suggestions: list = field(default_factory=list)


@dataclass
class Reading:
    pos: str          # noun | adj
    case: str
    number: str = None
    gender: str = None
    participle: bool = False


def readings(analyses):
    out = []
    for a in analyses:
        parts = a.tag.split(".")
        case = next((p for p in parts if p in CASE_NAMES), None)
        if not case:
            continue
        number = "sg" if "sg" in parts else "pl" if "pl" in parts else None
        gender = "m" if "m" in parts else "f" if "f" in parts else None
        if parts[0] == "N":
            out.append(Reading("noun", case, number, gender))
        elif parts[0] in ("A", "P", "Num"):
            out.append(Reading("adj", case, number, gender))
        elif parts[0] == "V" and parts[1].startswith("p"):
            out.append(Reading("adj", case, number, gender, participle=True))
    return out


class Word:
    """A token with its own readings and those of its diacritic-only variants."""

    def __init__(self, grammar, text, start, end):
        self.g, self.text, self.start, self.end = grammar, text, start, end
        self.lower = text.lower()
        self.own = grammar.readings_of(text)       # by original spelling: Lietuvos is a name
        self.known = grammar.known(text)          # includes derived words and compounds
        self._variants = None

    @property
    def variants(self):
        if self._variants is None:
            forms = self.g.variants_of(self.lower)
            if self.text[:1].islower():
                forms = [f for f in forms if f[:1].islower()]   # ežerėlių is not the name Ežerėliu
            self._variants = [(f, self.g.readings_of(f)) for f in forms]
        return self._variants

    def pos_readings(self):
        """Own readings, or the variants' readings for an unknown word."""
        if self.own or self.known:
            return self.own
        return [r for _, rs in self.variants for r in rs]

    @property
    def is_noun(self):
        return any(r.pos == "noun" for r in self.pos_readings())

    @property
    def is_participle(self):
        """Participles act like verbs (take objects, predicate nouns): not part of a phrase."""
        rs = [r for r in self.pos_readings() if r.pos == "adj"]
        return bool(rs) and all(r.participle for r in rs)

    @property
    def can_be_verb(self):
        """palaikė is a listed verb, so it is not an adjective here; prastos is a verb
        only via a rule-built prefix (pra+stos), which doesn't outweigh the adjective."""
        for a in self.g.an.analyze(self.text):
            parts = a.tag.split(".")
            if parts[0] == "V" and len(parts) > 1 and parts[1] in FINITE:
                vp = re.sub(r"^(nebe|tebe|ne|be|te)", "", a.prefix)
                if vp in ("", "si"):
                    return True
        return False

    def can_be(self, case):
        return any(r.case == case for r in self.pos_readings())

    def is_quantity(self):
        return self.lower in QUANTIFIER_WORDS or any(
            a.lemma.lower() in QUANTIFIER_LEMMAS and a.kind in ("noun", "num")
            or a.kind == "num" and a.lemma.endswith(("lika", "dešimt"))     # not Respublika
            for a in self.g.an.analyze(self.text))

    def is_comparative(self):
        return any(".cmp" in a.tag for a in self.g.an.analyze(self.text))

    @property
    def is_adj(self):
        rs = self.pos_readings()
        return any(r.pos == "adj" for r in rs) and not any(r.pos == "noun" for r in rs)

    def cap(self, form):
        return form[0].upper() + form[1:] if self.text[:1].isupper() else form


def _could_agree(w1, w2):
    """Could these two words be in one noun phrase (allowing a diacritic fix)?"""
    r1 = w1.pos_readings() + [r for _, rs in w1.variants for r in rs]
    r2 = w2.pos_readings() + [r for _, rs in w2.variants for r in rs]
    return any(_agree(a, b) for a in r1 for b in r2)


def _agree(r1, r2):
    def same(a, b):
        return not a or not b or a == b
    return r1.case == r2.case and same(r1.number, r2.number) and same(r1.gender, r2.gender)


class Grammar:
    def __init__(self, analyzer):
        self.an = analyzer
        self._read, self._var, self._known = {}, {}, {}

    def known(self, w):
        if w not in self._known:
            self._known[w] = self.an.check(w).status != "unknown"
        return self._known[w]

    def readings_of(self, w):
        if w not in self._read:
            self._read[w] = readings(self.an.analyze(w))
        return self._read[w]

    def variants_of(self, w):
        """Other real words spelled like w apart from diacritics."""
        if w not in self._var:
            self._var[w] = sorted(f for f in self.an.folded_forms(fold(w))
                                  if f.lower() != w and self.an._analyze_exact(f))
        return self._var[w]

    # ------------------------------------------------------------------
    def check(self, text):
        toks = [Word(self, m.group(), m.start(), m.end()) for m in WORD.finditer(text)]
        gaps = [text[toks[i - 1].end:t.start] if i else text[:t.start] for i, t in enumerate(toks)]
        adjacent = [i > 0 and g.strip() == "" for i, g in enumerate(gaps)]
        issues = {}

        def add(issue):
            issues.setdefault(issue.start, issue)

        def phrase(i):
            """Adjectives/pronouns/participles up to and including the first noun after i."""
            span, j = [], i + 1
            while j < len(toks) and adjacent[j]:
                w = toks[j]
                if span and not _could_agree(span[-1], w):
                    break         # už didžiausią | tuo metu: a new phrase starts
                if w.is_noun:
                    span.append(w)
                    break
                if not w.is_adj or w.is_participle:
                    break
                span.append(w)
                j += 1
            return span

        def require(w, cases, rule, why):
            """Flag w if it cannot be in `cases` but a diacritic variant can."""
            if any(r.case in cases for r in w.own):
                return
            if "gen" not in cases and any(r.case == "gen" for r in w.own):
                return            # may be a genitive modifier of a later noun: su lietuvių kultūra
            fixes = [w.cap(f) for f, rs in w.variants if any(r.case in cases for r in rs)]
            if not fixes:
                return
            if w.known and not w.own:
                return            # indeclinable word: nothing to check
            add(Issue(w.start, w.end, w.text, rule if w.known else "context", why, fixes))

        for i, w in enumerate(toks):
            nxt_adjacent = i + 1 < len(toks) and adjacent[i + 1]
            # 1. prepositions (also recognised without diacritics: pries, is, i, uz)
            prep = w.lower if w.lower in PREPOSITIONS else (
                PREP_BY_FOLD.get(fold(w.lower)) if not w.known else None)
            if prep and nxt_adjacent:
                span = phrase(i)
                numeral = span and any(a.kind == "num" for a in self.an.analyze(span[0].text))
                if (span and span[-1].is_noun and not numeral                 # per šešiolika metų
                        and not (prep == "apie" and span[0].is_quantity())):   # apie pusė = "about half"
                    cases = PREPOSITIONS[prep]
                    want = " or ".join(CASE_NAMES[c] for c in sorted(cases))
                    for x in span:
                        require(x, cases, "case", f"'{prep}' takes the {want}")
            # 3. quantity words
            if nxt_adjacent and w.is_quantity():
                span = phrase(i)
                if span and span[-1].is_noun and not any(x.is_comparative() for x in span):
                    for x in span:
                        require(x, {"gen"}, "quantity", f"after '{w.text}' use the genitive")
            # 4. commas
            if i > 0 and w.lower in CLAUSE_STARTERS and adjacent[i]:
                prev = toks[i - 1].lower
                nxt = toks[i + 1].lower if nxt_adjacent else ""
                indefinite = nxt in INTERROGATIVES or nxt.startswith(("kok", "kur", "kie"))
                skip = (prev in NO_COMMA_AFTER or prev in PREPOSITIONS
                        or w.text[:1].isupper()                              # names, initials: O. Mauseris
                        or text[w.end:w.end + 1] == "."
                        or (w.lower in ("bet", "kai") and indefinite)        # bet kas, kai kurie
                        or (w.lower == "nors" and (prev in INTERROGATIVES or nxt == "ir"))  # kas nors
                        or (w.lower in KURIS and (prev in ("bet", "kai")      # bet kuris
                                                  or nxt in ("nors", "laikui", "laiką", "laiko"))))
                if not skip:
                    add(Issue(w.start, w.end, w.text, "comma",
                              f"comma needed before '{w.text}'", [", " + w.text]))
            # comma before a preposition that introduces a relative clause: ..., su kuriuo
            if (i > 0 and w.lower in PREPOSITIONS and adjacent[i] and nxt_adjacent
                    and toks[i + 1].lower in KURIS and toks[i - 1].lower not in NO_COMMA_AFTER):
                add(Issue(w.start, w.end, w.text, "comma",
                          f"comma needed before '{w.text} {toks[i + 1].text}'", [", " + w.text]))

        # 2. adjective-noun agreement
        for i in range(1, len(toks)):
            a, n = toks[i - 1], toks[i]
            if not adjacent[i] or a.start in issues:
                continue
            if (not (a.is_adj and n.is_noun) or a.is_participle or a.can_be_verb
                    or not (a.known or n.known)):
                continue
            if a.lower in ("vienas", "viena", "vieni", "vienos"):
                continue          # viena kitą = each other
            if n.can_be("gen") and not a.can_be("gen"):
                # Genitive modifiers sit between an adjective and its noun:
                # profesionalūs [Lietuvos cirko] artistai. Skip them to the head.
                j = i
                while (j + 1 < len(toks) and adjacent[j + 1] and toks[j].known
                       and toks[j].can_be("gen") and toks[j + 1].is_noun):
                    j += 1
                if j == i or toks[j].can_be("gen") or not toks[j].known:
                    continue
                n = toks[j]
            if n.start in issues:
                continue
            ar = [r for r in a.pos_readings() if r.pos == "adj"]
            nr = [r for r in n.pos_readings() if r.pos == "noun"]
            if a.known and n.known and any(_agree(x, y) for x in ar for y in nr):
                continue
            fix_n = [n.cap(f) for f, rs in n.variants
                     if any(_agree(x, y) for x in ar for y in rs if y.pos == "noun")]
            fix_a = [a.cap(f) for f, rs in a.variants
                     if any(_agree(x, y) for x in rs if x.pos == "adj" for y in nr)]
            msg = f"'{a.text} {n.text}': adjective and noun must agree in case and number"
            # An unknown word may only reorder its own suggestions; it never
            # justifies changing a correctly spelled neighbour.
            if not n.known:
                fix_a = []
            if not a.known:
                fix_n = []
            if fix_n:
                add(Issue(n.start, n.end, n.text, "agreement" if n.known else "context", msg, fix_n))
            elif fix_a:
                add(Issue(a.start, a.end, a.text, "agreement" if a.known else "context", msg, fix_a))

        return sorted(issues.values(), key=lambda x: x.start)
