"""Simulate typing in the HeliBoard fork, word by word, using the Rust library.

Mirrors VarneleDictionary.kt (autocorrect decision on space) and
VarneleSentenceFixer.kt (re-check the sentence, apply safe fixes and commas).

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
SAFE_RULES = {"case", "agreement", "quantity", "negation", "relative", "object", "subject", "phrase", "valency"}
LETTER_RULES = {"phrase"}      # earlier words: may change letters (viena nukritusią sagutė -> nukritusi)


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
    """What VarneleDictionary + HeliBoard would commit for this word on space."""
    r = kb(word, context)
    if r["status"] != "unknown":
        fixes = r["contextFixes"]
        if fixes and (fixes[0]["diacritic"] or r["contextRule"] in ("subject", "rare", "phrase")):   # aš buvo -> buvau, kak -> kai
            return fixes[0]["w"]
        fixes = [c for c in fixes if c["diacritic"]]
        return fixes[0]["w"] if fixes else word
    s = r["suggestions"]
    if not s:
        return word
    top = s[0]
    clearly = r["contextRule"] == "context" or len(s) == 1 or s[1]["cost"] - top["cost"] >= 0.08
    if (clearly and top["diacritic"]) or top["fcost"] <= 1.0:
        return top["w"]
    return word


def folded(w):
    return w.lower().translate(FOLD)


SOFT_WINDOW = 6     # the last words of the sentence whose diacritics fix_soft may change


def fix_soft(sentence, soft):
    """VarneleSentenceFixer's pass over the words the keyboard itself gave diacritics (autocorrected,
    not typed that way): Rust's keyboard_soft checks the sentence with them as typed, so the words
    after them can choose the twin (kad ziema … rimtesne -> žiema, not the more frequent žiemą).
    soft: their word indices -> the form typed; a word no longer spelled like it (edited) is dropped."""
    spans = [m.span() for m in re.finditer(r"[^\W\d_]+", sentence)]
    typed = list(sentence)
    for k, t in list(soft.items()):
        if k < len(spans) - SOFT_WINDOW or k == len(spans) - 1:
            continue      # older words stay; the word just finished has nothing after it yet
        a, b = spans[k] if k < len(spans) else (0, 0)
        if b - a == len(t) and folded(sentence[a:b]) == folded(t):
            typed[a:b] = t
        else:
            del soft[k]
    if not soft:
        return sentence
    line = _ask("soft\t" + sentence.replace("\t", " ").replace("\n", " ") + "\t"
                + "".join(typed).replace("\t", " ").replace("\n", " ")).readline()
    s = list(sentence)
    for f in json.loads(line):
        s[f["start"]:f["end"]] = f["word"]
    return "".join(s)


def fix_sentence(sentence, soft=None):
    """VarneleSentenceFixer: the keyboard's own diacritics first (fix_soft), then two passes of
    safe fixes and commas."""
    if soft:
        sentence = fix_soft(sentence, soft)
    for _ in range(2):
        s = list(sentence)
        for f in sorted(findings(sentence), key=lambda f: -f["start"]):
            if f["rule"] == "comma":
                # wait for the next word: "pirk bet" may become "pirk bet ką" (no comma)
                if any(ch.isalpha() for ch in sentence[f["end"]:]) and f["start"] >= 2 and sentence[f["start"] - 1] == " " and sentence[f["start"] - 2].isalpha():
                    s.insert(f["start"] - 1, ",")
            elif f["rule"] in SAFE_RULES and f["suggestions"]:
                fix = f["suggestions"][0]
                if fix != f["word"] and (f["rule"] in LETTER_RULES or len(fix) == len(f["word"])
                                         and fix.lower().translate(FOLD) == f["word"].lower().translate(FOLD)):
                    s[f["start"]:f["end"]] = fix
        sentence = "".join(s)
    return sentence


def type_text(text, soft=True):
    """Type the text word by word. Any non-letter (space, no-break space, quote, bracket, colon,
    dash) ends a word, as on the keyboard: „Del and Sarasas:Lietuvos are words too.
    soft: the sentence fixer may change the diacritics autocorrect gave a word (fix_soft)."""
    out = ""
    words = {}                            # soft words: index -> typed form
    pieces = re.split(r"([^\W\d_]+)", text)      # separator, word, separator, word, ...
    for i, piece in enumerate(pieces):
        if i % 2 == 0:
            out += piece
            continue
        before = re.findall(r"[^\W\d_]+", out)
        context = " ".join(before[-3:])
        got = autocorrect(piece, context)
        if soft and got != piece and len(got) == len(piece) and folded(got) == folded(piece):
            words[len(before)] = piece
        out += got
        if i + 1 < len(pieces):           # the separator that finishes the word
            out += pieces[i + 1]
            pieces[i + 1] = ""
        out = fix_sentence(out, words)
    return out.strip()


if __name__ == "__main__":
    for t in sys.argv[1:]:
        print(f"typed: {t}\n  got: {type_text(t)}")
