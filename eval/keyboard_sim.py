"""Simulate typing in the HeliBoard fork, word by word, using the Rust library: the same
decisions as the keyboard (autocorrect on space, then the sentence fixer), which are made there.

    python3 eval/keyboard_sim.py "kodel nepataiso visu zodzou kuriu as rasau?"
"""

import json
import re
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
RUST = [str(ROOT / "rust/target/release/varnele"), "--data", str(ROOT / "data/varnele.bin")]
FOLD = str.maketrans("ąčęėįšųūž", "aceeisuuz")   # y is its own key, not a diacritic


_server = None


SERVE = ["serve"]   # extra flags may follow (predict_sim.py --raw-lm)


def _ask(line):
    """One request to a long-running `varnele serve` (loading the data once, not per call)."""
    global _server
    if _server is None:
        _server = subprocess.Popen(RUST + SERVE, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    _server.stdin.write(line + "\n")
    _server.stdin.flush()
    return _server.stdout


def kb(word, context):
    return json.loads(_ask(f"kb\t{word}\t{context}").readline())


def findings(text):
    out = _ask("json\t" + text.replace("\t", " ").replace("\n", " "))
    return [json.loads(l) for l in iter(out.readline, "\n")]


def autocorrect(word, context):
    """What the keyboard commits for this word on space (Rust: KeyboardWord::autocorrection)."""
    return kb(word, context)["autocorrect"] or word


def fix_sentence(text, picked=False):
    """The sentence fixer (Rust: SentenceFixer) on the text before the cursor."""
    one = text.replace("\t", " ").replace("\n", " ")
    r = json.loads(_ask(f"fix\t{one}\t{int(picked)}").readline())
    return text[:len(text) - r["delete"]] + r["insert"]


def type_text(text, soft=True):
    """Type the text word by word. Any non-letter (space, no-break space, quote, bracket, colon,
    dash) ends a word, as on the keyboard: „Del and Sarasas:Lietuvos are words too.
    soft: the sentence fixer may change the diacritics autocorrect gave a word."""
    out = ""
    _ask("fixreset").readline()
    pieces = re.split(r"([^\W\d_]+)", text)      # separator, word, separator, word, ...
    for i, piece in enumerate(pieces):
        if i % 2 == 0:
            out += piece
            continue
        # the context as the keyboard passes it (VarneleDictionary.sentenceSoFar): the sentence before the word,
        # its last 80 characters, punctuation and all (Labas, Boruta: a name inside a sentence)
        context = re.split(r"[.!?\n]", out)[-1][-80:].strip()
        if not re.search(r"[^\W\d_]", context):
            context = ""
        got = autocorrect(piece, context)
        out += got
        if soft:
            one = out.replace("\t", " ").replace("\n", " ")
            _ask(f"fixed\t{one}\t{piece}\t{got}").readline()
        # the separator that finishes the word, a key at a time
        for c in (pieces[i + 1] if i + 1 < len(pieces) else "") or " ":
            out = fix_sentence(out + c)
        if i + 1 < len(pieces):
            pieces[i + 1] = ""
    return out.strip()


if __name__ == "__main__":
    for t in sys.argv[1:]:
        print(f"typed: {t}\n  got: {type_text(t)}")
