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
eval/           evaluate.py (vs Hunspell), restore.py, parity.py, keyboard_sim.py, corpus fetch/freq,
                extract_wiki.py + training.py (dump text), build_ngrams.py, swipe_sim.py, predict_sim.py,
                clean_conv.py + extract_conv.py (conversational text: cleaning, test sets, text to count)
tests/          unittest: test_morphology.py, test_grammar.py
vendor/ispell-lt  BSD word list (stems + class flags only; its affix rules are NOT used)
data/           extra.txt (our lexicon additions), abbreviations.txt, freq.tsv, lemma_freq.tsv,
                varnele.bin (generated, git-ignored), index.pkl (cache, git-ignored)
corpus/         Wikipedia (git-ignored): test/ (150 articles, evaluation only), freq/ (600 articles, the old
                frequency corpus), wiki/ (the lt dump + text/ from extract_wiki.py: 213k articles, 31M words,
                the test articles left out; eval/training.py counts on it when present, else on freq/)
```

## Commands

```bash
python3 -m unittest discover tests                 # all tests (must stay green)
python3 -m varnele check FILE [--formal] [--no-grammar]
python3 -m varnele words WORD...                   # analyses + suggestions
python3 -m varnele export                          # -> data/varnele.bin (needed by Rust/Android); build the Rust
                                                   # binary first: count tables are built by `varnele fst`
cargo build --release --manifest-path rust/Cargo.toml
rust/target/release/varnele check FILE | json FILE | words W... | kb WORD [CONTEXT...] | bench
python3 eval/parity.py                             # Rust must equal Python: 100% identical findings
python3 eval/restore.py --sentences 300            # strip all diacritics, measure restoration
python3 eval/commas.py [corpus/freq] [--show-wrong]  # strip all commas, precision of each comma rule
python3 eval/keyboard_sim.py "kodel nepataiso ..." # simulate the HeliBoard fork word by word
python3 eval/keyboard_restore.py                   # restore.py's 300 sentences typed through the keyboard model
rust/target/release/varnele serve                  # stdin requests "kb\tWORD\tCONTEXT" / "json\tTEXT" / "learn\tTEXT" /
                                                   # "gesture\tX,Y X,Y…\tCAP\tN\tCONTEXT" / "predict\tCONTEXT\tPREFIX\tN" (used by the sims)
rust/target/release/varnele swipe WORD...         # decode each word's ideal swipe path
python3 eval/swipe_sim.py [--noise 0.3] [--cut 0.4] # restore.py's 300 sentences swiped through the gesture decoder + keyboard model
python3 eval/extract_wiki.py                       # corpus/wiki/ltwiki-latest-pages-articles.xml.bz2 -> corpus/wiki/text
python3 eval/build_freq.py [--conv-weight W]       # Wikipedia + conversational text -> data/freq.tsv, lemma_freq.tsv (words seen 10+ times)
python3 eval/build_ngrams.py [--conv-weight W]     # the same -> data/bigrams.tsv, trigrams.tsv (seen 10+ times; then export)
python3 eval/predict_sim.py                        # next word among the top 3 predictions, same 300 sentences
                                                   # --learn: the user model learns the test set in order first
python3 eval/predict_grammar.py [--corpus DIR]     # top 3 after prepositions/adjectives: how many break the case or agreement
python3 eval/clean_conv.py                         # what cleaning repairs/drops in corpus/raw/{opensubtitles,tatoeba}, with examples
python3 eval/extract_conv.py                       # cleaned -> corpus/conv/{subtitles,tatoeba} (tests), heldout.tsv, train/*.txt
python3 eval/predict_sim.py --corpus corpus/conv/subtitles   # any of the four sims on dialogue; tatoeba: add --no-paragraph
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

