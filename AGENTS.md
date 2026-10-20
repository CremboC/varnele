# Varnelė: agent notes (read this first, every session)

Rule-based Lithuanian spell and grammar checker, plus a fork of the HeliBoard
Android keyboard that uses it for autocorrect. This file is the memory of the
project: what exists, why it is built this way, what was learned, what is next.
Keep it current when something changes.

## Goals and preferences of the owner

- Lithuanian checking that actually works on a phone, **as you type, with
  autocorrect**. Without autocorrect it "slows everything down massively", so a
  checker that only underlines is not enough.
- Typical input is typed **without diacritics** (`maciau`, `pries pora dienu`)
  and in the **spoken register** (`valgyt`, `buvom`, `mokykloj`).
- Rule-based grammar first; statistics only where rules cannot decide
  (ranking by word/lemma frequency).
- Measure every change: false alarms on real text, plus the restoration and
  keyboard simulations below. Precision matters more than recall.
- Commit when asked; push to `origin` (github.com/CremboC/varnele) when asked.

## Repositories

| Path | What |
|---|---|
| `~/git/varnele` | This repo. Python grammar "compiler", Rust runtime, Android spell-checker app, evaluations |
| `~/git/HeliBoard` | Fork of github.com/Helium314/HeliBoard (GPL-3.0) with Varnelė as the Lithuanian dictionary. Local only; no GitHub fork yet. Its `AI_USAGE.md` forbids AI-generated upstream PRs: **never open PRs upstream from this work** |

Layout of this repo:

```
varnele/        Python: lexicon loading, paradigms, analyzer, suggestions, grammar rules, export
rust/core       Rust runtime: same behaviour, loads data/varnele.bin   (crate "varnele")
rust/android    JNI bridge (cdylib libvarnele_android.so, data embedded via include_bytes!)
android/        Stand-alone app: system spell checker service + test screen
eval/           evaluate.py (vs Hunspell), restore.py, parity.py, keyboard_sim.py, corpus fetch/freq
tests/          unittest: test_morphology.py, test_grammar.py
vendor/ispell-lt  BSD word list (stems + class flags only; its affix rules are NOT used)
data/           extra.txt (our lexicon additions), abbreviations.txt, freq.tsv, lemma_freq.tsv,
                varnele.bin (generated, git-ignored), index.pkl (cache, git-ignored)
corpus/         Wikipedia articles (git-ignored): test/ (150, evaluation only), freq/ (600, frequencies)
```

## Commands

```bash
python3 -m unittest discover tests                 # all tests (must stay green)
python3 -m varnele check FILE [--formal] [--no-grammar]
python3 -m varnele words WORD...                   # analyses + suggestions
python3 -m varnele export                          # -> data/varnele.bin (needed by Rust/Android)
cargo build --release --manifest-path rust/Cargo.toml
rust/target/release/varnele check FILE | json FILE | words W... | kb WORD [CONTEXT...] | bench
python3 eval/parity.py                             # Rust must equal Python: 100% identical findings
python3 eval/restore.py --sentences 300            # strip all diacritics, measure restoration
python3 eval/keyboard_sim.py "kodel nepataiso ..." # simulate the HeliBoard fork word by word
.venv/bin/python eval/evaluate.py                  # vs Hunspell lt_LT (needs spylls + make myspell)
```

Wikipedia false-alarm check (run after every grammar change; all flags should be
real errors in the articles):

```bash
python3 - <<'EOF'
import collections, pathlib
from varnele.__main__ import Checker
ck=Checker(); by=collections.Counter()
for p in sorted(pathlib.Path("corpus/test").glob("*.txt")):
    t="\n".join(l for l in p.read_text().splitlines() if "\\displaystyle" not in l and "{\\" not in l)
    for f in ck.check_text(t):
        if f.rule not in ("unknown","colloquial","context"): by[f.rule]+=1; print(f.rule, f.word, f.suggestions[:2])
print(dict(by))
EOF
```

Android (both projects): `JAVA_HOME=$HOME/.sdkman/candidates/java/current`,
SDK `~/Library/Android/sdk`, adb `~/Library/Android/sdk/platform-tools/adb`.
`cd android && ./gradlew installDebug`; HeliBoard: `cd ~/git/HeliBoard && ./gradlew assembleDebug`
then `adb install -r app/build/outputs/apk/debug/HeliBoard_4.3-beta1-debug.apk`.
Varnelė debug logs on the phone: `adb logcat -s Varnele:V`.

## Architecture and key decisions

1. **Lexicon = ispell-lt stems + flags**, our own paradigms generate every form
   (12 noun declensions, adjectives with definite forms/degrees/-umas/-okas, verbs
   from 3 principal parts: all tenses, moods, participles, gerunds, verbal nouns,
   reflexives). ~10 M forms.
2. **Index = stem + shared ending signature** (~96k stems, ~400 signatures).
   Lookup tries every split point. Diacritic-blind ("folded") index is built lazily.
