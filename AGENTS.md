# Varnelė: agent notes (read this first, every session)

Rule-based Lithuanian spell and grammar checker, plus a fork of the HeliBoard
Android keyboard that uses it for autocorrect, a Mac autocorrect app and a Chrome
extension. This file holds what every session needs: how to work, the commands,
the shape of the system, the gotchas. The detail (every rule's exceptions, the
keyboard's design, all measurements, the backlog) is in `docs/`, see "Where the
detail is". Keep both current when something changes.

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
- Commit when asked; push when asked. **Local `main` and `origin/main` (github.com/CremboC/varnele) are one
  branch and stay on the same commit: "push to main" or "merge to main" means both, never one of them.**
  - Landing work from a worktree: `git fetch origin`, rebase onto `origin/main`, `git push origin HEAD:main`,
    then `git -C ~/git/varnele merge --ff-only origin/main` in the same step.
  - Pushing from `~/git/varnele`: `git fetch origin`, `git merge --ff-only origin/main` first, then push.
  - Before building, testing or recording from `~/git/varnele`, also `git fetch origin` and fast-forward if
    `git status -sb` says behind. A keyboard built from a stale checkout fails silently (see Gotchas: `Native.kt` arguments).
  - Uncommitted work may be another session's. If it blocks the fast-forward, stash only the files that
    collide (`git stash push -- FILE`) and pop them after; never reset, and commit only your own hunks.
  - The fork is the same: `~/git/HeliBoard` `main` and `fork/main` stay on one commit (`origin` there is
    upstream, pull only). A fork change needing a new Rust signature lands with its varnele commit.

## Repositories

| Path | What |
|---|---|
| `~/git/varnele` | This repo. Python grammar "compiler", Rust runtime, Android spell-checker app, evaluations |
| `~/git/HeliBoard` | **Varnelė Klaviatūra (HeliBoard fork)**: fork of github.com/Helium314/HeliBoard (GPL-3.0) with Varnelė as the Lithuanian dictionary, at github.com/CremboC/Varnele-Keyboard (renamed from CremboC/HeliBoard on 2026-10-20), work on branch `main` (the old `varnele` branch was fast-forwarded into it and deleted). Remotes: `origin` = upstream Helium314/HeliBoard, now HeliBorg/HeliBoard (pull only, never push; take updates by merging `origin/main` into `main`), `fork` = CremboC/Varnele-Keyboard (push here). Upstream's `AI_USAGE.md` forbids AI-generated upstream PRs: **never open PRs upstream from this work** |

Layout of this repo:

```
varnele/        Python: lexicon loading, paradigms, analyzer, suggestions, grammar rules, export
rust/core       Rust runtime: same behaviour, loads data/varnele.bin   (crate "varnele")
rust/android    JNI bridge (cdylib libvarnele_android.so; data/varnele.bin ships as an uncompressed asset, mapped by Native.init)
rust/wasm       WebAssembly bridge for the extension (data embedded, no bindings generator)
rust/desktop    Desktop autocorrect in every text field: engine.rs (any OS), mac.rs + mac_selftest.rs, mac/ (bundle)
android/        Stand-alone app: system spell checker service + test screen
extension/      Chrome extension: Varnelė's underlines in every text field (rust/wasm is its bridge)
eval/           evaluate.py (vs Hunspell), restore.py, parity.py, keyboard_sim.py, corpus fetch/freq,
                extract_wiki.py + training.py (dump text), build_ngrams.py, swipe_sim.py, predict_sim.py,
                clean_conv.py + extract_conv.py (conversational text: cleaning, test sets, text to count)
tests/          unittest: test_morphology.py, test_grammar.py
vendor/ispell-lt  BSD word list (stems + class flags only; its affix rules are NOT used)
data/           extra.txt (our lexicon additions), abbreviations.txt, freq.tsv, lemma_freq.tsv,
                varnele.bin (generated, git-ignored), index.pkl (cache, git-ignored)
docs/           the detail behind this file: rules, architecture, keyboard, desktop, numbers, backlog, history
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
rust/target/release/varnele check FILE | json FILE | words W... | kb WORD [CONTEXT...] [--after TEXT] | bench
python3 eval/parity.py                             # Rust must equal Python: 100% identical findings
python3 eval/restore.py --sentences 300            # strip all diacritics, measure restoration
python3 eval/commas.py [corpus/freq] [--show-wrong]  # strip all commas, precision of each comma rule
python3 eval/agreement.py [DIR...] [--max N] [--show] # break one word of agreeing modifier+modifier+noun phrases, count fixes
python3 eval/build_valency.py [--workers 8]        # case of the phrase next to each verb, on the training text -> data/valency.tsv
                                                   # (~80 s; then export). restore.py also applies the valency rule's fixes
rust/desktop/mac/bundle.sh [--reset]               # build ~/Applications/Varnele.app (macOS menu-bar app); a rebuild
                                                   # loses its Accessibility grant: ask the owner first
rust/target/release/varnele-desktop --sim "text"   # type text through the desktop engine (stdin too; --no-english)
cargo test --release -p varnele-desktop --manifest-path rust/Cargo.toml
python3 eval/keyboard_sim.py "kodel nepataiso ..." # type through the engine's keyboard decisions, word by word
python3 eval/keyboard_restore.py [--no-soft]       # restore.py's 300 sentences typed through the keyboard model
                                                   # (--no-soft: the fixer leaves autocorrect's diacritics alone)
rust/target/release/varnele serve                  # stdin requests "kb\tWORD\tCONTEXT[\tAFTER]" / "json\tTEXT" / "learn\tTEXT" /
                                                   # "gesture\tX,Y X,Y…\tCAP\tN\tCONTEXT" / "predict\tCONTEXT\tPREFIX\tN" /
                                                   # "fixreset" / "fixed\tBEFORE\tTYPED\tCOMMITTED" /
                                                   # "fix\tBEFORE\tPICKED" (the sentence fixer; used by the sims)
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

Demo videos (`eval/demo_videos.py`, typed in Google Messages by `eval/emulator_touch.py`, which drives the
emulator console: real-time taps, long presses and swipes, unlike `input tap`): `ROUND=N … setup`, `… record
SCENE demo`, `… compose SCENE demo` (needs Pillow) -> `demo/final/`. Each ROUND is a fresh chat. The system
spell checker is switched off for them (the emulator's is Gboard's English one); `forget()` clears what
rehearsals taught the keyboard, else `Ksbsd` turns up in the strip.

Always pass `-s emulator-5554`, so a connected phone is never touched. The test app's field starts
with a sample text: tap it (540, 530), `input keyevent 123` moves to the end. Read the field with
`uiautomator dump` (its EditText `text=`), the strip from `predict …` / `ghost …` lines in the log or a
screenshot (`adb -s emulator-5554 exec-out screencap -p > s.png`).

## One engine

**Every rule and every decision about language lives in the Rust core, and every rule that changes or
marks text in `check_text` also in Python; apps hand it what was typed and apply what it says** (owner,
2026-10-30). Keyboard, Mac app, extension and `eval/keyboard_sim.py` all call `rust/core/src/fix.rs`:
`KeyboardWord::autocorrection`, `fix_level` / `suggestion_level`, `confident_fix` (what may change
without asking), `SentenceFixer` (the word just finished, earlier words, commas, the app's own diacritics),
`word_context`, `Tally` (is this text Lithuanian). A new rule or threshold in Kotlin, JavaScript or a sim is a
bug. What stays in an app: HeliBoard's score compensation (`score`, `KEY_SLIP_SCORE`: its normalisation, not a
language decision), settings, UI, reading and writing the field, and the Mac's English guard (`lean`: it needs
the system dictionary; the extension has none and asks `Tally`). Rust-only with no Python twin, because
`check_text` doesn't use them: gesture decoding, the language model, predictions, `keyboard_soft`.

## Where the detail is

Read the file for the area before changing it; none of these is loaded by default. Paths are in this repo
(`~/git/varnele/docs/…`), also when this file is read from the fork.

| File | Holds | Read it when |
|---|---|---|
| `docs/rules.md` | Every context rule: examples and each exception, with the false alarm it came from | Touching `grammar.py` / `grammar.rs`, or judging a flag |
| `docs/architecture.md` | Lexicon, index, sound rules, prefixes, spoken layer, suggestions and their costs, w/q/x slips (item 7), lexicon fixes (item 12; more lexicon notes in the backlog) | Touching the analyzer, paradigms, suggester, `data/extra.txt` |
| `docs/keyboard.md` | The fork and the keyboard side of the core: settings, scores and HeliBoard's normalisation, rare twins, sentence fixer, swipe decoder, language model, predictions and ghost, user model, tap log and touch model, data format v3, release builds and Play | Touching `fix.rs`, `lm.rs`, `gesture.rs`, `user.rs`, `counts.rs`, `export.py`, rare twins (`common_twin` in `__main__.py` / `checker.rs`, `RARE_TWIN_RATIO`), the JNI bridge or the fork |
| `docs/desktop.md` | The Mac app (`rust/desktop`) and the Chrome extension | Touching either |
| `docs/numbers.md` | Measurements per round of work, with what was tried and dropped (a rule's or feature's own figures are often with it in the other files: grep the term across `docs/`) | Before tuning a threshold or retrying an idea; to compare a new run |
| `docs/backlog.md` | Open problems, ideas, things left on purpose and why, corpus sources | Picking the next task; before "fixing" a known gap |
| `docs/history.md` | One line per landed round | Rarely; `git log` has the rest |

Keeping them current: a new rule or exception goes into `docs/rules.md`, its numbers into `docs/numbers.md`
(at the top), what is left open into `docs/backlog.md`, one line into `docs/history.md`. This file changes
only when a command, a working rule, the layout or a gotcha changes: keep it under ~28 KB.

## Architecture in short

- **Lexicon** = ispell-lt stems + class flags; our own paradigms generate every form (~10M). Index = stem +
  shared ending signature, lookup tries every split; a diacritic-blind ("folded") index is built lazily.
  Fixes and additions live in `data/extra.txt` (`-word/FLAGS` drops an entry).
- **Lookup** adds sound rules at the stem/ending boundary, the prefix grammar (ne-/be-/te- + verbal prefixes +
  `-si-`), the spoken register (`valgyt`, `buvom`, `mokykloj`) and productive word formation with blocking.
- **Suggestions**: diacritic-blind lookup + one typo on folded text, ranked by weighted edit distance minus form
  and lemma frequency. Text typed with no diacritics pays for them once, so frequency decides.
- **Context rules** (`grammar.py` / `grammar.rs`): case fixes fire only when a diacritic-only twin satisfies them;
  re-inflection is generated from the word's own entry. A line break ends a sentence.
- **Python = compiler and reference, Rust = runtime.** `export` writes `data/varnele.bin`; Rust must stay
  line-for-line equivalent. Any rule change goes into both, then `eval/parity.py` (100%).
- Offsets are characters in Python/Rust; the JNI bridge converts to UTF-16.

## Context rules (index; the exceptions are in docs/rules.md unless a row says otherwise)

| Rule | Example |
|---|---|
| case (prepositions) | `prieš pora` → `porą`, `į teisės mokykla` → `mokyklą` |
| distributive `po` | `po dvi sėdynės` → `sėdynes` |
| quantity | `daug vaiku` → `vaikų`, `10 metu` → `metų` |
| case (verbs, indefinites) | `ieškau raktu` → `raktų`, `ka nors` → `ką nors` |
| agreement (pair) | `gražią kavine` → `kavinę`, `visa skrydi` → `visą skrydį`; neuter `visą tai` → `visa tai` |
| phrase (2+ modifiers + noun, least cost) | `viena nukritusią sagutė` → `nukritusi` |
| valency (counts in `data/valency.tsv`, last) | `padariau klaida` → `klaidą`, `Visa šita isterija mačiau` → `Visą šitą isteriją` |
| predicate adjective | `ji nedidele` → `nedidelė`, `kad žiema žymiai rimtesne` → `rimtesnė` |
| genitive before a head noun | `miesto gyventoju skaičius` → `gyventojų` |
| context ranking of unknown words | `rado salyga` → `sąlygą` (reorders suggestions only) |
| preposition that became a verb | `kabo virs stalo` → `virš` |
| negation | `neturiu laiką` → `laiko`; keeps an instrumental the verb governs (`netikiu Dievu`) |
| subject | `aš buvo` → `buvau`, by corpus pair evidence |
| object | `mačiau namas` → `namą`, `Jonas mato namas` |
| relative | `žodžių kuriu aš rašau` → `kurių`, `knyga, kuria skaičiau` → `kurią` |
| comma | `sakė kad` → `, kad`; parentheticals, address, lists, participial phrases, `negu`, repeated connectives. Comma rules left out on purpose: docs/backlog.md, "Phone-testing list" |
| rare (twin) | `sakini` → `sakinį`, `veliau` → `vėliau`: docs/keyboard.md ("rare twin"), the ratio sweep in docs/numbers.md |
| slips, key-shift | `ziwma` → `žiema`: docs/architecture.md item 7; `ksbsd` → `labas`: docs/keyboard.md |

## Working on a rule

1. Reproduce with `python3 -m varnele check` / `words`, and `rust/target/release/varnele kb` for the keyboard.
2. Change Python and Rust together. Every observed false alarm or fix becomes a CORRECT / FLAGGED case in
   `tests/test_grammar.py`.
3. Measure both ways on the same lines: false alarms on correct text (the Wikipedia check above, the dialogue
   test sets, a dump sample) **and** right/wrong fixes on that text stripped of diacritics. A guard that looks
   good on correct text alone has cost as many right fixes as it removed false alarms (negation, 2026-11-04: 184 gone, 193 lost).
4. `eval/parity.py`; `eval/restore.py --sentences 300` and `eval/keyboard_restore.py`, each also with
   `--corpus corpus/conv/subtitles` and `--corpus corpus/conv/tatoeba`; swipe and predict sims if the language
   model or counts changed (`--no-paragraph` for Tatoeba is theirs only).
5. Record: the exception in `docs/rules.md`, the numbers in `docs/numbers.md`.

Baselines, 300 sentences, Wikipedia / subtitles / Tatoeba (2026-11-05, docs/numbers.md; the 2026-11-08 changes
moved them by +0.2 at most, so re-run before comparing): restore.py 72.1 / 74.1 / 79.5%, 0 correct words changed;
keyboard_restore 75.7 / 76.7 / 83.4%, correct words changed 2 / 0 / 1. Wikipedia test flags 20, all real.
Parity 100%; data file 17.2 MB; sentence of 12 words ~1.9 ms on the Mac.

## Keyboard in short (docs/keyboard.md has the rest)

- "Varnelė Klaviatūra", app ID `dev.imbrasas.varnele.keyboard` (`.debug` for debug builds); internal packages
  stay `helium314.keyboard.*`. `dev/imbrasas/varnele/Native.kt`: the JNI class name must stay exactly this.
- `VarneleDictionary.kt` is the main dictionary for `lt` and calls `Native.check` (Rust `keyboard_word`).
  HeliBoard autocorrects when `score/1e6 × (1 − editDistance/len)` passes its threshold or the suggestion is
  whitelisted; Varnelė's scores compensate that normalisation. Lithuanian ignores the confidence slider.
- The sentence fixer (`SentenceFixer`, `fix.rs`) runs after every finished word: diacritic-only grammar fixes,
  phrase re-inflections, commas, the keyboard's own diacritics re-decided, the whole sentence around the cursor.
- Swipe (`gesture.rs`), the language model (`lm.rs`), predictions and the ghost, the user model (`user.rs`)
  are Rust only, not in parity.
- What autocorrects is the owner's choice: diacritic-only fixes, the subject and phrase rules, `rare`, `formal`
  (`SURE_RULES`, `fix_level`); other re-inflections are shown only; a resumed word never autocorrects.
  **A typed diacritic is meant** and never taken away; a capitalised unknown word inside a sentence is a name
  and only gains diacritics.
- Privacy: nothing typed is stored or logged (desktop); the user model and tap log skip incognito, password,
  URL and e-mail fields. Debug logging must respect that.
- Release: a push to the fork's `main` runs the release CI (signed `nouserlib` bundle for Play). Version codes,
  signing, the upload keystore and the local signed build: "Release builds" in docs/keyboard.md.

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
  An emulator that crashed or was killed shows a crash-report consent dialog at the next boot and waits
  for it (no adb ports, `Showing crashdialog` in the log): `emulator_ready.sh` passes `-crash-report-mode
  never`; a stuck one ignores SIGTERM (`kill -9` its qemu process, remove the AVD's `*.lock` files).
- Galaxy Z Fold7 has two displays: `screencap` needs a display id; use
  `uiautomator dump` to read the screen as text instead.
- Wireless adb drops regularly; re-check `adb devices` before installing.
- zsh does not word-split `$VAR` commands; use a shell function.
- `data/index.pkl` is rebuilt whenever a source file is newer than it. A second checkout of older code
  sharing `data/` (a symlink, to compare old and new) has fresh file times and rebuilds the shared
  cache from its old paradigms: give such a checkout its own `data/` copy.
- Parity needs deterministic order: inflection reads forms from the index
  (`Index.entry_forms`), sorts use (score, word) keys.
- Wikipedia API rate-limits; `fetch_corpus.py` uses cirrusdoc bulk text with backoff.

- HeliBoard's user history learns every word committed as typed. Repeating a test
  sentence trains it on the wrong spelling; that is why whitelisted Varnelė fixes skip
  the history comparison in `Suggest.shouldBeAutoCorrected`.

- Lemma frequencies: a listed particle/preposition reading (tag W) takes the whole count
  of its form, else `iš` made the verb `ižti` "common" (1175) and `neisiu` was "fixed"
  to `neišiu` by the rare-twin rule. Names share lowercased lemma keys with verbs
  (`Klausė`/`klausė`), so a capitalised suggestion for lowercase input costs +0.3.
  After a lexicon change that moves readings the tables were rebuilt (`build_freq.py`, `build_valency.py`, export):
  only where `corpus/wiki/text` and `corpus/conv/train` exist, else `eval/training.py` silently counts on the 600
  articles and overwrites the tracked tables. Check the row counts in the diff.
- The keyboard inserts a comma only once the next word is typed (`pirk bet` → `bet ką`).
  Commas *after* a word (`Deja, jis`) are issues on the following word, so they wait one
  more word: `Deja jis.` at the end of a message stays without the comma.
- Rules that need the first fix to see the second: `labas, jonai kaip` (gap may be a comma),
  `radau nukritusia sagutę` (autocorrect fixes the last word first). Test both orders.
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
- Words with `q`, `w` or `x` are skipped as foreign: no underline, so test the underline with `sirdgv`, not `zzzxq`.
- Key-shift doesn't autocorrect on the emulator (2026-10-30): `fofrkua` keeps `didelis` first in the strip but
  stays as typed. Probably HeliBoard's distance weight: every letter differs, so 1 − distance/length = 0
  whatever KEY_SLIP_SCORE is.
- **The data file is an asset, not part of the library** (2026-11-03): both apps copy `data/varnele.bin` into
  `assets/` uncompressed (`noCompress += "bin"`), `Native.init(context)` memory-maps it and hands it to
  `dataNative` before anything else (the keyboard: `App.onCreate`); without it `Native.available` is false.
  Embedded with `include_bytes!` it was in each of the 4 ABI libraries and their symbol files: the Play bundle
  went from 104 to 40 MB, the library from 18 to 1.2 MB. A compressed asset can't be mapped (`openFd` throws).
- **The fork's `Native.kt` and `rust/android/src/lib.rs` must have the same arguments**, and nothing checks
  that: the fork's `word(…, after, keyShift, formal)` on a Rust side without `after` builds and runs, with
  the arguments shifted. Found 2026-10-30 from a local `main` 3 commits behind `origin/main`: `formal` took
  `keyShift`'s value, so every spoken form became standard (`buvom` → `buvome`) with the setting off. If the
  log shows `colloquial fix=[…]` while formal is off, suspect this first.
- The system spell checker draws its own underlines, whatever the keyboard knows: with Gboard's (English,
  the emulator's default) `Paprasčiausiuosiuose vienkiemiuose` is red under Varnelė Klaviatūra too. The fork's
  own spell checker service is still HeliBoard's, not Varnelė. Testers need to switch the system one off or
  select the `dev.imbrasas.varnele` app's.
