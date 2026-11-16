# Measurements

The first entries (2026-11-05 back to 2026-10-30) are the newest; below them the order is by topic. Where figures conflict, the newer date wins. Measurements of 2026-11-08 (`po`, numerals, the language model in typed autocorrect, `visa skrydi`) are with their rules: docs/architecture.md item 12, docs/rules.md, docs/keyboard.md. New entries go at the top.

- **Known issues, worked through with an adversarial review each** (2026-11-05, 16 commits after 4fcf31a, local only).
  Flags on 5.7M words of correct text (subtitle sample, dump sample, the test sets; unknown words not counted):
  18,078 → 10,579, nearly all of the drop false alarms: the subject rule 6,380 → 263 (`mes visi` → `visime`), cross-line
  adjacency 260, vocative/degree `per` and `kas … per` 991, `šiuo metu`, `pasimėgauti` ≠ `gauti`, bogus `-ys` plurals 37.
  On 20k subtitle and 3k dump lines stripped of diacritics, right first fixes 1,262 → 1,308 and 2,708 → 2,723, wrong or
  false 146 → 89 and 108 → 87. restore.py Wikipedia / subtitles / Tatoeba 71.9 / 73.7 / 79.3 → 72.1 / 74.1 / 79.5%
  (whole sentences 32.3 / 45.7 / 55.3 → 33.0 / 46.7 / 55.7%). keyboard_restore 75.8 / 76.6 / 83.1 → 75.7 / 76.7 /
  83.4% with the simulation now passing the sentence's own words, as the keyboard does (with the old context it
  read 76.0 / 77.2 / 83.4%), correct words changed 2 / 4 / 8 → 2 / 0 / 1 (Tatoeba's 2,000-sentence run: 4, all `Sita
  knyga` → `Šitą knygą`, see the rare-twin item in docs/backlog.md). Names autocorrected inside sentences 3,317 → 38 of 6,319. The whole-
  sentence fixer: a word retyped mid-sentence right 188 → 204 (subtitles) and 171 → 187 (Wikipedia) of 250.
  Parity 100% throughout. Open from this round: `Sita knyga` (autocorrect agrees with its own guess), coordinated
  objects, `Palauk kūdiki` (animacy), `Visos linijos radialines`, the gesture path's names (it checks keys in
  lowercase).

- **Bare reflexive entries, negation over instrumentals** (2026-11-04, from the third to fifth reviews of the valency
  work: `jis didžiuoju kunigaikščiu tapo` → `didžiuoja`, `nesididžiuoju tuo darbu` → `darbų`). The loader reads ispell-lt's
  689 bare R/O lines (docs/architecture.md, item 1): 429 reflexive-only verbs (plain forms only with `-si-`), 198 flags join
  their verb entries; data/freq.tsv, lemma_freq.tsv, valency.tsv rebuilt. The negation rule keeps an instrumental the
  verb governs (docs/rules.md); after `būti` the genitive-before-noun rule applies (`tai buvo garbes reikalas` → `garbės`:
  `buvo` had hidden behind its particle reading). A phrase stops at a question word but not at `kažkur`, `kažkas`
  (`Padariau kažkur klaida` → `klaidą`). Measure negation on the same lines both ways: the first guard looked good on
  correct text (184 false alarms gone in 6.4M words) and lost 193 right fixes on 16.7k stripped lines (`nesi-` keys
  with no counts, genitive-object verbs, only the noun judged, word frequency over the verb's counts, negated counts
  ignored). Now, against 5b84348 (Rust), negation + valency on those 16.7k lines (subtitle and dump lines with a
  negated verb, each correct and stripped): false alarms on correct text 193 → 24; stripped right 1,496 → 1,379, wrong
  285 → 123; 801 `nepaisant` lines unchanged. Validation (1.9M stripped words): 32 right negation fixes lost, 56 wrong
  gone, 52 new right fixes (`kurių` 18, valency 20, agreement 7, case 7), 1 new wrong. Correct text (4.6M subtitle
  words + 1.8M of the dump): 722 unknown words gone (`Lažinuosi` 122, `Mėgaukis`, `šaipaisi`), 50 new commas before
  indirect questions, all right (`aš žinojau, kas tai buvo`), 7 object false alarms gone (`buvo labai sunki`); all
  rules: test 20 → 20, freq 87 → 87, subtitles 219 → 214, Tatoeba 48 → 47. restore.py, keyboard_restore.py unchanged
  (Tatoeba keyboard whole sentences 62.0 → 62.3%, 9 → 8 correct words changed); restore.py doesn't count negation
  fixes (`FIX_RULES`). Parity 100%. Left (`musu` → `musų` fixed 2026-11-05): `Braunas` reads as the spoken `braunasi`; `vidurį nakties` →
  `vidury` in more sentences now that `Buvo` is a verb; key-shift and one-typo autocorrect can reach never-seen forms
  of the new reflexive verbs (`Basteris` → `bastęsis`, `Hobitsai` → `Jovytasi`: ~30 in 6.4M words; a frequency floor
  for autocorrect targets would touch every keyboard decision, so not done here); `nesikėsina tave nužudyti` →
  `tavęs` is new (arguably right: negation reaches an infinitive's object).
- **A phrase with no case** (2026-11-03, owner: `Galbūt reikia padidinti įprasta dydi?` stayed). The valency rule skipped
  phrases that don't agree with themselves; now it takes one whose noun can only be a vocative (`lost_case`) when: a twin
  of it in a case is `RARE_TWIN_RATIO` (10) times as frequent, counting a form missing from freq.tsv as seen `FREQ_MIN`
  (10) times (`dydi` 0 / `dydį` 2,721; not `tėti` 10,747 / 880, `ligoni` – / 70, `šuneli` 56 / 43: the vocative
  `sūneli` is no such twin); the modifiers agree with each other, can't be verbs other than participles and only gain
  diacritics (not `nupirkti automobili` → `nupirktą`, `uždusinti kūdiki` → `uždūsintį`, `mažame nameli`); the case is 5×
  the verb's most frequent case that is no object, `NOT_OBJECT_CASES` nom/dat/ins/loc (a genitive is one: `turite
  laiko`; `ateiti`: acc 28, dat 14, so `Ateik šuneli` stays; `turi` 1st/2nd: acc 7,164, loc 1,222, so `Ar turite skėti?`
  → `skėtį`); the verb is no genitive noun that may modify an address (`Pakrančių apsaugos sraigtasparni, …`, `laimės
  kūdiki`). A phrase with no case also steps over `mano/tavo/savo/mūsų/jūsų` after the verb (`SPAN_POSSESSIVES`:
  `Duok man tavo numeri` → `numerį`); for every phrase it was 55% right in a second review (`dalyvauja savo noru` →
  `norų`, `Nekalbėk mano vardu`, `Žinau kur tavo mašina` → `mašiną`: the set-phrase guard never sees `savo noru`). The first version (any vocative-only noun, modifiers re-inflected, `have` 0) was broken by an
  adversarial review: infinitives made participles (453 of 20k subtitle lines), addresses without a comma made objects
  (27 of 278). Now (after both reviews): 11,686 subtitle lines with a noun's ogonek dropped 414 → 1,285 flags, the 871 new all right, none
  lost; the 278 addresses with their comma dropped 5 flags, as before; correct text test / freq / subtitles / Tatoeba
  unchanged, also 1.6M words of the dump; every 4th subtitle line of the training text (4.5M words) 19 new flags, all
  real (`Paimsi truputi`, `prarasi savo ženkleli`, `Pradėsime rugsėji`). restore.py, keyboard_restore.py unchanged,
  parity 100%. Left: `Palauk kūdiki` → `kūdikį` (an address; `palaukti` takes accusative durations, never seen without
  a comma in 18M words; nothing in the data tells `kūdiki` from `numeri`, `truputi`: only animacy would).
  Then: a phrase no longer steps over a question word (`Žinau kur mašina`, `Ar žinai kieno ta mašina`, `supranti kodėl
  man gėda`: indirect questions), `didžiuotis` is a verb (data/extra.txt; ispell-lt had only bare `didžiuotis/R`,
  `didžiuojasi/R`, `didžiavosi/O`, so `didžiuojuosi`, 739 times in the subtitles, was unknown and `Turėtum didžiuotis
  tėčiu` → `tėčių`), and data/valency.tsv rebuilt with the phrase finder that steps over possessives (903k → 954k
  counts, 35.7k → 36.8k rows: `turi savo namą` now counts). On the 4.5M-word subtitle sample, against the first
  commit: 4 false alarms and 414 unknown `didžiuo-` forms gone, 2 real fixes lost (`Noriu puse iš anksto`, `Palauk
  truputėli`), 2 new (`pasakė kvailyste`, a comma); correct text, restore.py, keyboard_restore.py unchanged, parity 100%.
- **One engine** (2026-10-30, owner: rules belong in the engine). `rare` and key-shift in `check_text`, Python
  and Rust, parity 100% (7,682 findings). Correct text (test / freq / subtitles / Tatoeba): 20 / 87 / 219 / 48 flags
  → 20 / 88 / 224 / 48, the 6 new ones `viska`, `Viska`, `musų`, `bučiau`, `užplusta` (real errors), `papalis`. The
  first version flagged 56: names and twins that took a typed diacritic away. restore.py Wikipedia / subtitles
  / Tatoeba 70.2 / 71.8 / 77.9 → 71.9 / 73.7 / 79.3%, whole sentences 30.3 / 42.0 / 54.0 → 32.3 / 45.7 / 55.3%, 0
  changed. keyboard_restore.py 76.3 / 76.9 / 83.2 → 75.7 / 76.8 / 83.2% with those guards (Wikipedia's are names,
  stripped: the guards are what stops the keyboard changing correct ones), whole sentences 39.0 / 49.0 / 61.7 →
  38.3 / 49.0 / 61.7%. Running the real fixer in the sim instead of its old copy: 75.8 / 76.6 / 83.1%, whole
  sentences 38.3 / 49.0 / 62.0%, the same correct words changed: the copy lacked the last-word fix and sentence
  ends (`ji emiau` → `ėmė`, the subject rule on the word just finished, is what the keyboard really does).

- Wikipedia (150 articles, 65k words): 20 context flags, **all real errors**
  (16 commas incl. `nariu, pasiekusiu tokį aukštą postą`, `kylanti grėsme`, `prastos kokybes`, `daugybę metu`,
  `FIA Šiaurines Europos zonos`); unchanged by the Wikipedia-dump frequencies once `apsiuvu` was fixed.
  The 600 freq articles: 84 flags (`kuri kuria`, `kurie kuria` no longer get a comma; `pasteliniu spalvų
  deriniai`); 86 with the dump frequencies, the new ones not yet reviewed.
- **Agreement across a phrase** (2026-10-22): new flags on Wikipedia, all real errors in the articles: test
  20 → 20, freq 86 → 87 (`šiokia tokią kompensaciją`), 1.4M words of the dump (4 samples tuned on, 3
  fresh ones checked after) +4 (`visoms jaučiančios būtybėms`, `tam tikrų religinės praktikų`,
  `specialiais ryškias ženklais`, `Pirmuosiuose laisvose rinkimuose`); subtitles 218 → 217 (the object
  rule's `suradote viena kitą` gone), Tatoeba 48. `eval/agreement.py` (552 phrases of test+freq; 84 of
  subtitles+Tatoeba), fixed before → after, with the wrong fixes and flags on the phrase's other words:
  the modifier before the noun in another case 13 → **384** (0 wrong; others changed 131 → 42, the
  pair rule's), the first modifier in another case 1 → 64 (re-inflecting the first word is not
  allowed: predicates), the first modifier without diacritics 5 → 25, dialogue 7 → 54 and 7 → 19.
  restore.py unchanged (all diacritics stripped: no word shows the case). keyboard_restore.py: subtitles
  74.0 / 44.0 → 74.2 / 44.3%, Tatoeba 81.5 / 58.0 → 81.7 / 58.7% with 10 → 9 correct words changed,
  Wikipedia 74.0 / 36.0% unchanged, with phrase fixes autocorrected (`tie grazus didele namai` →
  `gražūs dideli`, `ten stovi grazus nauja namas` → `naujas`, also on the emulator) and an unknown
  modifier after a modifier ranked by agreement (`visa sita isterija` → `šita`; autocorrect took the
  more frequent `šitą` and the rules then made the phrase accusative). Mid-typing, a phrase whose noun
  could be a genitive with nothing typed after it waits (`apgultos užbaigta taikos | sutartimi`).
- **Valency** (2026-10-22): on correct text (test, freq, 7 dump samples, subtitles, Tatoeba; ~1.7M words)
  3 new flags: `iškilo problemėle` (a real error in the subtitles), `Bare auga` (a city), `Sesele
  išgyveno`. Tuned on that text and on the stripped test sentences: at ratio 3, before the guards, 976
  false alarms; ratio 10 / 20 / 30 / 50 with the guards: 14 / 8 / 3 / 1 false, 11 / 9 / 9 / 6 right fixes
  of 11 (stripped text, 0 wrong). restore.py (now applying valency fixes): Wikipedia 70.0% unchanged,
  subtitles 71.5 → 71.9%, Tatoeba 77.6 → 78.0%, whole sentences 41.7 → 42.0%, 53.3 → 54.0%, 0 changed.
  keyboard_restore.py, after the phrase commit → with valency: Wikipedia 74.0 / 36.0 → 74.3 / 36.3%,
  subtitles 74.2 / 44.3 → 74.9 / 45.3%, Tatoeba 81.7 / 58.7 → 82.3 / 59.7%, correct words changed 2 / 4 / 9
  (unchanged). eval/agreement.py: within 2 of the phrase commit (case before the noun 384 → 382, second
  modifier without diacritics 67 → 71). Sentence of 12 words 1.75 ms (Rust bench). On the emulator:
  `visa sita isterija maciau vakar` → `Visą šitą isteriją mačiau vakar` (the sentence fixer, once
  `mačiau` is typed), `ant stalo guli viena nukritusia sagute` → `nukritusi sagutė`, `kada baigsis visa
  sita isterija` stays nominative.
  Compound past and cleaner counts (2026-10-23, owner: `Visa šita istorija esu girdėjęs vakar` wasn't
  fixed; the simple past `girdėjau` wasn't either: `girdėjo` had 10 nominatives before it, all `Puikiai
  girdėjau` / `Vaikinai girdėjau` and 3rd person `girdi`). keyboard_restore: Wikipedia 74.3 → 74.6%,
  subtitles 74.9 / 45.3 → 75.0 / 45.7%, Tatoeba 82.3 / 59.7% unchanged; restore.py subtitles 71.9 → 71.7%,
  Tatoeba 78.0 → 77.9% (`stipria advokate Lik Redik`: names follow; `nedora orgazma`: orgazmas not in the
  lexicon); correct text: `sužadėtuves` (a real error), `problemėle` (real), `Sesele`; parity 100%.
- **Clauses without a verb, conjunctions, the keyboard's own diacritics** (2026-10-23, owner's phone tests:
  `O cia neprivaloma nepaisant to, kad ziema zymiai rimtesne` got `žiemą`, undone, and no `rimtesnė`;
  `Cia individualios teises zymiai svarbesnes negu visuomenes saugumas` kept `svarbesnes`, `visuomenes`).
  Correct text, test / freq / subtitles / Tatoeba 20 / 87 / 219 / 48 flags unchanged; 9.7M words of the dump
  (12 files + 4 samples): 1 new, a real error (`sistemų ir variantu autorius`), 3 lost, all old false alarms
  (`ji atliko dekoratyvinę`, `yra apragėjusiu galu liežuvis`); the first version had 30 new there, each
  now a guard in the rules table. restore.py: Wikipedia 70.0 → 70.2%, subtitles 71.7 → 71.8%, Tatoeba
  77.9%, 0 changed. keyboard_restore.py, Wikipedia / subtitles / Tatoeba: before 74.6 / 75.0 / 82.3%
  (whole sentences 36.3 / 45.7 / 59.7%); the grammar 74.8 / 75.0 / 82.3% (36.7 / 45.7 / 59.7%); with
  `keyboard_soft` 74.9 / 75.0 / 82.4% (36.7 / 45.3 / 60.0%), correct words changed 2 / 4 / 9 throughout;
  the soft pass changes 5 words for the better and 2 for the worse (`su kiaušiniu mišraine`, `surašymą
  sudarę baltaodžiai`). Sentence of 12 words 1.9 ms (unchanged). Keyboard simulation and emulator: both
  sentences come out right, also without the undo (`kad žiemą` → `žiema` once `rimtesne` is typed).
  Left: `Visos linijos radialines` (a real error, but a genitive-or-plural subject right before the
  adjective is mostly genitive + noun), the subtitle gain of the first version (the guards).
- **`visa tai` and common twins of seen words** (2026-10-30, the owner typing `tačiau visą tai ateis vėliau` on the
  Mac). `visą tai`: 309 different sentences in 48M words (test, freq, the dump, dialogue), ~8% of all
  `visa tai`; 302 flagged, all real errors (read: the 26 before a noun or adjective, a sample of the rest), 7
  left alone (`visą tai laiką`; `manai`, `valdai`, `krūva`, `netiesa` also read as a dative or accusative;
  a text ending in `ištaisyti`; the unknown `priešaky`). Wikipedia flags 20 / 87 unchanged, restore.py
  unchanged, parity 100% (also on those 314 lines, none of them in the parity articles).
  Rare twin, keyboard_restore, ratio 7 / 10 / 20 / 30 vs before, Wikipedia / subtitles / Tatoeba: restored 74.9 / 75.0 /
  82.4% → 76.3 / 76.9 / 83.2% (7, 10), 76.1 / 76.8 / 83.0% (20), 76.0 / 76.8 / 83.0% (30); whole sentences 36.7 /
  45.3 / 60.0% → 39.0 / 49.0 / 61.7% (7, 10), 39.0 / 48.7 / 61.0% (20), 38.7 / 48.7 / 61.0% (30); correct
  words changed 2 / 4 / 9 throughout (3 on Wikipedia before twins were chosen by the words before:
  `pavojingiausia … mašiną`). 10 is kept for its margin: `ja` (instrumental of `ji`, correct) has ratio 5.5.
  Correct text typed through the keyboard model (6,451 sentences of the three test sets): no new change, the
  two differences are typos in the text (`viska`, `musų`). Of the words at ratio ≥ 10 the correct uses in 48M
  words, ~70 tokens: `sis` after a hyphen (`10-sis`, if the keyboard splits there), `grizo`, `grizai`,
  `grizus` (a grizzly, one film), `gris` (Pinot gris), `masina` (lures), `stabo`, `geliu`; the rest are missing
  diacritics in the text, although the cleaning dropped lines typed without them. Swipe σ 0.3, Wikipedia:
  final word right 73.6 → 74.1%, keys unchanged. `kb` on seen words, median 0.035 → 0.045 ms, 95% unchanged
  (Mac, through serve). Left: `mano masina neveikia` → `mašiną` (nothing before chooses the case).
- **Unknown word after a pronoun** (2026-10-30, `Maciau ji pries pora dienu` got `priės`; `ji` there stands for
  `ją`): the rule took any verb of that person, in diacritic-cost order, whatever its cost. Measured on 664k
  sentences with a pronoun + word, diacritics stripped (test, freq, both dialogue test sets, the dialogue training
  text, which the frequencies are counted on), top suggestion against the original word at the rule's 107,971
  firings: old rule 99,803 right, plain suggester 100,154, verbs in the suggester's order 100,642; with the gap
  0 / 0.1 / 0.15 / **0.2** / 0.25 / 0.3 / 0.5 / 1.0: 100,461 / 100,995 / 101,057 / **101,053** / 101,068 / 101,001 /
  100,928 / 100,726. A form-frequency ratio instead of the gap did no better (101,048 at 30×). Old against new
  Rust, end to end: the top suggestion changed at 2,154 words, 1,396 now right, 145 right before (some are
  errors in the text: `pažysti`), 613 neither (`sikt` → `šikti`, was `šiki`). Wikipedia flags, `restore.py
  --sentences 300` and `keyboard_restore.py` identical on all three sets (the samples hold no such word), parity
  100%, also on 20,000 stripped sentences. On 3,000 sentences each: subtitles whole sentences 44.5 → 44.6%,
  keyboard words changed to another word 510 → 507, the rest identical.
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
  words, 6–17 ms unknown words with suggestions, data load ~110 ms. Data file 17.2 MB (v3, with the conversational counts, triples, ranked lists and valency).
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
  costs ~0.08 µs a key. Fix: ranked lists made at export (see Data format v3 in docs/keyboard.md), also for the frequent-word
  fallback (`kas` after `Gal ka`: every ka- word listed and sorted, 0.9 ms). Through serve on the Mac,
  median of 30 warm calls, before → after (predict N=5): `<s>` 8.2 → 0.05 ms, `Labas. ` 8.1 → 0.06,
  `Ir ` 3.0 → 0.10, `Gal ` 0.18 → 0.13, `<s>` + `k` 0.62 → 0.04; ghost `Gal ka` 1.2 → 0.20 ms. 100
  sentences with their paragraph, median / 95%: subtitles predict 0.93 / 9.0 → 0.62 / 2.1 ms, ghost
  1.46 / 3.0 → 1.07 / 2.4 ms; Wikipedia predict 0.81 / 3.2 → 0.50 / 2.1 ms, ghost 1.31 / 2.9 → 0.95 /
  2.3 ms. Every prediction identical (11,176 predict/ghost requests compared, `--raw-lm` too; predict_sim
  `--ghost` on the three sets and swipe_sim on subtitles unchanged). What is left with a long paragraph
  (1,500 characters): `lm_context` analysing its last 150 words, 0.3 ms, and `p_predict` for each of
  its ~190 words as candidates, 0.6 ms (`analyze_exact` per word), done again for the ghost's next word.
  On the emulator, warm predictions at a sentence start now take 1–5 ms (were 1.3–2.9 s); the
  remaining 0.1–2 s outliers come with the emulator's own frames at 600–800 ms (Mac load 16), and the
  same request a moment later takes 3 ms: emulator timings are only meaningful on an idle Mac.
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
  alarms on dialogue (`Mes visi` → `visime`, `jis visai` → `visau`), see "Corpus beyond Wikipedia" in docs/backlog.md.

