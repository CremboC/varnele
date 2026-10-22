"""Repair and filter the conversational corpora (OpenSubtitles, Tatoeba) before any use.

Repairs are deterministic and kept only when the original word is not a word Varnelė knows and
the repaired one is:
  - Baltic text (cp1257) decoded as Western (cp1252): `Ðvieèianti lazdelë` → `Šviečianti lazdelė`;
    `ü` typed for `ū` (`Büsiu` → `Būsiu`)
  - OCR: capital I inside a lowercase word → l (`fiImo` → `filmo`); l before a consonant at the
    start of a word → I (`lki` → `Iki`, `lš` → `Iš`; known in lowercase too, so not `lt` → `IT`)
HTML/ASS tags, [sound descriptions] and ♪ are removed. A line is dropped (None) when it is:
  - still holding an unknown word with letters outside Lithuanian (other encodings:
    `©viesiausia i¹ ¹viesił`, `AnksŃiau`; Cyrillic)
  - typed without diacritics: an unknown lowercase word whose best suggestion only adds them
    (`cia` → `čia`; in Tatoeba mostly learners' `sedėti`, `tūrėti`), or, in subtitles, a line
    without any diacritic with 2+ such lines within 5 lines either side (films typed without them)
  - not Lithuanian: no diacritic, and 2+ lowercase unknown words making at least half of its
    words (English lines; names alone are kept: `Taip, Sonny.`)
  - a credit: release groups, sites; `Išvertė …`, `Subtitrai …` without a sentence end
Varnelė's grammar corrections and typo suggestions are not applied: on dialogue the context
rules have false alarms (`Aš jus įvesiu` → `jusiu`, `per toli` → `tolį`, `ką gali` → `galį`) and
suggestions guess (`salsa` → `sala`); the test sets would then also grade Varnelė against itself.
Human typos are left: they fall under the counts' minimum.

Word statuses are cached in corpus/conv/words.tsv (built on the first run, a few minutes).

    python3 eval/clean_conv.py [--show N]        # statistics and examples of each repair/drop
"""
import argparse
import collections
import gzip
import json
import pathlib
import random
import re
import subprocess
import sys
import threading

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "eval"))

from keyboard_sim import FOLD, RUST  # noqa: E402

RAW = ROOT / "corpus" / "raw"
SOURCES = {"opensubtitles": RAW / "opensubtitles" / "lt-v2024.txt.gz",
           "tatoeba": RAW / "tatoeba" / "lt-v2026-07-08.txt.gz"}
CACHE = ROOT / "corpus" / "conv" / "words.tsv"
WORD = re.compile(r"[^\W\d_]+")
LT = set("aąbcčdeęėfghiįyjklmnoprsštuųūvzžqwx")
DIACRITIC = re.compile("[ąčęėįšųūžĄČĘĖĮŠŲŪŽ]")
DASH = re.compile(r"^\s*-+\s*")
TAGS = re.compile(r"<[^>]*>|\{\\[^}]*\}|\[[^\]]*\]|♪")
CREDIT = re.compile(r"torrent|www\.|https?:|\.(com|lt|net|org)\b|opensubtitles|\bteam\b|\bripped\b|"
                    r"^(i[šs]vert[ėe]|vert[ėe]|vertimas|tekst[ąa] vert[ėe]|subtitr\w*|titrai|sinchroniz\w*)\b"
                    r"(?=[^.!?]*$)", re.I)
CONSONANT = set("bcčdfghkmnprsštvzž")
KNOWN = {"ok", "colloquial"}


def read(source):
    with gzip.open(SOURCES[source], "rt", encoding="utf-8") as f:
        return [DASH.sub("", TAGS.sub("", l)).strip() for l in f]


def repairs(w):
    """Candidate repairs of one word, most specific first."""
    out = []
    if any(c.lower() not in LT for c in w):
        try:
            out.append(w.encode("cp1252").decode("cp1257"))
        except UnicodeError:
            pass
        if "ü" in w:
            out.append(w.replace("ü", "ū"))
    if "I" in w[1:] and w[1:].replace("I", "").islower():
        out.append(w[0] + w[1:].replace("I", "l"))
    if len(w) > 1 and w[0] == "l" and w[1] in CONSONANT:
        out.append("I" + w[1:])
    return [r for r in dict.fromkeys(out) if r != w]


