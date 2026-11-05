"""Command line: python3 -m varnele [check FILE | words W... | build]"""

import argparse
from pathlib import Path
import re
import sys

from .analyzer import Analyzer
from .index import Index
from .phonology import LT_ALPHABET, fold
from .grammar import Grammar, Issue, RARE_TWIN_RATIO
from .suggest import Suggester, _cost, _diacritic_cost, key_and_neighbours

TOKEN = re.compile(r"[^\W\d_]+(?:[-‑][^\W\d_]+)*")
URL = re.compile(r"\S+\.(?:lt|com|org|net|eu|gov|edu|info)\b\S*|\S+@\S+|https?://\S+")
LT_LETTERS = set(LT_ALPHABET)
ROMAN = re.compile(r"^[IVXLCDM]+$")
ABBREV = set((Path(__file__).resolve().parent.parent / "data" / "abbreviations.txt")
             .read_text("utf-8").split())


def is_foreign(word):
    return any(c not in LT_LETTERS for c in word.lower())


# Letters Lithuanian doesn't use and the keys touching them (staggered rows: w is above a and s, not d)
SLIP_KEYS = {"w": "qeas", "q": "wa", "x": "zsdc"}
CASE_PARTS = {"nom", "gen", "dat", "acc", "ins", "loc", "voc"}
# what may stand between a sentence's end and its first word
OPENERS = " \t\"'„“”«»‘’([-–—"


def sentence_start(text, pos):
    """Only spaces, quotes and brackets between the start of the text or a sentence end and pos."""
    i = pos
    while i > 0 and text[i - 1] in OPENERS:
        i -= 1
    return i == 0 or text[i - 1] in ".!?…\n"


def sentence_before(text, pos):
    """The sentence up to pos; empty when pos starts it."""
    if sentence_start(text, pos):
        return ""
    i = pos
    while i > 0 and text[i - 1] not in ".!?…\n":
        i -= 1
    return text[i:pos]


def sentence_after(text, pos):
    """The rest of the sentence from pos, with its full stop."""
    i = pos
    while i < len(text) and text[i] not in ".!?…\n":
        i += 1
    return text[pos:i + 1]


