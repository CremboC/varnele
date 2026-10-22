"""Count word pairs and triples in the training text (eval/training.py: the Wikipedia dump, else
corpus/freq, plus the conversational text times --conv-weight; never a test set) -> data/bigrams.tsv,
data/trigrams.tsv

Words as the keyboard sees them (runs of letters, lowercased); "<s>" starts a sentence. First
the words seen MIN+ times "<TAB>WORD<TAB>N"; then for every previous word: one line "PREV<TAB><TAB>TOTAL<TAB>DISTINCT" (all its pairs, for smoothing),
then its pairs seen at least MIN times "PREV<TAB>WORD<TAB>N". `python3 -m varnele export` puts
them into varnele.bin for the keyboard's language model (`P(word | previous word)`, backing off
to word frequency). data/trigrams.tsv is the same for two previous words "A B" (`P(word | A B)`,
backing off to the pairs): "A B<TAB><TAB>TOTAL<TAB>DISTINCT", then "A B<TAB>WORD<TAB>N" for the
triples seen MIN+ times, only for the "A B" that have one. Sentences of reference boilerplate
(archive links) are left out.

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
    ids = {START: 0}       # words as numbers: tens of millions of pairs and triples fit in memory

    def count(source):
        pairs, triples = collections.Counter(), collections.Counter()
        for text in source:
            for words in sentences(text):
                prev2, prev = None, 0
                for w in words:
                    i = ids.setdefault(w, len(ids))
                    pairs[prev << 32 | i] += 1
                    if prev2 is not None:
                        triples[(prev2 << 32 | prev) << 32 | i] += 1
                    prev2, prev = prev, i
        return pairs, triples

    pairs, triples = count(texts())
    seen, seen3 = pairs.copy(), triples.copy()  # --min applies to how often a pair was really seen,
    if a.conv_weight:                           # not to its weight: a subtitle pair seen once never ships
        conv, conv3 = count(conversational())
        for have, have_seen, new in ((pairs, seen, conv), (triples, seen3, conv3)):
            for k, n in new.items():
                have_seen[k] += n
                have[k] += round(a.conv_weight * n)
        print(f"conversational: {len(conv):,} pairs, {len(conv3):,} triples, {sum(conv.values()):,} tokens, "
              f"weight {a.conv_weight}", file=sys.stderr)
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
    del pairs, seen, kept

    total, distinct, kept = collections.Counter(), collections.Counter(), collections.defaultdict(list)
    for k, n in triples.items():
        v = k >> 32
        total[v] += n
        distinct[v] += 1
        if seen3[k] >= a.min:
            kept[v].append((word[k & 0xFFFFFFFF], n))
    name = lambda v: f"{word[v >> 32]} {word[v & 0xFFFFFFFF]}"
    with open(ROOT / "data" / "trigrams.tsv", "w") as f:
        for v in sorted(kept, key=lambda v: (-total[v], name(v))):
            f.write(f"{name(v)}\t\t{total[v]}\t{distinct[v]}\n")
            for w, n in sorted(kept[v], key=lambda wn: (-wn[1], wn[0])):
                f.write(f"{name(v)}\t{w}\t{n}\n")
    n_kept = sum(len(ws) for ws in kept.values())
    print(f"{len(triples):,} triples, {n_kept:,} seen {a.min}+ times after {len(kept):,} word pairs", file=sys.stderr)


if __name__ == "__main__":
    main()