**Device tests run on the emulator by default** (owner, 2026-10-22), not the Fold7: it never locks,
drops off wireless adb or needs the owner. Use the phone only when the owner asks for it or the test
needs real hardware (real swipe traces, the Fold's two screens, split keyboard, speed on the phone).
Worktrees build the keyboard with `-Pvarnele.dir=<the varnele worktree>`.

```bash
eval/emulator_ready.sh app/build/outputs/apk/debug/VarneleKlaviatura_1.0-debug.apk   # boot, install, select the keyboard
adb -s emulator-5554 shell am start -n dev.imbrasas.varnele/.MainActivity            # this repo's test app: a text field
python3 eval/emulator_type.py "mano drakonas valgo morkas. "                          # type by tapping the keys
adb -s emulator-5554 logcat -s Varnele:V                                              # what Varnelė did, per word
```

Always pass `-s emulator-5554`, so a connected phone is never touched. The test app's field starts
with a sample text: tap it (540, 530), `input keyevent 123` moves to the end. Read the field with
`uiautomator dump` (its EditText `text=`), the strip from `predict …` / `ghost …` lines in the log or a
screenshot (`adb -s emulator-5554 exec-out screencap -p > s.png`).

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
| case (prepositions) | `prieš pora` → `porą`, `į didele kavine`, `link namu` → `namų`; after an acc/ins preposition a genitive that can't be its object is a modifier, so the noun after it is checked (`į teisės mokykla` → `mokyklą`) | genitive modifiers (`su lietuvių kultūra`), that head rule only for a typed preposition (not the numeral `I pasaulinio karo metu`) and not across all-caps words (`į NATO diena`), `apie` + quantity (`apie pusė`), numerals (`per šešiolika`), phrase must end in a noun, phrase stops at a word that can't agree (`už didžiausią | tuo metu`), participles end the phrase |
| quantity | `daug vaiku` → `vaikų`; a number ending in 0 or 11–19 + noun (`10 metu` → `metų`, `15 euru`) | comparatives (`kiek silpnesnes`), only `kind == num` for -lika/-dešimt (not `Respublika`); numbers: only a known lowercase noun right after the number (not units `20 m atstumu`, manner `12 etniniu pagrindu`, labels `KNM-ER 1813 atveju`), not decimals or ordinals |
| case (verbs, indefinites) | GENITIVE_VERBS laukti, ieškoti, bijoti, siekti, reikėti, vengti: `lauksiu tavo zinutes` → `žinutės`, `ieškau raktu`; `koki nors` → `kokį nors`, `ka nors` → `ką nors` | verbs as in negation (durations, quantities), possessives skipped (`tavo`); prefixed verbs only with a real prefix (`plaukė` is not `p+laukė`) |
| agreement (adj+noun, case/number/gender) | `gražią kavine`, `prastos kokybes`, `šita žmogų` | `viena kitą` (only before a kitas form: `vienos eilutes` → `eilutės`); adjective that is likely a verb (`palaikė`); skip over genitive modifiers to the head (`profesionalūs [Lietuvos cirko] artistai`); a genitive with no head after it is checked on its other noun readings (`žmogų` is also a bogus gen pl); unknown word never changes a known neighbour; participles allowed except when the noun can be acc/loc or the participle is a predicate verb (`tapusią vienuole`, `išrinktas prezidentu`, `einanti sakinio gale`), but a -tinas participle takes no accusative (`pažintini taką` → `pažintinį`; other passives do: `nutarta datą paankstinti`). Keyboard order: an adjective agreeing with neither the genitive after it nor the noun after the genitives takes its twin agreeing with the genitive (`dalyvaujančiu šalių viršūnių susitikimą` → `dalyvaujančių`), only once a word follows the genitives (`su dideliu žmonių …` waits; `su dideliu žmonių būriu` agrees), not when that word is a preposition or connective (`svarbiausiu musulmonų kovos prieš … centru`), not after a predicative verb (`laikomas lemiamu serbų kovoje`), all words known. Which word changes: a preposition before decides (`pro nedideles gyvenvietės` → `gyvenvietes`), else the one typed without diacritics (`nedidele mergaitė` → `nedidelė`, `visa energiją` → `visą`) |
| predicate adjective | `ji nedidele` → `nedidelė`, `mergaitė buvo (labai) nedidele` | subject = jis/ji/jie/jos or a noun whose most frequent lemma is nominative; nouns and `jos` need a nominative copula (būti, atrodyti, likti, jaustis; not `tapo parapine`); the adjective ends the clause; participles skipped |
| genitive before a head noun | `miesto gyventoju skaičius` → `gyventojų`, `vietoves gyventojai` → `vietovės`, `branduoliniu ginklu sutartis` (modifiers too) | each from Wikipedia: not when both share a case and number as nouns (`pilotu bandytoju`, `naktiniu gyvenimu`, `kalba žodžiu rinkliava`; but `teises mokyklą`, and `Medžiokles plotas`, plotas also being a participle), head genitive-only, head a verb or adverb (`su broliu namo`); not lemma metas (`vienu metu`); not when the form is ≥⅓ as frequent as its genitive (`Sovietmečiu`, `laikotarpiu`); not after a verb, possessive, `šiuo`, or a governing preposition up to 3 words left (`į Kalavijuočių ordino žemes`), unless the preposition is right before and the head can take its case, also by a diacritic (`į teises mokykla` → `teisės`); an instrumental after a genitive or name only if its genitive is seen 5+ times (`vidaus reikalų` yes, `karo metu`, `Vyriausybės potvarkiu` no) |
| context ranking of unknown words (reorders suggestions only) | both adjective and noun unknown: each keeps the candidates agreeing with the other's (`dalyvaujanciu saliu` → `dalyvaujančių`); after a TRANSITIVE_VERBS verb (itself possibly unknown, by its candidates) accusative candidates first (`rado salyga` → `sąlygą`); genitive-before-noun for unknown words, all genitive candidates (`sienu klausimas` → `sienų`) | allowed candidates keep the suggester's order (`sienų`, not `šienų`); not when the adjective's candidates include a finite verb (`% sudare baltaodziai` → `sudarė`); no infinitive/verb in the object phrase (`turi buti`); compared with the rule for known words: an unknown head counts by its candidates, the head's diacritic twins count for the shared-case check (`zaidimu bendrove`), genitive chains allowed, no corpus-evidence guard for an instrumental after a genitive; any verb instead of TRANSITIVE_VERBS was worse (`sudaro dirbama zeme`) |
| preposition that became a verb | `kabo virs stalo` → `virš` | the phrase after it takes the preposition's case and the clause already has a verb before it (`Mama virs sriubos` = will boil) |
| negation | `neturiu laiką` → `laiko`; a typo after an adjective takes the agreeing genitive (`visų zodziou` → `žodžių`, not `žodžio`; also via the adjective's diacritic variants), `nemačiau jį` → `jo`, `nepataiso visu` → `visų` | durations/quantities (`nedirbau visą dieną`, `daugybę metų`), copulas, a one-word phrase with an adverb reading (`neatėjo laiku` = on time) |
| subject | `aš buvo` → `buvau`, `aš vakar buvo`, `jis jau einu` | pronoun + finite verb, up to 2 adverb/particle-only words between (not pronouns, connectives, prepositions, `ne`, `tai`); not a coordinated subject (`aš ir jis buvome`). An unknown word after the pronoun ranks verbs of that person first (`jis ziuri` → `žiūri`, not the jury `žiuri`, more frequent on Wikipedia) |
| object (1st/2nd person verb; 3rd person transitive verb with its subject before it) | `mačiau namas` → `namą`, `matau dar viena klaida` → `vieną klaidą`, `Jonas mato namas`, `jis vakar nupirko nauja knyga`, `mačiau labai gražus namas` (adverbs between) | 3rd person: only TRANSITIVE_VERBS with a real prefix, not reflexive (`atsirado` = atsi+rado); the subject is jis/ji/jie or a noun whose most frequent lemma is nominative (`Jonas`, not the name Jona), not coordinated (`Jonas ir Petras`); no infinitive in the phrase (`turėtų būti suprantama`), no lone adverb (`atsirado kartu`); copulas, reflexives, verbs only if "mostly a verb" (not `metu`, `keli`, `tik`); nom/ins words only after TRANSITIVE_VERBS (matyti, rasti, turėti…; not motion `einu gatve` or instrument `rašau ranka`); skips `dar/jau/vėl/irgi/tik/net`; not clause words (`manau, kas…`). "Mostly a verb" skips a reading whose prefix the rules added when another reading with a shorter prefix spells the same prefixed lemma: `apsiuvu` (instrumental of apsiuvas) is ap+siuva only through the dictionary's apsiuva (never seen), not through the common siuva (`aukso spalvos apsiuvu žvaigždė` stays). After a transitive verb the phrase may hold participles and an instrumental-only word takes its accusative diacritic twin (`radau nukritusia sagute` → `nukritusią sagutę`) when the whole phrase is instrumental or the head is already accusative (keyboard order); same POS/number/gender (`tuo metu` ≠ `metų`); not `tapusią vienuole` |
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
  - **Varnelė settings screen** (fork, `settings/screens/VarneleScreen.kt`, main settings entry
    "Varnelė" shown when the library loads): the fork's own settings go here; more are to move
    here later (key-shift still sits on Text correction). First one: **formal Lithuanian**
    (`varnele_formal`, default off). `SettingsValues` copies it into `Native.formal`, which every
    `Native.check`/`Native.gesture` call passes to Rust: `keyboard_word(…, formal)` gives a
    colloquial word its standard form as a context fix with rule `formal` (whitelisted, like
    `subject`/`rare`: `VarneleDictionary.SURE_RULES`, also applied by the sentence fixer), and
    `gesture(…, formal)` hands back a spoken candidate as its standard form, deduplicated
    (`einam` → `einame`), so no colloquial form is ever suggested. Unknown words never got
    spoken suggestions (the suggester only proposes dictionary forms). CLI: `--formal` on
    `kb`, `swipe` and `serve`.
  - **key-shift** (setting `varnele_key_shift`, default on, Text correction screen):
    if the word is unknown and no correction is within one typo, search words where
    every letter is the typed key or a neighbour (`fofrkua` → `didelis`, `ksbsd` →
    `labas`); DFS over a folded stem-prefix set with a 200k-step budget, ranked by
    lemma+form frequency then fewest shifted keys; top guess autocorrects.
    0.4 ms per word after warm-up (tables built in warmUp).
  - `Suggest.kt` (fork change): a whitelisted Varnelė suggestion always autocorrects.
    Upstream lets the user-history predictions veto a fix when the typed word is valid,
    and testing teaches it the uncorrected words (`nauja sakini` stayed).
  - gesture typing (batch mode): Varnelė's own decoder (below), wired on branch
    `paulius/varnele-swipe` of the fork: gestures are on for Lithuanian without Google's library
    (`VarneleDictionary.gesturesFor`, also gating the settings screens); `MainKeyboardView.setKeyboard`
    hands the letter keys' centres and the view offset to `VarneleDictionary.setGestureKeyboard`
    (points are view coordinates, keys keyboard coordinates); in batch mode `getSuggestions` calls
    `Native.gesture` (JNI `gestureNative`) with the path in key widths, then checks each candidate's
    keys like a word typed without diacritics (`Native.check`: diacritic-only context fix or
    suggestion), top 5 in Varnelė's order, the first is committed. Without the library
    `BinaryDictionary.getSuggestions` declines gestures (the native gesture policy is null and would
    crash), so user history and contacts don't take part in swipes. The sentence fixer also runs in
    `InputLogic.onStartBatchInput` after the previous gesture's word is committed (no separator is
    typed between gestures). The debug build logs the key centres (`gesture keys (view px)`) for
    replaying swipes with `adb shell input motionevent DOWN/MOVE/UP`.
- **Gesture decoder prototype** (`rust/core/src/gesture.rs`, Rust only like key-shift; no Python
  twin, so not in parity). Input: finger path in key widths over `Layout` (QWERTY default: keys 1
  wide, rows 1.4 high, `z` after a 1.5 wide shift). Candidates: `Data::walk_forms` walks the
  folded stems like the key-shift DFS; each letter's key (folded `i` = `i` or `y` key) must be
  within 1.0 of the path after the previous letter's match (earliest match, a doubled letter is
  one key), first/last within 1.2 of the start/end, and the ideal path so far ≥ 0.6 × the finger
  path so far − 1 (a skipped letter makes it short). Prefix chains as in the analyzer, walking
  only entries that can take them (verbs, `ne`+N flag). Score: shape = 0.2 × mean distance of
  corresponding resampled points (32) + 0.8 × DTW mean distance (DTW only for the 300 best),
  cost = 4·shape² + the suggester's frequency score, +0.3 for a capitalised name with shift off,
  +0.3 for a never-seen prefixed form (`įįvykdyte`). Spoken shortenings are candidates too: a
  signature suffix with a COLLOQUIAL full ending whose tag passes the test also yields the short
  ending (`einame` → `einam`, `valgyti` → `valgyt`; `Folded::spoken`, built once), scored by their
  own frequency plus the lemma frequency of the formal twin; subtitles σ 0.3 keys top 1 / final word
  81.8 / 74.4 → 82.7 / 75.0%, Tatoeba 85.6 / 79.3 → 85.4 / 79.2%, Wikipedia unchanged, same speed
  (a strip-and-check per suffix in the walk instead doubled the 95th percentile). Output: the keys swiped (no diacritics), which
  the keyboard then treats as a word typed without diacritics (autocorrect + sentence fixer pick
  `prieš`, `dienų`). Nothing found → one retry with radii ×1.5 and a smaller budget.
  Speed: prefix chains walk only entries the analyzer's prefix rules allow (`analyzer::allowed` with
  no tag), verbal-prefix chains only verb stems (`Data::verb_stem_prefixes`), and the chains run on 4
  threads, each with its own step budget (600k without a prefix, 150k per chain) so results don't
  depend on timing. Requiring the ideal path ≥ 0.75 × the finger path − 1 (now 0.6) would halve the
  time again for −0.3 points.
  The lexical cost also subtracts 0.3 × log10 of the language model's P(word | context) / P(word).
  Tried and dropped: a per-letter anchor distance (favours short words, 34% top-1), a "don't cut
  past a sharp corner" prune (real corners are often > 1 key from the letter: recall 92 → 74%).
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

