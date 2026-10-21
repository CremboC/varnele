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
| `~/git/HeliBoard` | **Varnelė Klaviatūra (HeliBoard fork)**: fork of github.com/Helium314/HeliBoard (GPL-3.0) with Varnelė as the Lithuanian dictionary, at github.com/CremboC/Varnele-Keyboard (renamed from CremboC/HeliBoard on 2026-10-20), work on branch `main` (the old `varnele` branch was fast-forwarded into it and deleted). Remotes: `origin` = upstream Helium314/HeliBoard, now HeliBorg/HeliBoard (pull only, never push; take updates by merging `origin/main` into `main`), `fork` = CremboC/Varnele-Keyboard (push here). Upstream's `AI_USAGE.md` forbids AI-generated upstream PRs: **never open PRs upstream from this work** |

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
python3 eval/commas.py [corpus/freq] [--show-wrong]  # strip all commas, precision of each comma rule
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
then `adb install -r app/build/outputs/apk/debug/VarneleKlaviatura_1.0-debug.apk`.
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
   weighted edit distance (same-class diacritic 0.3, i/y 0.6 because y is its own key
   so `sita` means `šita` not `syta`, adjacent key 0.8, other 1.0)
   minus form and lemma frequency bonuses. Input typed with no diacritics at all pays
   0.3 once for any number of missing diacritics, so frequency decides (`turetu` →
   `turėtų`, not the rare `turėtu`); restoration 62.9% → 65.8%. A word's diacritic
   variants in grammar are ordered by this cost (`šitą` before `sytą`). Lowercase input penalises capitalised names.
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
| case (prepositions) | `prieš pora` → `porą`, `į didele kavine`, `link namu` → `namų` | genitive modifiers (`su lietuvių kultūra`), `apie` + quantity (`apie pusė`), numerals (`per šešiolika`), phrase must end in a noun, phrase stops at a word that can't agree (`už didžiausią | tuo metu`), participles end the phrase |
| quantity | `daug vaiku` → `vaikų`; a number ending in 0 or 11–19 + noun (`10 metu` → `metų`, `15 euru`) | comparatives (`kiek silpnesnes`), only `kind == num` for -lika/-dešimt (not `Respublika`); numbers: only a known lowercase noun right after the number (not units `20 m atstumu`, manner `12 etniniu pagrindu`, labels `KNM-ER 1813 atveju`), not decimals or ordinals |
| case (verbs, indefinites) | GENITIVE_VERBS laukti, ieškoti, bijoti, siekti, reikėti, vengti: `lauksiu tavo zinutes` → `žinutės`, `ieškau raktu`; `koki nors` → `kokį nors`, `ka nors` → `ką nors` | verbs as in negation (durations, quantities), possessives skipped (`tavo`); prefixed verbs only with a real prefix (`plaukė` is not `p+laukė`) |
| agreement (adj+noun, case/number/gender) | `gražią kavine`, `prastos kokybes`, `šita žmogų` | `viena kitą` (only before a kitas form: `vienos eilutes` → `eilutės`); adjective that is likely a verb (`palaikė`); skip over genitive modifiers to the head (`profesionalūs [Lietuvos cirko] artistai`); a genitive with no head after it is checked on its other noun readings (`žmogų` is also a bogus gen pl); unknown word never changes a known neighbour; participles allowed except when the noun can be acc/loc or the participle is a predicate verb (`tapusią vienuole`, `išrinktas prezidentu`, `einanti sakinio gale`). Which word changes: a preposition before decides (`pro nedideles gyvenvietės` → `gyvenvietes`), else the one typed without diacritics (`nedidele mergaitė` → `nedidelė`, `visa energiją` → `visą`) |
| predicate adjective | `ji nedidele` → `nedidelė`, `mergaitė buvo (labai) nedidele` | subject = jis/ji/jie/jos or a noun whose most frequent lemma is nominative; nouns and `jos` need a nominative copula (būti, atrodyti, likti, jaustis; not `tapo parapine`); the adjective ends the clause; participles skipped |
| genitive before a head noun | `miesto gyventoju skaičius` → `gyventojų`, `vietoves gyventojai` → `vietovės`, `branduoliniu ginklu sutartis` (modifiers too) | each from Wikipedia: not when both share a case (`pilotu bandytoju`, `naktiniu gyvenimu`), head genitive-only, head a verb or adverb (`su broliu namo`); not lemma metas (`vienu metu`); not when the form is ≥⅓ as frequent as its genitive (`Sovietmečiu`, `laikotarpiu`); not after a verb, possessive, `šiuo`, or a governing preposition up to 3 words left (`į Kalavijuočių ordino žemes`); an instrumental after a genitive or name only if its genitive is seen 5+ times (`vidaus reikalų` yes, `karo metu`, `Vyriausybės potvarkiu` no) |
| preposition that became a verb | `kabo virs stalo` → `virš` | the phrase after it takes the preposition's case and the clause already has a verb before it (`Mama virs sriubos` = will boil) |
| negation | `neturiu laiką` → `laiko`; a typo after an adjective takes the agreeing genitive (`visų zodziou` → `žodžių`, not `žodžio`; also via the adjective's diacritic variants), `nemačiau jį` → `jo`, `nepataiso visu` → `visų` | durations/quantities (`nedirbau visą dieną`, `daugybę metų`), copulas, a one-word phrase with an adverb reading (`neatėjo laiku` = on time) |
| subject | `aš buvo` → `buvau`, `aš vakar buvo`, `jis jau einu` | pronoun + finite verb, up to 2 adverb/particle-only words between (not pronouns, connectives, prepositions, `ne`, `tai`); not a coordinated subject (`aš ir jis buvome`). An unknown word after the pronoun ranks verbs of that person first (`jis ziuri` → `žiūri`, not the jury `žiuri`, which the Wikipedia corpus prefers) |
| object (1st/2nd person verb; 3rd person transitive verb with its subject before it) | `mačiau namas` → `namą`, `matau dar viena klaida` → `vieną klaidą`, `Jonas mato namas`, `jis vakar nupirko nauja knyga`, `mačiau labai gražus namas` (adverbs between) | 3rd person: only TRANSITIVE_VERBS with a real prefix, not reflexive (`atsirado` = atsi+rado); the subject is jis/ji/jie or a noun whose most frequent lemma is nominative (`Jonas`, not the name Jona), not coordinated (`Jonas ir Petras`); no infinitive in the phrase (`turėtų būti suprantama`), no lone adverb (`atsirado kartu`); copulas, reflexives, verbs only if "mostly a verb" (not `metu`, `keli`, `tik`); nom/ins words only after TRANSITIVE_VERBS (matyti, rasti, turėti…; not motion `einu gatve` or instrument `rašau ranka`); skips `dar/jau/vėl/irgi/tik/net`; not clause words (`manau, kas…`). After a transitive verb the phrase may hold participles and an instrumental-only word takes its accusative diacritic twin (`radau nukritusia sagute` → `nukritusią sagutę`) when the whole phrase is instrumental or the head is already accusative (keyboard order); same POS/number/gender (`tuo metu` ≠ `metų`); not `tapusią vienuole` |
| relative | `žodžių kuriu aš rašau` → `kurių`; case from the clause verb: `knyga, kuria skaičiau` → `kurią` | needs a following finite verb (`dainas kuriu pats` stays); not when `kuriu` is the verb kurti: an object pronoun or `ir` + verb follows (`kuriu tai, kas`, `kuriu ir rašau`); the case fix needs a non-negated, non-reflexive TRANSITIVE_VERBS verb within 2 words (a transitive reading counts even if not "mostly a verb": `skaičiau`/`skaičius`); not `plunksna, kuria rašau`, `kuria didžiuojuosi` |
| comma | `sakė kad` → `, kad`; before `net`/`ypač` + connective (`veikia, net jeigu`); indirect question after QUESTION_VERBS when a verb follows (`matau, ką man rašo`, not `ką nors`, `ką tik`), before kuris-forms and preps + kuris; demonstrative + kas-word (`tai, kas reikalinga`, `viską, ką turiu`) | `bet kas`, `kai kurie`, `kas nors` (also typed without diacritics: `koki nors`), `nors ir`, names/initials, after another connective; a kuris-form that is the verb kurti (`kuria ir parduoda`, `kuria baldus`, `kuri kuria`, `kuria tai`; `kuria ir` at the end waits for the next word); `Tai kas …?` at a sentence start |
| comma (section 8) | parenthetical `Deja, …`, `Beje`, `Pavyzdžiui`, `Vadinasi`, `Kita vertus`, `Be abejo`, `Mano nuomone`, `Ko gero` at sentence start; `jis, deja, …` / `beje` / `pavyzdžiui` inside (both sides); greeting + address `Labas, Jonai, kaip…`, `Ačiū, drauge`; `…, negu` + verb within 3 words; repeated `nei…, nei`, `arba…, arba`, `Ar…, ar`; postposed participial phrase `žmogus, stovintis prie lango, žiūri`; lists `obuolius, kriaušes ir slyvas` | `Žinoma` only before a pronoun/verb (`Žinoma tik viena rūšis`); not after a connective; `Laba diena`, `Sveiki draugai` (agreeing adjective); mid-sentence `ar` = "or"; participle: not a nominative past participle (predicate `Pavadinimas kilęs`), not a nominative with no other verb in the sentence (`Laumės mėgstančios`), not if a capitalised word or agreeing noun follows within 3 words (`žygiavusia Aleksandro kariauna`), not genitive-only agreement; list: three lowercase nouns with no genitive reading sharing case+number, not time words, not after a modifier (`tomis pačiomis spalvomis ir`) |

"Mostly a verb": listed particles/adverbs (`W`) are never verbs; otherwise verb
lemma frequency must beat other lemmas (`mačiau` yes, `metu` no). A rule-built
prefix reading does not make an adjective a verb (`prastos` ≠ `pra+stos`).

## Keyboard (Varnelė Klaviatūra, HeliBoard fork) design

- Renamed "Varnelė Klaviatūra": app ID `dev.imbrasas.varnele.keyboard` (`.debug` for debug
  builds), provider authorities under the same ID, so it installs next to HeliBoard.
  Internal packages stay `helium314.keyboard.*`. Lithuanian is enabled first on a fresh
  install. Credits are in the fork's README and the About screen.
- Fork defaults on: key borders, vibration, number row, emoji key, language switch key.
- **Gboard layout on every screen**: `Settings.useTabletLayout()` is false, so tablets and the
  Fold inner screen (≥600 dp, HeliBoard's "tablet") keep the phone layout (backspace next to `m`,
  enter bottom right, no extra `, .` keys, full key width). Split mode is cut from it:
  `⇧ z x c v | b n m ⌫` like Gboard (the tablet layout put `b` left). Split is on by default only
  on a foldable that is open with smallest width ≥600 dp (`Defaults.splitKeyboardDefault`): Fold
  open yes, Flip never (open it is phone-sized, closed only the cover screen). Upstream's
  `isTablet` is false for sw768dp+ (metrics 2), so this uses `Settings.isWideScreen()`.
  A typed space is moved behind `. , ; : ! ?` (`tašką .` → `tašką. `).
- `dictionary/VarneleDictionary.kt`: main dictionary for locale `lt`, prepended
  in `DictionaryFactory.getMainDictsForLocale`. Calls `Native.check(word, prevWords)`
  (Rust `keyboard_word`). HeliBoard autocorrects when
  `score/1e6 * (1 - editDistance/len)` ≥ threshold (~0.185) or the suggestion is
  `KIND_WHITELIST`.
  - valid typed word → returned with score 1.2M (never "corrected")
  - context fix of a valid word: diacritic-only or the subject rule (`aš buvo` →
    `buvau`, owner's choice) → whitelisted, 1.3M (autocorrects); otherwise 1.1M (shown
    only). The sentence fixer applies subject fixes only to the word just finished, so a
    backspace revert of an earlier word is not undone.
  - unknown word: whitelisted if diacritic-only and clearly best (margin 0.08,
    or context chose); autocorrect-appropriate if **typoCost ≤ 1.0**, where
    typoCost is the edit cost ignoring diacritics (`zodzou` → `žodžių` = 0.8).
    **Scores compensate HeliBoard's normalisation**, which counts every changed
    letter including diacritics (`zodzou` → `žodžių` = 4 edits / 6 letters):
    score = target × 1e6 / (1 − levenshtein/len), target 1.0 for diacritic-only,
    0.9 − 0.4·typoCost for one typo, 0.05 otherwise; scores kept strictly decreasing.
  - **rare twin** (Rust `keyboard_word`, keyboard only): a valid word whose form and
    lemma never occur in the frequency corpus, with a diacritic-only twin whose
    lemma does, gets the twin as a context fix (`sakini` → `sakinį`). A capitalised word counts its
    lowercase readings too (`Kuriu` is the name Kurys, but also `kuriu`, so it is not → `Kurių`). A twin that is only
    a participle or a vocative is never kept (`testuoju` no longer → `tęstuoju`). The rule
    also covers never-seen 2–4 letter words one neighbouring key from a word seen 50+
    times (`verai` → `gerai`, not the name `Verai`); keyboard-only `kak` → `kai`.
  - suggestion ranking: a negated form with no frequency of its own borrows the plain
    form's (`Neturetu` → `Neturėtų`); a suggestion differing from the input only by being a
    capitalised name costs +0.5.
  - **key-shift** (setting `varnele_key_shift`, default on, Text correction screen):
    if the word is unknown and no correction is within one typo, search words where
    every letter is the typed key or a neighbour (`fofrkua` → `didelis`, `ksbsd` →
    `labas`); DFS over a folded stem-prefix set with a 200k-step budget, ranked by
    lemma+form frequency then fewest shifted keys; top guess autocorrects.
    0.4 ms per word after warm-up (tables built in warmUp).
  - `Suggest.kt` (fork change): a whitelisted Varnelė suggestion always autocorrects.
    Upstream lets the user-history predictions veto a fix when the typed word is valid,
    and testing teaches it the uncorrected words (`nauja sakini` stayed).
  - gesture typing (batch mode) is left to binary dictionaries
- `inputlogic/VarneleSentenceFixer.kt`, hooked at the end of
  `InputLogic.handleSeparatorEvent` and `onPickSuggestionManually` (a picked suggestion
  finishes a word too; the picked word itself is left as chosen): after each finished word, re-check the
  current sentence and apply **only** diacritic-only grammar fixes and missing
  commas, two passes, rewriting from the first changed character through
  `RichInputConnection`. It first re-checks the word the separator just finished and
  applies `VarneleDictionary.confidentFix` (the whitelisted kind), so punctuation
  (`sakini?`) and learned words can't leave it unfixed. This is how later words fix earlier ones
  (`visu … žodžių` → `visų`, `kuriu … rašau` → `kurių`, `, kurių`).
- **Red underline for unknown words** (`VarneleDictionary.markMisspelled`, called from
  `InputLogic.commitChosenWord`): a committed word Varnelė does not know gets a
  `SuggestionSpan` with `FLAG_MISSPELLED` and its corrections, so the text field draws the
  underline itself, as Gboard does, whatever the system spell checker is. Only
  `FLAG_MISSPELLED`: fields drop a span that also has `FLAG_EASY_CORRECT` (tested on the
  Fold7; `FLAG_GRAMMAR_ERROR` alone draws blue, could mark grammar findings). Underlines
  are lost when the field is refocused or the keyboard restarts, and the sentence fixer's
  rewrite drops them for the rewritten text.
- The system spell checker (`dev.imbrasas.varnele` app) gets no session when its language is
  "automatic" and the phone language is not Lithuanian: Android matches the system locale.
- `dev/imbrasas/varnele/Native.kt`: JNI class name must stay exactly this.
  ProGuard keep rule added. Library missing → keyboard works without Varnelė.
- Gradle task `cargoBuildVarnele` builds the Rust lib for 4 ABIs from
  `../varnele` (or `-Pvarnele.dir=`) into `app/src/main/jniLibs` (git-ignored).

## Release builds and Google Play (keyboard)

- CI: `.github/workflows/varnele-release.yml` in the fork, on push to `main` and manual
  dispatch. Checks out this repo (main) next to HeliBoard, Python 3.12, Rust + 4 Android
  targets, cargo-ndk, NDK 28.0.13004108; builds the **`nouserlib`** build type (the Play
  build: no user-supplied gesture library, Play forbids loading outside code). Artifacts:
  signed `.aab` (Play) and signed universal APK (phone testing). Upstream's two workflows
  only trigger on dispatch/PR and never run on the fork (files kept for merges). While this
  repo is private, CI checks it out with secret `VARNELE_DEPLOY_KEY` (read-only deploy key
  on this repo; key pair `~/.keystores/varnele-deploy-key`).
- Version: versionName **1.0**, versionCode **10000 + GitHub run number** (env
  `VERSION_CODE`, 10000 locally). It must stay above upstream's codes (4300) because
  HeliBoard's AppUpgrade runs every `oldVersion <= N` migration; after an upstream merge,
  check new migrations with N < 10000, they won't run for our upgrades. Renaming the
  workflow restarts the run number: raise the offset above the last uploaded code.
- Signing: GitHub secrets on CremboC/Varnele-Keyboard `VARNELE_KEYSTORE_BASE64`,
  `VARNELE_KEYSTORE_PASSWORD`, `VARNELE_KEY_ALIAS` (`upload`), `VARNELE_KEY_PASSWORD`.
  Gradle reads `VARNELE_KEYSTORE_FILE` + the three others from the environment; without
  them release builds are unsigned and debug builds are unaffected.
- **Upload keystore: `~/.keystores/varnele-upload.jks`, passwords in
  `~/.keystores/varnele-upload.env`** (outside both repos, never commit). Back both up
  (password manager): losing the key means an upload-key reset through Play support.
  SHA-256 AA:14:F6:1A:17:FF:0B:A7:66:31:CA:81:66:1D:43:FE:77:38:99:5E:D8:44:2F:47:90:B4:BD:AB:20:81:D4:41.
- Local signed build: `source ~/.keystores/varnele-upload.env && ./gradlew assembleNouserlib
  bundleNouserlib`; the APK installs as `dev.imbrasas.varnele.keyboard` next to `.debug`.

## Latest numbers

- Wikipedia (150 articles, 65k words): 19 context flags, **all real errors**
  (16 commas incl. `nariu, pasiekusiu tokį aukštą postą`, `kylanti grėsme`, `prastos kokybes`, `daugybę metu`).
  The 600 freq articles: 83 flags (`kuri kuria`, `kurie kuria` no longer get a comma).
- Commas removed from the articles (`eval/commas.py`), new rules, right/wrong on test+freq:
  participial phrase 91/10 (8 of the 10 are commas missing in the articles), lists 27/0,
  parenthetical 31/0, address 2/0, negu 2/0, repeated connective 1/0. Old rules 2440/62
  (the wrong ones are mostly article errors, as in the Wikipedia check).
- vs Hunspell lt_LT: fewer false alarms on lowercase words (2,018 vs 2,483 tokens),
  better diacritic fixes (#1 correct 56.7% vs 40.0%), worse on keyboard typos
  (detect 89.3 vs 95.3%, #1 70.0 vs 76.0%).
- Restoration (all diacritics stripped, 300 sentences): 63.1% → 67.7% with
  context rules (66.1% before the genitive-before-noun rule; 59.7% → 62.8% before the flat diacritic cost); words valid without diacritics (29%) are the ceiling for a
  checker; a most-frequent-spelling baseline gets 71.9%.
- Rust: load 22 ms, correct word 0.001 ms, misspelling + suggestions ~0.8 ms,
  sentence ~1.6 ms (Mac). Phone (Fold7): 0.05–0.8 ms valid words, 6–17 ms
  unknown words with suggestions, data load ~110 ms. Data file 5.3 MB.
- Keyboard simulation: `kodel nepataiso visu zodzou kuriu as rasau?` →
  `kodėl nepataiso visų žodžių, kurių aš rašau?`; `dabar meginu nauja sakini` →
  `dabar mėginu naują sakinį`; Rust key-shift search 0.4 ms, sentence 1.5 ms (Mac).

## Gotchas (learned the hard way)

- My keyboard simulation (`eval/keyboard_sim.py`) models Varnelė's decisions, not
  HeliBoard's native score normalisation; a fix that works in the simulation can
  still fail on the phone if its score doesn't pass `calcNormalizedScore`. Always
  read `adb logcat -s Varnele:V` after a phone test.
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
- Wikipedia API rate-limits; `fetch_corpus.py` uses cirrusdoc bulk text with backoff.

- HeliBoard's user history learns every word committed as typed. Repeating a test
  sentence trains it on the wrong spelling; that is why whitelisted Varnelė fixes skip
  the history comparison in `Suggest.shouldBeAutoCorrected`.

## Ideas and open problems (backlog)

### Phone-testing list of 2026-10-19: done, and what was left on purpose

Done (rules in the table above, tests in tests/test_grammar.py): relative case from the
verb (`kuria skaičiau` → `kurią`), postposed participial phrases, parenthetical words,
greeting + address, lists, `nei/arba/ar` repeated, `negu` + clause, subject with adverbs
between, `Radau nukritusia sagute`. `ne tik …, bet ir` and `ne …, o …` were already
covered by the clause-starter rule (`bet`, `o`).

Left deliberately:
- **Sentence-initial participial phrases** (`Grįžęs namo, jis …`): under the current
  VLKK rules separating an adverbial participle phrase is optional, and Wikipedia mostly
  doesn't (prototype: 7 commas in the articles vs 23 without). An auto-inserted comma
  would be a style choice, not a fix.
- **`atrodo`, `aišku`, `pagaliau`**: also plain verbs/adverbs (`jis atrodo pavargęs`);
  **`galbūt`, `turbūt`, `tikriausiai`** are not set off at all in Lithuanian; **`be to`**
  is also "without it" (`be to negalima`).
- **`ir … ir`, `tai … tai`**: `Ir tai buvo gerai ir naudinga` (sentence `ir` + ordinary
  `ir`), and `tai` is mostly a pronoun; `nei` alone is comparative (`geriau nei aš`) and
  `kaip` has too many uses for a comma-before-clause rule.
- **Vocative without a greeting** (`Kaip sekasi Jonai?`): vocatives are mostly also
  nominative plural (`Jonai`, `draugai`), and `drauge` is also "together".
- **3rd-person noun subjects** (`Jonas esu`): `Mama einu namo` is a missing comma after
  an address, not a wrong verb.
- Only the word after the greeting is checked (`Laba diena Jonai` gets no comma).

- **Statistics for diacritic twins: tried 2026-10-21, not shipped.** A class-bigram model
  (POS+case labels, top function words lexicalised, one EM step) trained on corpus/freq.
  Choosing between same-lemma twins that only add diacritics: at a 100:1 likelihood ratio
  it restored 54 twins (4 wrong) in 300 stripped sentences but changed 9 words in the 65k
  correct test words; at 10:1, 118/8 and 86 changes. Most of its correct-text changes are
  `karo metu` and acc/nom choices needing the verb. As a re-ranker of unknown words'
  diacritic candidates it moved #1 from 1005 to 1024 of 1267. Not worth a new table in
  varnele.bin; retry with a much bigger corpus (full Wikipedia dump plus conversational text).
- The keyboard applies only diacritic-only fixes, so re-inflections from the object rule
  (`Jonas mato namas` → `namą`) are shown but never autocorrected; `nauja knyga` → `naują knygą` is.
- Verify on the phone (owner's tests so far found real gaps every time): the
  score compensation for `zodzou`, rare twins, key-shift autocorrect.
- The frequency corpus (600 articles, 173k words) is too small for the rare-twin
  rule and for ranking; a full Wikipedia dump would help a lot.

- **Verb transitivity**: a small hand list (TRANSITIVE_VERBS) exists; a corpus-derived
  one would cover more. Still open: `Radau nukritusia sagute` (participles end the
  phrase, and `sagute` is instrumental-only so it needs the acc diacritic variant).
- Agreement across a whole phrase: `dar viena nukritusią sagutę` → `vieną`
  (pronoun/numeral before adj+noun).
- Bigger frequency corpus (full Wikipedia dump) and word-pair counts for ranking
  ambiguous diacritic choices (`žmones`/`žmonės`).
- ispell-lt has no plain reflexive-only verbs (džiaugtis, juoktis, elgtis, domėtis;
  only apsidžiaugti etc. in lietuviu.ivpk). Added to data/extra.txt; others may be
  missing too: check 1sg `-uosi` forms of common ones.
- data/extra.txt drops `bereikal` (`-bereikal`) and adds `bereikalo`.
- Idea: `net ne vienos/vieno/vienas` + noun almost always means `nė vienos` (not a single);
  plain `ne vienas` ("more than one") is valid, so only `net ne` + a vienas form is a signal.
- ispell-lt lists some pronouns as nouns too (`šita/D`, `kita/D`, `tokia/ND`), which hides
  them from agreement. `-word/FLAGS` in data/extra.txt drops such an entry.
- Lemma frequencies: a listed particle/preposition reading (tag W) takes the whole count
  of its form, else `iš` made the verb `ižti` "common" (1175) and `neisiu` was "fixed"
  to `neišiu` by the rare-twin rule. Names share lowercased lemma keys with verbs
  (`Klausė`/`klausė`), so a capitalised suggestion for lowercase input costs +0.3.
- The keyboard inserts a comma only once the next word is typed (`pirk bet` → `bet ką`).
  Commas *after* a word (`Deja, jis`) are issues on the following word, so they wait one
  more word: `Deja jis.` at the end of a message stays without the comma.
- Rules that need the first fix to see the second: `labas, jonai kaip` (gap may be a comma),
  `radau nukritusia sagutę` (autocorrect fixes the last word first). Test both orders.
- Reviewed en.wikipedia Lithuanian_grammar (2026-10-20). Added from it: numbers + genitive plural,
  genitive-governing verbs. Not added: `arti` + genitive (also the verb "to plough"), dual
  agreement (optional in modern use), word order/aspect (tendencies), neuter predicates
  (`buvo vėsu`). The article has no usable sections on comma rules or verb government beyond
  what is above; a Lithuanian source (VLKK rules) would be the next step.
- `ziuri` on its own still becomes `žiuri` (jury): `žiūri` never occurs in the 750 Wikipedia
  articles, `žiuri` 6 times. Only a subject pronoun fixes it (`jis ziuri`); a conversational
  frequency corpus would fix it for good.
- `adb install` waits forever when wireless adb has dropped: reconnect first
  (`adb mdns services`, then `adb connect HOST:PORT`).
- HeliBoard capitalises sentences only if the text field asks for it
  (TYPE_TEXT_FLAG_CAP_SENTENCES); the test app's field now does.
- The keyboard fixer's fold keeps `y` (it is a key): i/y changes are never auto-applied.
- Lexicon gaps: loanwords and names (`klipas`, `singlas`); induce stems from a
  corpus by finding multiple forms of a guessed paradigm.
- Keyboard: completions for half-typed words (now we show corrections);
  speed up unknown-word suggestions (6–17 ms on phone); interplay of the
  sentence fixer with HeliBoard's backspace-reverts-autocorrect is untested.
- Typo detection/ranking still behind Hunspell; keyboard-adjacency weights could
  be tuned on real typing data.
- Spoken-form normalisation option in the keyboard (`valgyt` → `valgyti`) is
  available (`--formal`) but not wired to a setting.
- iOS later: the Rust core is portable; keyboard extensions have tight memory limits.

## History (commits on varnele/main)

1. Rule-based checker, ispell-lt stems, evaluation vs Hunspell
2. Context rules: prepositions, agreement, quantities, commas
3. Verb rules: negation genitive, subject-verb person, objects
4. Rust runtime + Android spell-checker app (parity 100%)
5. participle agreement, negation via diacritics, relative pronoun, typo
   candidates as context variants, keyboard typo cost, AGENTS.md
6. keyboard: rare-twin rule, key-shift search (+ HeliBoard setting), score
   compensation for HeliBoard's normalisation
7. keyboard: fixes survive punctuation and user history (HeliBoard fork)
8. reflexive-only verbs, i/y cost, case requirements prefer candidates agreeing with the adjective
9. transitive objects, indirect-question commas, flat diacritic cost, pronoun-noun cleanup
10. phone list: parenthetical/address/list/participial-phrase/negu/repeated-connective commas,
    relative case from the verb, subject over adverbs, instrumental objects; eval/commas.py
11. `link` + genitive; `viena kitą` skip narrowed; keyboard rename, fork on GitHub (notes)
12. kurti vs kuris (`kuria ir parduoda`, `Kuriu tai, kas`), `tai, kas` commas, `neatėjo laiku`,
    `jis ziuri` → `žiūri`
13. `koki nors` (no comma, `kokį`), numbers + genitive plural, genitive verbs
14. genitive before a head noun, 3rd person objects with adverbs between, predicate
    adjectives, agreement fix direction, `virs` → `virš`
