# Varnelė: a rule-based Lithuanian spell checker

*Varnelė* is both the háček on č/š/ž and a checkmark ✓.

Pure Python 3, no dependencies. Every inflected form comes from hand-written
grammar rules. Only the stem list is borrowed, from
[ispell-lt](https://github.com/ispell-lt/ispell-lt) (BSD licence, in `vendor/`).

```
python3 -m varnele check FILE            # report misspellings with suggestions
python3 -m varnele check FILE --formal   # also report spoken shortenings (buvom, valgyt)
python3 -m varnele check FILE --no-grammar   # word-by-word only
python3 -m varnele words žodis ...       # show analyses / suggestions for words
python3 -m varnele build                 # rebuild data/index.pkl (automatic when rules change)
python3 -m unittest discover tests
```

## How it works

| Layer | File | What it does |
|---|---|---|
| Sound rules | `varnele/phonology.py` | Changes where stem meets ending: t/d+i → č/dž, j+i → j, future š+s → š, imperative g+k → k |
| Paradigms | `varnele/paradigms.py` | 12 noun declensions; adjectives with definite forms, degrees, `-umas`, `-okas`; verbs from their 3 principal parts (all tenses, moods, participles, gerunds, verbal nouns, reflexives) |
| Index | `varnele/index.py` | 9.2 M forms stored as ~96 k stems × ~350 shared ending sets |
| Prefix grammar | `varnele/analyzer.py` | `ne-/nebe-/be-/te-/tebe-` + 12 verbal prefixes + the `-si-` infix, checked against each verb's prefix flags |
| Spoken register | `varnele/analyzer.py` | `-ti→-t`, `-me→-m`, `-te→-t`, `-si→-s`, `-oje→-oj`, `-uose→-uos`, `-oms→-om`, … mapped back to formal forms |
| Word formation | `varnele/derivation.py` | Productive suffixes (`-inis`, `-iškas`, `-ininkas`, diminutives…), compounds, `geo-/anti-/neo-…` prefixes. **Blocked** whenever a dictionary word is one slip away |
| Context rules | `varnele/grammar.py` | Preposition government (`prieš pora` → `porą`), adjective–noun agreement in case/number/gender, genitive after quantities (`daug vaiku` → `vaikų`), missing commas before `kad`, `nes`, `bet`, `kuris`… Case rules fire only when a diacritic-only fix exists |
| Suggestions | `varnele/suggest.py` | Diacritic-blind lookup + one typo, ranked by weighted edit distance (diacritic swaps cheap, adjacent keys cheaper), form and lemma frequency |

Additions to the lexicon go in `data/extra.txt` (same `word/FLAGS` syntax as ispell-lt).

## Evaluation (150 random lt.wikipedia articles, 55 k tokens, unseen during development)

Reproduce: `python3 eval/fetch_corpus.py corpus/test 150 1500`, then
`python3 eval/fetch_corpus.py corpus/freq 600 800 corpus/test` and `python3 eval/build_freq.py`,
then `.venv/bin/python eval/evaluate.py` (needs `pip install spylls` and `make myspell` in
`vendor/ispell-lt`). Hunspell lt_LT is built from the same
ispell-lt data; it's the checker in LibreOffice, Firefox and Chrome.

| | varnele | Hunspell lt_LT |
|---|---|---|
| False alarms on lowercase words (tokens) | **2,018** | 2,483 |
| All diacritics dropped: detected / right fix #1 / in top 5 | 70.7 / **56.7 / 70.7 %** | 70.0 / 40.0 / 48.0 % |
| One diacritic dropped: detected / #1 | 62.3 / **60.3 %** | 62.3 / 48.0 % |
| i/y/į swapped: detected / #1 | 99.0 / 94.3 % | 98.7 / **97.3 %** |
| Keyboard typo: detected / #1 / top 5 | 89.3 / 70.0 / 87.7 % | **95.3 / 76.0 / 92.0 %** |

Undetected one-diacritic errors are mostly real-word errors
(`žmonės → žmones`). Catching those needs sentence context.

### Context rules

On the same 150 articles (edited text, so nearly every flag ought to be wrong)
the context rules raise 17 flags in 65 k words. All 17 are real errors in the
articles: 15 missing commas plus `prastos kokybes` and `daugybę metu`.

`python3 eval/restore.py` strips every diacritic from 300 real sentences, applies
the top suggestion for each flagged word and counts what comes back:

| | words only | + context rules |
|---|---|---|
| Words needing a diacritic, restored correctly | 59.7 % | **62.8 %** |
| Correct words wrongly changed | 0 | 1 |
| Whole sentence exactly right | 23.0 % | **26.7 %** |

Most of what is still missed is valid without diacritics and needs wider
context: `kalba`/`kalbą`, `nedidele`/`nedidelė`, `virs`/`virš`.

## Known gaps

- The lexicon (2020) lacks many loanwords and names (`klipas`, `singlas`, foreign surnames).
- Ordinary typos are detected and ranked less well than by Hunspell.
- Context rules cover prepositions, agreement and quantities only. Verb government
  (`pakeičiau pora` → `porą`), subject–verb agreement and the genitive after
  negation (`neturiu laiką` → `laiko`) are not checked yet.
