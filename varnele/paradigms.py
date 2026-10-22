"""Inflection paradigms: turn a lemma (plus its class) into every surface form.

Each generator returns a list of (form, tag). Tags are dotted strings such as
"N.sg.gen", "A.f.pl.loc", "V.prs.1sg.refl", "V.pap.m.sg.nom" so the analyzer
can ask questions like "is this a locative?" or "is this a reflexive form?".

Ending tables list the 7 cases in order nom, gen, dat, acc, ins, loc, voc.
An entry can be a string, a tuple of accepted alternatives, or None.
"""

from .phonology import join, underlying

CASES = ("nom", "gen", "dat", "acc", "ins", "loc", "voc")


def _alts(x):
    if x is None:
        return ()
    return (x,) if isinstance(x, str) else x


def _decline(out, stem, row, tag, verb=False):
    for case, ends in zip(CASES, row):
        for e in _alts(ends):
            out.append((join(stem, e, verb), f"{tag}.{case}"))


# --------------------------------------------------------------------------
# Nouns (the 12 declension paradigms of DLKG)
# --------------------------------------------------------------------------

PL_AS = ["ai", "ų", "ams", "us", "ais", "uose", "ai"]
PL_IAS = ["iai", "ių", "iams", "ius", "iais", "iuose", "iai"]
PL_A = ["os", "ų", "oms", "as", "omis", "ose", "os"]
PL_IA = ["ios", "ių", "ioms", "ias", "iomis", "iose", "ios"]
PL_E = ["ės", "ių", "ėms", "es", "ėmis", "ėse", "ės"]
PL_US = ["ūs", "ų", "ums", "us", "umis", "uose", "ūs"]


def _pl_istem(genpl):
    return ["ys", genpl, "ims", "is", "imis", "yse", "ys"]


NOUN = {
    # name: (lemma ending, singular row, plural row)
    "as":  ("as", ["as", "o", "ui", "ą", "u", "e", ("e", "ai")], PL_AS),
    "jas": ("as", ["as", "o", "ui", "ą", "u", "yje", ("au", "ai")], PL_AS),
    "ias": ("ias", ["ias", "io", "iui", "ią", "iu", "yje", ("y", "iau")], PL_IAS),
    "is":  ("is", ["is", "io", "iui", "į", "iu", "yje", "i"], PL_IAS),
    "ys":  ("ys", ["ys", "io", "iui", "į", "iu", "yje", "y"], PL_IAS),
    "us":  ("us", ["us", "aus", "ui", "ų", "umi", "uje", "au"], PL_US),
    "ius": ("ius", ["ius", "iaus", "iui", "ių", "iumi", "iuje", "iau"], PL_IAS),
    "a":   ("a", ["a", "os", "ai", "ą", "a", "oje", "a"], PL_A),
    "ia":  ("ia", ["ia", "ios", "iai", "ią", "ia", "ioje", "ia"], PL_IA),
    "i":   ("i", ["i", "ios", "iai", "ią", "ia", "ioje", "i"], PL_IA),
    "ė":   ("ė", ["ė", "ės", "ei", "ę", "e", "ėje", "e"], PL_E),
    "is_f": ("is", ["is", "ies", "iai", "į", "imi", "yje", "ie"], None),
    "is_m": ("is", ["is", "ies", "iui", "į", "imi", "yje", "ie"], None),
}

FEMININE = {"a", "ia", "i", "ė", "is_f"}   # paradigm -> grammatical gender (rest masculine)

# Plural-only nouns (marškiniai, durys, Trakai, Kėdainiai, ...).
PLURALIA_GENDER = {"iai": "m", "ai": "m", "ūs": "m", "ios": "f", "os": "f", "ės": "f"}
PLURALIA = [("iai", PL_IAS), ("ai", PL_AS), ("ios", PL_IA), ("os", PL_A),
            ("ės", PL_E), ("ūs", PL_US)]


