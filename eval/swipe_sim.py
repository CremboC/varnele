"""Gesture typing simulation: restore.py's sentences swiped word by word.

Each word becomes a finger path over the QWERTY layout (key widths; keys 1 wide, rows 1.4
high, as gesture.rs's Layout::qwerty): every key centre is missed by a random offset, corners
are cut, and the points are joined by a smooth curve. The path is decoded by the Rust gesture
search (`varnele serve`, request `gesture`), the top candidate is committed through the
keyboard model (keyboard_sim.py: autocorrect, then the sentence fixer), which chooses the
diacritics. Words the gesture can't spell (one key, digits, all caps, one letter) are tapped.

    python3 eval/swipe_sim.py [--sentences N] [--noise 0.3] [--cut 0.4] [--show K]
    python3 eval/swipe_sim.py --words labas nežinau     # decode single words, show candidates
"""

import argparse
import collections
import json
import math
import random
import re
import sys
import time
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "eval"))

from restore import STRIP, WORD, sentences  # noqa: E402
from keyboard_sim import _ask, autocorrect, fix_sentence, kb  # noqa: E402

ROWS = [("qwertyuiop", 0.5), ("asdfghjkl", 1.0), ("zxcvbnm", 2.0)]
CENTRE = {c: (x0 + i, 0.7 + 1.4 * r) for r, (row, x0) in enumerate(ROWS) for i, c in enumerate(row)}
KEYFOLD = str.maketrans("ąčęėįšųūž", "aceeisuuz")   # y is its own key


def keys(word):
    """The keys swiped for a word, repeated keys once."""
    out = []
    for c in word.lower().translate(KEYFOLD):
        if not out or out[-1] != c:
            out.append(c)
    return out


def catmull_rom(pts, per=8):
    """A smooth curve through the points."""
    if len(pts) < 2:
        return list(pts)
    ext = [pts[0]] + pts + [pts[-1]]
    out = []
    for i in range(1, len(ext) - 2):
        p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
        for k in range(per):
            t = k / per
            t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * (2 * p1[d] + (-p0[d] + p2[d]) * t + (2 * p0[d] - 5 * p1[d] + 4 * p2[d] - p3[d]) * t2
                                    + (-p0[d] + 3 * p1[d] - 3 * p2[d] + p3[d]) * t3) for d in (0, 1)))
    out.append(pts[-1])
    return out


def swipe_path(word, rng, noise, cut):
    """A noisy finger path for the word: each key missed by N(0, noise), interior corners
    pulled towards their neighbours' midpoint by up to `cut` key widths, small jitter."""
    tgt = [(CENTRE[c][0] + rng.gauss(0, noise), CENTRE[c][1] + rng.gauss(0, noise * 1.2)) for c in keys(word)]
    for i in range(1, len(tgt) - 1):
        mid = ((tgt[i - 1][0] + tgt[i + 1][0]) / 2, (tgt[i - 1][1] + tgt[i + 1][1]) / 2)
        d = math.dist(mid, tgt[i])
        f = min(cut * rng.random(), d) / d if d > 0 else 0
        tgt[i] = (tgt[i][0] + f * (mid[0] - tgt[i][0]), tgt[i][1] + f * (mid[1] - tgt[i][1]))
    # the finger stays on the keyboard (letter rows from 0 to 4.2)
    return [(min(max(x + rng.gauss(0, 0.03), 0), 10), min(max(y + rng.gauss(0, 0.03), 0), 4.2)) for x, y in catmull_rom(tgt)]


def gesture(path, cap, n=5, context=""):
    pts = " ".join(f"{x:.3f},{y:.3f}" for x, y in path)
    context = context.replace("\t", " ").replace("\n", " ")[-1500:]
    return json.loads(_ask(f"gesture\t{pts}\t{int(cap)}\t{n}\t{context}").readline())


def swipeable(word):
    return (len(word) > 1 and not (word.isupper()) and all(c in CENTRE for c in word.lower().translate(KEYFOLD))
            and len(keys(word)) > 1)


def swipe_text(text, rng, noise, cut, log, before=""):
    """Enter the sentence word by word; log gets (original, top keys, top 3, committed, ms) per swiped word.
    `before`: the text before the sentence (for the language model's paragraph cache)."""
    out = ""
    pieces = re.split(r"([^\W\d_]+)", text)
    for i, piece in enumerate(pieces):
        if i % 2 == 0:
            out += piece
            continue
        context = " ".join(re.findall(r"[^\W\d_]+", out)[-3:])
        if swipeable(piece):
            t = time.perf_counter()
            cands = gesture(swipe_path(piece, rng, noise, cut), piece[0].isupper(), 40, (before + " " + out).strip())
            ms = (time.perf_counter() - t) * 1000
            top = cands[0]["w"] if cands else ""
            word = autocorrect(top, context) if top else piece.translate(STRIP)
            log.append((piece, top, [c["w"] for c in cands], word, ms))
        else:
            word = autocorrect(piece.translate(STRIP), context)   # tapped
        out += word
        if i + 1 < len(pieces):
            out += pieces[i + 1]
            pieces[i + 1] = ""
        out = fix_sentence(out)
    return out.strip()


