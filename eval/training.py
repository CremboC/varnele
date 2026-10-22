"""The text the frequency tables are counted on: the Wikipedia dump's plain text
(corpus/wiki/text, eval/extract_wiki.py; the evaluation articles left out) when it is there,
else the 600 articles of corpus/freq. Never corpus/test."""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent


def texts():
    """Each training text, one paragraph per line."""
    wiki = sorted((ROOT / "corpus" / "wiki" / "text").glob("wiki-*.txt"))
    if wiki:
        for p in wiki:
            yield p.read_text("utf-8")
        return
    for p in sorted((ROOT / "corpus" / "freq").glob("*.txt")):
        lines = p.read_text("utf-8").splitlines()[2:]   # title, blank line
        yield "\n".join(l for l in lines if "\\displaystyle" not in l and "{\\" not in l)
