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
SAFE_RULES = {"case", "agreement", "quantity", "negation", "relative", "object", "subject"}


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
        if fixes and (fixes[0]["diacritic"] or r["contextRule"] in ("subject", "rare")):   # aš buvo -> buvau, kak -> kai
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


def fix_sentence(sentence):
    """VarneleSentenceFixer: two passes of safe fixes and commas."""
    for _ in range(2):
        s = list(sentence)
        for f in sorted(findings(sentence), key=lambda f: -f["start"]):
            if f["rule"] == "comma":
                # wait for the next word: "pirk bet" may become "pirk bet ką" (no comma)
                if any(ch.isalpha() for ch in sentence[f["end"]:]) and f["start"] >= 2 and sentence[f["start"] - 1] == " " and sentence[f["start"] - 2].isalpha():
                    s.insert(f["start"] - 1, ",")
            elif f["rule"] in SAFE_RULES and f["suggestions"]:
                fix = f["suggestions"][0]
                if fix != f["word"] and len(fix) == len(f["word"]) and fix.lower().translate(FOLD) == f["word"].lower().translate(FOLD):
                    s[f["start"]:f["end"]] = fix
        sentence = "".join(s)
    return sentence


def type_text(text):
    """Type the text word by word. Any non-letter (space, no-break space, quote, bracket, colon,
    dash) ends a word, as on the keyboard: „Del and Sarasas:Lietuvos are words too."""
    out = ""
    pieces = re.split(r"([^\W\d_]+)", text)      # separator, word, separator, word, ...
    for i, piece in enumerate(pieces):
        if i % 2 == 0:
            out += piece
            continue
        context = " ".join(re.findall(r"[^\W\d_]+", out)[-3:])
        out += autocorrect(piece, context)
        if i + 1 < len(pieces):           # the separator that finishes the word
            out += pieces[i + 1]
            pieces[i + 1] = ""
        out = fix_sentence(out)
    return out.strip()


if __name__ == "__main__":
    for t in sys.argv[1:]:
        print(f"typed: {t}\n  got: {type_text(t)}")