def lookup(words, workers=6):
    """{word: (status, best suggestion, diacritic only)} from `varnele serve`, cached on disk."""
    cache = {}
    if CACHE.exists():
        for l in CACHE.read_text("utf-8").splitlines():
            w, st, best, dia = l.split("\t")
            cache[w] = (st, best, dia == "1")
    todo = sorted(set(words) - cache.keys())
    if todo:
        print(f"looking up {len(todo):,} words", file=sys.stderr)
        lock = threading.Lock()

        def work(chunk):
            p = subprocess.Popen(RUST + ["serve"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
            for w in chunk:
                p.stdin.write(f"kb\t{w}\t\n")
                p.stdin.flush()
                r = json.loads(p.stdout.readline())
                s = r["suggestions"][:1]
                with lock:
                    cache[w] = (r["status"], s[0]["w"] if s else "", bool(s and s[0]["diacritic"]))
            p.stdin.close()
            p.wait()

        threads = [threading.Thread(target=work, args=(todo[i::workers],)) for i in range(workers)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text("".join(f"{w}\t{st}\t{b}\t{int(d)}\n" for w, (st, b, d) in sorted(cache.items())), "utf-8")
    return cache


def clean(lines, stretches=True, stats=None, examples=None):
    """The lines repaired, None for dropped ones (same length and numbering as the input).
    stretches: neighbouring lines belong together (subtitles, not Tatoeba)."""
    stats = stats if stats is not None else collections.Counter()
    examples = examples if examples is not None else collections.defaultdict(list)
    types = {w for l in lines for w in WORD.findall(l)}
    candidates = {r for w in types for r in repairs(w)}
    known = lookup(types | candidates | {r.lower() for r in candidates})

    def note(kind, text):
        stats[kind] += 1
        examples[kind].append(text)

    out, nodia = [], []
    for l in lines:
        fixed = l
        for w in sorted(set(WORD.findall(l)), key=len, reverse=True):
            if known[w][0] in KNOWN:
                continue
            for r in repairs(w):
                if known[r][0] in KNOWN and (r[0] != "I" or w[0] == "I" or known[r.lower()][0] in KNOWN):
                    fixed = re.sub(rf"(?<!\w){re.escape(w)}(?!\w)", r, fixed)
                    note("repaired " + ("encoding" if any(c.lower() not in LT for c in w) else "OCR I/l"),
                         f"{w} → {r} | {l[:70]}")
                    break
        words = WORD.findall(fixed)
        unknown = [w for w in words if known.get(w, ("unknown",))[0] == "unknown"
                   or any(c.lower() not in LT for c in w) and known.get(w, ("",))[0] not in KNOWN]
        why = None
        if not words:
            why = "no words" if fixed else None
        elif CREDIT.search(fixed):
            why = "credit"
        elif any(any(c.lower() not in LT for c in w) for w in unknown):
            why = "foreign letters"
        elif (len(lower := [w for w in unknown if w.islower()]) >= 2 and 2 * len(lower) >= len(words)
              and not DIACRITIC.search(fixed)):
            why = "not Lithuanian"
        elif any(w.islower() and known[w][2] and known[w][1].lower().translate(FOLD) == w.translate(FOLD)
                 for w in unknown):
            why = "without diacritics"
        nodia.append(why == "without diacritics")
        if why and why != "no words":
            note("dropped: " + why, fixed[:90])
        out.append(None if why else fixed)
    # stretches typed without diacritics: their lines that happen to be valid words only
    for i, l in enumerate(out):
        if stretches and l and not DIACRITIC.search(l) and sum(nodia[max(0, i - 5):i + 6]) >= 2:
            note("dropped: in a stretch without diacritics", l[:90])
            out[i] = None
    stats["lines"] += len(lines)
    stats["kept"] += sum(1 for l in out if l)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", type=int, default=12)
    a = ap.parse_args()
    for source in SOURCES:
        stats, examples = collections.Counter(), collections.defaultdict(list)
        clean(read(source), source == "opensubtitles", stats, examples)
        print(f"== {source}: {stats['lines']:,} lines, {stats['kept']:,} kept")
        for k, v in sorted(stats.items()):
            if k not in ("lines", "kept"):
                print(f"  {k:42s} {v:8,}")
        for k in sorted(examples):
            print(f"-- {k}")
            for e in random.Random(1).sample(examples[k], min(a.show, len(examples[k]))):
                print("    " + e)


if __name__ == "__main__":
    main()
