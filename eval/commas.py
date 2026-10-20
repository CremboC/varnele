"""Comma rules on text with its commas removed.

Every comma in the Wikipedia articles is deleted, the checker runs on the result,
and each comma it asks for is compared with the original text. A flag where the
original had no comma is a false alarm (or an error in the article: print them).

    python3 eval/commas.py [DIR] [--show-wrong] [--show-right]
"""

import collections
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from varnele.__main__ import Checker  # noqa: E402


def strip_commas(line):
    """Text without commas, and the set of word offsets (in it) that had a comma before them."""
    out, had = [], set()
    i = 0
    while i < len(line):
        if line[i] == "," and i + 1 < len(line) and line[i + 1] == " ":
            i += 1                       # drop ", " -> " "; the next word had a comma
            had.add(len(out) + 1)
            continue
        out.append(line[i])
        i += 1
    return "".join(out), had


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    folder = pathlib.Path(args[0] if args else "corpus/test")
    ck = Checker()
    right, wrong = collections.Counter(), collections.Counter()
    for p in sorted(folder.glob("*.txt")):
        for line in p.read_text().splitlines():
            if "\\displaystyle" in line or "{\\" in line or not line.strip():
                continue
            text, had = strip_commas(line)
            for f in ck.check_text(text):
                if f.rule != "comma":
                    continue
                kind = re.sub(r"'[^']*'", "X", f.message)
                ok = f.start in had
                (right if ok else wrong)[kind] += 1
                if ("--show-wrong" in sys.argv and not ok) or ("--show-right" in sys.argv and ok):
                    print("OK " if ok else "BAD", kind, "|", text[max(0, f.start - 60):f.end + 30])
    print(f"{'rule':55} right wrong")
    for k in sorted(set(right) | set(wrong), key=lambda k: -(right[k] + wrong[k])):
        print(f"{k:55} {right[k]:5} {wrong[k]:5}")
    print(f"{'total':55} {sum(right.values()):5} {sum(wrong.values()):5}")


if __name__ == "__main__":
    main()
