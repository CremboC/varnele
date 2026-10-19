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
    seen, entries, blacklist = set(), [], set()
    sources = []
    for name in ISPELL_FILES:
        text = (ISPELL / f"lietuviu.{name}").read_bytes().decode("iso-8859-13")
        sources.append(text.splitlines())
    if EXTRA.exists():
        extra = []
        for line in EXTRA.read_text("utf-8").splitlines():
            if line.startswith("-"):
                blacklist.add(line[1:].split("#", 1)[0].strip())
            else:
                extra.append(line)
        sources.append(extra)
    for lines in sources:
        for word, flags in _parse(lines):
            key = (word, flags)
            if key in seen:
                continue
            seen.add(key)
            entries.append((word, kind_of(flags), flags))
    return entries, blacklist
