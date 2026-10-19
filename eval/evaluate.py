"""Compare varnele against Hunspell lt_LT on real Lithuanian text.

Run with the venv (it has spylls, a pure-Python Hunspell):
    .venv/bin/python eval/evaluate.py [--no-hunspell] [--samples N]

1. False alarms: words in edited Wikipedia text that a checker rejects.
2. Synthetic errors: corrupt correct words the way people do (drop diacritics,
   swap i/y, typos) and measure detection and whether the right fix is offered.
"""

import argparse
import collections
import json
import pathlib
import random
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from varnele.__main__ import ABBREV, Checker, is_foreign, tokens  # noqa: E402

OUT = ROOT / "eval" / "out"
STRIP = str.maketrans("ąčęėįšųūž", "aceeisuuz")
DIACRITIC = {"ą": "a", "č": "c", "ę": "e", "ė": "e", "į": "i", "š": "s", "ų": "u", "ū": "u", "ž": "z"}
KEYB = ["qwertyuiop", "asdfghjkl", "zxcvbnm"]


def neighbours(c):
    for r, row in enumerate(KEYB):
        if c in row:
            i = row.index(c)
            return [row[j] for j in (i - 1, i + 1) if 0 <= j < len(row)] + \
                   [KEYB[rr][i] for rr in (r - 1, r + 1) if 0 <= rr < 3 and i < len(KEYB[rr])]
    return list("aeistu")


def corrupt(w, kind, rnd):
    if kind == "no_diacritics":
        s = w.translate(STRIP)
        return s if s != w else None
    if kind == "one_diacritic":
        idx = [i for i, c in enumerate(w) if c in DIACRITIC]
        if not idx:
            return None
        i = rnd.choice(idx)
        return w[:i] + DIACRITIC[w[i]] + w[i + 1:]
    if kind == "i_y":
        idx = [i for i, c in enumerate(w) if c in "iyį"]
        if not idx:
            return None
        i = rnd.choice(idx)
        return w[:i] + rnd.choice([x for x in "iyį" if x != w[i]]) + w[i + 1:]
    if kind == "typo":
        i = rnd.randrange(len(w))
        op = rnd.choice(["del", "sub", "ins", "swap"])
        if op == "del":
            return w[:i] + w[i + 1:]
        if op == "sub":
            return w[:i] + rnd.choice(neighbours(w[i])) + w[i + 1:]
        if op == "ins":
            return w[:i] + rnd.choice(neighbours(w[i])) + w[i:]
        if i < len(w) - 1:
            return w[:i] + w[i + 1] + w[i] + w[i + 2:]
        return None


