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
from .suggest import DATA, _cost, _load_freq

WORD = re.compile(r"[^\W\d_]+(?:[-‑][^\W\d_]+)*")
FINITE = {"prs", "pst", "pstf", "fut", "cond", "imp", "inf"}
CASE_NAMES = {"nom": "nominative", "gen": "genitive", "dat": "dative", "acc": "accusative",
              "ins": "instrumental", "loc": "locative", "voc": "vocative"}

# Preposition -> cases it governs. ("po" takes three cases: nothing to check.)
PREPOSITIONS = {
    **dict.fromkeys(["į", "per", "pro", "prieš", "apie", "pagal", "palei", "pas", "aplink"], {"acc"}),
    **dict.fromkeys(["iš", "be", "nuo", "prie", "iki", "ligi", "dėl", "ant", "virš", "tarp",
                     "anot", "pasak", "šalia", "vietoj", "netoli", "anapus", "šiapus", "abipus",
                     "vidury", "vidur", "link"], {"gen"}),
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
# (number, gender) each form of kuris can have; gender None = any
KURIS_FEATURES = {
    "kuris": {("sg", "m")}, "kuri": {("sg", "f")}, "kurio": {("sg", "m")},
    "kurios": {("sg", "f"), ("pl", "f")}, "kuriam": {("sg", "m")}, "kuriai": {("sg", "f")},
    "kurį": {("sg", "m")}, "kurią": {("sg", "f")}, "kuriuo": {("sg", "m")}, "kuria": {("sg", "f")},
    "kuriame": {("sg", "m")}, "kurioje": {("sg", "f")}, "kurie": {("pl", "m")},
    "kurių": {("pl", None)}, "kuriems": {("pl", "m")}, "kurioms": {("pl", "f")},
    "kuriuos": {("pl", "m")}, "kurias": {("pl", "f")}, "kuriais": {("pl", "m")},
    "kuriomis": {("pl", "f")}, "kuriuose": {("pl", "m")}, "kuriose": {("pl", "f")},
}
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

INTERROGATIVES_FOLDED = {fold(w) for w in INTERROGATIVES}

# Negated verbs take a genitive object: neturiu laiko, nemačiau jo.
NEG_PRONOUNS = {"jį": "jo", "ją": "jos", "juos": "jų", "jas": "jų", "mane": "manęs",
                "tave": "tavęs", "mus": "mūsų", "jus": "jūsų", "save": "savęs", "tą": "to",
                "šį": "šio", "šią": "šios", "tuos": "tų", "šiuos": "šių"}
# ...except durations, which stay accusative: nedirbau visą dieną
TIME_LEMMAS = {"diena", "naktis", "savaitė", "mėnuo", "metai", "valanda", "minutė", "sekundė",
               "kartas", "rytas", "vakaras", "žiema", "vasara", "pavasaris", "ruduo", "para",
               "pusmetis", "dešimtmetis", "šimtmetis", "amžius", "laikotarpis", "popietė"}
# Verbs that take a genitive object: laukiu tavo žinutės, reikia pagalbos, ieškau raktų
# (principal parts, matched by ending so prefixed entries count)
GENITIVE_VERBS = ("laukti", "laukia", "laukė", "ieškoti", "ieško", "ieškojo", "bijoti", "bijo", "bijojo",
                  "siekti", "siekia", "siekė", "reikėti", "reikia", "reikėjo", "vengti", "vengia", "vengė")
VERB_PREFIXES = {"ap", "at", "į", "iš", "nu", "pa", "par", "per", "pra", "pri", "su", "už", "api", "ati"}
POSSESSIVES = {"mano", "tavo", "savo", "jo", "jos", "jų", "mūsų", "jūsų"}
# A number ending in 0 or 11-19 takes the genitive plural: 10 metų, 15 eurų (not 2,5 or the ordinal 10.)
GEN_NUMBER = re.compile(r"(?:^|[\s(–—-])(\d+)\s+$")
TIME_WORDS = {"visą", "visus", "visas", "kiekvieną", "ištisą", "ištisus", "ištisas"}
# Linking verbs take a nominative or instrumental, not an object.
# Verbs whose object is practically never a bare instrumental, so "matau viena klaida" is
# an accusative typed without diacritics (motion verbs do take one: einu gatve). Principal
# parts, matched by ending so prefixed entries count (pamatyti, surado). Verbs that take an
# instrument (rašau ranka, valgau šakute) stay out.
TRANSITIVE_VERBS = ("matyti", "mato", "matė", "rasti", "randa", "rado", "turėti", "turi", "turėjo",
                    "gauti", "gauna", "gavo", "pirkti", "perka", "pirko", "žinoti", "žino", "žinojo",
                    "mylėti", "myli", "mylėjo", "girdėti", "girdi", "girdėjo", "sutikti", "sutinka", "sutiko",
                    "skaityti", "skaito", "skaitė")
# words that may stand between a verb and its object: matau dar vieną klaidą
OBJECT_SKIP = {"dar", "jau", "vėl", "irgi", "tik", "net"}
# verbs of seeing, knowing and saying that take an indirect question: matau, ką man rašo
# (principal parts, matched by ending so prefixed entries count)
QUESTION_VERBS = ("matyti", "mato", "matė", "žinoti", "žino", "žinojo", "suprasti", "supranta", "suprato",
                  "sakyti", "sako", "sakė", "klausti", "klausia", "klausė", "girdėti", "girdi", "girdėjo",
                  "galvoti", "galvoja", "galvojo", "manyti", "mano", "manė", "aiškinti", "aiškina", "aiškino",
                  "rodyti", "rodo", "rodė", "pasakoti", "pasakoja", "pasakojo")
# these start a clause, they are not the object: manau, kas ... / žinau, kuris ...
CLAUSE_WORDS = {"kas", "kuris", "kuri", "kurie", "kurios", "koks", "kokia", "kokie", "kokios"}
# an object right after kuria/kuriu makes it the verb kurti: kuriu tai, kas reikalinga
VERB_OBJECTS = {"tai", "tą", "viską", "jį", "ją", "juos", "jas"}
# a demonstrative followed by a kas-word starts a relative clause: tai, kas reikalinga
DEMONSTRATIVES = {"tai", "tas", "ta", "tą", "to", "viskas", "viską", "visko"}
KAS_FORMS = {"kas", "ką", "ko", "kam", "kuo"}
# accusative forms of kuris: knyga, kurią skaičiau
KURIS_ACC = ("kurį", "kurią", "kuriuos", "kurias")

# Parenthetical words, set off by commas: Deja, neatėjo. / Jis, beje, sutiko.
# (galbūt, turbūt, tikriausiai are not set off; atrodo, aišku, pagaliau are also plain words)
INTRO_ANYWHERE = {"deja", "beje", "pavyzdžiui"}
INTRO_START = INTRO_ANYWHERE | {"vadinasi", "žinoma"}
INTRO_PAIRS = {("kita", "vertus"), ("be", "abejo"), ("mano", "nuomone"), ("ko", "gero")}
# Greetings: a vocative or a new clause after them takes a comma (Labas, Jonai, kaip sekasi?)
GREETINGS = {"labas", "laba", "labi", "labos", "sveikas", "sveika", "sveiki", "sveikos", "ačiū",
             "dėkui", "labanakt", "sudie", "sveikinu"}
SUBJECT_PRONOUNS = {"aš", "tu", "jis", "ji", "mes", "jūs", "jie", "jos"}
# Between a subject pronoun and its verb (aš vakar buvo): not these
SUBJECT_NO_SKIP = {"tai", "tas", "ta", "šis", "ši", "tie", "tos", "ne", "nei", "ar", "jo", "jos", "jų"}
# a participial phrase does not run across these
PHRASE_STOP = {"ir", "bei", "ar", "arba", "o", "bet", "nei", "negu", "kaip"} | CLAUSE_STARTERS
SENTENCE_GAP = re.compile(r"[.!?…\n(„“\"«»–—-]")

COPULAS = {"būti", "buvo", "būna", "esa", "yra", "tapti", "tapo", "tampa", "likti", "liko", "lieka",
           "atrodyti", "atrodė", "atrodo", "vadintis", "vadinosi", "vadinasi", "gimti", "gimė",
           "gimsta", "mirti", "mirė", "miršta", "jaustis", "jautėsi", "jaučiasi", "pasidaryti",
           "pasidarė", "pasidaro", "pasirodyti", "pasirodė", "pasirodo", "dirbti", "dirbo", "dirba"}
# Linking verbs whose predicate adjective is nominative (tapo parapine, dirbo vienas: not these)
NOMINATIVE_COPULAS = {"būti", "buvo", "būna", "esa", "yra", "atrodyti", "atrodė", "atrodo", "likti", "liko",
                      "lieka", "jaustis", "jautėsi", "jaučiasi"}
# Participles of these verbs take a predicate instrumental, not an agreeing noun:
# tapusią vienuole, išrinktas prezidentu, vadinamas tėvu, laikomas didvyriu.
# Principal parts; matched by ending so prefixed entries (išrinkti) count too.
PREDICATIVE_VERBS = ("būti", "buvo", "būna", "esa", "tapti", "tapo", "tampa", "likti", "liko", "lieka",
                     "atrodyti", "atrodė", "atrodo", "vadinti", "vadino", "vadina", "vadintis",
                     "laikyti", "laikė", "laiko", "rinkti", "rinko", "renka", "skirti", "skyrė", "skiria",
                     "pažinti", "pažino", "pažįsta", "skelbti", "skelbė", "skelbia", "tituluoti",
                     "titulavo", "tituluoja", "dirbti", "dirbo", "dirba", "gimti", "gimė", "gimsta",
                     "mirti", "mirė", "miršta", "jaustis", "jautėsi", "jaučiasi", "rodyti", "rodė", "rodo")
COPULA_FORMS = {"nėra", "nesu", "nesi", "nesame", "nesate", "esu", "esi", "esame", "esate", "yra"}
# Subject pronoun -> person of the verb
SUBJECT_PERSON = {"aš": "1sg", "tu": "2sg", "mes": "1pl", "jūs": "2pl",
                  "jis": "3", "ji": "3", "jie": "3"}
PERSONS = {"1sg", "2sg", "3", "1pl", "2pl"}
# subject pronoun -> (number, gender) of its predicate adjective
PRONOUN_FEATURES = {"jis": ("sg", "m"), "ji": ("sg", "f"), "jie": ("pl", "m"), "jos": ("pl", "f")}
PERSON_NAMES = {"1sg": "1st person singular", "2sg": "2nd person singular", "3": "3rd person",
                "1pl": "1st person plural", "2pl": "2nd person plural"}


# valency: a phrase takes the case its verb takes this many times as often as the one it has, seen
# at least VALENCY_MIN times (eval/build_valency.py -> data/valency.tsv); after a 1st/2nd person verb,
# where the phrase can't be its subject, VALENCY_RATIO_12 times and VALENCY_MIN_12 (no false alarm in
# 1.7M words of Wikipedia and dialogue at any value tried)
VALENCY_RATIO = 30
VALENCY_RATIO_12 = 5
VALENCY_MIN = 20
VALENCY_MIN_12 = 10


def _load_valency():
    """(verb, class, after|before, case) -> count."""
    out = {}
    path = DATA / "valency.tsv"
    if path.exists():
        for line in path.read_text("utf-8").splitlines():
            *k, n = line.split("	")
            out[tuple(k)] = int(n)
    return out


def _load_pairs():
    """"PREV WORD" -> count, the language model's word pairs (data/bigrams.tsv, as in varnele.bin)."""
    out = {}
    path = DATA / "bigrams.tsv"
    if path.exists():
        for line in path.read_text("utf-8").splitlines():
            v, word, n, *_ = line.split("\t")
            if v and word:
                out[f"{v} {word}"] = int(n)
    return out


def has_diacritics(w):
    return any(c in "ąčęėįšųūžĄČĘĖĮŠŲŪŽ" for c in w)


def retag(tag, **change):
    """V.prs.3 + person=1sg -> V.prs.1sg; N.m.sg.acc + case=gen -> N.m.sg.gen"""
    parts = tag.split(".")
    for i, p in enumerate(parts):
        if "case" in change and p in CASE_NAMES:
            parts[i] = change["case"]
        if "person" in change and p in PERSONS:
            parts[i] = change["person"]
        if change.get("number") and p in ("sg", "pl"):
            parts[i] = change["number"]
        if change.get("gender") and p in ("m", "f"):
            parts[i] = change["gender"]
    return ".".join(parts)


def adds_diacritics(w, f):
    """f is w with diacritics added, none of w's own changed: ta -> tą, not kavinę -> kavine."""
    return len(w) == len(f) and all(a == b or b in "ąčęėįšųūž" and fold(b) == a for a, b in zip(w, f))


def finite(a):
    parts = a.tag.split(".")
    return parts[0] == "V" and len(parts) > 2 and parts[1] in FINITE and parts[2] in PERSONS


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
            if not forms and not self.known:
                # an unknown word with no diacritic-only reading: its typo corrections
                # (zodzou -> žodžiu, žodžių) let the context choose between them
                forms = self.g.suggestions_of(self.text)
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


def phrase_feats(words):
    """(case, number, gender) a phrase has as written: its noun's readings every modifier agrees with."""
    out = []
    for r in words[-1].own:
        f = (r.case, r.number, r.gender)
        if r.pos == "noun" and r.case != "voc" and f not in out and all(any(_agree(x, r) for x in t.own) for t in words[:-1]):
            out.append(f)
    return out


def _could_agree_own(w1, w2):
    """Do these two words agree as they are spelled?"""
    return any(_agree(a, b) for a in w1.own for b in w2.own)


def _agree(r1, r2):
    def same(a, b):
        return not a or not b or a == b
    return r1.case == r2.case and same(r1.number, r2.number) and same(r1.gender, r2.gender)


class Grammar:
    def __init__(self, analyzer, suggester=None):
        self.an = analyzer
        self.sg = suggester
        self._read, self._var, self._known, self._an, self._forms = {}, {}, {}, {}, {}
        self._sugg = {}
        self.lemma_freq = _load_freq("lemma_freq.tsv")
        self.freq = _load_freq("freq.tsv")
        self.valency = _load_valency()
        self._pairs = None

    def analyses(self, w):
        if w not in self._an:
            self._an[w] = self.an.analyze(w)
        return self._an[w]

    def inflect(self, analysis, tag):
        """Forms of the same word with another tag, keeping its prefix: laiką -> laiko."""
        if analysis.entry < 0:
            return []
        if analysis.entry not in self._forms:
            self._forms[analysis.entry] = self.an.index.entry_forms(analysis.entry)
        out = []
        for form, t in self._forms[analysis.entry]:
            f = analysis.prefix + form
            if t == tag and f not in out and self.an._analyze_exact(f):
                out.append(f)
        return out

    def reinflect(self, w, keep, **change):
        """All re-inflections of word w's readings that pass keep(tag)."""
        out = []
        for a in self.analyses(w.text):
            if keep(a.tag):
                for f in self.inflect(a, retag(a.tag, **change)):
                    f = w.cap(f)
                    if f not in out and f != w.text:
                        out.append(f)
        return out

    def mostly_verb(self, analyses):
        """Is the verb reading the likely one? metu (I throw / time), keli (you lift /
        several) and tik (fit! / only) are usually not verbs; mačiau is a verb even
        though the rare adjective matus has the same comparative form."""
        if any(a.tag == "W" for a in analyses):
            return False          # tik, beveik: listed particles/adverbs, not imperatives
        verb = other = 0
        # a prefix the rules added counts with the dictionary's own prefixed verb if there is one:
        # apsiuvu is ap+siuva only through apsiuva (never seen), not through siuva (common)
        for a in analyses:
            if len(a.prefix) > min(len(b.prefix) for b in analyses if (b.prefix + b.lemma).lower() == (a.prefix + a.lemma).lower()):
                continue
            f = self.lemma_freq.get(a.lemma.lower(), 0)
            if a.tag.startswith("V."):
                verb = max(verb, f)
            else:
                other = max(other, f, 1)
        return other == 0 or verb > other

    def mostly_particle(self, analyses):
        """A listed particle/adverb reading that is the frequent one: labai (very), not labas."""
        w = max((self.lemma_freq.get(a.lemma.lower(), 0) for a in analyses if a.tag == "W"), default=-1)
        return w > 0 and all(self.lemma_freq.get(a.lemma.lower(), 0) <= w for a in analyses)

    def active_participle(self, w):
        """Every reading is an active participle (or a gerund): stovintis, nukritusią."""
        an = self.analyses(w)
        return bool(an) and all(a.tag.startswith(("V.pap.", "V.pprs.", "V.ger.")) for a in an)

    def adverb(self, w):
        """Only adverb or particle readings: vakar, dar, tikrai (not tikras)."""
        an = self.analyses(w)
        return bool(an) and all(a.tag in ("W", "Adv") for a in an)

    def verb_keys(self, w):
        """(verb, class) of each verb reading of w, for valency: the principal part with its
        prefix, "!" first when negated (nemačiau takes a genitive), "~" last when reflexive;
        class "12" (1st/2nd person), "3", "inf" or "ger". None when w is mostly not a verb, a
        participle (it agrees with its noun) or a copula (būti takes a predicate)."""
        an = self.analyses(w)
        # not a participle: they agree with a noun, and the neuter ones (kuriama programa) are predicates
        vs = [a for a in an if a.tag.startswith("V.") and not (a.tag.split(".")[1][0] == "p" and a.tag.split(".")[1] not in FINITE)]
        if not vs or not self.mostly_verb(an) or w.lower() in COPULA_FORMS or any(a.lemma in COPULAS for a in vs):
            return None
        out = set()
        for a in vs:
            p = a.tag.split(".")
            m = re.match(r"nebe|tebe|ne|be|te", a.prefix)
            rest = a.prefix[m.end():] if m else a.prefix
            key = ("!" if m and m.group() in ("ne", "nebe") else "") + rest + a.lemma + ("~" if "refl" in p else "")
            cls = ("12" if p[2] != "3" else "3") if finite(a) else "inf" if p[1] == "inf" else "ger"
            out.add((key, cls))
        if any(c == "3" for _, c in out):
            out = {(k, c) for k, c in out if c != "12"}    # girdi: you hear or he hears; a subject may come
        return out

    def valency_verb(self, toks, adjacent, i):
        """(keys, first index) of the verb at i for valency: a verb (verb_keys), or the participle of a
        compound past after a finite būti (esu girdėjęs: girdėti, 1st person, from esu; nesu girdėjęs: negated).
        No keys: ([], i)."""
        t = toks[i]
        keys = self.verb_keys(t.text) if t.known else None
        if keys:
            return sorted(keys), i
        an = self.analyses(t.text)
        if not (i > 0 and adjacent[i] and an and all(a.tag.startswith("V.pap.") and "nom" in a.tag.split(".") for a in an)):
            return [], i
        aux = [a for a in self.analyses(toks[i - 1].text)
               if finite(a) and a.lemma in ("esa", "nesa", "yra", "nėra", "buvo", "būna", "būti")]
        if not aux:
            return [], i
        neg = any(a.lemma in ("nesa", "nėra") or a.prefix.startswith("ne") for a in aux)
        classes = {"3" if a.tag.split(".")[2] == "3" else "12" for a in aux}
        out = set()
        for a in an:
            m = re.match(r"nebe|tebe|ne|be|te", a.prefix)
            rest = a.prefix[m.end():] if m else a.prefix
            key = ("!" if neg else "") + rest + a.lemma + ("~" if "refl" in a.tag.split(".") else "")
            out |= {(key, c) for c in classes}
        return sorted(out), i - 1

    def valency_phrase(self, toks, adjacent, i, after, text):
        """Indices of the noun phrase right after (adverbs may come between) or right before the
        verb at i: modifiers and their noun. None when there is none, or it may belong to something
        else: a word before it in the clause (a preposition, a possessive), a noun or adjective after it
        (a genitive modifier: mato miesto namus, baigė Vilniaus pedagoginį institutą), or across a
        quote or number (baigė Kauno „Aušros“ gimnaziją), an adverb reading of a lone word (imasi kartu
        su: together)."""
        def cont(k):
            """the gap before token k holds something other than spaces and clause punctuation"""
            gap = text[toks[k - 1].end:toks[k].start].strip()
            return bool(gap) and not any(c in ",.;:!?()" for c in gap)
        def head(t):          # not the emphatic pronoun, listed as a noun: Pati mačiau (I saw it myself); not a
            # capitalised word read only as a name (Puikiai girdžiu: the village Puikiai, not "perfectly")
            return (any(r.pos == "noun" for r in t.own) and t.lower not in ("pats", "pati", "patys", "pačios")
                    and not (t.text[:1].isupper() and all(a.lemma[:1].isupper() for a in self.analyses(t.text))))

        def mod(t):
            return t.known and t.own and all(r.pos == "adj" for r in t.own)

        def skip(t):
            # an adverb, not a preposition (su, po), a connective or a quantity
            return (self.adverb(t.text) and t.lower not in PREPOSITIONS and t.lower != "po"
                    and t.lower not in CLAUSE_STARTERS and t.lower not in NO_COMMA_AFTER and not t.is_quantity())
        if after:
            k, skipped = i + 1, 0
            while k < len(toks) and adjacent[k] and skipped < 2 and skip(toks[k]):
                k, skipped = k + 1, skipped + 1
            start = k
            while k < len(toks) and adjacent[k] and toks[k].known and not head(toks[k]) and mod(toks[k]):
                k += 1
            if k >= len(toks) or not adjacent[k] or not toks[k].known or not head(toks[k]):
                return None
            if k + 1 < len(toks) and (cont(k + 1) or adjacent[k + 1] and (
                    head(toks[k + 1]) or mod(toks[k + 1]) or toks[k + 1].lower in ("ir", "bei", "arba")
                    or not toks[k + 1].known and not self.variants_of(toks[k + 1].lower))):
                return None   # baigė Vilniaus pedagoginį institutą: Vilniaus modifies what comes next; tapė tiršta
                              # akvarele ir aliejumi: the case of both; peržiūrėti komanda gcc: a name or term follows
                              # (an unknown word with no diacritic twin; orgazma is orgazmą typed without one)
            return self._valency_lone(toks, list(range(start, k + 1)))
        h = i - 1
        if h < 0 or not adjacent[i] or not toks[h].known or not head(toks[h]):
            return None
        k = h - 1
        while k >= 0 and adjacent[k + 1] and mod(toks[k]) and not head(toks[k]):
            k -= 1
        if k >= 0 and (cont(k + 1) or adjacent[k + 1] and toks[k].lower not in CLAUSE_STARTERS
                       and toks[k].lower not in ("ir", "bei", "arba")):
            return None       # it starts the clause (not: Su šia nuomone sutinka, savo didybe rodo, per dvi savaites privalo)
        return self._valency_lone(toks, list(range(k + 1, h + 1)))

    def _valency_lone(self, toks, idx):
        if len(idx) == 1 and any(a.tag in ("W", "Adv") for a in self.analyses(toks[idx[0]].text)):
            return None
        if any(a.lemma in TIME_LEMMAS or a.lemma in ("prasmė", "būdas", "metas") for a in self.analyses(toks[idx[-1]].text)):
            return None       # savaite anksčiau, plačiąja prasme, tuo metu: adverbials
        t = toks[idx[-1]]
        if len(idx) == 1 and any(r.case == "ins" for r in t.own) and not any(r.case in ("nom", "voc") for r in t.own):
            # an instrumental as frequent as its nominatives is an adverb: Sovietmečiu, Tarpukariu priklausė
            # (not pinigu: pinigai; not sesute, also "sister!")
            noms = [f for a in self.analyses(t.text) if a.tag.startswith("N.") and a.tag.endswith(".ins")
                    for num in ("sg", "pl") for f in self.inflect(a, retag(a.tag, case="nom", number=num))]
            if noms and self.freq.get(t.lower, 0) >= max(self.freq.get(f.lower(), 0) for f in noms):
                return None
        return idx

    def pair(self, a, b):
        """How often the corpus has word b right after word a (lowercase)."""
        if self._pairs is None:
            self._pairs = _load_pairs()
        return self._pairs.get(f"{a} {b}", 0)

    def known(self, w):
        if w not in self._known:
            self._known[w] = self.an.check(w).status != "unknown"
        return self._known[w]

    def readings_of(self, w):
        if w not in self._read:
            self._read[w] = readings(self.an.analyze(w))
        return self._read[w]

    def suggestions_of(self, w):
        """Typo corrections of an unknown word, lower case (candidates for context rules)."""
        if self.sg is None:
            return []
        if w not in self._sugg:
            self._sugg[w] = [s.lower() for s in self.sg.suggest(w)]
        return self._sugg[w]

    def ranked(self, w, forms):
        """Candidates of an unknown word that the context allows, in the suggester's order
        (frequency first): sienu before a noun -> sienų, not šienų (hay)."""
        order = self.suggestions_of(w)
        return sorted(forms, key=lambda f: order.index(f.lower()) if f.lower() in order else len(order))

    def variants_of(self, w):
        """Other real words spelled like w apart from diacritics."""
        if w not in self._var:
            # closest first: šita -> šitą before sytą (y is its own key)
            self._var[w] = sorted((f for f in self.an.folded_forms(fold(w))
                                   if f.lower() != w and self.an._analyze_exact(f)),
                                  key=lambda f: (_cost(w, f.lower()), f))
        return self._var[w]

    # ------------------------------------------------------------------
    def check(self, text):
        toks = [Word(self, m.group(), m.start(), m.end()) for m in WORD.finditer(text)]
        gaps = [text[toks[i - 1].end:t.start] if i else text[:t.start] for i, t in enumerate(toks)]
        adjacent = [i > 0 and g.strip() == "" for i, g in enumerate(gaps)]
        issues = {}

        def add(issue):
            issues.setdefault(issue.start, issue)

        def phrase(i, participles=False):
            """Adjectives/pronouns up to and including the first noun after i; participles
            end the phrase unless allowed (radau nukritusią sagutę)."""
            span, j = [], i + 1
            while j < len(toks) and adjacent[j]:
                w = toks[j]
                if span and w.lower in ("mano", "tavo", "savo", "mūsų", "jūsų") and j + 1 < len(toks) and adjacent[j + 1]:
                    j += 1
                    continue      # tą mano didelę kavinę (not jo: žino visas jo užnugaris yra ...)
                if span and not _could_agree(span[-1], w):
                    break         # už didžiausią | tuo metu: a new phrase starts
                if w.is_noun:
                    span.append(w)
                    break
                if not w.is_adj or (w.is_participle and not participles):
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
            variants = [(f, rs) for f, rs in w.variants if any(r.case in cases for r in rs)]
            if not variants:
                return
            # an unknown word's candidates: prefer those agreeing with the adjective before it
            # (nepataiso visų zodziou -> žodžių, not žodžio)
            i = next(k for k, t in enumerate(toks) if t.start == w.start)
            if not w.known and i > 0 and adjacent[i] and toks[i - 1].known and toks[i - 1].is_adj:
                prev = toks[i - 1]      # its diacritic variants too: visu (not fixed yet) -> visų
                ar = [r for r in prev.pos_readings() + [r for _, rs in prev.variants for r in rs] if r.pos == "adj"]
                variants.sort(key=lambda v: not any(_agree(x, y) for x in ar for y in v[1]
                                                    if y.pos == "noun" and y.case in cases))
            fixes = [w.cap(f) for f, _ in variants]
            if w.known and not w.own:
                return            # indeclinable word: nothing to check
            add(Issue(w.start, w.end, w.text, rule if w.known else "context", why, fixes))

        def starts_sentence(i):
            return i == 0 or bool(SENTENCE_GAP.search(gaps[i]))

        def verb_at(k):
            an_k = self.analyses(toks[k].text)
            return any(finite(a) for a in an_k) and self.mostly_verb(an_k)

        def verb_with_object(i):
            """kuria / kuriu as the verb kurti, not kuris: Įmonė kuria ir parduoda,
            (aš) kuriu tai, kas reikalinga."""
            if not any(finite(a) for a in self.analyses(toks[i].text)) or i + 1 >= len(toks) or not adjacent[i + 1]:
                return False
            nx = toks[i + 1]
            if nx.lower in VERB_OBJECTS or (i > 0 and adjacent[i] and toks[i - 1].lower in KURIS):
                return True       # kuri kuria, kurie kuria: the relative pronoun is the one before
            if nx.known and nx.own and all(r.pos == "noun" and r.case == "acc" for r in nx.own):
                return True       # kuria baldus
            # kuria ir parduoda; at the end of the text wait for the next word (the keyboard types on)
            return nx.lower in ("ir", "bei", "arba") and (i + 2 == len(toks) or adjacent[i + 2] and verb_at(i + 2))

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
                    # a genitive that can't be the object modifies a head after it: į teisės mokykla -> mokyklą
                    # (a typed preposition, not the numeral in "I pasaulinio karo metu"; not "į NATO diena")
                    k = i + len(span)
                    while (prep == w.lower and "gen" not in cases and k + 1 < len(toks) and adjacent[k + 1]
                           and toks[k].known and any(r.case == "gen" for r in toks[k].own)
                           and not any(r.case in cases for r in toks[k].own)
                           and not toks[k].text.isupper() and toks[k + 1].is_noun):
                        k += 1
                    span = phrase(k - 1) if k > i + len(span) else []
                    if span and span[-1].is_noun:
                        for x in span:
                            require(x, cases, "case", f"'{prep}' takes the {want}")
            # 2b. numbers: 10 metu -> metų
            # (a noun right after the number: not units "20 m atstumu", manner "12 etniniu pagrindu",
            # labels "KNM-ER 1813 atveju")
            m = GEN_NUMBER.search(gaps[i])
            if (m and int(m.group(1)) > 0 and (int(m.group(1)) % 10 == 0 or 11 <= int(m.group(1)) % 100 <= 19)
                    and w.known and w.is_noun and len(w.lower) >= 3 and w.text[:1].islower()
                    and not (i > 0 and len(toks[i - 1].text) > 1 and toks[i - 1].text.isupper())):
                require(w, {"gen"}, "quantity", f"after '{m.group(1)}' use the genitive plural")
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
                        or (w.lower == "nors" and (fold(prev) in INTERROGATIVES_FOLDED or nxt == "ir"))  # kas nors, koki nors
                        or (w.lower in KURIS and (prev in ("bet", "kai")      # bet kuris
                                                  or verb_with_object(i)            # įmonė kuria ir parduoda
                                                  or nxt in ("nors", "laikui", "laiką", "laiko"))))
                if not skip:
                    add(Issue(w.start, w.end, w.text, "comma",
                              f"comma needed before '{w.text}'", [", " + w.text]))
                elif (prev in ("net", "ypač") and i >= 2 and adjacent[i - 1]   # veikia, net jeigu ...
                      and toks[i - 2].lower not in NO_COMMA_AFTER and toks[i - 2].lower not in PREPOSITIONS
                      and not w.text[:1].isupper() and not toks[i - 1].text[:1].isupper()):
                    p = toks[i - 1]
                    add(Issue(p.start, p.end, p.text, "comma",
                              f"comma needed before '{p.text} {w.text}'", [", " + p.text]))
            # comma before a preposition that introduces a relative clause: ..., su kuriuo
            if (i > 0 and w.lower in PREPOSITIONS and adjacent[i] and nxt_adjacent
                    and toks[i + 1].lower in KURIS and toks[i - 1].lower not in NO_COMMA_AFTER):
                add(Issue(w.start, w.end, w.text, "comma",
                          f"comma needed before '{w.text} {toks[i + 1].text}'", [", " + w.text]))

        # a preposition that lost its diacritic and became a verb: kabo virs stalo -> virš
        # (only when the clause has another verb: mama virs sriubos = will boil)
        for i, w in enumerate(toks):
            prep = PREP_BY_FOLD.get(fold(w.lower))
            if not prep or prep == w.lower or not w.known or i + 1 >= len(toks) or not adjacent[i + 1]:
                continue
            span = phrase(i)
            if not span or not span[-1].is_noun or not all(x.known and any(x.can_be(c) for c in PREPOSITIONS[prep])
                                                            for x in span):
                continue
            j = i
            while j > 0 and not starts_sentence(j):
                j -= 1
            if any(verb_at(k) for k in range(j, i)):
                add(Issue(w.start, w.end, w.text, "case", f"'{w.text}' before '{span[-1].text}' is the preposition '{prep}'",
                          [w.cap(prep)]))

        # indefinite pronoun typed without diacritics: koki nors -> kokį nors, ka nors -> ką nors
        for i in range(len(toks) - 1):
            w = toks[i]
            if toks[i + 1].lower != "nors" or not adjacent[i + 1] or w.lower in INTERROGATIVES:
                continue
            fix = [w.cap(f) for f, _ in w.variants if f.lower() in INTERROGATIVES]
            if fix:
                add(Issue(w.start, w.end, w.text, "case" if w.known else "context",
                          f"'{w.text} nors': an indefinite pronoun", fix))

        # 6. relative pronoun typed without diacritics: žodžių kuriu aš rašau -> kurių
        for i in range(1, len(toks)):
            w, prev = toks[i], toks[i - 1]
            if w.lower in KURIS_ACC or not (adjacent[i] or gaps[i].strip() == ",") or not prev.is_noun:
                continue
            fw = fold(w.lower)
            nouns = [r for r in prev.pos_readings() if r.pos == "noun"]

            def agrees(feats):
                # kuris agrees with its noun in number and gender (not case)
                return any((r.number is None or r.number == num) and (g is None or r.gender is None or r.gender == g)
                           for r in nouns for num, g in feats)
            if w.lower in KURIS:
                # its case comes from the verb of the clause: knyga kuria skaičiau -> kurią
                cands = [k for k in KURIS_ACC if fold(k) == fw and agrees(KURIS_FEATURES[k])]
                j = i + 1
                while j < len(toks) and j <= i + 2 and adjacent[j] and not toks[j].lower in PHRASE_STOP:
                    an_j = self.analyses(toks[j].text)
                    # (skaičiau is a verb here although the noun skaičius is more frequent)
                    if any(finite(a) and a.lemma.endswith(TRANSITIVE_VERBS) and not a.prefix.startswith("ne")
                           and not a.tag.endswith(".refl") for a in an_j):
                        break
                    if any(finite(a) for a in an_j) and self.mostly_verb(an_j):
                        cands = []
                        break
                    j += 1
                else:
                    cands = []
                if cands:
                    add(Issue(w.start, w.end, w.text, "relative",
                              f"'{toks[j].text}' takes an accusative object", [w.cap(c) for c in cands]))
                continue
            cands = [k for k, feats in KURIS_FEATURES.items() if fold(k) == fw and agrees(feats)]
            if not cands or verb_with_object(i):
                continue
            # the relative clause needs a verb of its own, otherwise "kuriu" may be the
            # verb itself: "dainas kuriu pats" (I write songs myself)
            j, verb_follows = i + 1, False
            while j < len(toks) and j <= i + 5 and adjacent[j]:
                an_j = self.analyses(toks[j].text)
                if any(finite(a) for a in an_j) and self.mostly_verb(an_j):
                    verb_follows = True
                    break
                j += 1
            if verb_follows:
                add(Issue(w.start, w.end, w.text, "relative",
                          f"relative pronoun after '{prev.text}'", [w.cap(c) for c in cands]))

        # 7. comma before an indirect question after a verb of seeing, knowing or saying:
        #    matau, ką man rašo / nežinau, kur jis gyvena (not: ką nors, ką tik)
        for i in range(1, len(toks)):
            w, prev = toks[i], toks[i - 1]
            if w.lower not in INTERROGATIVES or not adjacent[i] or w.text[:1].isupper():
                continue
            nxt = toks[i + 1].lower if i + 1 < len(toks) and adjacent[i + 1] else ""
            if nxt in ("nors", "tik", "ne"):
                continue
            # a relative clause after a demonstrative: kuriu tai, kas reikalinga / viską, ką turiu
            # ("Tai kas dabar?" at the start of a sentence is a question)
            if (w.lower in KAS_FORMS and prev.lower in DEMONSTRATIVES and nxt
                    and not (prev.lower == "tai" and (i < 2 or not adjacent[i - 1]))
                    and not (i >= 2 and adjacent[i - 1] and toks[i - 2].lower in PREPOSITIONS)):
                add(Issue(w.start, w.end, w.text, "comma", f"comma needed before '{w.text}' after '{prev.text}'",
                          [", " + w.text]))
                continue
            pa = self.analyses(prev.text)
            if not (any(finite(a) and a.lemma.endswith(QUESTION_VERBS) for a in pa) and self.mostly_verb(pa)):
                continue
            j, verb_follows = i + 1, False       # the question needs a verb of its own
            while j < len(toks) and j <= i + 5 and adjacent[j]:
                an_j = self.analyses(toks[j].text)
                if any(finite(a) for a in an_j) and self.mostly_verb(an_j):
                    verb_follows = True
                    break
                j += 1
            if verb_follows:
                add(Issue(w.start, w.end, w.text, "comma", f"comma needed before '{w.text}'", [", " + w.text]))

        # 8. more commas: parenthetical words, greetings and address, repeated connectives,
        #    participial phrases
        def comma_before(k, why):
            if k < len(toks) and adjacent[k]:
                t = toks[k]
                add(Issue(t.start, t.end, t.text, "comma", why, [", " + t.text]))

        def connective(t):
            return t.lower in NO_COMMA_AFTER or t.lower in CLAUSE_STARTERS or t.lower in PREPOSITIONS

        for i, w in enumerate(toks):
            nxt_adjacent = i + 1 < len(toks) and adjacent[i + 1]
            # Deja, neatėjo. / Kita vertus, ... / Jis, beje, sutiko.
            if starts_sentence(i) and nxt_adjacent:
                pair = i + 2 < len(toks) and adjacent[i + 2] and (w.lower, toks[i + 1].lower) in INTRO_PAIRS
                if pair:
                    comma_before(i + 2, f"comma needed after '{w.text} {toks[i + 1].text}'")
                elif w.lower in INTRO_START and not toks[i + 1].text[:1].isupper():
                    nx = toks[i + 1]
                    # žinoma = "it is known" (Žinoma tik viena rūšis): only before a subject or verb
                    if w.lower != "žinoma" or nx.lower in SUBJECT_PRONOUNS or verb_at(i + 1):
                        comma_before(i + 1, f"comma needed after '{w.text}'")
            elif (w.lower in INTRO_ANYWHERE and not w.text[:1].isupper() and adjacent[i]
                  and not connective(toks[i - 1])):
                comma_before(i, f"'{w.text}' is set off by commas")
                if nxt_adjacent:
                    comma_before(i + 1, f"'{w.text}' is set off by commas")
            # Labas, Jonai, kaip sekasi? / Ačiū, drauge.
            # (the gap may already hold the first comma: Labas, Jonai kaip ...)
            if (starts_sentence(i) and w.lower in GREETINGS and i + 1 < len(toks)
                    and (adjacent[i + 1] or gaps[i + 1].strip() == ",")):
                nx = toks[i + 1]
                vocative = (nx.known and any(r.case == "voc" for r in nx.own)
                            and not any(_agree(a, b) for a in self.readings_of(w.lower) if a.pos == "adj" for b in nx.own))
                if vocative:
                    comma_before(i + 1, f"the address '{nx.text}' is set off by commas")
                    if i + 2 < len(toks) and adjacent[i + 2] and not any(r.case == "voc" for r in toks[i + 2].own):
                        comma_before(i + 2, f"the address '{nx.text}' is set off by commas")
                elif nx.lower in SUBJECT_PRONOUNS or nx.lower in INTERROGATIVES:
                    comma_before(i + 1, f"comma needed after '{w.text}'")
            # comparison with a clause: geriau, negu tikėjausi
            if w.lower == "negu" and i > 0 and adjacent[i] and not connective(toks[i - 1]):
                j = i + 1
                while j < len(toks) and j <= i + 3 and adjacent[j] and not verb_at(j):
                    j += 1
                if j < len(toks) and j <= i + 3 and adjacent[j] and verb_at(j):
                    comma_before(i, f"comma needed before '{w.text}' + clause")
            # repeated connectives: nei Jonas, nei Petras / arba tu, arba aš / ar ateisi, ar ne
            # ("ar" = "or" in a sentence: only the question particle at the start counts)
            if w.lower in ("nei", "arba", "ar") and (starts_sentence(i) or w.lower != "ar" and gaps[i].strip() == ","):
                j = i + 1
                while j < len(toks) and j <= i + 6 and adjacent[j] and toks[j].lower != w.lower:
                    j += 1
                if j < len(toks) and j <= i + 6 and adjacent[j] and j > i + 1 and not connective(toks[j - 1]):
                    comma_before(j, f"repeated '{w.text}': comma before the second one")
            # participial phrase after its noun: Žmogus, stovintis prie lango, žiūri
            if (i > 0 and adjacent[i] and nxt_adjacent and toks[i - 1].known
                    and not toks[i + 1].lower in PHRASE_STOP and self.active_participle(w.text)):
                nr = [r for r in toks[i - 1].own if r.pos == "noun"]
                # a nominative past participle is mostly a predicate: Pavadinimas kilęs iš ..., Miestas įsikūręs
                pr = [r for r in w.own if r.pos == "adj"
                      and not (r.case == "nom" and any(a.tag.startswith("V.pap.") for a in self.analyses(w.text)))]
                agreeing = [b for b in nr if any(_agree(a, b) for a in pr)]
                later = any((toks[k].text[:1].isupper() or any(_agree(a, b) for a in pr for b in toks[k].own
                                                              if b.pos == "noun"))
                            for k in range(i + 1, min(i + 4, len(toks))) if adjacent[k])
                # nominative: a predicate unless the sentence has a verb of its own (Laumės mėgstančios ...)
                j = i
                while j > 0 and not starts_sentence(j):
                    j -= 1
                sentence_verb = any(verb_at(k) for k in range(j, min(i + 8, len(toks))) if k != i
                                    and (k < i or all(adjacent[m] for m in range(i + 1, k + 1))))
                if (agreeing and not later                       # žygiavusia Aleksandro kariauna: attribute of the later noun
                        and any(b.case != "gen" for b in agreeing)  # upės buvusios ...: genitive chains are ambiguous
                        and (sentence_verb or all(b.case != "nom" for b in agreeing))):
                    comma_before(i, f"the phrase '{w.text} …' is set off by commas")
                    j = i + 1
                    while j < len(toks) and j <= i + 6 and adjacent[j] and toks[j].lower not in PHRASE_STOP:
                        if verb_at(j):
                            comma_before(j, f"the phrase '{w.text} …' is set off by commas")
                            break
                        j += 1
            # list: obuoliai, kriaušės ir slyvos
            if (i > 0 and adjacent[i] and i + 2 < len(toks) and adjacent[i + 1] and adjacent[i + 2]
                    and toks[i + 1].lower in ("ir", "bei", "arba") and toks[i - 1].lower != w.lower):
                three = [toks[i - 1], w, toks[i + 2]]
                if i >= 2 and adjacent[i - 1] and toks[i - 2].is_adj:
                    three = []        # tomis pačiomis spalvomis ir ...: a modifier may cover more than one word
                # no genitive readings at all: bangos amplitudės ir fazės = "the wave's amplitude and phase"
                if three and all(t.known and t.text[:1].islower() and t.own
                       and all(r.pos == "noun" and r.case != "gen" for r in t.own) for t in three):
                    shared = set.intersection(*({(r.case, r.number) for r in t.own} for t in three))
                    if any(a.lemma in TIME_LEMMAS for t in three for a in self.analyses(t.text)):
                        shared = set()   # pavasarį gegužę ir birželį
                    if shared:
                        comma_before(i, f"comma between list items '{toks[i - 1].text}' and '{w.text}'")

        def between(k):
            """An adverb that may stand between a verb and its object or subject: vakar, labai."""
            t = toks[k]
            return ((self.adverb(t.text) or self.mostly_particle(self.analyses(t.text)))
                    and t.lower not in SUBJECT_NO_SKIP and t.lower not in SUBJECT_PERSON
                    and t.lower not in NO_COMMA_AFTER and t.lower not in CLAUSE_STARTERS
                    and t.lower not in PREPOSITIONS and t.lower not in INTERROGATIVES and not t.is_quantity())

        def subject_before(i):
            """The verb at i has its subject in front of it: jis (vakar) nupirko, mano mama skaito."""
            k = i - 1
            while k >= 0 and adjacent[k + 1] and between(k):
                k -= 1
            if k < 0 or not adjacent[k + 1]:
                return False
            t = toks[k]
            if t.lower in ("jis", "ji", "jie"):
                return k == 0 or toks[k - 1].lower not in ("ir", "bei", "arba", "ar", "nei") or not adjacent[k]
            # a noun that can only be the subject (not Knygą skaito mama, not kas/ką); by its most
            # frequent lemma (Jonas, not the accusative plural of Jona); mama is also instrumental
            nouns = [a for a in self.analyses(t.text) if a.tag.startswith("N.")]
            top = max((self.lemma_freq.get(a.lemma.lower(), 0) for a in nouns), default=0)
            cases = {a.tag.split(".")[-1] for a in nouns if self.lemma_freq.get(a.lemma.lower(), 0) == top}
            return (t.known and t.is_noun and cases <= {"nom", "voc", "ins"} and "nom" in cases
                    and t.lower not in INTERROGATIVES and t.lower not in CLAUSE_WORDS
                    and not (k > 0 and adjacent[k] and toks[k - 1].lower in ("ir", "bei", "arba", "ar", "nei")))

        # 5. verbs: negation + genitive, subject-verb agreement, objects of 1st/2nd person
        for i, w in enumerate(toks):
            if i + 1 >= len(toks) or not adjacent[i + 1]:
                continue
            alls = self.analyses(w.text)
            verbs = [a for a in alls if finite(a) or a.tag == "V.inf"]
            if not verbs or not self.mostly_verb(alls):
                continue
            if any(r.pos == "adj" for r in w.own) and _could_agree(w, toks[i + 1]):
                continue          # Atskiri ruožai: an adjective agreeing with its noun, not "you separate"
            lemmas = {a.lemma for a in verbs} | {w.lower}
            copula = bool(lemmas & COPULAS) or w.lower in COPULA_FORMS
            nxt = toks[i + 1]
            negated = any(a.prefix.startswith("ne") for a in verbs)

            if negated and not copula:
                if nxt.lower in NEG_PRONOUNS:
                    add(Issue(nxt.start, nxt.end, nxt.text, "negation",
                              f"after the negated verb '{w.text}' use the genitive",
                              [nxt.cap(NEG_PRONOUNS[nxt.lower])]))
                    continue
                span = phrase(i)
                timey = any(x.lower in TIME_WORDS or x.is_quantity() or any(
                            a.lemma in TIME_LEMMAS for a in self.analyses(x.text)) for x in span)
                # an adverb reading is not an object: neatėjo laiku (on time), not laikų
                adverbial = len(span) == 1 and any(a.tag in ("W", "Adv") for a in self.analyses(span[0].text))
                if span and span[-1].is_noun and not timey and not adverbial:
                    for x in span:
                        cases = {r.case for r in x.own}
                        why = f"after the negated verb '{w.text}' use the genitive"
                        if cases and cases <= {"acc"}:          # unambiguously accusative
                            fix = self.reinflect(x, lambda t: t.endswith(".acc"), case="gen")
                            if fix:
                                add(Issue(x.start, x.end, x.text, "negation", why, fix))
                                continue
                        require(x, {"gen"}, "negation", why)  # nepataiso visu žodžių -> visų
                    continue

            # verbs with a genitive object: lauksiu tavo zinutes -> žinutės, reikia pagalbą -> pagalbos
            if not negated and any(any(a.lemma == v or a.lemma.endswith(v) and a.lemma[:-len(v)] in VERB_PREFIXES
                                       for v in GENITIVE_VERBS) for a in verbs):
                k = i       # possessives stand before the noun: laukiu tavo žinutės
                while k + 1 < len(toks) and adjacent[k + 1] and toks[k + 1].lower in POSSESSIVES:
                    k += 1
                span = phrase(k)
                timey = any(x.lower in TIME_WORDS or x.is_quantity() or any(
                            a.lemma in TIME_LEMMAS for a in self.analyses(x.text)) for x in span)
                if span and span[-1].is_noun and not timey:
                    for x in span:
                        require(x, {"gen"}, "case", f"'{w.text}' takes the genitive")
                continue

            persons = {a.tag.split(".")[2] for a in verbs if finite(a)}
            transitive = any(a.lemma.endswith(TRANSITIVE_VERBS) for a in verbs)
            # a real prefix, not reflexive: pamato, nupirko (not atsirado = atsi+rado)
            plain_transitive = any(any(a.lemma == v or a.lemma.endswith(v) and a.lemma[:-len(v)] in VERB_PREFIXES
                                       for v in TRANSITIVE_VERBS) and "si" not in a.prefix for a in verbs)
            # objects after a 1st/2nd person verb can't be its subject: matau namas -> namą;
            # nor after a 3rd person transitive verb whose subject came before it: Jonas mato namas
            if (persons and (persons <= {"1sg", "2sg", "1pl", "2pl"} or plain_transitive and subject_before(i))
                    and not copula and not negated and not any(a.tag.endswith(".refl") for a in verbs)):
                k = i     # dar, jau and adverbs may stand between: mačiau labai gražų namą
                while k + 1 < len(toks) and adjacent[k + 1] and (toks[k + 1].lower in OBJECT_SKIP or between(k + 1)):
                    k += 1
                span = phrase(k, participles=transitive)
                if any(any(a.tag == "V.inf" for a in self.analyses(x.text)) for x in span) or (
                        len(span) == 1 and any(a.tag in ("W", "Adv") for a in self.analyses(span[0].text))):
                    span = []     # turėtų būti suprantama, sutiko baigti; atsirado kartu (together)
                allowed = {"nom", "voc", "ins"} if transitive else {"nom", "voc"}
                # the whole phrase instrumental (radau nukritusia sagute), not tapusią vienuole; or
                # only the modifiers, once the noun is fixed (radau nukritusia sagutę)
                ins_phrase = transitive and all(any(r.case == "ins" for r in t.own) for t in span)
                head_acc = transitive and bool(span) and any(r.case == "acc" for r in span[-1].own)
                if span and span[-1].is_noun and span[0].lower not in CLAUSE_WORDS:
                    hn = [r for r in span[-1].own if r.pos == "noun"]
                    for x in span:
                        if x is not span[-1] and hn and not any(
                                (not r.number or not h.number or r.number == h.number)
                                and (not r.gender or not h.gender or r.gender == h.gender) for r in x.own for h in hn):
                            continue      # mačiau dideli namą: the number is wrong, not the case (didelį, not didelius)
                        cases = {r.case for r in x.own}
                        fix = []
                        if cases and cases <= allowed and cases & {"nom", "voc"}:
                            fix = self.reinflect(x, lambda t: t.endswith((".nom", ".voc")) and ".voc" not in t,
                                                 case="acc")
                        if not fix and (ins_phrase or head_acc and x is not span[-1]) and cases <= {"ins", "voc"}:
                            # radau nukritusia sagute -> nukritusią sagutę (the accusative lost its diacritic);
                            # same part of speech, number and gender (tuo metu is not metų)
                            own = [r for r in x.own if r.case == "ins"]
                            fix = [x.cap(f) for f, rs in x.variants
                                   if any(r.case == "acc" and r.pos == o.pos and r.number == o.number
                                          and r.gender == o.gender for r in rs for o in own)]
                        if fix:
                            add(Issue(x.start, x.end, x.text, "object",
                                      f"the object of '{w.text}' takes the accusative", fix))

        # an unknown word after a verb (both may be typed without diacritics): its accusative
        # candidates first (iskele salyga -> sąlygą); it only reorders suggestions
        def cand_analyses(t):
            return self.analyses(t.text) if t.known else [a for f, _ in t.variants for a in self.analyses(f)]

        for i, w in enumerate(toks):
            if i + 1 >= len(toks) or not adjacent[i + 1]:
                continue
            alls = cand_analyses(w)
            verbs = [a for a in alls if finite(a)]
            if not verbs or not self.mostly_verb(alls) or (any(r.pos == "adj" for r in w.pos_readings())
                                                          and _could_agree(w, toks[i + 1])):
                continue
            if (any(a.lemma in COPULAS for a in verbs) or w.lower in COPULA_FORMS
                    or any(a.prefix.startswith("ne") or a.tag.endswith(".refl") for a in verbs)
                    or not any(a.lemma.endswith(TRANSITIVE_VERBS) for a in verbs)):
                continue
            k = i
            while k + 1 < len(toks) and adjacent[k + 1] and (toks[k + 1].lower in OBJECT_SKIP or between(k + 1)):
                k += 1
            span = phrase(k, participles=True)
            if (not span or not span[-1].is_noun or span[0].lower in CLAUSE_WORDS
                    or any(any(a.tag == "V.inf" or finite(a) for a in cand_analyses(x)) for x in span)):
                continue          # turi buti (būti, not būtį)
            for x in span:
                acc = [x.cap(f) for f, rs in x.variants if any(r.case == "acc" for r in rs)]
                if not x.known and acc and len(acc) < len(x.variants):
                    add(Issue(x.start, x.end, x.text, "context", f"the object of '{w.text}' takes the accusative",
                                self.ranked(x.text, acc)))

        # subject pronoun + verb: aš buvo -> buvau
        for i in range(len(toks) - 1):
            pron = toks[i]
            want = SUBJECT_PERSON.get(pron.lower)
            if not want or not adjacent[i + 1] or (i > 0 and toks[i - 1].lower in ("ir", "bei", "arba", "ar", "nei")):
                continue          # aš ir jis buvome: a coordinated subject
            # adverbs and particles may stand between: aš vakar buvo -> buvau
            k = i + 1
            while (k + 1 < len(toks) and k <= i + 2 and adjacent[k + 1] and self.adverb(toks[k].text)
                   and toks[k].lower not in SUBJECT_NO_SKIP and toks[k].lower not in SUBJECT_PERSON
                   and toks[k].lower not in NO_COMMA_AFTER and toks[k].lower not in CLAUSE_STARTERS
                   and toks[k].lower not in PREPOSITIONS and toks[k].lower not in INTERROGATIVES):
                k += 1
            v = toks[k]
            if v.start in issues:
                continue
            if not v.known:
                # an unknown word: candidates that are verbs of that person first
                # (jis ziuri -> žiūri "looks", not žiuri "jury")
                fix = [v.cap(f) for f, _ in v.variants
                       if any(finite(a) and a.tag.split(".")[2] == want for a in self.analyses(f))]
                if fix:
                    add(Issue(v.start, v.end, v.text, "context",
                              f"'{pron.text}' needs the {PERSON_NAMES[want]} form of the verb", fix))
                continue
            fin = [a for a in self.analyses(v.text) if finite(a)]
            if not fin or any(a.tag.split(".")[2] == want for a in fin):
                continue
            fix = []
            for a in fin:
                for f in self.inflect(a, retag(a.tag, person=want)):
                    if v.cap(f) not in fix:
                        fix.append(v.cap(f))
            if fix:
                add(Issue(v.start, v.end, v.text, "subject",
                          f"'{pron.text}' needs the {PERSON_NAMES[want]} form of the verb", fix))

        # predicate adjective: ji nedidele -> nedidelė, mergaitė buvo nedidele -> nedidelė
        def is_copula(t):
            return t.lower in COPULA_FORMS or any(a.lemma in NOMINATIVE_COPULAS for a in self.analyses(t.text)
                                                  if a.tag.startswith("V."))

        def fits(r, feats):
            return r.pos == "adj" and r.case == "nom" and any(
                (r.number is None or r.number == num) and (r.gender is None or r.gender == gen) for num, gen in feats)

        for i in range(len(toks) - 1):
            sub = toks[i]
            if not adjacent[i + 1] or (i > 0 and adjacent[i] and toks[i - 1].lower in ("ir", "bei", "arba", "ar", "nei")):
                continue
            if sub.lower in PRONOUN_FEATURES:
                feats = {PRONOUN_FEATURES[sub.lower]}
            elif sub.known and sub.is_noun and not sub.text[:1].isupper() or starts_sentence(i) and sub.known and sub.is_noun:
                nouns = [a for a in self.analyses(sub.text) if a.tag.startswith("N.")]
                top = max((self.lemma_freq.get(a.lemma.lower(), 0) for a in nouns), default=0)
                best = readings([a for a in nouns if self.lemma_freq.get(a.lemma.lower(), 0) == top])
                if not best or not {r.case for r in best} <= {"nom", "voc", "ins"} or not any(r.case == "nom" for r in best):
                    continue
                feats = {(r.number, r.gender) for r in best if r.case == "nom"}
            else:
                continue
            k = i + 1
            while k + 1 < len(toks) and k <= i + 3 and adjacent[k + 1] and between(k) and not is_copula(toks[k]):
                k += 1
            copula = is_copula(toks[k])
            if copula:
                k += 1
                while k + 1 < len(toks) and k <= i + 5 and adjacent[k] and adjacent[k + 1] and between(k):
                    k += 1
            elif sub.lower not in ("jis", "ji", "jie"):
                continue          # a noun needs the copula: jos (her) gražios suknelės
            if k >= len(toks) or not adjacent[k] or k <= i:
                continue
            a = toks[k]
            end = k + 1 == len(toks) or not adjacent[k + 1] or toks[k + 1].lower in PHRASE_STOP
            if not end or not a.is_adj or a.is_participle or a.start in issues:
                continue
            if a.known and any(fits(r, feats) for r in a.own):
                continue
            fix = [a.cap(f) for f, rs in a.variants if any(fits(r, feats) for r in rs)]
            if a.known and not a.own:
                continue
            if fix:
                add(Issue(a.start, a.end, a.text, "agreement" if a.known else "context",
                          f"'{sub.text} … {a.text}': the predicate adjective agrees with the subject", fix))

        # 2a. agreement across a phrase of 2+ modifiers and its noun: the case, number and gender
        #     that cost the fewest changes win (viena nukritusią sagutė -> nukritusi, ta mano didele
        #     kavinę -> tą, didelę). Adding a lost diacritic costs 1, re-inflecting a modifier 2; a typed
        #     diacritic never changes and the noun is never re-inflected.
        def modifier(k):
            """Not an adverb (paprastai, dažniausiai), a neuter pronoun (tai, tam tikras) or a preposition."""
            t = toks[k]
            return (t.known and t.own and t.is_adj and not t.can_be_verb and t.lower not in POSSESSIVES
                    and t.lower not in KURIS and t.lower not in INTERROGATIVES and t.lower not in PREPOSITIONS
                    and t.lower not in ("tai", "tam", "to", "tuo")
                    and not any(a.tag == "W" or a.tag.startswith(("Adv", "Num")) for a in self.analyses(t.text))
                    and (t.text[:1].islower() or starts_sentence(k)))

        def fits(r, feats, pos):
            return (r.pos == pos and r.case == feats[0] and (not r.number or not feats[1] or r.number == feats[1])
                    and (not r.gender or not feats[2] or r.gender == feats[2]))

        def phrase_fix(t, feats, head):
            """(cost, fixes) of giving t these features."""
            pos = "noun" if head else "adj"
            if any(fits(r, feats, pos) for r in t.own):
                return 0, []
            dia = [t.cap(f) for f, rs in t.variants if any(fits(r, feats, pos) for r in rs)]
            added = [f for f in dia if adds_diacritics(t.lower, f.lower())]
            if added:
                return 1, added
            if not head:
                out = []
                for a in self.analyses(t.text):
                    if a.tag.split(".")[0] in ("A", "P", "Num") or a.tag.startswith("V.p"):
                        for f in self.inflect(a, retag(a.tag, case=feats[0], number=feats[1], gender=feats[2])):
                            f = t.cap(f)
                            if f not in out and f.lower() != t.lower and any(fits(r, feats, pos) for r in self.readings_of(f)):
                                out.append(f)
                if out:
                    return 2, out
            return 99, []        # a typed diacritic never changes: kavinę, pailga lėkštašlaitė neryškia papėde

        settled = set()
        for h in range(len(toks)):
            head = toks[h]
            if not head.known or not any(r.pos == "noun" for r in head.own):
                continue
            mods, coord, k = [], None, h - 1
            while k >= 0 and adjacent[k + 1]:
                if (modifier(k) and mods and toks[k].is_participle and not _could_agree_own(toks[k], toks[mods[-1]])
                        and not _could_agree_own(toks[k], head)):
                    break         # a participle with its object: įrengtas | modernų baseiną (publikuotame genetinis tyrime: no)
                if modifier(k):
                    mods.append(k)
                elif toks[k].lower in POSSESSIVES and k > 0 and adjacent[k] and modifier(k - 1):
                    pass          # ta mano didelę kavinę
                elif toks[k].lower in ("ir", "bei") and mods and coord is None and k > 0 and adjacent[k] and modifier(k - 1):
                    coord = k     # didelę ir gražią kavinę
                else:
                    break
                k -= 1
            if len(mods) < 2:
                continue
            idx = sorted(mods) + [h]
            words = [toks[j] for j in idx]
            if any(t.start in issues for t in words):
                continue          # an earlier rule knows the case: mačiau didele graži kavinę
            if head.can_be("gen") and h + 1 == len(toks) and not text[head.end:].strip():
                continue          # it may be a modifier of a noun still to come: apgultos užbaigta taikos | sutartimi
            if (head.can_be("gen") and h + 1 < len(toks) and adjacent[h + 1] and toks[h + 1].is_noun
                    or any(t.lower in ("vienas", "viena", "vieni", "vienos") for t in words)
                    and any(t.lower.startswith("kit") for t in words)):
                continue          # tos gražios mergaitės batai; vienas kitam simbolis
            if (any(r.pos == "adj" for r in head.own) and h + 1 < len(toks) and adjacent[h + 1]
                    and any(r.pos in ("adj", "noun") for r in toks[h + 1].own)):
                continue          # an adjective that is also a noun, before more: pirmasis mūrinis pastatas
            last = toks[max(mods)]
            if any(t.is_participle and any(a.lemma.endswith(PREDICATIVE_VERBS) for a in self.analyses(t.text))
                   for t in words[:-1]):
                continue          # tapusią vienuole
            if (last.is_participle and (head.can_be("acc") or head.can_be("loc"))
                    and not any(_agree(x, y) for x in last.own for y in head.own if y.pos == "noun")
                    and not _could_agree_own(toks[idx[-3]], head)):
                continue          # viena baigusi mokyklą: the participle takes an object (didžiules keliaujančios parodas: no)
            prep = PREPOSITIONS.get(toks[idx[0] - 1].lower) if idx[0] > 0 and adjacent[idx[0]] else None
            targets = []
            for rs in [head.own] + [rs for _, rs in head.variants]:
                for r in rs:
                    feats = (r.case, r.number, r.gender)
                    if r.pos == "noun" and feats not in targets and (not prep or r.case in prep):
                        targets.append(feats)
            scored = []
            for feats in targets:
                fixes = [(t, *phrase_fix(t, feats, t is head)) for t in words]
                scored.append((sum(c for _, c, _ in fixes), feats, [x for x in fixes if x[1]]))
            if not scored:
                continue
            best = min(c for c, _, _ in scored)
            if best == 0:
                settled.update(idx)
                continue
            top = [s for s in scored if s[0] == best]
            if best > 3 or any([(t.start, f) for t, _, f in s[2]] != [(t.start, f) for t, _, f in top[0][2]] for s in top):
                continue          # nothing close, or two readings as good
            _, feats, outliers = top[0]
            first = toks[idx[0]]
            j = idx[0] - 1
            while j >= 0 and adjacent[j + 1] and between(j):
                j -= 1
            # the first word may end something before the phrase: a predicate (žinomos visame pasaulyje,
            # buvo lengva visą dieną) or a partitive head (vienas didžiausių miestų): only a lost diacritic
            if feats[0] == "gen" and not prep and any(t is first or t.lower.startswith("vien") for t, _, _ in outliers):
                continue          # a partitive genitive: vienas didžiausių miestų, turinčių vieną storiausių kamienų
            if last.is_participle and any(t is head for t, _, _ in outliers) and not _could_agree_own(last, head):
                continue          # the participle may govern the noun: vieną pašovęs strėle
            if any(t is first and (c > 1 or t.lower.endswith("iausia")       # pirmiausia, svarbiausia: adverbs
                                   or j >= 0 and adjacent[j + 1] and is_copula(toks[j])
                                   or feats[0] == "acc" and any(a.lemma in TIME_LEMMAS for a in self.analyses(head.text)))
                   for t, c, _ in outliers):
                continue
            if coord is not None and any(t.start < toks[coord].start or c > 1 for t, c, _ in outliers):
                continue          # only the word after "ir", by a lost diacritic: didelę ir gražia kavinę -> gražią
                                  # (rezervines ir pagrindinę komandas: two teams)
            if any(t.is_participle and t is not last for t, _, _ in outliers):
                continue          # a predicate further left: Sienos atkurtos tomis pačiomis spalvomis
            if any(t is not head and t.own and (all(r.case == "gen" for r in t.own) or all(
                    ".def." in a.tag for a in self.analyses(t.text)) and any(r.case in ("gen", "dat") for r in t.own))
                   for t, _, _ in outliers):
                continue          # an adjective as a noun: pirmoji kairiųjų pergalė, palankesnė baltiesiems baigmė,
                                  # nuolatinį pirmosios virsmą
            # the noun and the modifier before it, agreeing as written, are a phrase of their own:
            # pailga lėkštašlaitė | neryškia papėde (with an indistinct foot)
            if (len(outliers) >= 2 and outliers[-1][0] is head and outliers[-2][0] is words[-2]
                    and _could_agree_own(words[-2], head)):
                continue
            # an outlier agrees with no neighbour that stays: du nauji | rusiška heraldika, pailga lėkštašlaitė |
            # neryškia papėde; right before the noun, a neighbour that can also have the phrase's case
            # doesn't count (viena, nom or ins: viena nukritusia sagutė -> nukritusi)
            out = {t.start for t, _, _ in outliers}
            if any(any(_could_agree_own(t, words[m]) and not (n == len(words) - 2 and any(fits(r, feats, r.pos) for r in words[m].own))
                       for m in (n - 1, n + 1) if 0 <= m < len(words) and words[m].start not in out)
                   for n, t in enumerate(words) if t.start in out):
                continue
            settled.update(idx)
            text_ = " ".join(t.text for t in words)
            for t, _, f in outliers:
                add(Issue(t.start, t.end, t.text, "phrase",
                          f"'{text_}': the words of a phrase agree in case, number and gender", f))

        # an unknown word after a modifier, typed as one itself: its candidates agreeing with it first
        # (visa sita -> šita, not the more frequent šitą). The keyboard autocorrects it before the noun is
        # typed, and the phrase rule then trusts the diacritic chosen. Nouns are the pair rule's.
        for i in range(1, len(toks)):
            a, w = toks[i - 1], toks[i]
            if not adjacent[i] or w.known or w.start in issues or not modifier(i - 1) or not w.variants:
                continue
            def modifier_form(f):
                return self.analyses(f) and all(x.tag.split(".")[0] in ("A", "P") for x in self.analyses(f))
            if not modifier_form(self.ranked(w.text, [f for f, _ in w.variants])[0]):
                continue          # likely a pronoun or adjective: nebereikalingi isaugus is išaugus, not išaugūs
            ar = [r for r in a.own if r.pos == "adj"]
            fix = [w.cap(f) for f, rs in w.variants if modifier_form(f) and any(_agree(x, y) for x in ar for y in rs)]
            if fix and len(fix) < len(w.variants):
                add(Issue(w.start, w.end, w.text, "context",
                          f"'{a.text} {w.text}': the words of a phrase agree in case, number and gender",
                          self.ranked(w.text, fix)))

        # 2. adjective-noun agreement
        for i in range(1, len(toks)):
            a, n = toks[i - 1], toks[i]
            if not adjacent[i] or a.start in issues or i - 1 in settled and i in settled:
                continue
            if not (a.is_adj and n.is_noun) or a.can_be_verb:
                continue
            no_gen = False
            if a.lower in ("vienas", "viena", "vieni", "vienos") and n.lower.startswith("kit"):
                continue          # viena kitą = each other (but: vienos eilutes -> eilutės)
            if n.can_be("gen") and not a.can_be("gen"):
                # Genitive modifiers sit between an adjective and its noun:
                # profesionalūs [Lietuvos cirko] artistai. Skip them to the head.
                j = i
                while (j + 1 < len(toks) and adjacent[j + 1] and toks[j].known
                       and toks[j].can_be("gen") and toks[j + 1].is_noun):
                    j += 1
                # agreeing with neither the genitive nor the noun after it, but a diacritic twin agrees with
                # the genitive: dalyvaujančiu šalių viršūnių susitikimą -> dalyvaujančių (the keyboard fixed
                # the genitive first); not su dideliu žmonių būriu. Wait for a word after the genitives
                # (su dideliu žmonių ...) that is not a preposition or connective (svarbiausiu musulmonų
                # kovos | prieš ... centru); not a predicate after tapo, laikomas (laikomas lemiamu serbų
                # kovoje); all known (įvairialypes Vokietijos alumnų kompetencijas: alumnų is not)
                ar = [r for r in a.own if r.pos == "adj"]
                hd = toks[j]
                hr = [r for r in hd.own if r.pos == "noun"]
                more = any(r.case != "gen" for r in hr) or (j + 1 < len(toks) and adjacent[j + 1] and toks[j + 1].lower
                                                            not in PREPOSITIONS and toks[j + 1].lower not in PHRASE_STOP)
                if (j > i and a.known and n.known and hd.known and ar and more
                        and not (i >= 2 and adjacent[i - 1] and any(
                            x.tag.startswith("V.") and x.lemma.endswith(PREDICATIVE_VERBS) for x in self.analyses(toks[i - 2].text)))):
                    gr = [r for r in n.own if r.pos == "noun" and r.case == "gen"]
                    if not any(_agree(x, y) for x in ar for y in hr + n.own if y.pos == "noun"):
                        fix = [a.cap(f) for f, rs in a.variants if any(_agree(x, y) for x in rs if x.pos == "adj" for y in gr)]
                        if fix:
                            add(Issue(a.start, a.end, a.text, "agreement",
                                      f"'{a.text} {n.text}': adjective and noun must agree in case and number", fix))
                            continue
                if j > i and not toks[j].can_be("gen") and toks[j].known:
                    n = toks[j]
                elif j > i or not any(r.pos == "noun" and r.case != "gen" for r in n.own):
                    continue
                else:
                    no_gen = True       # no head follows: not a modifier (šita žmogų -> šitą)
            # A participle before a noun is usually an attribute (nukritusią sagutę), but it
            # can also take an object (praėjusi advokatūrą), a place (einanti sakinio gale)
            # or a predicate (tapusią vienuole). A -tinas one takes no accusative: pažintini taką -> pažintinį.
            necessity = (all(x.tag.startswith("V.pnec.") for x in self.analyses(a.text))
                         and n.can_be("acc") and not n.can_be("ins") and not n.can_be("loc"))
            if a.is_participle and not necessity and (n.can_be("acc") or n.can_be("loc") or any(
                    an.lemma.endswith(PREDICATIVE_VERBS) for an in self.analyses(a.text))):
                continue
            if n.start in issues:
                continue
            ar = [r for r in a.pos_readings() if r.pos == "adj"]
            nr = [r for r in n.pos_readings() if r.pos == "noun" and not (no_gen and r.case == "gen")]
            if a.known and n.known and any(_agree(x, y) for x in ar for y in nr):
                continue
            fix_n = [n.cap(f) for f, rs in n.variants
                     if any(_agree(x, y) for x in ar for y in rs if y.pos == "noun")]
            fix_a = [a.cap(f) for f, rs in a.variants
                     if any(_agree(x, y) for x in rs if x.pos == "adj" for y in nr)]
            msg = f"'{a.text} {n.text}': adjective and noun must agree in case and number"
            if not a.known and not n.known:
                if any(finite(x) for f, _ in a.variants for x in self.analyses(f)):
                    continue      # % sudare baltaodziai: sudarė (a verb), not the participle sudarę
                # both typed without diacritics: each puts first the candidates that agree with
                # the other's, when that narrows them (dalyvaujanciu saliu -> dalyvaujančių šalių)
                for t, fix in ((n, fix_n), (a, fix_a)):
                    if fix and len(fix) < len(t.variants):
                        add(Issue(t.start, t.end, t.text, "context", msg, self.ranked(t.text, fix)))
                continue
            # An unknown word may only reorder its own suggestions; it never
            # justifies changing a correctly spelled neighbour.
            if not n.known:
                fix_a = []
            if not a.known:
                fix_n = []
            # a preposition before decides the case: pro nedideles gyvenvietės -> gyvenvietes
            prep = toks[i - 2].lower if i >= 2 and adjacent[i - 1] and toks[i - 2].lower in PREPOSITIONS else None
            if prep and fix_n and fix_a:
                if not any(r.case in PREPOSITIONS[prep] for r in ar):
                    fix_n = []
                elif not any(r.case in PREPOSITIONS[prep] for r in nr):
                    fix_a = []
            # otherwise change the word typed without diacritics: nedidele mergaitė -> nedidelė (not mergaite)
            if fix_a and not has_diacritics(a.text) and has_diacritics(n.text) and not prep:
                fix_n = []
            if fix_n:
                add(Issue(n.start, n.end, n.text, "agreement" if n.known else "context", msg, fix_n))
            elif fix_a:
                add(Issue(a.start, a.end, a.text, "agreement" if a.known else "context", msg, fix_a))

        # 9. a noun right before another noun is its genitive modifier: gyventoju skaičius ->
        #    gyventojų, vietoves gyventojai -> vietovės (the -ų/-ės lost their diacritics)
        #    An unknown word (typed without diacritics) gets its genitive candidates first:
        #    Hulos slapynes dalis -> šlapynės. Its other candidates stand for its own reading.
        for i in range(len(toks) - 1):
            w = toks[i]
            if (w.start in issues or not adjacent[i + 1]
                    or w.text[:1].isupper() and not starts_sentence(i)):
                continue
            if w.known:
                an_w = self.analyses(w.text)
                own, own_forms = w.own, [w.lower]
            else:
                rest = [f for f, rs in w.variants if not any(r.pos == "noun" and r.case == "gen" for r in rs)]
                an_w = [a for f in rest for a in self.analyses(f)]
                own, own_forms = [r for f in rest for r in self.readings_of(f)], rest
            nouns = [a for a in an_w if a.tag.startswith("N.")]
            if (not nouns or any(a.tag.endswith(".gen") for a in an_w) or any(a.tag in ("W", "Adv") for a in an_w)
                    or self.mostly_verb(an_w) and any(finite(a) for a in an_w)):
                continue          # laiku (on time), metu (I throw) are not modifiers
            lemmas = {a.lemma for a in nouns}
            fix = [w.cap(f) for f, _ in w.variants if f[:1].islower()
                   and any((a.lemma in lemmas or not w.known) and a.tag.startswith("N.") and a.tag.endswith(".gen")
                           for a in self.analyses(f))]
            if not fix:
                continue
            span = phrase(i)
            head = span[-1] if span else None
            # (an unknown head counts by its candidates when the word itself is unknown: on the
            # keyboard the head has been corrected by the time the sentence is re-checked)
            if (not head or not head.is_noun or not (head.known or not w.known) or head.text[:1].isupper()
                    or any(a.tag in ("W", "Adv") for a in cand_analyses(head)) or verb_at(i + len(span))):
                continue          # su broliu namo: namo is an adverb
            head_cases = {r.case for r in head.pos_readings()}
            own_cases = {r.case for r in own}
            if w.known:
                # one phrase only in the same case and number (gender may differ: kalba žodžiu rinkliava):
                # pilotu bandytoju, naktiniu gyvenimu; not teises mokyklą (acc pl + acc sg), Medžiokles
                # plotas (plotas is also a participle, not a noun)
                hn = [r for r in head.pos_readings() if r.pos == "noun"]
                if not head_cases or head_cases == {"gen"} or any(
                        x.case == y.case and (not x.number or not y.number or x.number == y.number) for x in own for y in hn):
                    continue      # tarpininku liaudies švietime
            else:
                # the head may have lost its diacritics too (zaidimu bendrove -> bendrovė): skip only
                # when every spelling of it could share the word's case
                head_cases |= {r.case for _, rs in head.variants for r in rs}
                if not head_cases or head_cases <= own_cases:
                    continue
            if lemmas == {"metas"}:
                continue          # vienu metu, tam tikru metu: "at a time"
            # an adverbial instrumental seen as often as its genitive: Sovietmečiu, laikotarpiu, būdu
            own_f = max(self.freq.get(f.lower(), 0) for f in own_forms)
            if own_f and own_f * 3 >= max(self.freq.get(f.lower(), 0) for f in fix):
                continue
            # modifiers before it must agree with the genitive too: branduoliniu ginklu -> branduolinių
            # ginklų; tuo metu žmonės stays (tuo has no genitive twin)
            gen = [r for f in fix for r in self.readings_of(f.lower()) if r.pos == "noun" and r.case == "gen"]
            mods, k, ok = [], i - 1, True
            while k >= 0 and adjacent[k + 1] and toks[k].is_adj:
                m = toks[k]
                if not any(_agree(x, y) for x in m.own for y in own):
                    break
                mf = [m.cap(f) for f, rs in m.variants if any(_agree(x, y) for x in rs if x.pos == "adj" for y in gen)]
                if not mf:
                    ok = False
                    break
                mods.append((m, mf))
                k -= 1
            if not ok:
                continue
            prep_head = False     # the head is the object of the preposition before: į teises mokykla
            if k >= 0 and adjacent[k + 1]:
                p = toks[k]
                an_p = self.analyses(p.text)
                pr = p.pos_readings()      # an unknown word (typed without diacritics): its candidates
                if p.lower in PREPOSITIONS:
                    # su metaliniu lankeliu dugne; but when the head can take the preposition's case (also
                    # by a diacritic), it is the object and the word its genitive: į teises mokykla(ą)
                    pc = PREPOSITIONS[p.lower]
                    if not any(r.pos == "noun" and r.case in pc
                               for r in head.pos_readings() + [r for _, rs in head.variants for r in rs]):
                        continue
                    prep_head = True
                elif any(a.tag.startswith("V.") for a in an_p) and self.mostly_verb(an_p):
                    continue      # pirkęs žemes kaimuose, tapo kasdieniniu gėrimu: governed by the verb
                elif p.lower in POSSESSIVES or an_p and all(a.tag == "W" for a in an_p):
                    continue      # jos pasirodymu danguje, šiuo metu
                # after a genitive (or a name) an instrumental is often its head: karo metu,
                # Vyriausybės potvarkiu, Aifelio dialektu; only a genitive the corpus knows well
                # wins there (vidaus reikalų, Čikagos lietuvių)
                elif (w.known and any(r.case == "ins" for r in own)
                        and (any(r.pos == "noun" and r.case == "gen" for r in pr) or not pr)
                        and max(self.freq.get(f.lower(), 0) for f in fix) < 5):
                    continue
            # a governor further left, across genitives: į Kalavijuočių ordino žemes,
            # tapo antruoju pagal dydį miestu
            j, governed = k, False
            while j >= 0 and j >= k - 3 and adjacent[j + 1] and not governed and not prep_head:
                t = toks[j]
                if t.lower in PREPOSITIONS:
                    governed = any(r.case in PREPOSITIONS[t.lower] for r in own)
                else:
                    governed = any(r.case == "ins" for r in own) and any(
                        a.tag.startswith("V.") and a.lemma.endswith(PREDICATIVE_VERBS) for a in self.analyses(t.text))
                j -= 1
            if governed:
                continue
            why = f"'{w.text} {head.text}': a noun before another noun is usually its genitive"
            if not w.known:
                add(Issue(w.start, w.end, w.text, "context", why, self.ranked(w.text, fix)))
                continue      # an unknown word never changes a known neighbour
            for m, mf in mods:
                add(Issue(m.start, m.end, m.text, "case", why, mf))
            add(Issue(w.start, w.end, w.text, "case", why, fix))

        # 10. valency: a phrase that agrees with itself in a case its verb rarely takes, when its lost
        #     diacritics (or a re-inflected modifier) give a case the verb often takes, as counted on the
        #     dump: visa šita isterija mačiau -> visą šitą isteriją (mačiau after a nominative: never)
        for i, v in enumerate(toks):
            keys, first = self.valency_verb(toks, adjacent, i)
            for after in (True, False) if keys else ():
                idx = self.valency_phrase(toks, adjacent, i if after else first, after, text)
                if not idx or any(toks[j].start in issues for j in idx):
                    continue
                words = [toks[j] for j in idx]
                if after and any(r.pos == "adj" for r in v.own) and _could_agree(v, words[0]):
                    continue          # an adjective of the phrase, not a verb: Gausi tautosaka (abundant)
                head = words[-1]
                typed = phrase_feats(words)
                if not typed:
                    continue          # it doesn't agree with itself: the phrase rule's
                pos = "after" if after else "before"
                if any(len(t.text) > 1 and t.text.isupper() or t.text[:1].isupper() and not starts_sentence(idx[n])
                       for n, t in enumerate(words)):
                    continue          # names and all caps: gyveno San Paule, PABUČIUOK MANE
                classes = {c for _, c in keys}
                cases = {f[0] for f in typed}
                if "nom" in cases and "3" in classes and not (after and subject_before(first)):
                    continue          # it may be the verb's subject: išleido leidykla, Kompanija prodiusavo
                if "loc" in cases:
                    continue          # an adjunct: kine debiutuojantis, specialiame inde
                # the clause, for other subjects: from the verb to the nearest connective or punctuation
                lo, hi = i, i
                while lo > 0 and adjacent[lo] and toks[lo - 1].lower not in CLAUSE_STARTERS:
                    lo -= 1
                while hi + 1 < len(toks) and adjacent[hi + 1] and toks[hi + 1].lower not in CLAUSE_STARTERS:
                    hi += 1
                other_subject = any(j not in idx and j != i and j != first and (toks[j].lower in SUBJECT_PERSON or toks[j].lower in PRONOUN_FEATURES
                                                                 or any(r.case == "nom" and r.pos == "noun" for r in toks[j].own))
                                    for j in range(lo, hi + 1))
                if "nom" in cases and classes & {"inf", "ger"} and not other_subject and any(
                        finite(a) and a.tag.split(".")[2] == "3" and not a.lemma.endswith(("reikia", "reikėjo", "reikėti"))
                        or toks[j].is_participle for j in range(lo, hi + 1) if j not in (i, first) for a in self.analyses(toks[j].text)):
                    continue          # the subject of the clause's 3rd person verb or participle: ėmė kontroliuoti
                                      # Britanija, pasiekus medžiaga tampa, tvarkyti surengta visuotinė talka (not: Prašau
                                      # jus patikrinti ta informacija, Reikia pasiekti stovykla)
                # an object already there: apgynė jį aukščiausiu įvertinimu, gaudo ją drobine paklode (jus: also jūs)
                other_object = any(j not in idx and j != i and j != first and (toks[j].lower in NEG_PRONOUNS and toks[j].lower != "jus" or toks[j].own and all(
                    r.case == "acc" for r in toks[j].own)) for j in range(lo, hi + 1))

                def n(case):
                    return sum(self.valency.get((k, c, pos, case), 0) for k, c in keys)
                have = max(n(f[0]) for f in typed)
                best = None
                for _, rs in head.variants:
                    for r in rs:
                        f = (r.case, r.number, r.gender)
                        if r.pos != "noun" or r.case == "voc" or any(f[0] == x[0] for x in typed):
                            continue
                        if f[0] == "nom" and ("3" not in classes or other_subject):
                            continue      # the subject: of a 3rd person verb, the only one (rūpinimasis gerove nukreipia)
                        if f[0] in ("acc", "gen") and other_object:
                            continue
                        fixes = [phrase_fix(t, f, t is head) for t in words]
                        if any(c > 2 for c, _ in fixes):
                            continue      # no form fits
                        m = n(f[0])
                        ratio = VALENCY_RATIO_12 if classes == {"12"} else VALENCY_RATIO
                        least = VALENCY_MIN_12 if classes == {"12"} else VALENCY_MIN
                        if m >= least and m >= ratio * (have + 1) and (best is None or m > best[0]):
                            best = (m, f, fixes)
                if best:
                    # a set phrase as written is more common than the fix: laisva valia, įvairia tematika
                    seq = [v] + words if after else words + [v]
                    fixed = {t.start: (fx[0] if c else t.text) for t, (c, fx) in zip(words, best[2])}
                    as_written = sum(self.pair(x.lower, y.lower) for x, y in zip(seq, seq[1:]))
                    as_fixed = sum(self.pair(fixed.get(x.start, x.text).lower(), fixed.get(y.start, y.text).lower())
                                   for x, y in zip(seq, seq[1:]))
                    if as_written > as_fixed:
                        best = None
                if best:
                    for t, (c, fix) in zip(words, best[2]):
                        if c:
                            add(Issue(t.start, t.end, t.text, "valency",
                                      f"'{v.text}' takes the {CASE_NAMES[best[1][0]]}", fix))

        return sorted(issues.values(), key=lambda x: x.start)