- **Language model** (`rust/core/src/lm.rs`, keyboard only): P(word | two previous words) from the
  word triples and pairs of the Wikipedia dump and the conversational text (`eval/build_ngrams.py` → `data/bigrams.tsv`,
  `data/trigrams.tsv` → varnele.bin: word counts tokenised like the keyboard, and per previous word (pair)
  its total and distinct followers over all pairs (triples), then the pairs and triples seen 10+ times,
  raw counts), absolute discounting (D 0.75): triples back off to pairs, pairs to word frequency; `<s>` =
  sentence start, commas don't part the words (the counts run across them). Plus a paragraph cache: lemmas of the last 150 words, the form's share of its
  lemma (`Vilnius` earlier → `Vilniaus`), 10% of the probability for swipe, 30% for predictions
  scaled by words / (words + 300): a few words are no topic (`Aš vakar buvau` predicted `aš`, `vakar`).
  `Analyzer::predict_words` ranks followers of the two previous words and of the previous word (20 candidates each), the paragraph's
  words and frequent words by it. `Checker::keyboard_predict` (JNI `predictNative`, serve `predict`)
  is what the keyboard shows: a name capitalised (`lietuvos` → `Lietuvos`), single letters other than
  `į`/`o` and abbreviations (`m`, `pr`, `kun`: the counts drop numbers and full stops) left out, and a
  word Varnelė doesn't know only if the context has it (`TSR`, as written there). Formal mode: a spoken
  form is given as its standard form, once (`ein` → `einame`, never `einam`), as swipe does.