class Hunspell:
    def __init__(self):
        from spylls.hunspell import Dictionary
        self.d = Dictionary.from_files(str(ROOT / "vendor/ispell-lt/build/myspell/lt_LT"))

    def ok(self, w):
        return self.d.lookup(w)

    def suggest(self, w, n=5):
        out = []
        for s in self.d.suggest(w):
            out.append(s)
            if len(out) >= n:
                break
        return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-hunspell", action="store_true")
    ap.add_argument("--samples", type=int, default=300, help="synthetic errors per error type")
    ap.add_argument("--corpus", default=str(ROOT / "corpus" / "test"))
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    ck = Checker()
    hs = None if a.no_hunspell else Hunspell()

    # ---------------- 1. false alarms on real text ----------------
    counts = collections.Counter()
    skipped = 0
    for p in sorted(pathlib.Path(a.corpus).glob("*.txt")):
        text = "\n".join(l for l in p.read_text("utf-8").splitlines()
                         if "\\displaystyle" not in l and "{\\" not in l)
        for w, _ in tokens(text):
            b = w.rstrip(".")
            if w.lower() not in ABBREV and (is_foreign(b) or (b.isupper() and len(b) > 1)):
                skipped += 1
            else:
                counts[w] += 1
    total = sum(counts.values())
    res = {"articles": len(list(pathlib.Path(a.corpus).glob("*.txt"))),
           "tokens_checked": total, "unique_words": len(counts), "tokens_skipped_foreign_or_caps": skipped}

    t = time.time()
    ours = {w: ck.check_word(w) for w in counts}
    res["ours_seconds_lookup"] = round(time.time() - t, 1)
    ours_bad = {w for w, (st, _) in ours.items() if st == "unknown"}
    ours_spoken = {w for w, (st, _) in ours.items() if st == "colloquial"}
    res["ours_flagged_tokens"] = sum(counts[w] for w in ours_bad)
    res["ours_flagged_unique"] = len(ours_bad)
    res["ours_flagged_lowercase_unique"] = sum(1 for w in ours_bad if w[:1].islower())
    res["ours_flagged_lowercase_tokens"] = sum(counts[w] for w in ours_bad if w[:1].islower())
    res["ours_spoken_unique"] = len(ours_spoken)
    with open(OUT / "flags_ours.tsv", "w") as f:
        for w in sorted(ours_bad, key=lambda w: (-counts[w], w)):
            f.write(f"{w}\t{counts[w]}\t{', '.join(ours[w][1][:3])}\n")

    if hs:
        t = time.time()
        hs_bad = set()
        for w in counts:
            base = w.rstrip(".")
            ok = (ours[w][0] == "skip" or hs.ok(base) or w.endswith(".") and ours[w][0] == "ok" and base.lower() in ABBREV
                  or "-" in base and all(hs.ok(x) or is_foreign(x) for x in base.split("-") if x))
            if not ok:
                hs_bad.add(w)
        res["hunspell_seconds_lookup"] = round(time.time() - t, 1)
        res["hunspell_flagged_tokens"] = sum(counts[w] for w in hs_bad)
        res["hunspell_flagged_unique"] = len(hs_bad)
        res["hunspell_flagged_lowercase_unique"] = sum(1 for w in hs_bad if w[:1].islower())
        res["hunspell_flagged_lowercase_tokens"] = sum(counts[w] for w in hs_bad if w[:1].islower())
        res["flagged_by_both_unique"] = len(ours_bad & hs_bad)
        for name, words in (("only_ours", ours_bad - hs_bad), ("only_hunspell", hs_bad - ours_bad)):
            with open(OUT / f"flags_{name}.tsv", "w") as f:
                for w in sorted(words, key=lambda w: (-counts[w], w)):
                    f.write(f"{w}\t{counts[w]}\n")

    # ---------------- 2. synthetic errors ----------------
    rnd = random.Random(42)
    pool = sorted(w for w in counts if w.islower() and w.isalpha() and len(w) >= 4 and w not in ours_bad
                  and (hs is None or w not in hs_bad))
    syn = {}
    for kind in ("no_diacritics", "one_diacritic", "i_y", "typo"):
        stats = collections.Counter()
        examples = []
        tries = 0
        while stats["n"] < a.samples and tries < a.samples * 20:
            tries += 1
            w = rnd.choice(pool)
            bad = corrupt(w, kind, rnd)
            if not bad or bad == w:
                continue
            stats["n"] += 1
            for name, okf, sugf in (
                ("ours", lambda x: ck.check_word(x)[0] != "unknown", lambda x: ck.check_word(x)[1]),
                *((("hunspell", hs.ok, hs.suggest),) if hs else ()),
            ):
                if okf(bad):
                    stats[f"{name}_accepted"] += 1  # often a different valid word
                    continue
                stats[f"{name}_detected"] += 1
                sugg = sugf(bad)
                stats[f"{name}_top1"] += bool(sugg) and sugg[0] == w
                stats[f"{name}_top5"] += w in sugg[:5]
                if name == "ours" and w not in sugg[:5] and len(examples) < 15:
                    examples.append(f"{bad} (want {w}) -> {sugg[:3]}")
        syn[kind] = dict(stats)
        syn[kind]["ours_misses"] = examples
        print(f"{kind}: {dict(stats)}", file=sys.stderr)
    res["synthetic"] = syn
    (OUT / "summary.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print(json.dumps({k: v for k, v in res.items() if k != "synthetic"}, ensure_ascii=False, indent=1))
    for kind, s in syn.items():
        n = s["n"]
        line = f"{kind:14s} n={n:4d} | ours: detect {s.get('ours_detected', 0) / n:5.1%} top1 {s.get('ours_top1', 0) / n:5.1%} top5 {s.get('ours_top5', 0) / n:5.1%}"
        if hs:
            line += f" | hunspell: detect {s.get('hunspell_detected', 0) / n:5.1%} top1 {s.get('hunspell_top1', 0) / n:5.1%} top5 {s.get('hunspell_top5', 0) / n:5.1%}"
        print(line)


if __name__ == "__main__":
    main()
