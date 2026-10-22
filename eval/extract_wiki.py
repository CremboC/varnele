"""Plain text from a Lithuanian Wikipedia dump, for word and word-pair frequencies.

Reads ltwiki-*-pages-articles.xml.bz2 (dumps.wikimedia.org) as a stream, keeps the main
namespace without redirects, leaves out the evaluation articles (corpus/test, by title) and
writes corpus/wiki/text/wiki-NNN.txt: one paragraph per line, articles separated by an empty
line. Stress marks are removed (Lithuanian letters keep their diacritics). The markup is stripped with regular expressions (templates, tables, references, files,
categories, link markup); each article stops at its reference sections. Headings, lists of
links and table rows are dropped: only running text is kept.
Text is CC BY-SA 4.0 (Wikipedia contributors); kept locally, git-ignored.

    python3 eval/extract_wiki.py [DUMP] [--limit N]
"""
import argparse
import bz2
import html
import pathlib
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parent.parent
WIKI = ROOT / "corpus" / "wiki"
PER_FILE = 5000   # articles per output file

# sections after which an article has only references and links
STOP = re.compile(r"^==+\s*(Šaltiniai|Nuorodos|Išnašos|Literatūra|Taip pat skaitykite|Išorinės nuorodos|"
                  r"Bibliografija|Pastabos|Galerija|Vikiteka)\s*==+\s*$", re.M)
COMMENT = re.compile(r"<!--.*?-->", re.S)
REF = re.compile(r"<ref[^>/]*/>|<ref[^>]*>.*?</ref>", re.S | re.I)
BLOCK = re.compile(r"<(math|gallery|code|pre|timeline|score|syntaxhighlight|source|imagemap|chem|hiero)[^>]*>.*?</\1>",
                   re.S | re.I)
TEMPLATE = re.compile(r"\{\{[^{}]*\}\}")
TABLE = re.compile(r"\{\|[^{}]*?\|\}", re.S)
LINK = re.compile(r"\[\[([^\[\]]*)\]\]")
NAMESPACE = re.compile(r"^\s*:?\s*(Failas|Vaizdas|File|Image|Kategorija|Category|Vikiteka|"
                       r"[a-z]{2,3}(-[a-z]+)?)\s*:", re.I)
EXTERNAL = re.compile(r"\[(?:https?:)?//[^\s\]]+\s*([^\]]*)\]")
URL = re.compile(r"https?://\S+")
TAG = re.compile(r"<[^>]+>")
QUOTES = re.compile(r"'{2,}")
STRESS = re.compile("[\u0300\u0301\u0303]")   # dictionary stress marks: Televìzija, ar̃


def nested(pattern, text, repl=""):
    """Replace innermost matches until none is left (templates and tables nest)."""
    for _ in range(20):
        text, n = pattern.subn(repl, text)
        if not n:
            break
    return text


def link(m):
    inner = m.group(1)
    if NAMESPACE.match(inner):
        return ""      # file, category, interlanguage link
    return inner.split("|")[-1]


def clean(wikitext):
    t = STOP.split(wikitext, maxsplit=1)[0]
    t = COMMENT.sub("", t)
    t = REF.sub("", t)
    t = BLOCK.sub("", t)
    t = nested(TEMPLATE, t)
    t = nested(TABLE, t)
    t = nested(LINK, t, link)
    t = EXTERNAL.sub(r"\1", t)
    t = URL.sub("", t)
    t = TAG.sub("", t)
    t = QUOTES.sub("", t)
    t = html.unescape(t).replace(" ", " ")
    out = []
    for line in t.splitlines():
        line = line.strip()
        # headings, lists, table remnants, indents, leftover markup
        if not line or line[0] in "=*#:;|!{}[" or line.startswith("__"):
            continue
        letters = sum(c.isalpha() for c in line)
        if letters < 40 or letters < 0.6 * len(line):
            continue
        out.append(re.sub(r"\s+", " ", line))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dump", nargs="?", default=str(WIKI / "ltwiki-latest-pages-articles.xml.bz2"))
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    held_out = {p.read_text("utf-8").split("\n", 1)[0].strip() for p in (ROOT / "corpus" / "test").glob("*.txt")}
    outdir = WIKI / "text"
    outdir.mkdir(parents=True, exist_ok=True)
    for old in outdir.glob("wiki-*.txt"):
        old.unlink()

    articles = skipped = words = 0
    out = None
    title = ns = None
    text = ""
    redirect = False
    for event, el in ET.iterparse(bz2.open(a.dump), events=("end",)):
        tag = el.tag.rsplit("}", 1)[-1]
        if tag == "title":
            title = el.text or ""
        elif tag == "ns":
            ns = el.text
        elif tag == "redirect":
            redirect = True
        elif tag == "text":
            text = el.text or ""
        elif tag == "page":
            if ns == "0" and not redirect and not text.lstrip().lower().startswith("#peradresavimas"):
                if title in held_out:
                    skipped += 1
                else:
                    paras = clean(text)
                    if paras:
                        if articles % PER_FILE == 0:
                            if out:
                                out.close()
                            out = open(outdir / f"wiki-{articles // PER_FILE:03d}.txt", "w", encoding="utf-8")
                        out.write("\n".join(paras) + "\n\n")
                        articles += 1
                        words += sum(len(p.split()) for p in paras)
                        if a.limit and articles >= a.limit:
                            break
            redirect, text = False, ""
            el.clear()
    if out:
        out.close()
    print(f"{articles:,} articles, {words:,} words; {skipped} evaluation articles left out", file=sys.stderr)


if __name__ == "__main__":
    main()
