"""Sentence-level diacritic restoration.

Take real sentences, strip every diacritic ("Grįžau prieš porą dienų" ->
"Grizau pries pora dienu"), run the checker, accept the top suggestion for
every flagged word, and count how many words come back exactly right.

    python3 eval/restore.py [--sentences N] [--show K]

Only words the checker accepts in the original text are scored, so names and
foreign words it doesn't know don't distort the result.
"""

import argparse
import pathlib
import random
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from varnele.__main__ import Checker  # noqa: E402

STRIP = str.maketrans("ąčęėįšųūžĄČĘĖĮŠŲŪŽ", "aceeisuuzACEEISUUZ")
WORD = re.compile(r"[^\W\d_]+")
FIX_RULES = {"unknown", "case", "agreement", "quantity", "context", "valency"}


def sentences(corpus):
    for p in sorted(pathlib.Path(corpus).glob("*.txt")):
        text = " ".join(l for l in p.read_text("utf-8").splitlines()[2:]
                        if l.strip() and "\\displaystyle" not in l and "{\\" not in l)
        for s in re.split(r"(?<=[.!?])\s+", text):
            words = WORD.findall(s)
            if 6 <= len(words) <= 40 and any(c in s for c in "ąčęėįšųūž"):
                yield s


def restore(ck, text, grammar):
    out = list(text)
    for f in ck.check_text(text, grammar=grammar):
        if f.rule in FIX_RULES and f.suggestions and len(f.suggestions[0]) == f.end - f.start:
            out[f.start:f.end] = f.suggestions[0]
    return "".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sentences", type=int, default=400)
    ap.add_argument("--show", type=int, default=6)
    ap.add_argument("--corpus", default=str(ROOT / "corpus" / "test"))
    a = ap.parse_args()

    ck = Checker()
    pool = list(sentences(a.corpus))
    sample = random.Random(3).sample(pool, min(a.sentences, len(pool)))
    stats = {g: {"words": 0, "need": 0, "fixed": 0, "broken": 0, "exact": 0} for g in (False, True)}
    examples = []
    for s in sample:
        stripped = s.translate(STRIP)
        known = {m.start() for m in WORD.finditer(s) if ck.check_word(m.group())[0] != "unknown"}
        for g in (False, True):
            r = restore(ck, stripped, g)
            st = stats[g]
            ok_all = True
            for m in WORD.finditer(s):
                if m.start() not in known:
                    continue
                orig, got = m.group(), r[m.start():m.end()]
                st["words"] += 1
                if orig != stripped[m.start():m.end()]:
                    st["need"] += 1
                    st["fixed"] += got == orig
                elif got != orig:
                    st["broken"] += 1
                ok_all &= got == orig
            st["exact"] += ok_all
            if g and not ok_all and len(examples) < a.show:
                examples.append((s, r))

    n = len(sample)
    print(f"{n} sentences with all diacritics removed\n")
    print(f"{'':28s}{'words only':>14s}{'+ context rules':>18s}")
    rows = [("words needing a diacritic", lambda st: f"{st['need']}"),
            ("  restored correctly", lambda st: f"{st['fixed'] / st['need']:.1%}"),
            ("correct words changed", lambda st: f"{st['broken']}"),
            ("all words right", lambda st: f"{(st['words'] - st['need'] + st['fixed'] - st['broken']) / st['words']:.1%}"),
            ("whole sentence right", lambda st: f"{st['exact'] / n:.1%}")]
    for name, fn in rows:
        print(f"{name:28s}{fn(stats[False]):>14s}{fn(stats[True]):>18s}")
    if examples:
        print("\nsentences still not fully restored:")
        for s, r in examples:
            diff = [f"{x}→{y}" for x, y in zip(WORD.findall(r), WORD.findall(s)) if x != y]
            print(f"  wanted: {s[:110]}\n  missed: {', '.join(diff[:8])}")


if __name__ == "__main__":
    main()
