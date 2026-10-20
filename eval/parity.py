"""Check that the Rust runtime gives exactly the same findings as Python.

    cargo build --release --manifest-path rust/Cargo.toml
    python3 -m varnele export
    python3 eval/parity.py [--corpus corpus/test]

Compares every finding (position, word, rule, suggestions in order) on every
article and reports the differences and the speed of both.
"""

import argparse
import json
import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from varnele.__main__ import Checker  # noqa: E402

RUST = ROOT / "rust" / "target" / "release" / "varnele"


def key(f):
    return (f["start"], f["end"], f["word"], f["rule"], tuple(f["suggestions"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default=str(ROOT / "corpus" / "test"))
    a = ap.parse_args()
    files = sorted(pathlib.Path(a.corpus).glob("*.txt"))

    ck = Checker()
    t = time.time()
    py = {}
    for p in files:
        py[p] = [{"start": f.start, "end": f.end, "word": f.word, "rule": f.rule,
                  "suggestions": f.suggestions} for f in ck.check_text(p.read_text("utf-8"))]
    t_py = time.time() - t

    t = time.time()
    rs = {}
    for p in files:
        out = subprocess.run([str(RUST), "--data", str(ROOT / "data" / "varnele.bin"), "json", str(p)],
                             capture_output=True, text=True, check=True).stdout
        rs[p] = [json.loads(line) for line in out.splitlines() if line]
    t_rs = time.time() - t

    total = same = 0
    diffs = []
    for p in files:
        a_, b_ = {key(f) for f in py[p]}, {key(f) for f in rs[p]}
        total += len(a_ | b_)
        same += len(a_ & b_)
        for k in sorted(a_ ^ b_)[:3]:
            diffs.append(f"{p.name}: {'python' if k in a_ else 'rust  '} {k}")
    words = sum(len(p.read_text("utf-8").split()) for p in files)
    print(f"{len(files)} articles, {words:,} words")
    print(f"findings identical: {same}/{total} ({same / max(total, 1):.2%})")
    print(f"python {t_py:.1f}s, rust {t_rs:.1f}s (rust includes starting a process per article)")
    for d in diffs[:30]:
        print("  ", d)


if __name__ == "__main__":
    main()