def noun(lemma, flags=""):
    out = []
    soft, hard = "I" in flags, "K" in flags
    genpl = ("ių",) if soft and not hard else ("ų",) if hard and not soft else ("ių", "ų")

    # Consonant-stem nouns: akmuo/akmens, sesuo/sesers, duktė/dukters
    if lemma.endswith("uo") or (lemma.endswith("ė") and "M" in flags):
        fem = "M" in flags
        stem = lemma[:-2] if lemma.endswith("uo") else lemma[:-1]
        stem += "er" if fem else "en"
        g = "f" if fem else "m"
        out.append((lemma, f"N.{g}.sg.nom"))
        sg = ([None, "s", "iai", "į", ("imi", "ia"), "yje", "ie"] if fem else
              [None, "s", "iui", "į", "iu", "yje", "ie"])
        _decline(out, stem, sg, f"N.{g}.sg")
        _decline(out, stem, _pl_istem(("ų", "ių")), f"N.{g}.pl")
        return out

    if lemma.endswith("is") and ("M" in flags or "V" in flags):
        name = "is_f" if "M" in flags else "is_m"
        _, sg, _ = NOUN[name]
        stem = lemma[:-2]
        g = "f" if name == "is_f" else "m"
        _decline(out, stem, sg, f"N.{g}.sg")
        _decline(out, stem, _pl_istem(genpl), f"N.{g}.pl")
        return out

    for end, pl in PLURALIA:
        if lemma.endswith(end) and len(lemma) > len(end) + 1:
            stem = underlying(lemma[:-len(end)]) if end[0] == "i" else lemma[:-len(end)]
            _decline(out, stem, pl, f"N.{PLURALIA_GENDER[end]}.pl")
            return out

    if lemma.endswith("ys") and len(lemma) > 4:
        # durys, kepenys, smegenys are plural i-stems; arklys is singular -ys.
        _decline(out, lemma[:-2], _pl_istem("ų"), "N.f.pl")
    if lemma.endswith("ias"):
        name = "ias"
    elif lemma.endswith("ijas"):
        _decline(out, lemma[:-2], [None, None, None, None, None, "uje", None], "N.m.sg")  # radijuje
        name = "jas"
    elif lemma.endswith("jas"):
        name = "jas"
    elif lemma.endswith("as"):
        name = "as"
    elif lemma.endswith("ius"):
        name = "ius"
    elif lemma.endswith("us"):
        name = "us"
    elif lemma.endswith("ys"):
        name = "ys"
    elif lemma.endswith("is"):
        name = "is"
    elif lemma.endswith("ia") and not lemma.endswith("ija"):
        name = "ia"
    elif lemma.endswith("a"):
        name = "a"
    elif lemma.endswith("ė"):
        name = "ė"
    elif lemma.endswith("i") and len(lemma) > 2:
        name = "i"
    else:
        return [(lemma, "N.indecl")]

    end, sg, pl = NOUN[name]
    stem = lemma[:-len(end)]
    if end[0] == "i":
        stem = underlying(stem)
    g = "f" if name in FEMININE else "m"
    _decline(out, stem, sg, f"N.{g}.sg")
    _decline(out, stem, pl, f"N.{g}.pl")
    return out


# --------------------------------------------------------------------------
# Adjectives (and everything that declines like one: participles, ordinals)
# --------------------------------------------------------------------------

