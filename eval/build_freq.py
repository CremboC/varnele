"""Count word frequencies in corpus/freq (never the test set) -> data/freq.tsv"""
import collections
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from varnele.__main__ import tokens  # noqa: E402

c = collections.Counter()
for p in (ROOT / "corpus" / "freq").glob("*.txt"):
    c.update(w.lower() for w, _ in tokens(p.read_text("utf-8")))
with open(ROOT / "data" / "freq.tsv", "w") as f:
    for w, n in c.most_common():
        if n >= 2:
            f.write(f"{w}\t{n}\n")
print(f"{len(c):,} word types, {sum(c.values()):,} tokens", file=sys.stderr)

# lemma frequencies: every form counts toward its lemma(s), except that a listed
# particle/preposition reading takes it all: "iš" must not make the verb ižti common
from varnele.analyzer import Analyzer  # noqa: E402
an = Analyzer()
lemmas = collections.Counter()
for w, n in c.items():
    analyses = an.analyze(w)
    listed = [a for a in analyses if a.tag == "W"]
    for lemma in {a.lemma.lower() for a in (listed or analyses)}:
        lemmas[lemma] += n
with open(ROOT / "data" / "lemma_freq.tsv", "w") as f:
    for w, n in lemmas.most_common():
        f.write(f"{w}\t{n}\n")
print(f"{len(lemmas):,} lemmas", file=sys.stderr)
