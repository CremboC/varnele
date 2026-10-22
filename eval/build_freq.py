"""Count word frequencies in the training text (eval/training.py: the Wikipedia dump, else
corpus/freq; never the test set) -> data/freq.tsv, data/lemma_freq.tsv

A word before a full stop counts as itself (the tokenizer yields "metais." for abbreviations).

    python3 eval/build_freq.py [--min N]
"""
import argparse
import collections
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "eval"))
from varnele.__main__ import tokens  # noqa: E402
from training import texts  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--min", type=int, default=10, help="words seen fewer times are left out (10: smaller data, same results as 2)")
a = ap.parse_args()

c = collections.Counter()
for t in texts():
    c.update(w.lower().rstrip(".") for w, _ in tokens(t))
c.pop("", None)
kept = [(w, n) for w, n in c.most_common() if n >= a.min]
with open(ROOT / "data" / "freq.tsv", "w") as f:
    for w, n in kept:
        f.write(f"{w}\t{n}\n")
print(f"{len(c):,} word types, {sum(c.values()):,} tokens, {len(kept):,} kept", file=sys.stderr)

# lemma frequencies: every form counts toward its lemma(s), except that a listed
# particle/preposition reading takes it all: "iš" must not make the verb ižti common
from varnele.analyzer import Analyzer  # noqa: E402
an = Analyzer()
lemmas = collections.Counter()
for w, n in kept:
    analyses = an.analyze(w)
    listed = [a for a in analyses if a.tag == "W"]
    for lemma in {a.lemma.lower() for a in (listed or analyses)}:
        lemmas[lemma] += n
with open(ROOT / "data" / "lemma_freq.tsv", "w") as f:
    for w, n in lemmas.most_common():
        f.write(f"{w}\t{n}\n")
print(f"{len(lemmas):,} lemmas", file=sys.stderr)