- **Predictions in the keyboard** (fork branch `paulius/varnele-predict`): `InputLogic.getSuggestedWords`
  hands the text before the word (the connection's 1024-character cache) to
  `VarneleDictionary.textBefore`. Nothing typed: `getSuggestions` returns 5 predictions
  (`KIND_PREDICTION`, Varnelė's order). Typing: `Suggest.addVarneleGhost` adds the **ghost**
  (`Checker::keyboard_ghost`, JNI `ghostNative`, serve `ghost`): the word completed (`kod` → `kodėl`),
  none when the word as typed is likelier than the completion (`tau`, not `tautos`), plus the next word
  when P ≥ 0.6 (`GHOST_NEXT_P`; right 71–73% of the times the ghost is tapped, see Latest numbers), added after the autocorrect decision, so it never autocorrects: it goes in the strip's
  centre, or next to it when the centre shows what space commits (an autocorrection, the typed word
  with "center suggestion is text to enter"). `SuggestionStripLayoutHelper` greys the part after the
  typed letters (`kod|ėl tu`); a tap commits it. Owner's choice (2026-10-22): strip first, inline ghost
  text in the field later (it would live in the composing region, which the app sees: search fields
  would query it). Varnelė's predictions are kept out of `shouldBeAutoCorrected`'s empty-word
  comparison (other scale).
- **User language model** (`rust/core/src/user.rs`, `Analyzer::user`, keyboard only; fork branch
  `paulius/varnele-user-lm`, setting "Learn from my writing" `varnele_learn`, **default on**, plus
  "Forget learned words", both on the Varnelė screen). Words and word pairs of the text *as it ends up*
  (after autocorrect and the sentence fixer; HeliBoard's user history learns words as typed).
  `VarneleUserLm.observe` hands Rust the text before the cursor after every finished word (separator,
  picked suggestion, the next gesture), right after the sentence fixer; `UserLm::observe` learns a
  sentence once the next one is begun, so a word backspaced and retyped is learned as it ends up, and the
  last sentence on `commit`: the enter key's editor action (send), the app clearing the field
  (`onUpdateSelection` to 0 with no text: a chat's send button), `onFinishInput`, a restarted field.
  A sentence is learned once where it stands (key: its words and the three words before it; the last
  1,000 keys), so a refocused field isn't counted twice; a send or a cleared field forgets the keys, so
  `Labas.` in every message counts every time (a first version keyed on the words alone learned it once,
  ever). A text cut at 1,024 characters skips its first piece of a sentence.
  Not learned: incognito (also fields asking for no learning), passwords, URLs/e-mail, other languages.
  Storage: `files/varnele_user.txt` (text, `1 word count [written]` / `2 prev word count`), loaded on the
  thread that loads Varnelė's data (not at all for a keyboard not typing Lithuanian), saved when the
  keyboard closes; at 10k words or 40k pairs every count halves and what drops below 0.4 goes (old and
  rare first). Use: `p_context` mixes in P_user(w | prev) (absolute discounting D 0.5, backing off to the
  user's word frequency) with share 0.5 · n / (n + 50), n = how often the user wrote `prev` before a word,
  so predictions, the ghost and swipe ranking all get it; `predict_words` adds the user's followers of
  `prev` and most frequent words as candidates; a word Varnelė doesn't know is predicted once the user
  wrote it twice, as written (`Freiburg`). Off: neither learned nor used (the file stays until forgotten).
  HeliBoard caches next-word suggestions per previous words (`Suggest.nextWordSuggestionsCache`); for
  Varnelė's locale the fork skips that cache, else the strip never changed after the first time in a
  field session (also hiding the paragraph context).
  Tested on the emulator (2026-10-22): after `Mano drakonas valgo morkas.` was learned once `valgo` came
  2nd after `drakonas`, after four times 1st; in a fresh text without it: `mano` first at a sentence
  start, `drakonas` after `Mano`, `valgo` after it; kept across a keyboard restart; Forget deletes the
  file and the strip is the corpus's again; switched off, the counts stay in the file but are not used.
- **Grammar in predictions** (`Grammar::next_word` / `fits_next` / `refit_next` in `grammar.rs`, Rust
  only, not in `check`, so not in parity; `Checker::grammar_rerank`): the last words before the cursor
  can require a case. After a preposition (`prep_cases`, also typed without diacritics when unknown:
  `i`) one of its cases; after an adjective (every reading A or P, a noun reading only of the same
  lemma: `geras`; not definite forms, often nouns: `pėsčiųjų tiltas`; not capitalised: `Vytauto
  Didžiojo universitete`; not kuris/question words/possessives) a word agreeing with it or a genitive
  (`geras Lietuvos krepšininkas`); after preposition + adjectives the readings in its cases. Then the
  language model's 30 best candidates: a word with a caseless reading is not judged (`per daug`, `apie
  tai`, `su savo`); one that can't fit keeps 1% of its probability, a genitive after a preposition
  that takes another case 30% (it may modify the object: `į Lietuvos sostinę`, `į šiaurės rytus`), and
  its noun/adjective forms that fit join with their own probability (`eiti į` → `pietus, šiaurę,
  rytus`, was `šiaurės` first). Predictions and the ghost both go through it. +0.1 ms per call.
- **Data format v3**: freq, lemma_freq, the language model's word counts, its pairs (`"PREV WORD"` →
  count, `"PREV "` → total << 32 | distinct) and triples (`"A B WORD"`, `"A B "`, the same; an optional last
  table, read only when bytes are left, so older files still load) are finite-state transducers (`rust/core/src/counts.rs`,
  `fst` crate), read in place: no hash map of 150k+ strings on the phone's heap. `export.py` pipes each
  table through `varnele fst`, so the Rust binary must be built before exporting. Lossless: every
  evaluation is identical to the v2 hash-map format. Sizes at words 10+ / pairs 10+: freq 1.1 MB,
  lemma_freq 0.2 MB, LM words 1.1 MB, pairs 3.5 MB (310k), the lexicon ~4.9 MB; varnele.bin 10.9 MB
  (v2 with words 2+ was 20.2 MB). Words 2+ instead of 10+ changed no result; pairs 5+ adds 3.5 MB for
  +0.2 points swipe, +0.8 / +2.0 prediction. Triples 10+ (191k, after 75k word pairs) add 3.5 MB:
  varnele.bin 13.0 → 16.5 MB; triples 20+ (78k) add 1.5 MB and keep ~¾ of the gain, 40+ (32k) 0.6 MB, ~½.
  **Ranked lists** (last table, optional the same way; `Counts::ranked_lists`, built by `varnele fst-ranked`
  from the three LM tables at export): for every pairs/triples head (`"<s> "`, `"ir "`, `"<s> aš "`) and
  every folded beginning of 0–3 letters that 500+ of its followers have, the 50 most frequent (the words
  table: the 100 most frequent words per beginning), keyed `HEAD + beginning + TAB + rank + word`. 321
  lists, +0.27 MB (16.5 → 16.8 MB). `Data::followers` reads a list when there is one and enough of it
  passes the caller's filter, else lists the table (`Counts::top_folded`: a bounded top n, no string per key).

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

- Wikipedia (150 articles, 65k words): 20 context flags, **all real errors**
  (16 commas incl. `nariu, pasiekusiu tokį aukštą postą`, `kylanti grėsme`, `prastos kokybes`, `daugybę metu`,
  `FIA Šiaurines Europos zonos`); unchanged by the Wikipedia-dump frequencies once `apsiuvu` was fixed.
  The 600 freq articles: 84 flags (`kuri kuria`, `kurie kuria` no longer get a comma; `pasteliniu spalvų
  deriniai`); 86 with the dump frequencies, the new ones not yet reviewed.
- Commas removed from the articles (`eval/commas.py`), new rules, right/wrong on test+freq:
  participial phrase 91/10 (8 of the 10 are commas missing in the articles), lists 27/0,
  parenthetical 31/0, address 2/0, negu 2/0, repeated connective 1/0. Old rules 2440/62
  (the wrong ones are mostly article errors, as in the Wikipedia check).
- vs Hunspell lt_LT: fewer false alarms on lowercase words (2,018 vs 2,483 tokens),
  better diacritic fixes (#1 correct 56.7% vs 40.0%), worse on keyboard typos
  (detect 89.3 vs 95.3%, #1 70.0 vs 76.0%).
- Restoration typed word by word through the keyboard model (`eval/keyboard_restore.py`, same 300
  sentences): 74.0% restored, 36.0% whole sentences right, 2 correct words changed (`ari` → `aria`,
  `ekspansija` → `ekspansiją`) with the Wikipedia-dump frequencies; 72.5%, 34.3%, 3 with the 600 articles (71.8%, 32.7% before
  the keyboard-order fixes `dalyvaujančių`, `teisės`, `Medžioklės`, `pažintinį`); the rare-twin
  rule makes the keyboard beat the checker (`metu` → `metų`, `siu` → `šių`, `padare` → `padarė`). The
  checker still gets 8 words the keyboard misses. Left on purpose: `žanru`, `papuošalu` after a genitive
  (their genitives are not in the frequency corpus; dropping that guard flagged `rotroskopavimo metodu`,
  `tradicijų puoselėjimu`, `menų kovotoju` on Wikipedia); `šlapynes dalis` (dalis is also acc pl);
  `Daugybes mokslininkų … dėka` (acc pl + genitive is fine: `tūkstančius žmonių`; only `dėka` decides);
  `Didžiausia įtaka turi` (object before the verb); `neįvykusi veiksmą`, `įgyta turtą` (participles with
  objects). The keyboard changes `kultūrinė ekspansija` to `kultūrinę ekspansiją`: autocorrect picks
  `kultūrinę` for `kulturine` on a frequency tie (0.008 vs 0.017) and the sentence fixer then makes
  the noun agree; it cannot tell autocorrected diacritics from typed ones.
- Restoration (all diacritics stripped, 300 sentences): 65.3% → 70.1% with
  context rules, 0 correct words changed, with the Wikipedia-dump frequencies (63.1% → 68.8% with the
  600 articles; 68.3% and 1 before the keyboard-order fixes; 67.7% before context ranking of unknown words, 66.1% before the genitive-before-noun rule; 59.7% → 62.8% before the flat diacritic cost); words valid without diacritics (29%) are the ceiling for a
  checker; a most-frequent-spelling baseline gets 71.9%.
- Rust: load 31 ms, correct word 0.001 ms, misspelling + suggestions ~0.9 ms,
  sentence ~2.5 ms (Mac, data v3). Phone (Fold7, measured with the old 5.3 MB data): 0.05–0.8 ms valid
  words, 6–17 ms unknown words with suggestions, data load ~110 ms. Data file 16.8 MB (v3, with the conversational counts, triples and ranked lists).
- Keyboard simulation: `kodel nepataiso visu zodzou kuriu as rasau?` →
  `kodėl nepataiso visų žodžių, kurių aš rašau?`; `dabar meginu nauja sakini` →
  `dabar mėginu naują sakinį`; Rust key-shift search 0.4 ms, sentence 1.5 ms (Mac).

- Swipe simulation (`eval/swipe_sim.py`, 3,493 swiped known words of the 300 sentences; each key
  missed by N(0, σ) in x, 1.2σ in y, corners cut by up to `cut` keys, Catmull-Rom curve, finger kept
  on the keyboard): keys right top-1 / top-3 / final word with diacritics right:
  σ 0.2: 87.1 / 96.4 / 77.2%; σ 0.3: 74.9 / 87.3 / 66.8%; σ 0.4: 52.3 / 63.9 / 46.8% (frequency
  only). With the language model and the article text before each sentence as the paragraph,
  σ 0.3: 77.0 / 88.1 / 68.5% (previous word alone 75.7 / 87.5 / 67.4%); with the Wikipedia-dump
  frequencies and pairs: 82.6 / 90.3 / 74.0%. When the keys are right the diacritics are right 89%.
  Decode on the Mac: median 2.4 ms, 95% 12 ms, max 113 ms (σ 0.3; 32 / 186 ms before the threads).
  On the Fold7 (cover screen, synthetic swipes replayed over adb, σ 30 px ≈ 0.28 keys): 2–17 ms for
  most words, `ne-` words 50–100 ms. Wrong words there are the simulation's near-identical paths:
  `maciau` → `mažiau` (c/z neighbours), `grazu nama` → `graži namas`, `jis` → `jos`; the sentence
  fixer adds `, kurių` between swipes.
  The noise model is a guess: no real swipe traces yet.
- Next-word prediction (`eval/predict_sim.py`, 3,997 words): the word is among the top 3 before
  typing 16.2%, after its first letter 33.1% with the Wikipedia dump (31M words, 310k pairs seen 10+
  times). With the 600 articles (167k words, 13.6k pairs seen twice): 12.9 / 26.3% (no paragraph:
  12.4 / 22.7%; previous word only, with the paragraph's words as candidates: 12.5 / 21.5%). All test
  sentences are Wikipedia: conversational text scores lower, see below.
  The keyboard's predictions (`keyboard_predict`, cache ramp, conversational counts), before typing /
  after one letter: Tatoeba 13.0 / 44.9 → **19.2 / 47.1%**, subtitles 12.0 / 31.5 → **13.0 / 32.9%**,
  Wikipedia 16.5 / 32.0 → 15.7 / 30.4% (the filter drops `m` and names Varnelė doesn't know: `Reicho`,
  `Freiburg`). 0.5 ms per call on the Mac after warm-up (0.6 with the grammar).
  Grammar in predictions (`eval/predict_grammar.py`, judged by the Python analyzer): top-3 predictions
  breaking the case after a preposition Wikipedia 43 → 3 of 627, subtitles 34 → 2 of 492, Tatoeba
  18 → 0 of 396; after an adjective 17 → 9 of 819, 4 → 0, 4 → 1 (the check also judges definite
  adjectives, which predictions leave alone); the word typed in the top 3 after a preposition 10.0 → 10.5%, 7.9 → 8.5%, 16.7%, after
  an adjective 30.4%, 11.3%, 39.1 → 41.3%. Overall before typing / after one letter: subtitles 13.0 /
  32.9 → 13.0 / 33.0%, Tatoeba and Wikipedia unchanged (prepositions and adjectives are ~10% of words).
  Ghost (`predict_sim.py --ghost`, letters typed without diacritics): a shown ghost is the word being
  typed 23.4% (Tatoeba), 16.5% (subtitles), 14.8% (Wikipedia) of the time; tapping the first right one
  completes 75.8 / 60.1 / 63.4% of the words of 3+ letters and saves 21.8 / 14.9 / 20.1% of their
  letters (23.2 / 16.3 / 14.7%, 75.3 / 59.7 / 62.8%, 21.7 / 14.7 / 19.9% before the grammar).
  On the Fold7: predictions 1–8 ms, the ghost 1–10 ms (34 ms after one letter before the
  frequent candidates came from the 2,000 most frequent words instead of every word with that letter;
  the typed-word test is a dictionary lookup, `check` guessed compounds for `se`); the strip shows
  `kod | kad | kod·ėl` (typed, autocorrection, ghost) and tapping the ghost commits `kodėl`.
- **User model learned in order** (`predict_sim.py --learn`, `swipe_sim.py --learn` vs `--in-order`: the
  sample in corpus order, all the test set's text before each sentence learned first, as if one user wrote
  it all; the test sets are 40 films / unrelated sentences / 150 articles, so a real user, who repeats
  their own names and phrases, should gain more), without → with:

  | | OpenSubtitles | Tatoeba | Wikipedia |
  |---|---|---|---|
  | prediction top 3, before typing / after 1 letter | 13.0 / 32.9 → 13.2 / 33.4% | 19.2 / 47.1 → **20.9 / 48.5%** | 15.7 / 30.4 → **17.6 / 33.6%** |
  | ghost right / words completed / letters saved | 16.3 / 59.7 / 14.7 → 16.5 / 60.3 / 15.2% | 23.2 / 75.3 / 21.7 → 23.6 / 76.1 / 22.4% | 14.7 / 62.8 / 19.9 → 15.8 / 65.2 / 22.5% |
  | swipe σ 0.3 keys top 1 / final word (in order) | 83.3 / 75.5 → 83.4 / 75.7% | | 82.3 / 73.8 → 82.7 / 74.2% |

  Shares 0.3–0.7 and ramps 10–100 all landed within ±0.3 points of these; a share for the user's word
  frequency regardless of the previous word added nothing. No measurable cost in time.
  **Word triples** (2026-10-22), before → after, subtitles / Tatoeba / Wikipedia: top 3 before typing
  13.0 / 19.2 / 15.7 → **15.1 / 22.8 / 17.2%**, after one letter 32.9 / 47.1 / 30.4 → **34.1 / 48.7 / 31.6%**;
  ghost completes 59.7 / 75.3 / 62.8 → 60.0 / 75.6 / 63.4% of the words, saves 14.7 / 21.7 / 19.9 →
  15.2 / 22.7 / 20.9% of their letters; swipe σ 0.3 unchanged (keys top 1 82.7 / 85.4 / 82.1 →
  82.6 / 85.5 / 82.1%, final word 75.0 / 79.2 / 73.4% both); same speed (predict median 1.6 ms, ghost
  1.3 ms on the Mac, through serve). Triples 20+: 14.6 / 22.1 / 16.9% and 33.6 / 48.2 / 31.1%.
  Again on top of the grammar re-ranking (main 873cca8), without → with triples: before typing
  13.0 / 19.2 / 15.7 → 15.1 / 22.8 / 17.1%, after one letter 33.0 / 47.1 / 30.4 → 34.1 / 48.7 / 31.6%, ghost
  letters saved 14.9 / 21.8 / 20.1 → 15.4 / 22.9 / 21.1%.
  **The ghost's next word** (`predict_sim.py --ghost`, at the tap of the first right ghost; right = the
  word that follows, also after a comma the sentence fixer adds, `maniau, kad`), with triples, share of
  taps that get one / right, subtitles / Tatoeba / Wikipedia: P ≥ 0.8 0.4 / 2.2 / 2.6%, 83 / 90 / 85%;
  0.7 1.4 / 3.1 / 4.4%, 75 / 85 / 74%; **0.6 2.5 / 4.8 / 6.4%, 71 / 72 / 73%**; 0.5 4.0 / 6.3 / 8.0%,
  57 / 66 / 67%; 0.3 7.7 / 12.2 / 13.6%, 44 / 50 / 50%; 0.2 33 / 41 / 42% right. The wrong ones are mostly
  the end of a sentence (`susipažinau su.`) or another word than the frequent one (`taip pat` vs `taip
  atrodys`). Counted without the comma, `kad` after a verb looked wrong: 29 / 37 / 62% at 0.5.
  On the emulator (2026-10-22): `Labas, kaip ` → `sekasi, laikaisi, tu` (the triple; `Kaip ` alone gives
  `ir, tu, tai`), the ghost after `Gal e` is `eime` (was the name `Eime`), after `Tai buvo pirma k` `kartą`.
  The same after the grammar re-ranking, which works with the triples: `Eiti į ` → `mokyklą, darbą, priekį`.
  **Fast at a sentence start (2026-10-22):** predictions after `<s>` took 8 ms on the Mac (1.3–2.9 s on
  the emulator), after `ir` 3 ms. Profiled: all of it was `Data::predict` listing every follower of the
  previous word (41,330 after `<s>`, 14,198 after `ir`) from the pairs FST, a String each, sorting them
  all to take 20; the grammar re-ranking, `check()` on candidates, the user model and the triples took
  < 0.2 ms together. A bounded top-20 scan without the strings only got to 3 ms: the fst stream itself
  costs ~0.08 µs a key. Fix: ranked lists made at export (see Data format v3), also for the frequent-word
  fallback (`kas` after `Gal ka`: every ka- word listed and sorted, 0.9 ms). Through serve on the Mac,
  median of 30 warm calls, before → after (predict N=5): `<s>` 8.2 → 0.05 ms, `Labas. ` 8.1 → 0.06,
  `Ir ` 3.0 → 0.10, `Gal ` 0.18 → 0.13, `<s>` + `k` 0.62 → 0.04; ghost `Gal ka` 1.2 → 0.20 ms. 100
  sentences with their paragraph, median / 95%: subtitles predict 0.93 / 9.0 → 0.62 / 2.1 ms, ghost
  1.46 / 3.0 → 1.07 / 2.4 ms; Wikipedia predict 0.81 / 3.2 → 0.50 / 2.1 ms, ghost 1.31 / 2.9 → 0.95 /
  2.3 ms. Every prediction identical (11,176 predict/ghost requests compared, `--raw-lm` too; predict_sim
  `--ghost` on the three sets and swipe_sim on subtitles unchanged). What is left with a long paragraph
  (1,500 characters): `lm_context` analysing its last 150 words, 0.3 ms, and `p_predict` for each of
  its ~190 words as candidates, 0.6 ms (`analyze_exact` per word), done again for the ghost's next word.
  The emulator's red underlines come from its system spell checker (Gboard, English), not Varnelė.
- **Conversational counts** (W=1: subtitles and Tatoeba count like Wikipedia; `eval/training.py`
  `conversational()`, lines of 4+ words once, cutoffs on raw counts so a pair seen once in a subtitle
  never ships; data file 10.9 → 13.0 MB), on the three test sets, before → after:

  | | OpenSubtitles | Tatoeba | Wikipedia |
  |---|---|---|---|
  | prediction top 3, before typing / after 1 letter | 8.2 / 24.2 → **12.0 / 31.5%** | 6.2 / 26.1 → **13.0 / 44.9%** | 16.2 / 33.1 → 16.5 / 32.0% |
  | swipe σ 0.3: keys top 1 / final word | 75.0 / 68.6 → **81.8 / 74.4%** | 78.4 / 72.9 → **85.6 / 79.3%** | 82.5 / 73.9 → 82.1 / 73.4% |
  | restore.py with context rules | 70.9 → 71.5%, 0 changed | 77.1 → 77.6%, 0 changed | 70.1 → 70.0%, 0 |
  | keyboard_restore.py: restored, whole sentences | 73.9 / 45.0 → 74.0 / 44.0%, 4 changed | 81.3 / 58.0 → 81.5 / 58.0%, 10 changed | 74.0 / 36.0%, 2 (same) |

  Wikipedia flags unchanged (20, all real). W=3 (dialogue counted three times): +0.3 points on
  dialogue, −0.5 on Wikipedia, 13.4 MB; W=10 the same trade, larger. Before the cutoffs used raw
  counts, W=3/W=10 shipped pairs seen once or twice in subtitles (16.7 / 59.9 MB).

- **Conversational test sets** (`eval/extract_conv.py`, cleaned, held out, never counted;
  Wikipedia-dump data before the conversational counts, 300 sentences each, Wikipedia figures from above in brackets):

  | | OpenSubtitles (with dialogue before) | Tatoeba (`--no-paragraph`) | Wikipedia |
  |---|---|---|---|
  | prediction top 3, before typing / after 1 letter | 8.2 / 24.2% (2,668 words) | 6.2 / 26.1% | (16.2 / 33.1%) |
  | swipe σ 0.3: keys top 1 / top 3 / final word | 75.0 / 89.2 / 68.6% | 78.4 / 91.1 / 72.9% | (82.5 / 90.3 / 73.9%) |
  | restore.py: words only → context rules | 67.5 → 70.9%, 0 changed | 73.9 → 77.1%, 0 changed | (65.3 → 70.1%, 0) |
  | keyboard_restore.py: restored, whole sentences | 73.9%, 45.0%, 4 changed | 81.3%, 58.0%, 10 changed | (74.0%, 36.0%, 2) |

  Prediction before typing halves on dialogue: the pairs are encyclopedic. Restoration holds up
  (chat sentences are short and simple). Before cleaning the checker "changed" 2 correct words per
  set, all errors in the text itself (`į mokykla`); now 0. The keyboard's changes are its own false
  alarms on dialogue (`Mes visi` → `visime`, `jis visai` → `visau`), see the corpus backlog item.

## Gotchas (learned the hard way)

- The keyboard simulation splits words at every non-letter (quotes, brackets, no-break spaces,
  colons), as the keyboard does; splitting only on spaces left `„Del`, `(del` unfixed.
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
- **Android emulator** (the default test device, see Commands; installed 2026-10-22 with
  `cmdline-tools/latest/bin/sdkmanager --install emulator "system-images;android-35;google_apis;arm64-v8a"`
  and `avdmanager create avd -n varnele_test -k … -d pixel_7`). Cold boot + install ~25 s. After
  `adb install -r` of the keyboard the system falls back to Gboard: `emulator_ready.sh` selects ours
  again; if taps type nothing, the keyboard is hidden (`dumpsys input_method | grep mInputShown`: tap
  the field). `input keycombination 113 29` (ctrl+A) to clear a field works only sometimes; force-stop
  the test app instead (`am force-stop dev.imbrasas.varnele`, it restarts with its sample text).
  `run-as dev.imbrasas.varnele.keyboard.debug cat files/varnele_user.txt` reads the learned counts.
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

- **Next: next-word prediction with ghost text** (owner's pick, 2026-10-22, after the swipe
  prototype). Started: `lm.rs` (bigrams + paragraph lemma cache, see the keyboard design section),
  used by swipe ranking and `predict_words`; the owner wants context from the whole sentence and
  paragraph. Done: the full Wikipedia dump, conversational text, predictions and the ghost in the
  strip, the grammar steering them (keyboard design section), trigrams. Next: phone-test the strip, inline ghost
  text, more grammar in predictions (verb government: `laukiu` + genitive, objects after
  TRANSITIVE_VERBS, numbers + genitive plural), a small neural model later. Build a language-model layer in the Rust core, not a separate system:
  corpus bigrams/trigrams with backoff to unigram frequency (in `varnele.bin` or a sibling file)
  plus a per-user overlay learned on the phone from the *final* text (done 2026-10-22: "User
  language model" in the keyboard design; next: per-user trigrams if trigrams land, learning which
  autocorrections the user reverts, a phone test over days of real use). Expose one
  `P(word | context)` via JNI that next-word suggestions, ghost text (inline completion of the
  current prefix + predicted next word, new UI in the fork), swipe ranking and tap autocorrect
  all use; it also breaks frequency ties (`žmones`/`žmonės`). Predictions keep diacritics through
  the analyzer. Needs a bigger, more conversational corpus than the 600 Wikipedia articles.
- **Formal mode**: done (2026-10-22), see "Varnelė settings screen" in the keyboard design. Still
  open: ranking with the standard frequency table below.
- **Corpus for the right register**, best first: (1) the user's own final text, learned on the
  phone (the overlay above); (2) OpenSubtitles Lithuanian (spoken dialogue; check the licence
  before shipping derived counts); (3) web crawls CC-100 / OSCAR / Leipzig `lit_web` (huge, mixed
  register; even a filtered slice is ~1000× the current 173k words); (4) forums and comments
  (supermama.lt, r/lithuania), very informal but often typed without diacritics: restore with
  Varnelė first or count folded forms only. Rebuild with `eval/build_freq.py`, measure with the
  restoration and keyboard evals.
- **Frequency tables split by register**: spoken forms counted under their own spelling and
  linked to the standard lemma; formal mode ranks with the standard table, informal with the
  mixed one, the user overlay on top of both. The n-gram model above uses the same split.

- **Swipe and spoken forms** (fixed 2026-10-22; owner found `einam` → `rytinam` on the Fold7):
  the walk now also yields spoken shortenings, see the gesture decoder above. Seen in the
  subtitles: `nepamirškim`, `sakėm` keys right but the keyboard's check of the keys then gives
  `nepamirškime`, `sakėme` (the suggester restores diacritics and the full ending at once, also
  when not formal): a typed or swiped spoken form without diacritics can't stay spoken yet.
- **Swipe, next steps** ((1) is done, phone-tested with replayed swipes; still to try with real
  fingers): (1) wire it into the fork: enable gesture input for `lt` without
  `JniUtils.sHaveGestureLib`, pass `ComposedData.mInputPointers` + key centres (divided by the key
  width) from `VarneleDictionary.getSuggestions` in batch mode to a new `Native.gesture`, run the
  top keys through `Native.check` for the diacritics; check the sentence fixer runs after a
  gesture (no separator is typed). (2) Phone speed: the Mac 95th percentile is 27 ms, the phone is
  ~5–10× slower, and HeliBoard asks again while the finger moves. (3) Record real traces on the
  Fold7 to replace the noise model. (4) Ranking is the main loss (92% of words are among the
  candidates, 75% first): short words on one row are the same line (`tuo`/`to`, `kaip`/`karo`,
  `kiek`/`kurk`), only context separates them: the next-word prediction model above.

- **Corpus beyond Wikipedia** (owner, 2026-10-22): Wikipedia is encyclopedic, third person, full of
  dates/places/`m.`; a keyboard types chat and everyday prose (`aš`, `tu`, questions, spoken forms
  `valgyt`, `buvom`). Sources checked 2026-10-22 (1 MB sample of each where possible; "1/2 p." =
  share of tokens that are `aš tu man tau mane tave mes jūs mums jums mano tavo esu esi`…;
  Wikipedia test articles: 0.07%, 0.2% questions):

  | Source | Lithuanian data, URL | Size | Licence / terms | Register, noise |
  |---|---|---|---|---|
  | OpenSubtitles v2024 (OPUS) | object.pouta.csc.fi/OPUS-OpenSubtitles/v2024/mono/lt.txt.gz | 26M tokens, 4.8M lines, 4,536 films, 49 MB gz | No licence; OPUS asks for a link to opensubtitles.org. Subtitles are fan translations of copyrighted films. Precedent: wordfreq ships counts from it under CC BY-SA 4.0 "with attribution to OpenSubtitles" | Dialogue: 1/2 p. 7.4%, 18% questions, 3.8 words/line. 28% repeated lines (`Taip.`, `Ne.`), ~5% unknown tokens (foreign names, words split by line breaks: `Prisi`, `Ke`), 8% of 6+ word lines without diacritics |
  | Tatoeba (OPUS v2026-07-08) | object.pouta.csc.fi/OPUS-Tatoeba/v2026-07-08/mono/lt.txt.gz | ~0.9M tokens, 1.7 MB gz | CC BY 2.0 FR (clear) | Short everyday sentences translated from English: 1/2 p. 12.4%, 15% questions, clean (0.7% unknown), but `Tomas`/`Marija` everywhere |
  | Leipzig Corpora Collection | downloads.wortschatz-leipzig.de/corpora/ `lit_news_2020_1M`, `lit_news_2019_300K`, `lit-lt_web_2016_1M`, `lit_newscrawl_2011_1M`, `lit_wikipedia_2021_300K` (.tar.gz) | 1M sentences each, ~200 MB tgz each | Downloads CC BY (online services CC BY-NC); cite Goldhahn et al. 2012 | News and web, sentence-level, deduplicated; the packages also hold word and neighbour co-occurrence counts. Not conversational (not sampled: the sentence file comes after the co-occurrence files in the archive) |
  | HPLT v3 | sentence-level via OPUS object.pouta.csc.fi/OPUS-HPLT/v3/mono/lt.txt.gz; documents huggingface.co/datasets/HPLT/HPLT3.0 (lit_Latn) | OPUS: 407M tokens, 1.1 GB gz; full: 20.4M documents, 36 GB | Packaging CC0; text belongs to the sites ("we do not own any of the text"), takedown process | Web: 1/2 p. 1.4%, 3% questions; cleanest crawl (0.5% repeated lines, 1.7% without diacritics), 4.7% unknown (English, names) |
  | CC-100 | data.statmt.org/cc-100/lt.txt.xz | 3.6 GB xz | No IP claim on the preparation; Common Crawl terms of use | Web: 1/2 p. 1.1%, 17% repeated lines (boilerplate), 4.6% unknown incl. `href`, `document` |
  | OSCAR 23.01 | huggingface.co/datasets/oscar-corpus/OSCAR-2301 (gated) | 1.67B words, 5.2M documents, 14.5 GB | Packaging CC0, text Common Crawl; **access suspended** on HF ("will not grant any access") | Web; not sampled |
  | MaCoCu | macocu.eu | **No Lithuanian** (under-resourced EU and candidate-country languages only) | | |
  | VDU Dabartinės lietuvių kalbos tekstynas | tekstynas.vdu.lt (search only); word-form list hdl.handle.net/20.500.11821/8 (CLARIN-LT) | 141M words (62% periodicals); list 1.85M forms | Texts not downloadable; list under CLARIN-LT PUB EULA (open access) | Edited press and fiction; single word forms only, no pairs: adds nothing over the Wikipedia dump for a keyboard |

  **Recommendation.** (1) Word pairs and form frequencies for the keyboard: **OpenSubtitles v2024**
  plus Tatoeba, weighted above Wikipedia; it is the only large dialogue source and has 100× the
  1st/2nd person rate. Licence is a grey zone like everyone's (wordfreq does the same): ship only
  counts, drop pairs seen in fewer than ~3 films so no line can be read back, credit OpenSubtitles.org
  and OPUS in the About screen. Deduplicate repeated lines per film before counting. (2) More
  general breadth than Wikipedia, if wanted: HPLT v3 via OPUS (cleanest web text, sentence files,
  1.1 GB), or Leipzig `lit_news_2020_1M` where a clear CC BY matters more than size. Skip CC-100
  (boilerplate), OSCAR (access closed), MaCoCu (no lt), VDU (no text, no pairs). (3) Held-out test
  sets, done (`eval/extract_conv.py`, baseline under "Latest numbers"): 40 stretches of 500 subtitle
  lines spread over the file (3,455 usable sentences) and 2,000 Tatoeba sentences (533 usable), both
  downloaded to corpus/raw/. **Count from `corpus/conv/train/*.txt` only** (17.9M + 0.7M words): it
  is cleaned and already leaves out the held-out lines and every line equal to a held-out line of
  4+ words (a film's other uploads repeat its lines); `heldout.tsv` lists both.
  Cleaning (`eval/clean_conv.py`) before any use, repairs only where the original word is unknown
  and the repair is known: Baltic text decoded as cp1252 (5.5k words: `Ðtai èia` → `Štai čia`,
  `jüs` → `jūs`), OCR I/l (11k: `kodėI`, `lš` → `Iš`). Drops 2.2% of subtitle lines: typed without
  diacritics (44k, plus 31k valid-looking lines among them), not Lithuanian (8k), other encodings
  and Cyrillic (6k), credits (3k); 0.3% of Tatoeba (learners' `sedėti`, `tūrėti`). Varnelė's own
  corrections are **not** applied: on dialogue the context rules have false alarms (subject rule
  `Aš jus įvesiu` → `jusiu`, `Mes visi` → `visime`; case after `per`: `per toli` → `tolį`,
  `per didelė rizika`; `ką gali` → `galį`; `Kiek tu` → `tų`), suggestions guess (`salsa` → `sala`),
  and the test sets would grade Varnelė against itself. Those false alarms are worth fixing in
  the rules: a keyboard sees this register all day.
  Done 2026-10-22 (owner: attribution is enough): subtitles and Tatoeba counted with Wikipedia at
  weight 1, see "Conversational counts" under Latest numbers; credits in README.md and the
  keyboard's About screen. Still open: the keyboard's false alarms on dialogue (4 and 10 correct
  words changed in the test sets), HPLT/Leipzig for more breadth.

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
- Restoration misses after context ranking (300 test sentences): 396 words valid without
  diacritics and left alone, 62 unknown words with the right form ranked lower. Many of those
  heads are rare valid words in stripped text (`daliu` = adjective dalus), which the keyboard's
  rare-twin rule fixes first; the checker does not have that rule.
- The keyboard applies only diacritic-only fixes, so re-inflections from the object rule
  (`Jonas mato namas` → `namą`) are shown but never autocorrected; `nauja knyga` → `naują knygą` is.
- Verify on the phone (owner's tests so far found real gaps every time): the
  score compensation for `zodzou`, rare twins, key-shift autocorrect.

- **Verb transitivity**: a small hand list (TRANSITIVE_VERBS) exists; a corpus-derived
  one would cover more. Still open: `Radau nukritusia sagute` (participles end the
  phrase, and `sagute` is instrumental-only so it needs the acc diacritic variant).
- Agreement across a whole phrase: `dar viena nukritusią sagutę` → `vieną`
  (pronoun/numeral before adj+noun).
- Word-pair counts (now in the language model) for the checker's ambiguous diacritic choices
  (`žmones`/`žmonės`): only swipe ranking and predictions use them so far.
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
- `ziuri` on its own now suggests `žiūri` first (with the dump: `žiūri` 185 times, the jury `žiuri`
  421, the ranking's lemma frequency decides); with the 600 articles it was `žiuri`.
- `adb install` waits forever when wireless adb has dropped: reconnect first
  (`adb mdns services`, then `adb connect HOST:PORT`). The same happens when the phone
  auto-locks on screen timeout. (Prefer the emulator, see Commands.) Run `eval/phone_ready.sh` before every phone step (and between
  a long build and its install): it reconnects through mDNS, checks the screen is awake and
  unlocked, limits every adb call to 8 s and fails fast with the reason, so ask the owner to
  unlock instead of waiting. Wrap other adb calls with `perl -e 'alarm 8; exec @ARGV' adb …`
  (macOS has no `timeout`).
- HeliBoard capitalises sentences only if the text field asks for it
  (TYPE_TEXT_FLAG_CAP_SENTENCES); the test app's field now does.
- The keyboard fixer's fold keeps `y` (it is a key): i/y changes are never auto-applied.
- Lexicon gaps: loanwords and names (`klipas`, `singlas`); induce stems from a corpus by finding multiple
  forms of a guessed paradigm. Done: spoken `eime` ("let's go", no ending shortening: `SPOKEN_WORDS` in
  analyzer.py/analyzer.rs, colloquial for `eikime`; predictions gave its name reading `Eime`), slang
  `bičas`/`biče` (data/extra.txt). The name rule capitalises little else in the subtitle test set: of 2,953
  capitalised predictions shown, 29 are words the subtitles write lowercase, English (`Oh`, `You`, `Of`,
  `Ho`, as written in the context) and `Bičas`. Frequent lowercase subtitle words still unknown:
  `nesijaudink` (822), `nesijaudinu`: ispell-lt has `jaudinti/TRNX`, no `S`, so ne+si is refused (R + N
  without S may be a general gap); `didžiuojuosi` (560, didžiuotis listed only as `didžiuojasi/R`);
  spoken vocatives `drauguži`, `brolau`, `berniuk`, `mergyt`, `vyruti`, `brangute`; `bliamba`, `vistiek`, `nėr`.
- Keyboard: completions for half-typed words (now we show corrections);
  speed up unknown-word suggestions (6–17 ms on phone); interplay of the
  sentence fixer with HeliBoard's backspace-reverts-autocorrect is untested.
- Typo detection/ranking still behind Hunspell; keyboard-adjacency weights could
  be tuned on real typing data.
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
15. context ranking of unknown words: on 1500 stripped sentences the top suggestion for
    unknown words is wrong 246 times instead of 272 (26 better, 0 worse)
16. keyboard order: adjective before genitives (`dalyvaujančių`), genitive between a preposition
    and its object (`į teises mokykla` → `teisės mokyklą`), case+number for the one-phrase check,
    -tinas participles take no accusative
17. gesture (swipe) decoder prototype in Rust (`gesture.rs`, `varnele swipe`, serve `gesture`), eval/swipe_sim.py
18. language model: corpus bigrams + paragraph lemma cache (`lm.rs`, data version 2), in swipe ranking
    and `predict_words`; eval/build_ngrams.py, eval/predict_sim.py
19. frequencies and word pairs from the full Wikipedia dump (eval/extract_wiki.py, eval/training.py; the
    `metais.` double count fixed), count tables as FSTs (`counts.rs`, data version 3, 10.9 MB),
    "mostly a verb" ignores rule-built prefixes shadowed by a dictionary verb (`apsiuvu`)
20. swipe in the keyboard (JNI `gestureNative`, threaded prefix chains), eval/phone_ready.sh; conversational
    test sets and cleaning (eval/extract_conv.py, eval/clean_conv.py); subtitles and Tatoeba counted with
    Wikipedia (W=1, cutoffs on raw counts, 13.0 MB), credits for the frequency sources
21. next-word predictions and the ghost in the keyboard strip (`keyboard_predict`, `keyboard_ghost`, JNI
    `predictNative`/`ghostNative`, serve `ghost`, `predict_sim.py --ghost`); paragraph cache faded in by length
22. user language model learned on the phone from the final text (`user.rs`, JNI `user*Native`, serve
    `learn`/`forget`, `--learn` in predict_sim.py and swipe_sim.py)
23. grammar in predictions: case after prepositions, agreement after adjectives (`grammar_rerank`,
    eval/predict_grammar.py)
24. word triples in the language model (data/trigrams.tsv, 16.5 MB), the ghost's next word at P ≥ 0.6 (serve
    `ghostnext`), `eime`, `bičas`
25. ranked follower lists made at export (`fst-ranked`, 16.8 MB): predictions at a sentence start 8 → 0.05 ms
    on the Mac, after `ir` 3 → 0.1 ms, the same predictions
