"""Count word pairs in the training text (eval/training.py: the Wikipedia dump, else corpus/freq,
plus the conversational text times --conv-weight; never a test set) -> data/bigrams.tsv

Words as the keyboard sees them (runs of letters, lowercased); "<s>" starts a sentence. First
the words seen MIN+ times "<TAB>WORD<TAB>N"; then for every previous word: one line "PREV<TAB><TAB>TOTAL<TAB>DISTINCT" (all its pairs, for smoothing),
then its pairs seen at least MIN times "PREV<TAB>WORD<TAB>N". `python3 -m varnele export` puts
them into varnele.bin for the keyboard's language model (`P(word | previous word)`, backing off
to word frequency). Sentences of reference boilerplate (archive links) are left out.

    python3 eval/build_ngrams.py [--min 10] [--conv-weight W]
"""
import argparse
import collections
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "eval"))
from training import CONV_WEIGHT, conversational, texts  # noqa: E402

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
    ap.add_argument("--min", type=int, default=10, help="pairs seen fewer times are left out (5: +3.5 MB, +0.4 points swipe)")
    ap.add_argument("--conv-weight", type=float, default=CONV_WEIGHT, help="a conversational pair counts this many")
    a = ap.parse_args()
    ids = {START: 0}       # words as numbers: tens of millions of pairs fit in memory

    def count(source):
        pairs = collections.Counter()
        for text in source:
            for words in sentences(text):
                prev = 0
                for w in words:
                    i = ids.setdefault(w, len(ids))
                    pairs[prev << 32 | i] += 1
                    prev = i
        return pairs

    pairs = count(texts())
    seen = pairs.copy()      # --min applies to how often a pair was really seen, not to its weight:
    if a.conv_weight:        # a subtitle pair seen once never ships
        conv = count(conversational())
        for k, n in conv.items():
            seen[k] += n
            pairs[k] += round(a.conv_weight * n)
        print(f"conversational: {len(conv):,} pairs, {sum(conv.values()):,} tokens, weight {a.conv_weight}", file=sys.stderr)
    word = list(ids)
    total, distinct, kept = collections.Counter(), collections.Counter(), collections.defaultdict(list)
    for k, n in pairs.items():
        v, w = word[k >> 32], word[k & 0xFFFFFFFF]
        total[v] += n
        distinct[v] += 1
        if seen[k] >= a.min:
            kept[v].append((w, n))
    words = collections.Counter()
    for k, n in pairs.items():
        words[word[k & 0xFFFFFFFF]] += n
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
