"""Download random Lithuanian Wikipedia articles (plain text) for testing.

Usage: python3 eval/fetch_corpus.py OUT_DIR N_ARTICLES [MIN_CHARS]
Text is CC BY-SA 4.0 (Wikipedia contributors); kept locally for evaluation only.
"""
import json
import pathlib
import sys
import time
import urllib.parse
import urllib.error
import urllib.request

API = "https://lt.wikipedia.org/w/api.php"
UA = "varnele-eval/0.1 (research prototype; local spell-checker testing)"


def get(params, tries=6):
    q = {"action": "query", "format": "json", **params}
    req = urllib.request.Request(API + "?" + urllib.parse.urlencode(q), headers={"User-Agent": UA})
    for i in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code != 429 or i == tries - 1:
                raise
            time.sleep(5 * 2 ** i)


def random_batch():
    """50 random articles with their plain text (CirrusSearch document) in one request."""
    pages = get({"generator": "random", "grnnamespace": 0, "grnlimit": 50,
                 "prop": "cirrusdoc"})["query"]["pages"]
    for pid, page in pages.items():
        docs = page.get("cirrusdoc") or []
        if docs:
            src = docs[0]["source"]
            yield pid, src.get("title", ""), src.get("text", "")


def main():
    out, n = pathlib.Path(sys.argv[1]), int(sys.argv[2])
    min_chars = int(sys.argv[3]) if len(sys.argv) > 3 else 1500
    skip = set()
    for d in sys.argv[4:]:  # other corpus dirs whose articles must not be reused
        skip |= {p.stem for p in pathlib.Path(d).glob("*.txt")}
    out.mkdir(parents=True, exist_ok=True)
    have = {p.stem for p in out.glob("*.txt")}
    while len(have) < n:
        for pid, title, text in random_batch():
            if pid in have or pid in skip or len(have) >= n or len(text) < min_chars:
                continue
            (out / f"{pid}.txt").write_text(title + "\n\n" + text, "utf-8")
            have.add(pid)
        print(f"{len(have)}/{n}", file=sys.stderr, flush=True)
        time.sleep(3)


if __name__ == "__main__":
    main()
