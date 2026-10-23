"""Verb valency: which case the noun phrase next to each verb has, counted on the training text
(eval/training.py: the Wikipedia dump and the conversational text) -> data/valency.tsv
(VERB \\t CLASS \\t after|before \\t CASE \\t count; then `python3 -m varnele export`).

A verb is a word that is mostly a verb (not a participle or a copula); its key and class come from
Grammar.verb_keys, the phrase from Grammar.valency_phrase, the very code the `valency` rule uses.
A phrase is counted when it has exactly one case as written (mačiau gražų namą: acc; mačiau
jo namą: no phrase; matau gatve: ins). Pairs seen fewer than MIN times are left out.

    python3 eval/build_valency.py [--workers 6] [--limit N]   (N: lines per text, for a quick try)
"""

import argparse
import collections
import multiprocessing
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "eval"))
from training import conversational, texts  # noqa: E402
from varnele.__main__ import Checker  # noqa: E402
from varnele.grammar import WORD, Word, phrase_feats  # noqa: E402

MIN = 3
G = None


def count(lines):
    out = collections.Counter()
    for line in lines:
        toks = [Word(G, m.group(), m.start(), m.end()) for m in WORD.finditer(line)]
        adjacent = [i > 0 and line[toks[i - 1].end:t.start].strip() == "" for i, t in enumerate(toks)]
        for i, t in enumerate(toks):
            keys = G.verb_keys(t.text)
            if not keys:
                continue
            for after in (True, False):
                idx = G.valency_phrase(toks, adjacent, i, after, line)
                if not idx:
                    continue
                cases = {f[0] for f in phrase_feats([toks[j] for j in idx])}
                if len(cases) == 1:
                    case = cases.pop()
                    for key, cls in keys:
                        out[(key, cls, "after" if after else "before", case)] += 1
    return out


def chunks(limit):
    """Lines of the training text in pieces of 20,000 (sentences don't cross lines)."""
    for text in list(texts()) + list(conversational()):
        lines = text.splitlines()[:limit] if limit else text.splitlines()
        for k in range(0, len(lines), 20000):
            yield lines[k:k + 20000]


def main():
    global G
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    G = Checker().grammar      # loaded once, shared by the forked workers
    t0 = time.time()
    total = collections.Counter()
    with multiprocessing.get_context("fork").Pool(a.workers) as pool:
        for n, c in enumerate(pool.imap_unordered(count, chunks(a.limit)), 1):
            total.update(c)
            if n % 20 == 0:
                print(f"{n} pieces, {len(total)} pairs, {time.time() - t0:.0f} s", file=sys.stderr)
    rows = sorted((k, v) for k, v in total.items() if v >= MIN)
    (ROOT / "data" / "valency.tsv").write_text("".join("\t".join(k) + f"\t{v}\n" for k, v in rows), "utf-8")
    print(f"{len(rows)} rows (of {len(total)}) -> data/valency.tsv, {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
