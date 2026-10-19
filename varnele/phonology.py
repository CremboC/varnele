"""Sound and spelling rules applied where a stem meets an ending."""

# Vowels after which a preceding "i" is only a softness marker (not a syllable).
BACK_VOWELS = set("aąouųū")

# Letters that differ only by diacritics / length / nasality. Most real-world
# Lithuanian spelling mistakes stay inside one of these classes.
FOLD = str.maketrans({
    "ą": "a", "č": "c", "ę": "e", "ė": "e", "į": "i", "y": "i",
    "š": "s", "ų": "u", "ū": "u", "ž": "z",
})

LT_ALPHABET = "aąbcčdeęėfghiįyjklmnoprsštuųūvzž"


def fold(s: str) -> str:
    return s.translate(FOLD)


def join(stem: str, ending: str, verb: bool = False) -> str:
    """Attach an ending to a stem, applying boundary sound changes.

    * t/d + i + back vowel -> č/dž   (mat+iau -> mačiau, med+io -> medžio)
    * future -s-: s/z + s -> s, š/ž + s -> š   (neš+siu -> nešiu, vež+s -> veš)
    * imperative -k-: g/k + k -> k   (bėg+k -> bėk)
    * after j the softness i is not written (atvej+ių -> atvejų, rugsėj+io -> rugsėjo)
    """
    if not stem:
        return ending
    if stem[-1] == "j" and len(ending) >= 2 and ending[0] == "i" and ending[1] in BACK_VOWELS:
        ending = ending[1:]
    if len(ending) >= 2 and ending[0] == "i" and ending[1] in BACK_VOWELS:
        if stem.endswith("t"):
            stem = stem[:-1] + "č"
        elif stem.endswith("d"):
            stem = stem[:-1] + "dž"
    if verb and ending[:1] == "s" and stem[-1] in "sšzž":
        stem = stem[:-1] + ("š" if stem[-1] in "šž" else "s")
        ending = ending[1:]
    if verb and ending[:1] == "k" and stem[-1] in "gk":
        stem = stem[:-1]
    return stem + ending


def underlying(stem: str) -> str:
    """Undo the č/dž softening to recover an underlying t/d stem."""
    if stem.endswith("dž"):
        return stem[:-2] + "d"
    if stem.endswith("č"):
        return stem[:-1] + "t"
    return stem
