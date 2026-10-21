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
from .suggest import _cost, _load_freq

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
    return ".".join(parts)


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
        for a in analyses:
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
                    for x in span:
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

        # 2. adjective-noun agreement
        for i in range(1, len(toks)):
            a, n = toks[i - 1], toks[i]
            if not adjacent[i] or a.start in issues:
                continue
            if not (a.is_adj and n.is_noun) or a.can_be_verb or not (a.known or n.known):
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
                if j > i and not toks[j].can_be("gen") and toks[j].known:
                    n = toks[j]
                elif j > i or not any(r.pos == "noun" and r.case != "gen" for r in n.own):
                    continue
                else:
                    no_gen = True       # no head follows: not a modifier (šita žmogų -> šitą)
            # A participle before a noun is usually an attribute (nukritusią sagutę), but it
            # can also take an object (praėjusi advokatūrą), a place (einanti sakinio gale)
            # or a predicate (tapusią vienuole).
            if a.is_participle and (n.can_be("acc") or n.can_be("loc") or any(
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
        for i in range(len(toks) - 1):
            w = toks[i]
            if (w.start in issues or not adjacent[i + 1] or not w.known
                    or w.text[:1].isupper() and not starts_sentence(i)):
                continue
            an_w = self.analyses(w.text)
            nouns = [a for a in an_w if a.tag.startswith("N.")]
            if (not nouns or any(a.tag.endswith(".gen") for a in an_w) or any(a.tag in ("W", "Adv") for a in an_w)
                    or self.mostly_verb(an_w) and any(finite(a) for a in an_w)):
                continue          # laiku (on time), metu (I throw) are not modifiers
            lemmas = {a.lemma for a in nouns}
            fix = [w.cap(f) for f, _ in w.variants if f[:1].islower()
                   and any(a.lemma in lemmas and a.tag.startswith("N.") and a.tag.endswith(".gen")
                           for a in self.analyses(f))]
            if not fix:
                continue
            span = phrase(i)
            head = span[-1] if span else None
            if (not head or not head.is_noun or not head.known or head.text[:1].isupper()
                    or any(a.tag in ("W", "Adv") for a in self.analyses(head.text)) or verb_at(i + len(span))):
                continue          # su broliu namo: namo is an adverb
            if {r.case for r in w.own} & {r.case for r in head.own} or {r.case for r in head.own} == {"gen"}:
                continue          # one phrase: pilotu bandytoju, naktiniu gyvenimu; tarpininku liaudies švietime
            if lemmas == {"metas"}:
                continue          # vienu metu, tam tikru metu: "at a time"
            # an adverbial instrumental seen as often as its genitive: Sovietmečiu, laikotarpiu, būdu
            own_f = self.freq.get(w.lower, 0)
            if own_f and own_f * 3 >= max(self.freq.get(f.lower(), 0) for f in fix):
                continue
            # modifiers before it must agree with the genitive too: branduoliniu ginklu -> branduolinių
            # ginklų; tuo metu žmonės stays (tuo has no genitive twin)
            gen = [r for f in fix for r in self.readings_of(f.lower()) if r.pos == "noun" and r.case == "gen"]
            mods, k, ok = [], i - 1, True
            while k >= 0 and adjacent[k + 1] and toks[k].is_adj:
                m = toks[k]
                if not any(_agree(x, y) for x in m.own for y in w.own):
                    break
                mf = [m.cap(f) for f, rs in m.variants if any(_agree(x, y) for x in rs if x.pos == "adj" for y in gen)]
                if not mf:
                    ok = False
                    break
                mods.append((m, mf))
                k -= 1
            if not ok:
                continue
            if k >= 0 and adjacent[k + 1]:
                p = toks[k]
                an_p = self.analyses(p.text)
                if p.lower in PREPOSITIONS and any(r.case in PREPOSITIONS[p.lower] for r in w.own):
                    continue      # su metaliniu lankeliu dugne
                if any(a.tag.startswith("V.") for a in an_p) and self.mostly_verb(an_p):
                    continue      # pirkęs žemes kaimuose, tapo kasdieniniu gėrimu: governed by the verb
                pr = p.pos_readings()      # an unknown word (typed without diacritics): its candidates
                if p.lower in POSSESSIVES or an_p and all(a.tag == "W" for a in an_p):
                    continue      # jos pasirodymu danguje, šiuo metu
                # after a genitive (or a name) an instrumental is often its head: karo metu,
                # Vyriausybės potvarkiu, Aifelio dialektu; only a genitive the corpus knows well
                # wins there (vidaus reikalų, Čikagos lietuvių)
                if (any(r.case == "ins" for r in w.own)
                        and (any(r.pos == "noun" and r.case == "gen" for r in pr) or not pr)
                        and max(self.freq.get(f.lower(), 0) for f in fix) < 5):
                    continue
            # a governor further left, across genitives: į Kalavijuočių ordino žemes,
            # tapo antruoju pagal dydį miestu
            j, governed = k, False
            while j >= 0 and j >= k - 3 and adjacent[j + 1] and not governed:
                t = toks[j]
                if t.lower in PREPOSITIONS:
                    governed = any(r.case in PREPOSITIONS[t.lower] for r in w.own)
                else:
                    governed = any(r.case == "ins" for r in w.own) and any(
                        a.tag.startswith("V.") and a.lemma.endswith(PREDICATIVE_VERBS) for a in self.analyses(t.text))
                j -= 1
            if governed:
                continue
            why = f"'{w.text} {head.text}': a noun before another noun is usually its genitive"
            for m, mf in mods:
                add(Issue(m.start, m.end, m.text, "case", why, mf))
            add(Issue(w.start, w.end, w.text, "case", why, fix))

        return sorted(issues.values(), key=lambda x: x.start)