def preceding(corpus, sample):
    """The article text before each sentence (as typed correctly), at most 1500 characters,
    starting at a sentence boundary so it doesn't end the previous sentence oddly."""
    texts = []
    for p in sorted(pathlib.Path(corpus).glob("*.txt")):
        texts.append(" ".join(l for l in p.read_text("utf-8").splitlines()[2:]
                              if l.strip() and "\\displaystyle" not in l and "{\\" not in l))
    out = {}
    for s in sample:
        for t in texts:
            i = t.find(s)
            if i >= 0:
                out[s] = t[max(0, i - 1500):i].strip()
                break
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sentences", type=int, default=300)
    ap.add_argument("--noise", type=float, default=0.3, help="key miss, standard deviation in key widths")
    ap.add_argument("--cut", type=float, default=0.4, help="corner cutting, at most this many key widths")
    ap.add_argument("--show", type=int, default=25)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--corpus", default=str(ROOT / "corpus" / "test"))
    ap.add_argument("--words", nargs="*")
    ap.add_argument("--no-paragraph", action="store_true", help="don't give the article text before each sentence")
    a = ap.parse_args()
    rng = random.Random(a.seed)

    if a.words:
        for w in a.words:
            for k in range(3):
                cands = gesture(swipe_path(w, rng, a.noise, a.cut), w[0].isupper())
                print(f"{w} #{k}: " + ", ".join(f"{c['w']} ({c['best']} {c['cost']:.2f} {c['shape']:.2f})" for c in cands))
        return

    pool = list(sentences(a.corpus))
    sample = random.Random(3).sample(pool, min(a.sentences, len(pool)))   # the same as restore.py
    before = {} if a.no_paragraph else preceding(a.corpus, sample)
    st = collections.Counter()
    misses = collections.Counter()
    restore_misses = collections.Counter()
    times = []
    for s in sample:
        log = []
        final = swipe_text(s, rng, a.noise, a.cut, log, before.get(s, ""))
        words, got = WORD.findall(s), WORD.findall(final)
        exact_sentence = len(words) == len(got) and all(x == y for x, y in zip(words, got))
        st["sentences"] += 1
        st["sentences right"] += exact_sentence
        # the final word for each swiped word: the n-th swipeable word of the sentence
        finals = [g for w, g in zip(words, got) if swipeable(w)] if len(words) == len(got) else None
        for k, (orig, top, top3, committed, ms) in enumerate(log):
            if kb(orig, "")["status"] == "unknown":
                st["unknown words (skipped)"] += 1
                continue
            times.append(ms)
            want = "".join(keys(orig))
            gotk = "".join(keys(top))
            st["swiped"] += 1
            st["keys @1"] += gotk == want
            st["keys @3"] += want in ["".join(keys(c)) for c in top3[:3]]
            st["keys @40"] += want in ["".join(keys(c)) for c in top3]
            if finals is not None:
                st["final words"] += 1
                ok = finals[k] == orig
                st["final right"] += ok
                if gotk == want:
                    st["keys right"] += 1
                    st["keys right, final right"] += ok
                    if not ok:
                        restore_misses[f"{orig} → {finals[k]}"] += 1
            if gotk != want:
                misses[f"{orig} → {top}  {top3[1:3]}"] += 1
    pct = lambda x, n: f"{100 * x / max(n, 1):.1f}%"
    print(f"noise {a.noise}, cut {a.cut}, {st['sentences']} sentences, {st['swiped']} swiped known words "
          f"({st['unknown words (skipped)']} unknown skipped)")
    print(f"  keys right, top 1:        {pct(st['keys @1'], st['swiped'])}")
    print(f"  keys right, top 3:        {pct(st['keys @3'], st['swiped'])}")
    print(f"  keys among the 40 kept:   {pct(st['keys @40'], st['swiped'])}")
    print(f"  final word right:         {pct(st['final right'], st['final words'])}")
    print(f"  ... when the keys were:   {pct(st['keys right, final right'], st['keys right'])}")
    print(f"  sentences right:          {pct(st['sentences right'], st['sentences'])}")
    times.sort()
    if times:
        print(f"  decode ms: median {times[len(times) // 2]:.1f}, 95% {times[int(len(times) * .95)]:.1f}, max {times[-1]:.1f}")
    if a.show:
        print("\nwrong keys:")
        for m, n in misses.most_common(a.show):
            print(f"  {n:3} {m}")
        print("\nright keys, wrong diacritics:")
        for m, n in restore_misses.most_common(a.show):
            print(f"  {n:3} {m}")


if __name__ == "__main__":
    main()