# masc sg, masc pl, fem sg, fem pl (6 cases each, no vocative)
ADJ = {
    "as":    (["as", "o", "am", "ą", "u", "ame"], ["i", "ų", "iems", "us", "ais", "uose"],
              ["a", "os", "ai", "ą", "a", "oje"], ["os", "ų", "oms", "as", "omis", "ose"]),
    "ias":   (["ias", "io", "iam", "ią", "iu", "iame"], ["i", "ių", "iems", "ius", "iais", "iuose"],
              ["ia", "ios", "iai", "ią", "ia", "ioje"], ["ios", "ių", "ioms", "ias", "iomis", "iose"]),
    "us":    (["us", "aus", "iam", "ų", "iu", "iame"], ["ūs", "ių", "iems", "ius", "iais", "iuose"],
              ["i", "ios", "iai", "ią", "ia", "ioje"], ["ios", "ių", "ioms", "ias", "iomis", "iose"]),
    "inis":  (["is", "io", "iam", "į", "iu", "iame"], ["iai", "ių", ("iams", "iems"), "ius", "iais", "iuose"],
              ["ė", "ės", "ei", "ę", "e", "ėje"], ["ės", "ių", "ėms", "es", "ėmis", "ėse"]),
    "esnis": (["is", "io", "iam", "į", "iu", "iame"], ["i", "ių", "iems", "ius", "iais", "iuose"],
              ["ė", "ės", "ei", "ę", "e", "ėje"], ["ės", "ių", "ėms", "es", "ėmis", "ėse"]),
    # active participles: dirbantis/dirbanti, dirbusio/dirbusi
    "ptc":   (["is", "io", "iam", "į", "iu", "iame"], ["ys", "ių", "iems", "ius", "iais", "iuose"],
              ["i", "ios", "iai", "ią", "ia", "ioje"], ["ios", "ių", "ioms", "ias", "iomis", "iose"]),
}

# Definite ("pronominal") forms: gerasis, geroji, gražusis, geresnysis, ...
PRON_HARD = (["asis", "ojo", "ajam", "ąjį", "uoju", "ajame"],
             ["ieji", "ųjų", "iesiems", "uosius", "aisiais", "uosiuose"],
             ["oji", "osios", "ajai", "ąją", "ąja", "ojoje"],
             ["osios", "ųjų", "osioms", "ąsias", "osiomis", "osiose"])


def _pron_soft(nom, acc):
    return ([nom, "iojo", "iajam", acc, "iuoju", "iajame"],
            ["ieji", "iųjų", "iesiems", "iuosius", "iaisiais", "iuosiuose"],
            ["ioji", "iosios", "iajai", "iąją", "iąja", "iojoje"],
            ["iosios", "iųjų", "iosioms", "iąsias", "iosiomis", "iosiose"])


PRON = {
    "as": PRON_HARD,
    "ias": _pron_soft("iasis", "iąjį"),
    "us": _pron_soft("usis", "ųjį"),
    "inis": _pron_soft("ysis", "įjį"),
    "esnis": _pron_soft("ysis", "įjį"),
    "ptc": _pron_soft("ysis", "įjį"),
}


def _adj_rows(out, stem, table, tag, verb=False):
    for (g, n), row in zip((("m", "sg"), ("m", "pl"), ("f", "sg"), ("f", "pl")), table):
        _decline(out, stem, row, f"{tag}.{g}.{n}", verb)


def adj_forms(stem, kind, tag="A", definite=True):
    out = []
    _adj_rows(out, stem, ADJ[kind], tag)
    if definite:
        _adj_rows(out, stem, PRON[kind], tag + ".def")
    return out


def adj_class(lemma):
    if lemma.endswith("didelis"):
        return lemma[:-2], "esnis"        # dideli, not *dideliai (mediniai, mažyčiai are right)
    for end, kind in (("ias", "ias"), ("as", "as"), ("us", "us"), ("is", "inis"), ("ys", "inis")):
        if lemma.endswith(end):
            stem = lemma[:-len(end)]
            return (underlying(stem) if end[0] == "i" else stem), kind
    return None, None


