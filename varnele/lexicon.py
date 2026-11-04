"""Load stems from the ispell-lt word lists (BSD licence) and our own additions.

We only take the *stems and their class flags* from ispell-lt; every inflected
form is produced by our own paradigms in paradigms.py.

ispell-lt flags we use:
  D        noun (declension chosen from the lemma ending)
  V / M    masculine / feminine consonant- or i-stem noun (dantis, akis, akmuo, sesuo)
  I / K    soft (-ių) / hard (-ų) genitive plural for i-stem nouns
  B        adjective;  Q  qualitative (degrees, adverbs)
  C / H    pronoun / numeral
  T E P Y  verb infinitive / present 3p / past 3p (Y = -yti verb with -ė past)
  U        monosyllabic -yti/-ūti verb with short future vowel (bus, lis)
  R / O    reflexive forms allowed
  N        ne-, nebe- allowed;  X  be-, te-, tebe- allowed;  S  reflexive ne-si-, be-si- ...
  a..l     verbal prefix ap at į iš nu pa par per pra pri su už allowed
Our own:
  Z        reflexive only: a plain form only with the -si- infix (nesidomiu, besidžiaugiantis; not didžiuoju
           "I am proud", which is the instrumental of didysis, nor gėrimas as a participle of gėrėtis)
  m..x     the same prefixes with the reflexive -si- infix (apsi-, atsi-, ...)
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ISPELL = ROOT / "vendor" / "ispell-lt"
ISPELL_FILES = ["zodziai", "veiksmazodziai", "vardai", "ivairus", "ivpk", "jargon"]
EXTRA = ROOT / "data" / "extra.txt"

PREFIXES = ["ap", "at", "į", "iš", "nu", "pa", "par", "per", "pra", "pri", "su", "už"]
PLAIN_PREFIX_FLAGS = "abcdefghijkl"
REFL_PREFIX_FLAGS = "mnopqrstuvwx"


def kind_of(flags: str) -> str:
    up = set(c for c in flags if c.isupper())
    if "C" in up:
        return "pron"
    if "H" in up:
        return "num"
    if "B" in up:
        return "adj"
    if up & {"D", "V", "M"}:
        return "noun"
    if "T" in up:
        return "inf"
    if "E" in up:
        return "prs"
    if up & {"P", "Y"}:
        return "pst"
    return "word"


def _parse(lines):
    for line in lines:
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        word, _, flags = line.partition("/")
        yield word.strip(), flags.strip()


def load():
    """Return (entries, blacklist). entries: list of (lemma, kind, flags)."""
    seen, entries, blacklist, dropped = set(), [], set(), set()
    sources = []
    for name in ISPELL_FILES:
        text = (ISPELL / f"lietuviu.{name}").read_bytes().decode("iso-8859-13")
        sources.append(text.splitlines())
    if EXTRA.exists():
        extra = []
        for line in EXTRA.read_text("utf-8").splitlines():
            if line.startswith("-") and "/" in line:     # -šita/D: drop a wrong lexicon entry
                dropped.add(next(_parse([line[1:]])))
            elif line.startswith("-"):
                blacklist.add(line[1:].split("#", 1)[0].strip())
            else:
                extra.append(line)
        sources.append(extra)
    for lines in sources:
        for word, flags in _parse(lines):
            key = (word, flags)
            if key in seen or key in dropped:
                continue
            seen.add(key)
            entries.append((word, kind_of(flags), flags))
    return _bare_verb_forms(entries), blacklist


def _bare_verb_forms(entries):
    """ispell-lt lists some verb forms with only a reflexive flag (R or O): the flag of another entry (buvo/O
    next to buvo/POSX...), or the reflexive forms of a verb with no plain ones (didžiuotis/R, didžiavosi/O). Read as plain words they gave common verbs a
    particle reading (buvo, saugo, būna) and left the reflexive-only ones without a paradigm. The flag goes to
    the entry of the same word and kind, and a reflexive form becomes a reflexive-only principal part (Z)."""
    verbs = {}
    for i, (word, kind, _) in enumerate(entries):
        if kind in ("inf", "prs", "pst"):
            verbs.setdefault(word, []).append(i)
    add, keep, new = {}, [], {}
    for i, (word, kind, flags) in enumerate(entries):
        if kind != "word" or not flags or set(flags) - set("RO"):
            keep.append(i)
            continue
        refl = word.endswith(("tis", "si"))
        stem = word[:-1] if word.endswith("tis") else word[:-2] if refl else word
        # the ending tells the kind; an -o form is present with R (bastosi: bastytis), past with O (didžiavosi)
        letter = ("T" if stem.endswith("ti") else "P" if stem.endswith("ė") else "E" if stem.endswith(("a", "i"))
                  else "P" if "O" in flags else "E")
        same = [k for k in verbs.get(stem, []) if entries[k][1] == kind_of(letter)]
        for k in same:
            add[k] = add.get(k, "") + flags
        if not same and not refl:
            keep.append(i)        # bėgėti/R, gavi/O: a plain form of no listed verb, its kind unsure; left a word
        elif not same:
            f = letter + flags + "SZ"
            new[(stem, f)] = (stem, kind_of(f), f)
    for k, f in add.items():
        word, kind, flags = entries[k]
        entries[k] = (word, kind, flags + "".join(c for c in dict.fromkeys(f) if c not in flags))
    return [entries[k] for k in keep] + list(new.values())
