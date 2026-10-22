"""The text the frequency tables are counted on: the Wikipedia dump's plain text
(corpus/wiki/text, eval/extract_wiki.py; the evaluation articles left out) when it is there,
else the 600 articles of corpus/freq; plus the conversational text (corpus/conv/train), weighted.
Never corpus/test or the conversational test sets."""
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


CONV_WEIGHT = 1.0   # a conversational occurrence counts this many Wikipedia ones (eval/build_*.py --conv-weight)


def conversational():
    """The cleaned conversational text (corpus/conv/train, eval/extract_conv.py: subtitles and
    Tatoeba, the held-out lines left out), one text of one line per line. A line of 4+ words counts
    once: a film's uploads repeat its lines, and a repeated long line would otherwise show up as a
    common word pair. Short lines (`Taip.`, `Ne.`) count every time: that is how often they are said."""
    seen = set()
    for p in sorted((ROOT / "corpus" / "conv" / "train").glob("*.txt")):
        out = []
        for line in p.read_text("utf-8").splitlines():
            if len(line.split()) >= 4:
                if line in seen:
                    continue
                seen.add(line)
            out.append(line)
        yield "\n".join(out)
