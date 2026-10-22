"""Next-word prediction: how often the word about to be typed is among the keyboard's top 3.

restore.py's 300 test sentences, each with the article text before it (as the paragraph the
user has written). At every word: is it among the 3 predictions before any letter is typed,
and after its first letter (typed without diacritics)? Lowercase comparison; words with
digits are skipped.

    python3 eval/predict_sim.py [--sentences N] [--no-paragraph] [--raw-lm]

--ghost also measures the strip's ghost: after each letter typed (without diacritics), is a ghost
shown, is its first word the word being typed, and how many letters would tapping the first right
ghost have saved (a tap counts as one key)? And the next word the ghost appends after the
completion: when the first right ghost is tapped, how often would a next word appended at
P >= each of NEXT_P be the word that follows (with only a space or a comma between: the sentence
fixer adds the comma of `maniau, kad`)?

Predictions are the keyboard's (names capitalised, unknown tokens left out); --raw-lm asks
the bare language model instead.

--learn simulates the user model learned on the phone (swipe_sim.Learner): the sentences are
measured in corpus order, and before each one the model has learned all the test set's text
before it (as if the user wrote the whole test set in order: earlier text teaches the later).
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
from swipe_sim import Learner, preceding  # noqa: E402


def predict(context, prefix, n=3):
    context = context.replace("\t", " ").replace("\n", " ")[-1500:]
    return [p["w"].lower() for p in json.loads(_ask(f"predict\t{context}\t{prefix}\t{n}").readline())]


NEXT_P = (0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2)


def ghost(context, typed):
    """The ghost's completion, and its likeliest next word with P (shown at P >= 0.5)."""
    context = context.replace("\t", " ").replace("\n", " ")[-1500:]
    return json.loads(_ask(f"ghostnext\t{context}\t{typed}").readline())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sentences", type=int, default=300)
    ap.add_argument("--no-paragraph", action="store_true")
    ap.add_argument("--corpus", default=str(ROOT / "corpus" / "test"))
    ap.add_argument("--raw-lm", action="store_true")
    ap.add_argument("--ghost", action="store_true")
    ap.add_argument("--learn", action="store_true", help="the user model learns the text before each sentence")
    a = ap.parse_args()
    if a.raw_lm:
        keyboard_sim.SERVE.append("--raw-lm")
    pool = list(sentences(a.corpus))
    sample = random.Random(3).sample(pool, min(a.sentences, len(pool)))   # the same as restore.py
    before = {} if a.no_paragraph else preceding(a.corpus, sample)
    st = collections.Counter()
    learner = Learner(a.corpus, sample, _ask) if a.learn else None
    if learner:
        sample = learner.order
    for s in sample:
        if learner:
            learner.before(s)
        ms = list(re.finditer(r"[^\W\d_]+", s))
        for i, m in enumerate(ms):
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
                    if not g["w"]:
                        continue
                    st["ghost shown"] += 1
                    if g["w"].lower() == w:
                        st["ghost right"] += 1
                        st["ghost words done"] += 1
                        st["ghost saved"] += len(w) - k - 1
                        follows = i + 1 < len(ms) and s[m.end():ms[i + 1].start()].strip() in ("", ",")
                        for t in NEXT_P:
                            if g["next"] and g["p"] >= t:
                                st[f"next {t}"] += 1
                                st[f"next {t} right"] += follows and g["next"].lower() == ms[i + 1].group().lower()
                        break
        if learner:
            learner.after(s)
    pct = lambda x, n: f"{100 * x / max(n, 1):.1f}%"
    print(f"{st['words']} words; next word among the top 3: before typing {pct(st['0 letters'], st['words'])}, "
          f"after one letter {pct(st['1 letter'], st['1 letter, words'])}")
    if a.learn:
        print(f"learned {learner.chars} characters of text")
    if a.ghost:
        print(f"ghost: {st['ghost shown']} shown up to the right one, right {pct(st['ghost right'], st['ghost shown'])}; "
              f"{pct(st['ghost words done'], st['ghost words'])} of the {st['ghost words']} words of 3+ letters "
              f"completed by it, {pct(st['ghost saved'], st['ghost letters'])} of their letters saved")
        print("next word appended at P >= " + ", ".join(
            f"{t}: {st[f'next {t}']} ({pct(st[f'next {t}'], st['ghost words done'])} of the taps), "
            f"{pct(st[f'next {t} right'], st[f'next {t}'])} right" for t in NEXT_P))


if __name__ == "__main__":
    main()
