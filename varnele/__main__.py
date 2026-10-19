"""Command line: python3 -m varnele [check FILE | words W... | build]"""

import argparse
from pathlib import Path
import re
import sys

from .analyzer import Analyzer
from .index import Index
from .phonology import LT_ALPHABET
from .grammar import Grammar, Issue
from .suggest import Suggester

TOKEN = re.compile(r"[^\W\d_]+(?:[-‑][^\W\d_]+)*")
URL = re.compile(r"\S+\.(?:lt|com|org|net|eu|gov|edu|info)\b\S*|\S+@\S+|https?://\S+")
LT_LETTERS = set(LT_ALPHABET)
ROMAN = re.compile(r"^[IVXLCDM]+$")
ABBREV = set((Path(__file__).resolve().parent.parent / "data" / "abbreviations.txt")
             .read_text("utf-8").split())


def is_foreign(word):
    return any(c not in LT_LETTERS for c in word.lower())


def tokens(text):
    """Yield (word, offset). Skips URLs/e-mails and ordinal tails like 1-ojo.
    A word immediately followed by "." is yielded as "word." so abbreviations
    can be recognised."""
    text = URL.sub(lambda m: " " * len(m.group()), text)
    for m in TOKEN.finditer(text):
        a, b = m.start(), m.end()
        if a >= 2 and text[a - 1] in "-‑" and text[a - 2].isdigit():
            continue
        w = m.group()
        if text[b:b + 1] == ".":
            w += "."
        yield w, a


class Checker:
    def __init__(self):
        self.an = Analyzer(Index.load())
        self.sg = Suggester(self.an)
        self.grammar = Grammar(self.an)

    def check_word(self, w):
        """-> (status, suggestions). status: ok | colloquial | unknown | skip"""
        if w.endswith("."):
            if w.lower() in ABBREV or len(w) == 2:   # šv., pvz., initials
                return "ok", []
            w = w[:-1]
        if is_foreign(w) or (w.isupper() and len(w) > 1):
            return "skip", []
        r = self.an.check(w)
        if r.status != "unknown":
            pass
        elif len(w) == 1:
            fix = sorted((f for f in self.an.folded_forms(w.lower()) if f != w.lower()),
                         key=lambda f: self.sg._score(w.lower(), f))
            return ("unknown", fix) if fix else ("skip", [])   # i -> į; else a variable/marker
        elif "-" in w or "‑" in w:
            parts = [p for p in re.split("[-‑]", w) if p]
            if ROMAN.match(parts[0]) and len(parts) == 2:   # XX-ojo, XIX-ajame
                return "ok", []
            if all(is_foreign(p) or self.an.check(p).status != "unknown" for p in parts):
                return "ok", []
        if r.status == "colloquial":
            return "colloquial", r.formal
        if r.status == "unknown":
            return "unknown", self.sg.suggest(w)
        return "ok", []


    def check_text(self, text, formal=False, grammar=True):
        """All findings in a text, in order: misspellings, spoken forms, grammar."""
        found, seen = {}, {}
        for word, pos in tokens(text):
            word = word if word.lower() in ABBREV else word.rstrip(".")
            if word not in seen:
                seen[word] = self.check_word(word)
            st, sugg = seen[word]
            if st == "unknown" or (st == "colloquial" and formal):
                found[pos] = Issue(pos, pos + len(word), word, st, "", list(sugg))
        if grammar:
            for g in self.grammar.check(text):
                if g.rule == "context":
                    # unknown word: let the context decide the order of suggestions
                    if g.start in found:
                        f = found[g.start]
                        f.suggestions = g.suggestions + [s for s in f.suggestions if s not in g.suggestions]
                        f.suggestions = f.suggestions[:5]
                        f.message = g.message
                elif g.start not in found:
                    found[g.start] = g
        return [found[k] for k in sorted(found)]


def main(argv=None):
    ap = argparse.ArgumentParser(prog="varnele", description="Rule-based Lithuanian spell checker")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="check a text file ('-' for stdin)")
    c.add_argument("file")
    c.add_argument("--formal", action="store_true", help="also report spoken shortenings")
    c.add_argument("--no-grammar", action="store_true", help="only check words one by one")
    w = sub.add_parser("words", help="analyse individual words")
    w.add_argument("words", nargs="+")
    sub.add_parser("build", help="rebuild the form index")
    a = ap.parse_args(argv)

    if a.cmd == "build":
        Index.load(rebuild=True)
        return
    ck = Checker()
    if a.cmd == "words":
        for word in a.words:
            st, sugg = ck.check_word(word)
            print(f"{word}: {st}" + (f" -> {', '.join(sugg)}" if sugg else ""))
            for an in ck.an.analyze(word)[:8]:
                pre = f"{an.prefix}+" if an.prefix else ""
                print(f"    {pre}{an.lemma}  {an.tag}")
        return
    text = sys.stdin.read() if a.file == "-" else open(a.file, encoding="utf-8").read()
    labels = {"unknown": "ERR ", "colloquial": "SPOKEN", "case": "GRAM", "agreement": "GRAM",
              "quantity": "GRAM", "comma": "COMMA",
              "negation": "GRAM", "subject": "GRAM", "object": "GRAM"}
    for f in ck.check_text(text, formal=a.formal, grammar=not a.no_grammar):
        line = text.count("\n", 0, f.start) + 1
        out = f"{line}:{labels[f.rule]} {f.word}" + (f" -> {', '.join(f.suggestions)}" if f.suggestions else "")
        print(out + (f"   ({f.message})" if f.message else ""))


if __name__ == "__main__":
    main()
