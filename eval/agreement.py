"""Agreement inside a noun phrase, on text with one word of a phrase broken.

Every run of two modifiers and a noun that agree (lowercase, no noun reading on the modifiers:
`kitą didelį namą`) is broken in one word, two ways:

    diacritics  the word typed without its diacritics, when that is another valid word
                (vieną -> viena, sagutę -> sagute): what the keyboard sees before autocorrect
    case        a modifier in another case of the same number and gender (nukritusi -> nukritusią,
                nominative <-> accusative, others -> nominative): a slip no diacritic restores

The checker runs on the sentence. For the broken word: fixed (the original is the first
suggestion), wrong fix (flagged, another first suggestion), missed. "Others changed" counts
flags on the phrase's other words that the unbroken sentence did not have.

    python3 eval/agreement.py [DIR...] [--max N] [--show]
"""

import collections
import pathlib
import random
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from varnele.__main__ import Checker  # noqa: E402
from varnele.grammar import WORD, retag  # noqa: E402
from varnele.phonology import fold  # noqa: E402

SENTENCE = re.compile(r"(?<=[.!?])\s+")


def features(an, w):
    """(pos, case, number, gender) of each reading: pos N or M (modifier)."""
    out = set()
    for a in an.analyze(w):
        p = a.tag.split(".")
        case = next((x for x in p if x in ("nom", "gen", "dat", "acc", "ins", "loc")), None)
        if not case:
            continue
        num = "sg" if "sg" in p else "pl" if "pl" in p else None
        gen = "m" if "m" in p else "f" if "f" in p else None
        if p[0] == "N":
            out.add(("N", case, num, gen))
        elif p[0] in ("A", "P") or p[0] == "V" and p[1].startswith("p"):
            out.add(("M", case, num, gen))
    return out


def shared(fs):
    """Features all three words share (modifier, modifier, noun)."""
    def fit(r, c):
        return r[1] == c[0] and r[2] in (None, c[1]) and r[3] in (None, c[2])
    cands = {(r[1], r[2], r[3]) for r in fs[2] if r[0] == "N"}
    return [c for c in cands if all(any(r[0] == "M" and fit(r, c) for r in f) for f in fs[:2])]


def phrases(an, sentence):
    toks = list(WORD.finditer(sentence))
    for i in range(len(toks) - 2):
        three = toks[i:i + 3]
        if any(sentence[a.end():b.start()].strip() for a, b in zip(three, three[1:])):
            continue
        words = [t.group() for t in three]
        if not all(w.islower() for w in words):
            continue
        fs = [features(an, w) for w in words]
        if not all(fs) or any(r[0] == "N" for f in fs[:2] for r in f) or not any(r[0] == "N" for r in fs[2]):
            continue
        feats = shared(fs)
        if len(feats) == 1:
            yield three, feats[0]


def broken(ck, word, pos, feats, kind):
    if kind == "diacritics":
        f = fold(word)
        return f if f != word and ck.an.analyze(f) else None
    if pos == 2:
        return None
    case, num, gen = feats
    want = {"nom": "acc", "acc": "nom"}.get(case, "nom")
    for a in ck.an.analyze(word):
        p = a.tag.split(".")
        if case in p and (p[0] in ("A", "P") or p[0] == "V" and p[1].startswith("p")):
            for f in ck.grammar.inflect(a, retag(a.tag, case=want)):
                if f != word and f.islower():
                    return f
    return None


def main():
    args = sys.argv[1:]
    limit = int(args[args.index("--max") + 1]) if "--max" in args else 2000
    dirs = [a for i, a in enumerate(args) if not a.startswith("--") and (i == 0 or args[i - 1] != "--max")]
    ck = Checker()
    cases = []
    for d in dirs or ["corpus/test"]:
        for p in sorted(pathlib.Path(d).glob("*.txt")):
            for line in p.read_text(errors="ignore").splitlines():
                if "\\displaystyle" in line or "{\\" in line:
                    continue
                for s in SENTENCE.split(line):
                    for three, feats in phrases(ck.an, s):
                        cases.append((s, three, feats))
    random.Random(1).shuffle(cases)
    cases = cases[:limit]
    tally = collections.defaultdict(collections.Counter)
    for s, three, feats in cases:
        before = {f.start for f in ck.check_text(s)}
        for kind in ("diacritics", "case"):
            for pos, t in enumerate(three):
                bad = broken(ck, t.group(), pos, feats, kind)
                if not bad:
                    continue
                text = s[:t.start()] + bad + s[t.end():]
                shift = len(bad) - len(t.group())
                flags = {f.start: f for f in ck.check_text(text)}
                key = (kind, ["modifier 1", "modifier 2", "noun"][pos])
                f = flags.get(t.start())
                res = ("fixed" if f and f.suggestions and f.suggestions[0].lower() == t.group().lower()
                       else "wrong fix" if f else "missed")
                tally[key][res] += 1
                others = [u for u in three if u is not t]
                if any(o.start() + (shift if o.start() > t.start() else 0) in flags and o.start() not in before
                       for o in others):
                    tally[key]["others changed"] += 1
                if "--show" in args and res != "missed":
                    print(res.upper(), kind, "|", " ".join(u.group() for u in three), "->", bad, "|",
                          f.suggestions[:2] if f else "")
    cols = ("fixed", "wrong fix", "missed", "others changed")
    print(f"{len(cases)} phrases")
    print(f"{'broken word':28}" + "".join(f"{c:>15}" for c in cols))
    for key in sorted(tally):
        print(f"{' '.join(key):28}" + "".join(f"{tally[key][c]:15}" for c in cols))


if __name__ == "__main__":
    main()
