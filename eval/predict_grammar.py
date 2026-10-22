"""Do the keyboard's predictions respect the grammar? Top 3 next words after a preposition,
an adjective, or a preposition + adjective, judged by the Python analyzer (independent of the
Rust code that steers them).

A prediction violates the grammar when every reading of it has a case and none fits: after a
preposition none of its cases (`į šiaurės`), after an adjective none agrees with it in case,
number and gender and none is a genitive (a modifier may come first: `geras Lietuvos
krepšininkas`). Words with a caseless reading (`per daug`, `apie tai`) are never violations.

    python3 eval/predict_grammar.py [--corpus DIR] [--no-paragraph] [--bin PATH]

First a fixed list of contexts with their top 3, then every such position in restore.py's
300 test sentences of the corpus: how often the typed word is in the top 3, and how many of
the top-3 predictions violate.
"""

import argparse
import collections
import pathlib
import random
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "eval"))

from restore import sentences  # noqa: E402
import keyboard_sim  # noqa: E402
from predict_sim import predict  # noqa: E402
from swipe_sim import preceding  # noqa: E402
from varnele.analyzer import Analyzer  # noqa: E402
from varnele.grammar import PREPOSITIONS, readings  # noqa: E402
from varnele.index import Index  # noqa: E402

CONTEXTS = [
    "Ar nori eiti į", "Rytoj važiuosime į", "Jis atėjo be", "Pasikalbėkime apie", "Ar eisi su",
    "Gyvenu prie", "Grįžau iš", "Laukiu nuo", "Mes važiavome per", "Tai buvo prieš",
    "Ar nori eiti į gražią", "Važiuojam su nauja", "Sėdėjau prie didelio", "Mačiau gražų",
    "Tai labai geras", "Nupirkau naują", "Ten gyvena daug", "Kalbėjome apie tą",
]

AN = None


def analyses(w):
    a = AN.analyze(w)
    return a or AN.analyze(w.capitalize())


def adjective(w):
    """Readings of a word that is only an adjective (gražią, naujo), else None."""
    an = analyses(w)
    if not an or any(a.tag.split(".")[0] != "A" for a in an):
        return None
    return [r for r in readings(an) if r.case != "voc"] or None


def requirement(context):
    """(prep cases or None, adjective readings or None) of the last words, if any."""
    words = re.findall(r"[^\W\d_]+|[^\w\s]", context.lower())
    if not words or not words[-1].isalpha():
        return None
    if words[-1] in PREPOSITIONS:
        return PREPOSITIONS[words[-1]], None
    adj = adjective(words[-1])
    if adj is None:
        return None
    cases = PREPOSITIONS.get(words[-2]) if len(words) > 1 else None
    if cases:
        adj = [r for r in adj if r.case in cases]
        return (cases, None) if adj else None
    return None, adj


def violates(req, w):
    cases, adj = req
    an = analyses(w)
    if not an or any(not readings([a]) for a in an):
        return False
    rs = readings(an)
    if cases:
        return not any(r.case in cases for r in rs)
    same = lambda x, y: x is None or y is None or x == y
    return not any(r.case == "gen" or any(r.case == a.case and same(r.number, a.number) and same(r.gender, a.gender)
                                          for a in adj) for r in rs)


def kind(req):
    return "after an adjective" if req[0] is None else "after a preposition"


def main():
    global AN
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default=str(ROOT / "corpus" / "test"))
    ap.add_argument("--no-paragraph", action="store_true")
    ap.add_argument("--sentences", type=int, default=300)
    ap.add_argument("--bin", help="another varnele binary (a baseline build)")
    a = ap.parse_args()
    if a.bin:
        keyboard_sim.RUST[0] = a.bin
    AN = Analyzer(Index.load())

    for c in CONTEXTS:
        req = requirement(c)
        top = predict(c + " ", "")
        marks = [w + ("✗" if req and violates(req, w) else "") for w in top]
        print(f"{c:28} {' '.join(marks)}")

    pool = list(sentences(a.corpus))
    sample = random.Random(3).sample(pool, min(a.sentences, len(pool)))   # the same as restore.py
    before = {} if a.no_paragraph else preceding(a.corpus, sample)
    st = collections.Counter()
    for s in sample:
        for m in re.finditer(r"[^\W\d_]+", s):
            req = requirement(s[:m.start()])
            if not req or not s[:m.start()].endswith(" "):
                continue
            k = kind(req)
            context = (before.get(s, "") + " " + s[:m.start()]).strip() + " "
            top = predict(context, "")
            st[k] += 1
            st[k + " right"] += m.group().lower() in top
            st[k + " predictions"] += len(top)
            st[k + " violations"] += sum(violates(req, w) for w in top)
    print()
    for k in ("after a preposition", "after an adjective"):
        n = st[k]
        print(f"{k}: {n} words, top 3 right {100 * st[k + ' right'] / max(n, 1):.1f}%, "
              f"{st[k + ' violations']} of {st[k + ' predictions']} predictions violate")


if __name__ == "__main__":
    main()