def adjective(lemma, flags=""):
    stem, kind = adj_class(lemma)
    if kind is None:
        return [(lemma, "A.indecl")]
    out = adj_forms(stem, kind)
    if kind == "as":
        out.append((stem + "a", "A.n"))
    elif kind == "ias":
        out.append((join(stem, "ia"), "A.n"))
    elif kind == "us":
        out.append((stem + "u", "A.n"))
    if "Q" in flags:  # qualitative: degrees and adverbs
        out += adj_forms(stem + "esn", "esnis", "A.cmp")
        sup = join(stem, "iaus")
        out += adj_forms(sup, "ias", "A.sup")
        out.append((join(stem, "iau"), "Adv.cmp"))
        out.append((join(sup, "iai"), "Adv.sup"))
        out.append((stem + "ai" if kind == "as" else join(stem, "iai"), "Adv"))
        out += [(f, "N.qual." + t[2:]) for f, t in noun(stem + "umas")]   # gerumas
        out += adj_forms(stem + "ok", "as", "A.dim", definite=False)       # gerokas
    return out


# --------------------------------------------------------------------------
# Pronouns and numerals (closed classes, flags C and H)
# --------------------------------------------------------------------------

def pronoun(lemma, flags=""):
    out = []
    if lemma.endswith("kas") and lemma in ("kas", "kažkas"):
        stem = lemma[:-2]
        _decline(out, stem, ["as", "o", "am", "ą", "uo", "ame"], "P.sg")
        return out
    if lemma.endswith("oks"):
        stem = lemma[:-1]
        _decline(out, stem, ["s", "io", "iam", "į", "iu", "iame"], "P.m.sg")
        _decline(out, stem, ["ie", "ių", "iems", "ius", "iais", "iuose"], "P.m.pl")
        t = ADJ["ias"]
        _decline(out, stem, t[2], "P.f.sg")
        _decline(out, stem, t[3], "P.f.pl")
        return out
    if lemma.endswith("okia"):
        return pronoun(lemma[:-2] + "s", flags)
    if lemma.endswith("a") and not lemma.endswith("as"):
        lemma += "s"
    if lemma.endswith("as"):
        stem = lemma[:-2]
        out += adj_forms(stem, "as", "P", definite=False)
        _decline(out, stem, [None, None, None, None, "uo", None], "P.m.sg")
        _decline(out, stem, ["ie", None, None, "uos", None, None], "P.m.pl")
    return out


def numeral(lemma, flags=""):
    out = []
    if lemma.endswith("lika"):
        _decline(out, lemma[:-1], ["a", "os", "ai", "ą", "a", "oje"], "Num")
    elif lemma.endswith("dešimt"):
        out.append((lemma, "Num.nom"))
        _decline(out, lemma, [None, "ies", "iai", None, "imi", "yje"], "Num")
        _decline(out, lemma, _pl_istem("ių"), "Num.pl")   # dešimtys, dešimčių
    elif lemma.endswith("eri") or lemma.endswith("i"):
        stem = lemma[:-1]
        _decline(out, stem, ["i", "ių", "iems", ("is", "ius"), "iais", "iuose"], "Num.m")
        _decline(out, stem, ["ios", "ių", "ioms", "ias", "iomis", "iose"], "Num.f")
    elif lemma.endswith("as"):  # ordinals: antras, penktas, trečias
        stem, kind = adj_class(lemma)
        out += adj_forms(stem, kind, "Num.ord")
        out.append((lemma, "Num.ord"))
    else:
        out.append((lemma, "Num"))
    return out


# --------------------------------------------------------------------------
# Verbs: one generator per principal part
# --------------------------------------------------------------------------

def _reflexive(form, tag):
    """Reflexive variant of a finite form with the -si(s) at the end."""
    if ".imp." in tag and form.endswith("ki"):
        return form + "s"
    for plain, refl in (("me", "mės"), ("te", "tės"), ("au", "ausi"), ("ai", "aisi"),
                        ("ei", "eisi"), ("u", "uosi"), ("tum", "tumeisi"), ("k", "kis")):
        if form.endswith(plain):
            return form[:-len(plain)] + refl
    if tag.endswith("2sg"):
        return form + "esi"  # dirbi -> dirbiesi, myli -> myliesi
    return form + "si"       # dirba -> dirbasi, tyli -> tylisi, dirbo -> dirbosi


