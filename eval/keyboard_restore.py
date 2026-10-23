"""Diacritic restoration through the keyboard, word by word.

Same sentences and scoring as restore.py, but instead of checking the whole stripped
sentence at once, each word is typed into the keyboard model (keyboard_sim.py: autocorrect
on space, then the sentence fixer), so only the words before it are known when it is
committed. Compares the result with the checker's restoration of the same sentences.

    python3 eval/keyboard_restore.py [--sentences N] [--show K]
"""

import argparse
import collections
import pathlib
import random
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "eval"))

from restore import STRIP, WORD, restore, sentences  # noqa: E402
from keyboard_sim import type_text  # noqa: E402
from varnele.__main__ import Checker  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sentences", type=int, default=300)
    ap.add_argument("--show", type=int, default=25)
    ap.add_argument("--corpus", default=str(ROOT / "corpus" / "test"))
    ap.add_argument("--no-soft", action="store_true", help="the sentence fixer leaves autocorrect's diacritics alone")
    a = ap.parse_args()

    ck = Checker()
    pool = list(sentences(a.corpus))
    sample = random.Random(3).sample(pool, min(a.sentences, len(pool)))   # the same as restore.py
    names = ("checker", "keyboard")
    stats = {n: collections.Counter() for n in names}
    only = {n: collections.Counter() for n in names}     # (stripped -> wanted) one gets right, the other not
    changed = {n: [] for n in names}                     # correct words changed
    missed = collections.Counter()                       # what the keyboard still gets wrong
    skipped = 0
    for s in sample:
        stripped = s.translate(STRIP)
        out = {"checker": restore(ck, stripped, True), "keyboard": type_text(stripped, soft=not a.no_soft)}
        words = WORD.findall(s)
        got = {n: WORD.findall(r) for n, r in out.items()}
        if any(len(g) != len(words) for g in got.values()):
            skipped += 1     # a word was split or merged: not comparable word by word
            continue
        known = [ck.check_word(w)[0] != "unknown" for w in words]
        for n in names:
            exact = True
            for k, (orig, typed, res) in enumerate(zip(words, WORD.findall(stripped), got[n])):
                if not known[k]:
                    continue
                st = stats[n]
                st["words"] += 1
                if orig != typed:
                    st["need"] += 1
                    st["fixed"] += res == orig
                elif res != orig:
                    st["broken"] += 1
                    changed[n].append(f"{orig}→{res} | {stripped[:90]}")
                exact &= res == orig
            stats[n]["exact"] += exact
        for k, (orig, typed) in enumerate(zip(words, WORD.findall(stripped))):
            if known[k] and orig != typed:
                ok = {n: got[n][k] == orig for n in names}
                if not ok["keyboard"]:
                    kind = "left as typed" if got["keyboard"][k] == typed else "changed to another word"
                    missed[kind] += 1
                for n, other in (names, names[::-1]):
                    if ok[n] and not ok[other]:
                        only[n][f"{typed}→{orig} ({other}: {got[other][k]})"] += 1

    n = len(sample) - skipped
    print(f"{n} sentences with all diacritics removed ({skipped} skipped: words split or merged)\n")
    print(f"{'':28s}{'checker':>12s}{'keyboard':>12s}")
    rows = [("words needing a diacritic", lambda st: f"{st['need']}"),
            ("  restored correctly", lambda st: f"{st['fixed'] / st['need']:.1%}"),
            ("correct words changed", lambda st: f"{st['broken']}"),
            ("all words right", lambda st: f"{(st['words'] - st['need'] + st['fixed'] - st['broken']) / st['words']:.1%}"),
            ("whole sentence right", lambda st: f"{st['exact'] / n:.1%}")]
    for name, fn in rows:
        print(f"{name:28s}{fn(stats['checker']):>12s}{fn(stats['keyboard']):>12s}")
    print(f"\nkeyboard misses: {dict(missed)}")
    for n_ in names:
        for c in changed[n_]:
            print(f"correct word changed by the {n_}: {c}")
    for n_ in names:
        print(f"\nright only with the {n_} ({sum(only[n_].values())}):")
        for w, c in only[n_].most_common(a.show):
            print(f"  {c}× {w}")


if __name__ == "__main__":
    main()
