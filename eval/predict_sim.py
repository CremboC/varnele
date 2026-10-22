"""Next-word prediction: how often the word about to be typed is among the keyboard's top 3.

restore.py's 300 test sentences, each with the article text before it (as the paragraph the
user has written). At every word: is it among the 3 predictions before any letter is typed,
and after its first letter (typed without diacritics)? Lowercase comparison; words with
digits are skipped.

    python3 eval/predict_sim.py [--sentences N] [--no-paragraph] [--raw-lm]

--ghost also measures the strip's ghost: after each letter typed (without diacritics), is a ghost
shown, is its first word the word being typed, and how many letters would tapping the first right
ghost have saved (a tap counts as one key)?

Predictions are the keyboard's (names capitalised, unknown tokens left out); --raw-lm asks
the bare language model instead.
"""

import argparse
import collections
import json
import pathlib
import random
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "eval"))

from restore import STRIP, sentences  # noqa: E402
import keyboard_sim  # noqa: E402
from keyboard_sim import _ask  # noqa: E402
from swipe_sim import preceding  # noqa: E402


def predict(context, prefix, n=3):
    context = context.replace("\t", " ").replace("\n", " ")[-1500:]
    return [p["w"].lower() for p in json.loads(_ask(f"predict\t{context}\t{prefix}\t{n}").readline())]


def ghost(context, typed):
    context = context.replace("\t", " ").replace("\n", " ")[-1500:]
    return json.loads(_ask(f"ghost\t{context}\t{typed}").readline())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sentences", type=int, default=300)
    ap.add_argument("--no-paragraph", action="store_true")
    ap.add_argument("--corpus", default=str(ROOT / "corpus" / "test"))
    ap.add_argument("--raw-lm", action="store_true")
    ap.add_argument("--ghost", action="store_true")
    a = ap.parse_args()
    if a.raw_lm:
        keyboard_sim.SERVE.append("--raw-lm")
    pool = list(sentences(a.corpus))
    sample = random.Random(3).sample(pool, min(a.sentences, len(pool)))   # the same as restore.py
    before = {} if a.no_paragraph else preceding(a.corpus, sample)
    st = collections.Counter()
    for s in sample:
        for m in re.finditer(r"[^\W\d_]+", s):
            w = m.group().lower()
            context = (before.get(s, "") + " " + s[:m.start()]).strip()
            st["words"] += 1
            st["0 letters"] += w in predict(context, "")
            if len(w) > 1:
                st["1 letter, words"] += 1
                st["1 letter"] += w in predict(context, w[0].translate(STRIP))
            if a.ghost and len(w) > 2:
                st["ghost words"] += 1
                st["ghost letters"] += len(w)
                for k in range(1, len(w)):
                    g = ghost(context, w[:k].translate(STRIP))
                    if not g:
                        continue
                    st["ghost shown"] += 1
                    if g.split()[0].lower() == w:
                        st["ghost right"] += 1
                        st["ghost words done"] += 1
                        st["ghost saved"] += len(w) - k - 1
                        break
    pct = lambda x, n: f"{100 * x / max(n, 1):.1f}%"
    print(f"{st['words']} words; next word among the top 3: before typing {pct(st['0 letters'], st['words'])}, "
          f"after one letter {pct(st['1 letter'], st['1 letter, words'])}")
    if a.ghost:
        print(f"ghost: {st['ghost shown']} shown up to the right one, right {pct(st['ghost right'], st['ghost shown'])}; "
              f"{pct(st['ghost words done'], st['ghost words'])} of the {st['ghost words']} words of 3+ letters "
              f"completed by it, {pct(st['ghost saved'], st['ghost letters'])} of their letters saved")


if __name__ == "__main__":
    main()