def _finite(out, stem, endings, tag, refl, verb=True):
    for person, ends in endings:
        for e in _alts(ends):
            form = join(stem, e, verb)
            out.append((form, f"V.{tag}.{person}"))
            if refl:
                out.append((_reflexive(form, f"V.{tag}.{person}"), f"V.{tag}.{person}.refl"))


PRESENT = {
    "a":  [("1sg", "u"), ("2sg", "i"), ("3", "a"), ("1pl", "ame"), ("2pl", "ate")],
    "ia": [("1sg", "iu"), ("2sg", "i"), ("3", "ia"), ("1pl", "iame"), ("2pl", "iate")],
    "i":  [("1sg", "iu"), ("2sg", "i"), ("3", "i"), ("1pl", "ime"), ("2pl", "ite")],
    "o":  [("1sg", "au"), ("2sg", "ai"), ("3", "o"), ("1pl", "ome"), ("2pl", "ote")],
}
PAST = {
    "o": [("1sg", "au"), ("2sg", "ai"), ("3", "o"), ("1pl", "ome"), ("2pl", "ote")],
    "ė": [("1sg", "iau"), ("2sg", "ei"), ("3", "ė"), ("1pl", "ėme"), ("2pl", "ėte")],
}


def _participle_act(out, stem, tag, short=None):
    """dirbant -> dirbantis/dirbanti/dirbančio/... (+ definite forms)."""
    out += adj_forms(stem, "ptc", tag)
    if short:
        out.append((short, f"{tag}.m.sg.nom"))


def verb_present(form3, flags=""):
    """Forms built on the present stem (3rd person present: dirba, jaučia, myli, rašo)."""
    out, refl = [], ("R" in flags or "O" in flags)
    if form3.endswith("ia"):
        conj, stem = "ia", underlying(form3[:-2])
    elif form3[-1] in "aio":
        conj, stem = form3[-1], form3[:-1]
    else:
        return [(form3, "V.prs.3")]
    _finite(out, stem, PRESENT[conj], "prs", refl)

    # participle and gerund stems: dirbant-, jaučiant-, mylint-, rašant-
    ptc = {"a": "ant", "ia": "iant", "i": "int", "o": "ant"}[conj]
    pstem = join(stem, ptc)
    out.append((pstem, "V.ger.prs"))
    _participle_act(out, pstem, "V.pprs", join(stem, {"i": "įs"}.get(conj, "ąs" if conj != "ia" else "iąs")))
    if refl:
        out.append((pstem + "is", "V.ger.prs.refl"))
        out.append((join(stem, "ąsis" if conj in "ao" else "iąsis" if conj == "ia" else "įsis"), "V.pprs.m.sg.nom.refl"))
    passive = {"a": "am", "ia": "iam", "i": "im", "o": "om"}[conj]
    out += adj_forms(join(stem, passive), "as", "V.ppp")
    out.append((join(stem, passive) + "a", "V.ppp.n"))
    if refl:
        out.append((join(stem, passive) + "asi", "V.ppp.n.refl"))   # orientuojamasi
    return out


def verb_past(form3, flags=""):
    """Forms built on the past stem (3rd person past: dirbo, matė, nešė)."""
    out, refl = [], ("R" in flags or "O" in flags)
    if form3[-1] not in "oė":
        return [(form3, "V.pst.3")]
    conj, stem = form3[-1], form3[:-1]
    _finite(out, stem, PAST[conj], "pst", refl)

    # Past active participle: dirbęs/dirbusi; -yti verbs soften: matęs/mačiusi
    soft = "Y" in flags
    pstem = join(stem, "ius" if soft else "us")
    out.append((stem + "ęs", "V.pap.m.sg.nom"))
    out.append((stem + "ę", "V.pap.m.pl.nom"))
    out += [(f, t) for f, t in adj_forms(pstem, "ptc", "V.pap") if t not in ("V.pap.m.sg.nom", "V.pap.m.pl.nom")]
    out.append((pstem, "V.ger.pst"))
    if refl:
        out += [(stem + "ęsis", "V.pap.m.sg.nom.refl"), (pstem + "is", "V.ger.pst.refl"),
                (pstem + "i", "V.pap.f.sg.nom.refl")]

    # Verbal noun: dirbimas, matymas, nešimas, abejojimas, buvimas
    vn = stem + ("ymas" if soft else "imas")
    vforms = noun(vn)
    out += [(f, "N.vn." + t[2:]) for f, t in vforms]
    if refl:  # kreipimasis, kreipimosi, kreipimąsi, kreipimaisi
        out += [(f + ("is" if f.endswith("s") else "si"), "N.vn." + t[2:] + ".refl") for f, t in vforms]
    return out