3. **Sound rules at the stem/ending boundary** (`phonology.join`): t/d+i+back
   vowel → č/dž, j+i → j, future s/š merge, imperative g/k+k → k.
4. **Prefix grammar at lookup**: ne-/nebe-/be-/te-/tebe- + 12 verbal prefixes
   (api-/ati- before p/b, t/d) + -si- infix, checked against ispell prefix flags.
   Principal parts with *no* prefix flags (data gap, e.g. krinta) accept all prefixes.
5. **Spoken register layer**: -t, -m, -t(e), -s(i), -oj, -ėj, -uj, -y, -uos, -om, -ėm, -im…
6. **Productive word formation** (derivation suffixes, compounds, prefixoids
   geo-/neo-/anti-…) with **blocking**: a guessed analysis is rejected if a
   dictionary word is one slip (diacritics or one typo) away.
7. **Suggestions**: diacritic-blind lookup + one typo on folded text; ranking =
   weighted edit distance (same-class diacritic 0.3, adjacent key 0.8, other 1.0)
   minus form and lemma frequency bonuses. Lowercase input penalises capitalised names.
8. **Context rules** (`grammar.py` / `grammar.rs`), see list below. Case rules
   only fire when a **diacritic-only** variant satisfies them; re-inflection
   (negation, subject, object) is generated from the word's own entry.
9. **Python = compiler/reference, Rust = runtime.** `export` writes everything
   the runtime needs; Rust must stay **line-for-line equivalent** (parity 100%).
   Any rule change goes into both `varnele/grammar.py` and `rust/core/src/grammar.rs`,
   then `eval/parity.py`.
10. Offsets are characters in Python/Rust; the JNI bridge converts to UTF-16.

## Context rules (all in Python and Rust)

| Rule | Example | Main exceptions (each from a real false alarm) |
|---|---|---|
| case (prepositions) | `prieš pora` → `porą`, `į didele kavine` | genitive modifiers (`su lietuvių kultūra`), `apie` + quantity (`apie pusė`), numerals (`per šešiolika`), phrase must end in a noun, phrase stops at a word that can't agree (`už didžiausią | tuo metu`), participles end the phrase |
| quantity | `daug vaiku` → `vaikų` | comparatives (`kiek silpnesnes`), only `kind == num` for -lika/-dešimt (not `Respublika`) |
| agreement (adj+noun, case/number/gender) | `gražią kavine`, `prastos kokybes` | `viena kitą`; adjective that is likely a verb (`palaikė`); skip over genitive modifiers to the head (`profesionalūs [Lietuvos cirko] artistai`); unknown word never changes a known neighbour; participles allowed except when the noun can be acc/loc or the participle is a predicate verb (`tapusią vienuole`, `išrinktas prezidentu`, `einanti sakinio gale`) |
| negation | `neturiu laiką` → `laiko`, `nemačiau jį` → `jo`, `nepataiso visu` → `visų` | durations/quantities (`nedirbau visą dieną`, `daugybę metų`), copulas |
| subject | `aš buvo` → `buvau` | only adjacent pronoun + finite verb |
| object (1st/2nd person verb) | `mačiau namas` → `namą` | copulas, reflexives, verbs only if "mostly a verb" (not `metu`, `keli`, `tik`) |
| relative | `žodžių kuriu aš rašau` → `kurių` | needs a following finite verb (`dainas kuriu pats` stays) |
| comma | `sakė kad` → `, kad`, before kuris-forms and preps + kuris | `bet kas`, `kai kurie`, `kas nors`, `nors ir`, names/initials, after another connective |

"Mostly a verb": listed particles/adverbs (`W`) are never verbs; otherwise verb
lemma frequency must beat other lemmas (`mačiau` yes, `metu` no). A rule-built
prefix reading does not make an adjective a verb (`prastos` ≠ `pra+stos`).

## Keyboard (HeliBoard fork) design

- `dictionary/VarneleDictionary.kt`: main dictionary for locale `lt`, prepended
  in `DictionaryFactory.getMainDictsForLocale`. Calls `Native.check(word, prevWords)`
  (Rust `keyboard_word`). HeliBoard autocorrects when
  `score/1e6 * (1 - editDistance/len)` ≥ threshold (~0.185) or the suggestion is
  `KIND_WHITELIST`.
  - valid typed word → returned with score 1.2M (never "corrected")
  - context fix of a valid word: diacritic-only → whitelisted, 1.3M (autocorrects);
    otherwise 1.1M (shown only)
  - unknown word: score `(2 - cost) * 700k`; whitelisted if diacritic-only and
    clearly best (margin 0.08, or context chose); autocorrect-appropriate if
    **typoCost ≤ 1.0**, where typoCost is the edit cost ignoring diacritics
    (`zodzou` → `žodžių` = 0.8)
  - gesture typing (batch mode) is left to binary dictionaries
