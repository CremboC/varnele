"""Simulate typing in the HeliBoard fork, word by word, using the Rust library.

Mirrors VarneleDictionary.kt (autocorrect decision on space) and
VarneleSentenceFixer.kt (re-check the sentence, apply safe fixes and commas).

    python3 eval/keyboard_sim.py "kodel nepataiso visu zodzou kuriu as rasau?"
"""

import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
RUST = [str(ROOT / "rust/target/release/varnele"), "--data", str(ROOT / "data/varnele.bin")]
FOLD = str.maketrans("ąčęėįšųūž", "aceeisuuz")   # y is its own key, not a diacritic
SAFE_RULES = {"case", "agreement", "quantity", "negation", "relative", "object", "subject"}


def kb(word, context):
    return json.loads(subprocess.run(RUST + ["kb", word, *context.split()], capture_output=True,
                                     text=True, check=True).stdout)


def findings(text):
    out = subprocess.run(RUST + ["json", "-"], input=text, capture_output=True, text=True, check=True).stdout
    return [json.loads(l) for l in out.splitlines() if l]


def autocorrect(word, context):
    """What VarneleDictionary + HeliBoard would commit for this word on space."""
    r = kb(word, context)
    if r["status"] != "unknown":
        fixes = [c for c in r["contextFixes"] if c["diacritic"]]
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
                if f["start"] >= 2 and sentence[f["start"] - 1] == " " and sentence[f["start"] - 2].isalpha():
                    s.insert(f["start"] - 1, ",")
            elif f["rule"] in SAFE_RULES and f["suggestions"]:
                fix = f["suggestions"][0]
                if fix != f["word"] and len(fix) == len(f["word"]) and fix.lower().translate(FOLD) == f["word"].lower().translate(FOLD):
                    s[f["start"]:f["end"]] = fix
        sentence = "".join(s)
    return sentence


def type_text(text):
    out = ""
    for i, raw in enumerate(text.split(" ")):
        tail = ""
        while raw and not raw[-1].isalpha():
            tail, raw = raw[-1] + tail, raw[:-1]
        context = " ".join(out.split()[-3:])
        word = autocorrect(raw, context) if raw else raw
        out += word + tail + " "
        out = fix_sentence(out)
    return out.strip()


if __name__ == "__main__":
    for t in sys.argv[1:]:
        print(f"typed: {t}\n  got: {type_text(t)}")
