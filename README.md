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
| Context rules | `varnele/grammar.py` | Preposition government (`prieš pora` → `porą`, `kabo virs stalo` → `virš`), adjective–noun agreement in case/number/gender, predicate adjectives (`ji nedidele` → `nedidelė`), genitive after quantities (`daug vaiku` → `vaikų`) and before a head noun (`gyventoju skaičius` → `gyventojų`), missing commas before `kad`, `nes`, `bet`, `kuris`…; genitive after negation (`neturiu laiką` → `laiko`), subject–verb person (`aš buvo` → `buvau`), objects of 1st/2nd person verbs and of 3rd person ones whose subject comes first (`mačiau namas`, `Jonas mato namas` → `namą`). Fixes are generated from the word's own paradigm. For an unknown word typed without diacritics the same rules choose among its candidates (`dalyvaujanciu saliu` → `dalyvaujančių`, `rado salyga` → `sąlygą`) |
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
(`žmonės → žmones`). The context rules below catch the ones grammar decides.

### Context rules

On the same 150 articles (edited text, so nearly every flag ought to be wrong)
the context rules raise 19 flags in 65 k words. All 19 are real errors in the
articles: 16 missing commas plus `prastos kokybes`, `kylanti grėsme` and `daugybę metu`.

`python3 eval/restore.py` strips every diacritic from 300 real sentences, applies
the top suggestion for each flagged word and counts what comes back:

| | words only | + context rules |
|---|---|---|
| Words needing a diacritic, restored correctly | 63.1 % | **68.3 %** |
| Correct words wrongly changed | 0 | 1 |
| Whole sentence exactly right | 24.3 % | **29.0 %** |

Most of what is still missed is valid without diacritics and grammar can't decide
it (`kalba` is "speaks" and "language", `žmones` an accusative). A model of case
sequences trained on the frequency corpus was tried for these and left out: on
173 k words of training text it changed too many correct words (see AGENTS.md).

## Rust runtime and Android app

Python is the grammar compiler; Rust is the runtime. `python3 -m varnele export`
writes `data/varnele.bin` (5.3 MB, 1.7 MB gzipped): stems, ending signatures,
frequencies and derivation tables. `rust/core` loads it and does all checking.

```
python3 -m varnele export
cargo build --release --manifest-path rust/Cargo.toml
rust/target/release/varnele check FILE
rust/target/release/varnele bench
python3 eval/parity.py        # Rust and Python must give identical findings
```

On the 150 test articles all 7,678 findings are identical. On an M-series Mac
Rust checks a misspelled word with suggestions in ~0.8 ms and a 12-word
sentence with all grammar rules in ~1.6 ms (load: 22 ms, ~90 MB peak).

`android/` is an app with the checker built in (`rust/android`, a JNI bridge).
It registers a system spell checker (red underlines for misspellings, blue for
grammar on Android 12+) and has a test screen. Needs the Android SDK + NDK
27.2, `cargo-ndk` and the Rust target `aarch64-linux-android`:

```
cd android && ./gradlew installDebug
```

Then pick Varnelė as the spell checker (Settings → search "spell checker").
It cannot replace a keyboard's own autocorrect (Gboard, Samsung Keyboard).

## Known gaps

- The lexicon (2020) lacks many loanwords and names (`klipas`, `singlas`, foreign surnames).
- Ordinary typos are detected and ranked less well than by Hunspell.
- Verb rules only fire on unambiguous verbs and phrases, so ambiguous cases pass:
  `pakeičiau pora` (`pora` could be instrumental), objects of 3rd person verbs with no
  subject before them (`Mato namas Jonas`), and words in between other than adverbs.

## Licence

BSD 3-Clause, see [LICENSE](LICENSE). The word list in `vendor/ispell-lt` and the
data generated from it (`data/varnele.bin`) also carry the ispell-lt notice
([vendor/ispell-lt/COPYING](vendor/ispell-lt/COPYING)); ship both with any binary.

The word and word-pair counts (`data/freq.tsv`, `data/lemma_freq.tsv`, `data/bigrams.tsv`, and
in `data/varnele.bin`) are counted from [Lithuanian Wikipedia](https://lt.wikipedia.org)
(CC BY-SA 4.0), subtitles from [OpenSubtitles.org](https://www.opensubtitles.org) via the
[OPUS](https://opus.nlpl.eu) collection (P. Lison and J. Tiedemann, 2016, *OpenSubtitles2016:
Extracting Large Parallel Corpora from Movie and TV Subtitles*) and [Tatoeba](https://tatoeba.org)
(CC BY 2.0 FR). Only counts are kept, no text; credit these sources with any binary.