- `inputlogic/VarneleSentenceFixer.kt`, hooked at the end of
  `InputLogic.handleSeparatorEvent`: after each finished word, re-check the
  current sentence and apply **only** diacritic-only grammar fixes and missing
  commas, two passes, rewriting from the first changed character through
  `RichInputConnection`. This is how later words fix earlier ones
  (`visu … žodžių` → `visų`, `kuriu … rašau` → `kurių`, `, kurių`).
- `dev/imbrasas/varnele/Native.kt`: JNI class name must stay exactly this.
  ProGuard keep rule added. Library missing → keyboard works without Varnelė.
- Gradle task `cargoBuildVarnele` builds the Rust lib for 4 ABIs from
  `../varnele` (or `-Pvarnele.dir=`) into `app/src/main/jniLibs` (git-ignored).

## Latest numbers

- Wikipedia (150 articles, 65k words): 18 context flags, **all real errors**
  (15 commas, `kylanti grėsme`, `prastos kokybes`, `daugybę metu`).
- vs Hunspell lt_LT: fewer false alarms on lowercase words (2,018 vs 2,483 tokens),
  better diacritic fixes (#1 correct 56.7% vs 40.0%), worse on keyboard typos
  (detect 89.3 vs 95.3%, #1 70.0 vs 76.0%).
- Restoration (all diacritics stripped, 300 sentences): 59.7% → 62.8% with
  context rules; words valid without diacritics (29%) are the ceiling for a
  checker; a most-frequent-spelling baseline gets 71.9%.
- Rust: load 22 ms, correct word 0.001 ms, misspelling + suggestions ~0.8 ms,
  sentence ~1.6 ms (Mac). Phone (Fold7): 0.05–0.8 ms valid words, 6–17 ms
  unknown words with suggestions, data load ~110 ms. Data file 5.3 MB.
- Keyboard simulation: `kodel nepataiso visu zodzou kuriu as rasau?` →
  `kodėl nepataiso visų žodžių, kurių aš rašau?`

## Gotchas (learned the hard way)

- Gradle **configuration cache** freezes task environments. The cargo task sets
  its own `TMPDIR` (build/tmp/cargo); otherwise a dead sandbox temp dir breaks rustc.
  Script-level vals must not be captured in task actions.
- Newer AGP: `android.ndkDirectory` is gone; use
  `androidComponents.sdkComponents.sdkDirectory` + `android.ndkVersion`.
- `android:supportedAttributes` in spellchecker.xml is not recognised by SDK 35.
- targetSdk 35+ is edge-to-edge: apply window insets (status bar, cutout, ime).
- Galaxy Z Fold7 has two displays: `screencap` needs a display id; use
  `uiautomator dump` to read the screen as text instead.
- Wireless adb drops regularly; re-check `adb devices` before installing.
- zsh does not word-split `$VAR` commands; use a shell function.
- Parity needs deterministic order: inflection reads forms from the index
  (`Index.entry_forms`), sorts use (score, word) keys.
- `varnele/restore.py` is an untracked, unused prototype of a sentence restorer
  (the keyboard's sentence fixer replaced the idea). Don't commit it unless asked.
- Wikipedia API rate-limits; `fetch_corpus.py` uses cirrusdoc bulk text with backoff.

## Ideas and open problems (backlog)

- **Verb transitivity lexicon** (from a corpus or verb flags): would allow
  `Radau nukritusia sagute` → `nukritusią sagutę` (object of a 3rd/1st person
  verb in instrumental). Motion verbs take instrumental (`einu gatve`), so it
  can't be a blanket rule.
- Agreement across a whole phrase: `dar viena nukritusią sagutę` → `vieną`
  (pronoun/numeral before adj+noun).
- Bigger frequency corpus (full Wikipedia dump) and word-pair counts for ranking
  ambiguous diacritic choices (`žmones`/`žmonės`).
- Lexicon gaps: loanwords and names (`klipas`, `singlas`); induce stems from a
  corpus by finding multiple forms of a guessed paradigm.
- Keyboard: completions for half-typed words (now we show corrections);
  speed up unknown-word suggestions (6–17 ms on phone); interplay of the
  sentence fixer with HeliBoard's backspace-reverts-autocorrect is untested.
- Typo detection/ranking still behind Hunspell; keyboard-adjacency weights could
  be tuned on real typing data.
- Spoken-form normalisation option in the keyboard (`valgyt` → `valgyti`) is
  available (`--formal`) but not wired to a setting.
- Create a GitHub fork for HeliBoard changes when the owner asks.
- iOS later: the Rust core is portable; keyboard extensions have tight memory limits.

## History (commits on varnele/main)

1. Rule-based checker, ispell-lt stems, evaluation vs Hunspell
2. Context rules: prepositions, agreement, quantities, commas
3. Verb rules: negation genitive, subject-verb person, objects
4. Rust runtime + Android spell-checker app (parity 100%)
5. (this round) participle agreement, negation via diacritics, relative pronoun,
   typo candidates as context variants, keyboard typo cost, AGENTS.md
