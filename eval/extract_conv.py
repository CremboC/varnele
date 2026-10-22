"""Conversational text: held-out test sets and the cleaned rest for counting.

The restore, predict and swipe evaluations use Wikipedia articles; a keyboard types chat. This
reads the OPUS monolingual files (see AGENTS.md "Corpus beyond Wikipedia"):

    corpus/raw/opensubtitles/lt-v2024.txt.gz   object.pouta.csc.fi/OPUS-OpenSubtitles/v2024/mono/lt.txt.gz
    corpus/raw/tatoeba/lt-v2026-07-08.txt.gz   object.pouta.csc.fi/OPUS-Tatoeba/v2026-07-08/mono/lt.txt.gz

cleans them (eval/clean_conv.py: encoding and OCR repairs, lines typed without diacritics,
foreign lines and credits dropped) and writes, in the format of corpus/test (title line, blank
line, text):

    corpus/conv/subtitles/NNN.txt   BLOCKS stretches of BLOCK_LINES consecutive subtitle lines, spread
                                    evenly over the file (it is in film order but has no film
                                    boundaries), one kept line each; the text before a sentence is
                                    the dialogue before it
    corpus/conv/tatoeba/NNNN.txt    TATOEBA random kept sentences, one per file (unrelated sentences
                                    give no context)
    corpus/conv/heldout.tsv         `source<TAB>line<TAB>N` for every held-out line (0-based),
                                    `source<TAB>text<TAB>TEXT` for every held-out line of 4+ words
    corpus/conv/train/SOURCE.txt    the cleaned lines for counting, one per line: held-out lines
                                    left out, and every line equal to a held-out line of 4+ words
                                    (a film's other uploads repeat its lines elsewhere)

Subtitles have no licence (link opensubtitles.org), Tatoeba is CC BY 2.0 FR; both kept
locally, git-ignored.

    python3 eval/extract_conv.py
    python3 eval/restore.py --corpus corpus/conv/subtitles --sentences 300
"""
import pathlib
import random
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "eval"))

from clean_conv import clean, read  # noqa: E402

OUT = ROOT / "corpus" / "conv"
BLOCKS, BLOCK_LINES = 40, 500
TATOEBA = 2000


def write(directory, name, title, lines):
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(title + "\n\n" + "\n".join(lines) + "\n", "utf-8")


def main():
    for d in ("subtitles", "tatoeba"):
        for old in (OUT / d).glob("*.txt"):
            old.unlink()
    rows = []
    for source in ("opensubtitles", "tatoeba"):
        lines = clean(read(source), stretches=source == "opensubtitles")
        held = set()
        if source == "opensubtitles":
            for b in range(BLOCKS):
                start = (2 * b + 1) * len(lines) // (2 * BLOCKS) - BLOCK_LINES // 2
                held.update(range(start, start + BLOCK_LINES))
                write(OUT / "subtitles", f"{b:03d}.txt", f"OpenSubtitles v2024 lines {start}-{start + BLOCK_LINES}",
                      [l for l in lines[start:start + BLOCK_LINES] if l])
        else:
            kept = [i for i, l in enumerate(lines) if l]
            for k, i in enumerate(sorted(random.Random(1).sample(kept, TATOEBA))):
                held.add(i)
                write(OUT / "tatoeba", f"{k:04d}.txt", f"Tatoeba line {i}", [lines[i]])
        texts = {lines[i] for i in held if lines[i] and len(lines[i].split()) >= 4}
        rows += [(source, "line", str(i)) for i in sorted(held)] + [(source, "text", t) for t in sorted(texts)]
        train = [l for i, l in enumerate(lines) if l and i not in held and l not in texts]
        (OUT / "train").mkdir(parents=True, exist_ok=True)
        (OUT / "train" / f"{source}.txt").write_text("\n".join(train) + "\n", "utf-8")
        print(f"{source}: {len(lines):,} lines, {sum(1 for l in lines if l):,} kept after cleaning, "
              f"{len(held):,} held out, {len(train):,} for counting ({sum(len(l.split()) for l in train):,} words)")
    (OUT / "heldout.tsv").write_text("".join("\t".join(r) + "\n" for r in rows), "utf-8")


if __name__ == "__main__":
    main()
