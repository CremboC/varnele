"""Count word pairs in corpus/freq (never the test set) -> data/bigrams.tsv

Words as the keyboard sees them (runs of letters, lowercased); "<s>" starts a sentence. First
the words seen MIN+ times "<TAB>WORD<TAB>N"; then for every previous word: one line "PREV<TAB><TAB>TOTAL<TAB>DISTINCT" (all its pairs, for smoothing),
then its pairs seen at least MIN times "PREV<TAB>WORD<TAB>N". `python3 -m varnele export` puts
them into varnele.bin for the keyboard's language model (`P(word | previous word)`, backing off
to word frequency). Sentences of reference boilerplate (archive links) are left out.

    python3 eval/build_ngrams.py [--min 2]
"""
import argparse
import collections
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
WORD = re.compile(r"[^\W\d_]+")
SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n+")
START = "<s>"
BOILERPLATE = ("Wayback Machine", "Nuoroda tikrinta", "Archyvuota kopija")


def sentences(text):
    for s in SENTENCE_END.split(text):
        if any(b in s for b in BOILERPLATE):
            continue
        words = [w.lower() for w in WORD.findall(s)]
        if words:
            yield words


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min", type=int, default=2)
    a = ap.parse_args()
    pairs = collections.Counter()
    for p in sorted((ROOT / "corpus" / "freq").glob("*.txt")):
        lines = p.read_text("utf-8").splitlines()[2:]   # title, blank line
        text = "\n".join(l for l in lines if "\\displaystyle" not in l and "{\\" not in l)
        for words in sentences(text):
            prev = START
            for w in words:
                pairs[prev, w] += 1
                prev = w
    total, distinct, kept = collections.Counter(), collections.Counter(), collections.defaultdict(list)
    for (v, w), n in pairs.items():
        total[v] += n
        distinct[v] += 1
        if n >= a.min:
            kept[v].append((w, n))
    words = collections.Counter()
    for (v, w), n in pairs.items():
        words[w] += n
    with open(ROOT / "data" / "bigrams.tsv", "w") as f:
        for w, n in sorted(words.items(), key=lambda wn: (-wn[1], wn[0])):
            if n >= a.min:
                f.write(f"\t{w}\t{n}\n")
        for v in sorted(kept, key=lambda v: (-total[v], v)):
            f.write(f"{v}\t\t{total[v]}\t{distinct[v]}\n")
            for w, n in sorted(kept[v], key=lambda wn: (-wn[1], wn[0])):
                f.write(f"{v}\t{w}\t{n}\n")
    n_kept = sum(len(ws) for ws in kept.values())
    print(f"{len(pairs):,} pairs, {n_kept:,} seen {a.min}+ times, {sum(pairs.values()):,} tokens", file=sys.stderr)


if __name__ == "__main__":
    main()
