# Keyboard (Varnelė Klaviatūra, HeliBoard fork) design

- Renamed "Varnelė Klaviatūra": app ID `dev.imbrasas.varnele.keyboard` (`.debug` for debug
  builds), provider authorities under the same ID, so it installs next to HeliBoard.
  Internal packages stay `helium314.keyboard.*`. Lithuanian is enabled first on a fresh
  install. Credits are in the fork's README and the About screen.
- Fork defaults on: key borders, vibration, number row, emoji key, language switch key. Night theme `black`
  (OLED), keyboard height 115% in portrait (unfolded and cover screen; landscape 100%), auto-correction
  confidence 0.5 (upstream 0.24) for English and other languages; Lithuanian ignores the slider and keeps
  0.24 (`Defaults.VARNELE_AUTO_CORRECT_CONFIDENCE`, used in `Suggest.shouldBeAutoCorrected`): Varnelė's
  scores are calibrated for its threshold 0.188 (at 0.7+ its 0.05-target suggestions would autocorrect).
- **Tap log** (`inputlogic/VarneleTapLog.kt`, setting "Record typing accuracy" `varnele_tap_log`, default
  off, Varnelė screen, with Export / Delete; works in release builds): for measuring whether misses are
  systematic before a touch model. A word's taps (WordComposer's pointers, keyboard coordinates) are labelled
  with the word as kept (committed and not reverted before the next word or leaving the field), only when
  its folded letters match the taps one to one and every tap is on a main-keyboard letter key (no gestures,
  resumed words, popup letters). One row per tap: meant / hit / previous letter, position in the word, offset
  from the meant key's centre in key widths/heights, position on the keyboard, key size, letter row (0 = top
  letter row), keyboard size, language, corrected, landscape / folded / split / one-handed, screen dp. Rows
  shuffled in batches of 200 before `files/varnele_taps.tsv` (16 MB cap); not in incognito, passwords, URLs.
  Checked on the emulator with taps placed below the centres by the old key height: logged dy 0.57 / 0.40 /
  0.23 per row, expected 0.55 / 0.39 / 0.24. The Material theme has no touch-position correction
  (`themes-lxx-base.xml`: `touchPositionCorrectionData` @null; Holo has AOSP's 2011 per-row data).
  **First log** (owner, 2026-11-05, English, 6,613 taps on the Fold7's cover screen): 5.3% of taps hit another
  key; taps land below the drawn key (top row +0.18 key heights, ~1.4 mm), and keys near the middle fall short
  towards the thumb reaching for them (`t`, `g`, `y` left by 0.14–0.22 key widths, `h`, `n`, `u` right): `t`→`r` 36,
  `h`→`j` 31, `e`→`w` 22, `o`→`k`/`l` 30. HeliBoard's hit box already holds the gap below each key (half a gap
  lower than the key drawn), which covers ~0.12 key heights of the low taps.
- **Touch model** (`keyboard/VarneleTouchModel.kt`, setting "Adapt keys to my typing" `varnele_touch_model`, default
  on, any language, plus "Forget how I tap"; Varnelė screen): learns from the tap log's labelled taps (the same
  words, whether or not the log is on) each letter key's mean offset from its hit box's centre, in key pitches,
  and `KeyDetector.detectHitKey` moves each letter key's hit box by it (a tap in two moved boxes goes to the
  nearer centre; in none, the usual detection). A key is a place (letter row from the bottom, column in half
  keys), so layouts of the same shape share it; per screen (orientation, size in dp, split, one-handed). A key's
  mean is shrunk towards its half row's and row's (30 taps' weight), counts halve every 1,000 taps, nothing moves
  before 100, shifts capped at 0.3 pitch, taps over 0.9 / 0.7 pitch off ignored. Stored as sums per place
  (`files/varnele_touch.tsv`), no text. Replaying the first log in order, learning as it goes: keys missed
  350 → 288 (112 now right, 50 now wrong); offsets per row alone: 352, per half row: 309. On the emulator, 108
  taps 45 px low moved the boundary under `t` from y 1787 to 1812. A tap whose letter is the word's with or
  without diacritics now counts as meant for the key hit (a German `ä` key was labelled `a`).
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
  - context fix of a valid word: diacritic-only, the subject rule (`aš buvo` →
    `buvau`, owner's choice) or the phrase rule (`viena nukritusią sagutė` → `nukritusi`,
    owner's choice 2026-10-22: the same grammar autocorrects and steers predictions) → whitelisted,
    1.3M (autocorrects); otherwise 1.1M (shown only). The sentence fixer applies subject fixes only
    to the word just finished, so a backspace revert of an earlier word is not undone; phrase fixes
    also to earlier words (`LETTER_RULES`), since the noun that shows the case comes last.
  - unknown word: whitelisted if diacritic-only and clearly best (margin 0.08,
    or context chose); autocorrect-appropriate if **typoCost ≤ 1.0**, where
    typoCost is the edit cost ignoring diacritics (`zodzou` → `žodžių` = 0.8).
    **Scores compensate HeliBoard's normalisation**, which counts every changed
    letter including diacritics (`zodzou` → `žodžių` = 4 edits / 6 letters):
    score = target × 1e6 / (1 − levenshtein/len), target 1.0 for diacritic-only,
    0.9 − 0.4·typoCost for one typo, 0.05 otherwise; scores kept strictly decreasing.
  - **rare twin** (`common_twin`, `common_neighbour` in Python and Rust; `check_text` gives rule `rare`, a
    blue suggestion, `keyboard_word` a context fix): a valid word whose form and
    lemma never occur in the frequency corpus, with a twin that only adds diacritics and whose
    lemma does (`sakini` → `sakinį`). A capitalised word counts its
    lowercase readings too (`Kuriu` is the name Kurys, but also `kuriu`, so it is not → `Kurių`), a capital
    inside a sentence is a name and stays, a twin is never a name (`Eduarda`). A twin that is only
    a participle or a vocative is never kept (`testuoju` no longer → `tęstuoju`). The rule
    also covers never-seen 2–4 letter words without diacritics one neighbouring key from a word seen 50+
    times (`gavi` → `gavo`, `duik` → `duok`; not `vašu`; `kak` no longer qualifies: the subtitles hold it). A typed diacritic is meant:
    before 2026-10-30 a twin could also take one away, and the keyboard changed a correct `dantistė` to
    `dantiste`. **key-shift** too is in `check_text` now, as suggestions, for an unknown word with nothing
    within a typo.
    A **seen** word gets the twin too when the twin's form is seen `RARE_TWIN_RATIO` (10) times as often
    as the word's form and its whole lemma, by added diacritics only, not i/y (`veliau`, of a verb seen
    79 times, → `vėliau` 48,849; also `viska`, `musu`, `sis`, `buk`, `rupi`; not `ligoje`, `lanke`,
    `butu`, `ja`: their lemma is common), and lowercase or with no words before it in the sentence
    (`Veliau`; a capital further on is a name). Comparing with the form alone also caught `ligoje`
    → `lygoje`. Twins in different cases: the one giving the fewest grammar issues with the words before,
    then the most frequent (`pavojingiausia žemės ūkio masina` → `mašina`, not `mašiną`).
  - **the language model in typed autocorrect** (2026-11-08, Rust only, `keyboard_word_in`; `check_text` untouched):
    an unknown word's corrections cost 0.3 × log10(P(w | two previous words, user model) / P(w)) less, as in swipe,
    reordered only within their kind (a typo fix never overtakes a diacritic one: `ka` → `ką`, not `kad`; without
    that guard Tatoeba lost 0.7 points), and rare twins the grammar leaves tied go by P(twin | previous words)
    instead of frequency (`mano masina` → `mašina`, `Sita knyga` → `Šita knyga`: was `Šitą knygą`). keyboard_restore,
    1,000 / 1,500 / 2,000 sentences, Wikipedia / subtitles / Tatoeba: restored 75.7 / 77.5 / 82.0 → 75.6 / 77.7 /
    81.8%, whole sentences 40.6 / 53.5 / 62.3 → 40.7 / 53.9 / 62.1%, correct words changed 9 / 9 / 4 → 7 / 9 / 1; correct
    text typed through the model (1,500 sentences each) 198 / 406 / 18 changed words → 198 / 407 / 18 (names and URLs
    swapping one wrong guess for another). Weight 0.15 the same, 0.5 worse. No measurable cost (FST lookups).
  - **a name stays a name** (2026-11-05): an unknown word with a capital inside a sentence (not after `:`, an
    opening quote or a dash) is autocorrected, by autocorrect or the sentence fixer's last-word fix, only into a
    twin adding diacritics that is a name or written 100+ times (`Siauliuose` → `Šiauliuose`, `Zemes` → `Žemės`),
    never by a typo correction (`KeyboardWord::name`, `name_fixes`): of 6,319 such words in the test sets 3,317
    were changed (`Boruta` → `Biruta`, `Black` → `Blank`, `Bresto` → `Bręsto`), now 38. HeliBoard's n-gram context
    is empty right after a comma, colon or quote: the fork then passes the sentence so far (`sentenceSoFar`), else
    `Labas, Boruta` looked like a sentence start. eval/keyboard_sim.py passes the sentence before the word (80
    characters), as the keyboard's context; keyboard_restore 76.0 / 76.9 / 83.4% → 75.7 / 76.7 / 83.4%
    (capitalised words with rare twins, `Kryziuocio`).
  - suggestion ranking: a negated form with no frequency of its own borrows the plain
    form's (`Neturetu` → `Neturėtų`); a suggestion differing from the input only by being a
    capitalised name costs +0.5.
  - **Varnelė settings screen** (fork, `settings/screens/VarneleScreen.kt`, main settings entry
    "Varnelė" shown when the library loads): all the fork's own settings. Corrections: key-shift
    (shown only with autocorrect on), **fix earlier words** (`varnele_fix_earlier`: the sentence
    fixer's grammar fixes before the word just finished; that word is always fixed), **add missing
    commas** (`varnele_commas`), **underline unknown words** (`varnele_underline`), formal;
    Predictions: **suggest the next word too** (`varnele_ghost_next`: off, the ghost is cut to its
    completion), learn, forget. All on by default except formal. **Formal Lithuanian**
    (`varnele_formal`, default off). `SettingsValues` copies it into `Native.formal`, which every
    `Native.check`/`Native.gesture` call passes to Rust: `keyboard_word(…, formal)` gives a
    colloquial word its standard form as a context fix with rule `formal` (whitelisted, like
    `subject`/`rare`: `VarneleDictionary.SURE_RULES`, also applied by the sentence fixer), and
    `gesture(…, formal)` hands back a spoken candidate as its standard form, deduplicated
    (`einam` → `einame`), so no colloquial form is ever suggested. Unknown words never got
    spoken suggestions (the suggester only proposes dictionary forms). CLI: `--formal` on
    `kb`, `swipe` and `serve`.
  - **key-shift** (setting `varnele_key_shift`, default on, Varnelė screen; `suggest.py`/`suggest.rs`):
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
- **A word inside a sentence** (2026-10-23, owner: going back to `kad ziwma zymiai rimtesne negu siaip`,
  fixing `ziwma`, then tapping `rimtesne` offered no `rimtesnė`): `InputLogic.setVarneleContext` hands
  `VarneleDictionary` the text after the word too (`textAfter`, 200 characters, also with the cursor inside
  a touched word; read from the app once per cursor move or new field and kept while typing, since typing
  at the cursor doesn't change it: the connection doesn't cache it, and asked on every keystroke it took
  over a second on a loaded emulator and made HeliBoard mark the connection slow), and when the sentence goes on after it, `Native.check` gets the sentence before the word
  and the rest of it up to its full stop (Rust `keyboard_word_in`, JNI `word(…, after, …)`, serve `kb`'s 4th
  field, CLI `kb … --after TEXT`): the grammar sees a whole sentence (not `partial`), so a touched valid word
  gets the sentence's fix (`rimtesne` → `rimtesnė`) and a word retyped mid-sentence is ranked by the words
  after it (`ziema` → `žiema`, was the more frequent `žiemą`). A touched word in Lithuanian always asks
  Varnelė (upstream showed only the word's SuggestionSpans when it had any: autocorrect's, the system spell
  checker's); the span words come after Varnelė's (`setResumed`). Resumed words never autocorrect
  (HeliBoard's `isResumed`), and the strip leaves out the typed word there, as upstream does for a touched
  word without spans. Not covered: a touched word whose sentence already holds the wrong twin (`kad žiemą
  žymiai rimtesne`), and the sentence fixer still fixes only the text before the cursor.
- **The sentence fixer** (`SentenceFixer` in `rust/core/src/fix.rs`; `inputlogic/VarneleSentenceFixer.kt` only
  hands it the text before the cursor and applies the edit), hooked at the end of
  `InputLogic.handleSeparatorEvent` and `onPickSuggestionManually` (a picked suggestion
  finishes a word too; the picked word itself is left as chosen): after each finished word, re-check the
  current sentence and apply **only** diacritic-only grammar fixes, the phrase rule's re-inflections
  (`tie grazus didele namai` → `gražūs dideli`) and missing commas, two passes, rewriting from the first changed character through
  `RichInputConnection`. It first re-checks the word the separator just finished and
  applies `VarneleDictionary.confidentFix` (the whitelisted kind), so punctuation
  (`sakini?`) and learned words can't leave it unfixed. This is how later words fix earlier ones
  (`visu … žodžių` → `visų`, `kuriu … rašau` → `kurių`, `, kurių`).
  **The keyboard's own diacritics are not trusted like typed ones** (2026-10-23, owner: `kad ziema zymiai
  rimtesne` got `žiemą`, the 5× more frequent twin, and then no `rimtesnė`): the fixer remembers, per
  sentence, each word autocorrect or its own last-word fix changed only by diacritics (word index → the
  form typed; `InputLogic.commitCurrentAutoCorrection` → `rememberAutocorrection` → JNI `fixRememberNative`, a
  backspace undo → `fixUndoneNative`, an edited word is forgotten), and with "fix earlier words" on, before its
  passes, calls `keyboard_soft(sentence, sentence with those words as typed)`: each of them among the last 6 words, not the one just finished, is checked as typed with
  the others as they stand (all of them as typed made `pačių idomiausiu nuotykių` a sentence of unknown
  words), and takes the grammar's first twin only when the twins it allows leave out its current spelling
  (`salygine taika` allows `sąlyginė` and `sąlygine`: the autocorrected `sąlyginė` stays). `kad žiemą
  žymiai rimtesne` → `žiema`, then `rimtesnė`; `kultūrinė ekspansija` is not fixed by it (the keyboard
  already changed `ekspansija` to agree). 0.15 ms a sentence (Mac, through serve). A word autocorrected by
  the fixer's last-word fix (not HeliBoard) can't be undone with backspace (HeliBoard committed it as typed).
  **The whole sentence** (2026-11-05, owner: "not only the previous word or two but the whole sentence, into the
  future too"): `SentenceFixer::apply_around(before, after, …)` also gets the text after the cursor (the fork reads
  it fresh, 400 characters cut at a space; a cached copy went stale after a picked suggestion or a space-bar cursor
  swipe), checks the sentence to its end and returns an `AroundEdit` (before: delete + insert; after: skip, delete,
  insert, the cursor staying put; the fork selects that span, commits, puts the cursor back, and leaves it if the
  app refuses the selection). The word just finished is decided with the rest of the sentence (`keyboard_word_in`),
  an autocorrected word is re-decided once any word follows it, also after the cursor, and after the cursor only
  findings that the word just finished brings are applied (the rest was there when those words were typed: a fix
  the user undid stays undone). Typing `i ` before `didele kavine.` gives `į didelę kavinę.`; `ziema ` after `kad`
  in `Tai svarbu, kad žymiai rimtesne negu šiaip.` gives `žiema … rimtesnė` (emulator). On 250 subtitle and 250
  Wikipedia sentences with one word retyped without diacritics mid-sentence, with autocorrect: the word and the
  sentence right 188 → 204 and 171 → 187. Serve: `fix\tBEFORE\tPICKED\tAFTER`. A sentence of 28 words takes ~7 ms a
  word on the Mac with text after it (0.1–5 ms without). JNI `fixNative(before, after, base, …)`: the fork's
  `Native.kt` must match.
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
  when P ≥ 0.6 (`GHOST_NEXT_P`; right 71–73% of the times the ghost is tapped, see docs/numbers.md), added after the autocorrect decision, so it never autocorrects: it goes in the strip's
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
  lemma: `geras`; or a participle, as in the phrase rule: `nukritusią`; not definite forms, often
  nouns: `pėsčiųjų tiltas`; not capitalised: `Vytauto Didžiojo universitete`; not kuris/question
  words/possessives) a word agreeing with it or a genitive (`geras Lietuvos krepšininkas`); after
  preposition + adjectives the readings in its cases. Adjectives that disagree (`viena nukritusią`,
  `į didelę gražia`) get what the phrase rule would choose (`G::modifier_cost`: as they are 0, a
  lost diacritic 1, re-inflected 2, the first word never re-inflected, unique cheapest), so the
  prediction and the later fix agree (was: no requirement). Neither change moved predict_sim or
  predict_grammar (identical on all three sets: such contexts are rare in finished text). Then the
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
  lists, +0.27 MB (16.5 → 16.8 MB). Then **valency** (optional the same way): `"VERB\tCLASS\tafter|before\tCASE"`
  → count, 40k rows seen 3+ times, +0.4 MB (17.2 MB). `Data::followers` reads a list when there is one and enough of it
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
  bundleNouserlib`; → `app/build/outputs/apk/nouserlib/VarneleKlaviatura_1.0-nouserlib.apk`; the APK installs as `dev.imbrasas.varnele.keyboard` next to `.debug`.