def adds_diacritics(w, f):
    """f is w with diacritics added, nothing else (not i/y: y is its own key)."""
    return len(w) == len(f) and all(a == b or (b in "ąčęėįšųūž" and fold(b) == a) for a, b in zip(w, f))


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
        self.grammar = Grammar(self.an, self.sg)

    def check_word(self, w, sentence_start=False):
        """-> (status, suggestions). status: ok | colloquial | unknown | skip.
        sentence_start: a capital may be the keyboard's own (Ziwma is ziwma)."""
        if w.endswith("."):
            if w.lower() in ABBREV or len(w) == 2:   # šv., pvz., initials
                return "ok", []
            w = w[:-1]
        if is_foreign(w) or (w.isupper() and len(w) > 1):
            fix = self.slip_fixes(w, sentence_start)
            return ("unknown", fix) if fix else ("skip", [])
        r = self.an.check(w)
        if r.status != "unknown":
            pass
        elif len(w) == 1:
            fix = sorted((f for f in self.an.folded_forms(w.lower()) if f != w.lower()),
                         key=lambda f: (self.sg._score(w.lower(), f), f))
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
            return "unknown", self.with_key_shift(w, self.sg.suggest(w))
        return "ok", []

    def with_key_shift(self, w, suggestions):
        """Nothing within a typo: maybe the hand was one key off (fofrkua -> didelis)."""
        fw = fold(w.lower())
        if all(_cost(fw, fold(s.lower())) > 1.0 for s in suggestions):
            return (self.sg.key_shift(w, 3) + suggestions)[:5]
        return suggestions

    def lemma_seen(self, w):
        return max((self.sg.lemma_freq.get(a.lemma.lower(), 0) for a in self.an.analyze(w)), default=0)

    def common_twins(self, word, context, after=""):
        """Diacritic-only twins of a valid word, the likeliest first, when the word itself is never seen in the frequency
        corpus (neither the form nor its lemma) and the twin's lemma is; or when the twin's form alone
        is seen RARE_TWIN_RATIO times as often as the word's form and all of its lemma (veliau, of a
        verb seen 79 times: vėliau 48,849; not ligoje, lanke: a common lemma). Twins in different
        cases (mašina, mašiną): the words around it choose, else the more frequent. context: with
        no words before it in the sentence, a capital may be the keyboard's own. after: the rest of
        the sentence, if known."""
        freq = self.sg.freq
        lw = word.lower()
        # a capitalised word is also its lowercase self: Kuriu is the name Kurys, but also kuriu (I create)
        seen = max(freq.get(lw, 0), self.lemma_seen(word), self.lemma_seen(lw))
        lowercase = word[:1].islower()
        start = not context.strip()
        if not lowercase and not start:
            return []       # a name inside a sentence
        twins = []
        for c in self.an.folded_forms(fold(lw)):
            an = self.an._analyze_exact(c)
            if c == lw or not c[:1].islower() or not an:
                continue
            # a twin that can only be a vocative (sakiny, "O sentence!") or a participle
            # (tęstuoju for testuoju) is rarely meant
            if not any(not a.tag.endswith(".voc") and not (a.tag.startswith("V.") and CASE_PARTS & set(a.tag.split(".")))
                       for a in an):
                continue
            f = freq.get(c.lower(), 0)
            score = f if seen else self.lemma_seen(c) + f
            # only diacritics added: a typed one is meant (dantistė, not dantiste), and y is its own
            # key (lig šiol, not lyg)
            if adds_diacritics(lw, c.lower()) and score >= (RARE_TWIN_RATIO * seen if seen else 3):
                twins.append((-score, c))
        twins.sort()

        def issues(c):
            text = f"{context.rstrip()} {c}{after}".lstrip()
            return sum(f.rule != "comma" for f in self.grammar.check(text, partial=not after.strip()))
        judged = (context.strip() or after.strip()) and len(twins) > 1
        # then the verb next to it: the case its counts show on that side (mašina neveikia, not mašiną)
        prev = re.search(r"([^\W\d_]+)\s*$", context)
        nxt = re.match(r"\s+([^\W\d_]+)", after)
        prev, nxt = prev and prev.group(1), nxt and nxt.group(1)
        fits = {c: self.grammar.verb_fit(c, prev, nxt) if judged else 0 for _, c in twins}
        # the verb decides only clearly: 3x the other twins' count and seen 10 times (not 7 against 4)
        top = max(fits.values(), default=0)
        decided = top >= 10 and all(v * 3 <= top for c, v in fits.items() if v != top)
        ranked = sorted(((issues(c) if judged else 0, -fits[c] if decided else 0, c)
                         for _, c in twins), key=lambda r: r[:2])     # a tie stays by frequency
        cap = word[:1].isupper()
        return [c[0].upper() + c[1:] if cap else c for n, v, c in ranked if (n, v) == ranked[0][:2]][:3]

    def common_neighbour(self, word):
        """The most frequent word (seen at least 50 times) that differs from a short (2-4 letters),
        never seen valid word in one letter typed with a neighbouring key: kak -> kai."""
        lw = word.lower()
        # a typed diacritic is no slip (vašu, not vadu)
        if not 2 <= len(lw) <= 4 or not word[:1].islower() or self.sg.freq.get(lw, 0) > 0 or set(lw) & set("ąčęėįšųūž"):
            return None
        if any(self.sg.lemma_freq.get(a.lemma.lower(), 0) > 0 for a in self.an.analyze(word)):
            return None
        best = None
        for i, c in enumerate(lw):
            for k in key_and_neighbours(c)[1:]:
                cand = lw[:i] + k + lw[i + 1:]
                f = self.sg.freq.get(cand, 0)
                if f >= 50 and (best is None or f > best[0]) and self.an._analyze_exact(cand):
                    best = (f, cand)
        return best[1] if best else None


    def slip_fixes(self, w, sentence_start=False):
        """A Lithuanian word with one finger slip onto w, q or x: the seen words it was meant to be,
        else []. The slip hit that key instead of one touching it (ziwma -> žiema, xiūrėti ->
        žiūrėti) or as well as a letter next to it that it touches (ziewma -> žiema). A foreign word
        stays foreign: one the corpus has (news, wifi), a name (a capital other than at a
        sentence start: Wiley), a word of 3 letters or fewer (tax, wp)."""
        if sentence_start and w[:1].isupper() and w[1:].islower():
            # not the capital itself: Westu, Xanderis are names
            return [] if w[0].lower() in SLIP_KEYS else [c[:1].upper() + c[1:] for c in self.slip_fixes(w.lower())]
        lw = w.lower()
        odd = [i for i, c in enumerate(lw) if c not in LT_LETTERS]
        if w != lw or len(w) < 4 or len(odd) != 1 or lw[odd[0]] not in SLIP_KEYS or lw in self.sg.freq:
            return []
        i = odd[0]
        keys = SLIP_KEYS[lw[i]]
        rest = fold(lw[:i] + lw[i + 1:])
        extra = any(0 <= j < len(lw) and fold(lw[j]) in keys for j in (i - 1, i + 1))

        def meant(c):
            if len(c) == len(w):
                return fold(c[i]) in keys and fold(c[:i] + c[i + 1:]) == rest
            return extra and len(c) == len(w) - 1 and fold(c) == rest
        return [c for c in self.sg.suggest(w, 20) if meant(c) and c in self.sg.freq][:5]

    def check_text(self, text, formal=False, grammar=True):
        """All findings in a text, in order: misspellings, spoken forms, grammar."""
        found, seen, valid = {}, {}, []
        for word, pos in tokens(text):
            word = word if word.lower() in ABBREV else word.rstrip(".")
            key = (word, sentence_start(text, pos))
            if key not in seen:
                seen[key] = self.check_word(*key)
            st, sugg = seen[key]
            if st == "unknown" or (st == "colloquial" and formal):
                found[pos] = Issue(pos, pos + len(word), word, st, "", list(sugg))
            elif st == "ok":
                valid.append((word, pos))
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
            for word, pos in valid:
                if pos not in found:
                    end = pos + len(word)
                    fixes = self.common_twins(word, sentence_before(text, pos), sentence_after(text, end))
                    if not fixes and (near := self.common_neighbour(word)):
                        fixes = [near]
                    if fixes:
                        found[pos] = Issue(pos, end, word, "rare", f"usually '{fixes[0]}'", fixes)
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
    sub.add_parser("export", help="write data/varnele.bin for the Rust runtime")
    a = ap.parse_args(argv)

    if a.cmd == "build":
        Index.load(rebuild=True)
        return
    if a.cmd == "export":
        from .export import export
        path, size = export()
        print(f"wrote {path} ({size / 1e6:.1f} MB)")
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
              "negation": "GRAM", "subject": "GRAM", "object": "GRAM", "relative": "GRAM", "rare": "RARE"}
    for f in ck.check_text(text, formal=a.formal, grammar=not a.no_grammar):
        line = text.count("\n", 0, f.start) + 1
        out = f"{line}:{labels.get(f.rule, "GRAM")} {f.word}" + (f" -> {', '.join(f.suggestions)}" if f.suggestions else "")
        print(out + (f"   ({f.message})" if f.message else ""))


if __name__ == "__main__":
    main()