def verb_infinitive(inf, flags=""):
    """Forms built on the infinitive stem (dirbti, matyti, nešti, būti)."""
    if not inf.endswith("ti"):
        return [(inf, "V.inf")]
    out, refl = [], ("R" in flags or "O" in flags)
    s = inf[:-2]
    out.append((inf, "V.inf"))
    if refl:
        out.append((inf + "s", "V.inf.refl"))

    # Future. Monosyllabic -yti/-ūti verbs flagged U shorten the vowel: bus, lis.
    fut3 = s + "s"
    if "U" in flags and s[-1:] in ("y", "ū"):
        fut3 = s[:-1] + {"y": "i", "ū": "u"}[s[-1]] + "s"
    _finite(out, s, [("1sg", "siu"), ("2sg", "si"), ("1pl", "sime"), ("2pl", "site")], "fut", refl)
    out.append((join(fut3[:-1], "s", True), "V.fut.3"))
    if refl:
        out.append((join(fut3[:-1], "s", True) + "is", "V.fut.3.refl"))

    # Conditional
    _finite(out, s, [("1sg", "čiau"), ("2sg", ("tum", "tumei")), ("3", "tų"),
                     ("1pl", ("tume", "tumėme")), ("2pl", ("tute", "tumėte"))], "cond", refl)
    # Imperative (+ archaic/poetic -ki)
    _finite(out, s, [("2sg", ("k", "ki")), ("1pl", "kime"), ("2pl", "kite")], "imp", refl)
    # Past frequentative
    _finite(out, s + "dav", PAST["o"], "pstf", refl)

    # Participles and other non-finite forms
    out += adj_forms(s + "t", "as", "V.ppp.pst")          # dirbtas, dirbtasis
    if refl:
        out.append((s + "tasi", "V.ppp.pst.n.refl"))       # kreiptasi
    # frequentative past participle: dirbdavęs, dirbdavusi, dirbdavus
    out += [(s + "davęs", "V.papf.m.sg.nom"), (s + "davę", "V.papf.m.pl.nom"), (s + "davus", "V.ger.pstf")]
    out += [(f, t) for f, t in adj_forms(s + "davus", "ptc", "V.papf")
            if t not in ("V.papf.m.sg.nom", "V.papf.m.pl.nom")]
    out += adj_forms(s + "tin", "as", "V.pnec")           # dirbtinas
    out += adj_forms(join(s, "sim", True), "as", "V.ppp.fut")  # dirbsimas
    fstem = join(s, "siant", True)
    out.append((fstem, "V.ger.fut"))
    _participle_act(out, fstem, "V.pfut", join(s, "siąs", True))
    if refl:
        out.append((fstem + "is", "V.ger.fut.refl"))
    for f, r, t in (("damas", "damasis", "m.sg"), ("dama", "damasi", "f.sg"),
                    ("dami", "damiesi", "m.pl"), ("damos", "damosi", "f.pl")):
        out.append((s + f, f"V.half.{t}"))
        if refl:
            out.append((s + r, f"V.half.{t}.refl"))
    out.append((s + "te", "V.bud"))
    return out
