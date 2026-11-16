# Architecture and key decisions (full notes)

Moved from AGENTS.md; the summary is there.

1. **Lexicon = ispell-lt stems + flags**, our own paradigms generate every form
   (12 noun declensions, adjectives with definite forms/degrees/-umas/-okas, verbs
   from 3 principal parts: all tenses, moods, participles, gerunds, verbal nouns,
   reflexives). ~10 M forms. ispell-lt's bare `word/R` and `word/O` lines (689: R/O are its reflexive
   flags, with no class flag) are read by `lexicon._bare_verb_forms`: the flag of a verb entry of the same
   word (`buvo/O`, `saugo/R`; read as words they gave common verbs a particle reading `W`, which made
   them "not mostly a verb"), or the reflexive form of a reflexive-only verb (`didžiuotis/R`,
   `bastosi/R`, `didžiavosi/O`: the kind from the ending, an `-o` present with R, past with O), which
   becomes a principal part with our own flag `Z`: a plain form of it only with the `-si-` infix (`_allowed` /
   `analyzer::allowed`: `nesidomiu`, `besidžiaugiantis`; `didžiuoju` stays the instrumental of didysis, `gėrimas`
   no participle of gėrėtis). 53 plain forms of no listed verb (`gavi/O`, `bėgėti/R`) are left words.
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
   variants in grammar are ordered by this cost, the same flat one for a word typed without diacritics, then
   by frequency (`šitą` before `sytą`; `vėją` before `veją`). A word typed without diacritics whose twin is a
   possessive 10× as frequent stands for it in a phrase (`nematau musu namo`: `mūsų`, not the flies' `musų`; frequency, not the part of speech, also orders the twins a rule
   requires (`kiek butu gerai` → `būtų`, would be; ordering by part of speech, `butų`, flats, was tried: after these
   words the subtitles write `būtų` 77 times, `butų` 8);
   ispell-lt lists the personal pronouns' forms as bare words, so `mūsų` has no case reading of its own). Lowercase input penalises capitalised names.
   **Finger slips onto w, q, x** (`slip_fixes` in `__main__.py` / `checker.rs`, 2026-10-23, owner: `ziwma`
   got nothing): a word with a letter Lithuanian doesn't use is foreign and skipped, unless it is lowercase,
   4+ letters, its one such letter is w, q or x, it is not in `freq.tsv` (foreign words seen 10+ times:
   `news`, `wiki`, `box`), and replacing that letter by a key touching it gives seen words (`SLIP_KEYS`:
   staggered rows, w touches q e a s, not d; the suggester's `_near` also counts the other diagonal, which
   made `kawa` → `kada`, `wirba` → `dirba`): `ziwma` → `žiema`, `priwglobsčio` → `prieglobsčio`, `xiūrėti` →
   `žiūrėti`; or deleting it when it was pressed as well as a letter next to it that it touches (`ziewma` →
   `žiema`, `dawrbas` → `darbas`; not `zwiema`). A capital counts as the keyboard's own only at a sentence
   start (`check_word(w, sentence_start)`: `check_text` by what precedes the word, `keyboard_word` when no
   words of the sentence come before; `Gwrai` → `Gerai`), and not when the capital is the slip itself
   (`Westu`, `Xanderis`, `Waltas`: names). The keyboard's underline passes the words before the word, else a
   name inside a sentence (`Narwi`) would count as a sentence start. On 23.5M words of correct text (test,
   freq, both dialogue test sets, the dialogue training text, 4 dump files) 72 flags, ~3 per million words:
   4 real typos (`Galėjqi` → `Galėjai`), the rest rare Latin and foreign words (`natrix`, `vertex`, `woke`),
   names at a sentence start (`Maxas` → `Mažas`, `Brokaw`, 18) and extra-key deletions into short words
   (`twai` → `tai`, `jaws` → `jas`, ~15). Replacement alone, lowercase only: 35; any capital at a sentence
   start: 86. Without the guards 502 of the 2,780 such tokens in the test sets alone (`New` → `Nes`,
   `index` → `indes`). keyboard_restore and parity unchanged.
8. **Context rules** (`grammar.py` / `grammar.rs`), see docs/rules.md. Case rules
   only fire when a **diacritic-only** variant satisfies them; re-inflection
   (negation, subject, object) is generated from the word's own entry.
9. **Python = compiler/reference, Rust = runtime.** `export` writes everything
   the runtime needs; Rust must stay **line-for-line equivalent** (parity 100%).
   Any rule change goes into both `varnele/grammar.py` and `rust/core/src/grammar.rs`,
   then `eval/parity.py`.
10. Offsets are characters in Python/Rust; the JNI bridge converts to UTF-16.
12. **Lexicon fixes in data/extra.txt** (2026-11-05): ispell-lt lists `šis/ši` ("this") only as bare words (particles), so
    no agreement rule saw `šią knygą`, `ši darbą`: it gets the pronoun paradigm (`paradigms.pronoun`, declined like jis)
    and the bare forms are dropped; `pirmiausia`, `daugiausia` get their adverb reading. `jis` and `pats` are bare
    words too: `jis` forms are handled by lists throughout the rules; a `pats` paradigm was tried and dropped (`pati
    savo slėptuvę`, `kuri pati vyną` became modifiers): `EMPHATIC` lists its forms instead. A phrase of a
    demonstrative and `metu` (`šiuo metu`, `tuo pačiu metu`) is an adverbial of time: no rule governs it.
    `du`/`dvi`, `trys`, `abu`/`abi` were bare words too (2026-11-08): `paradigms.SMALL_NUMERALS` declines them as plural
    numerals (`Num.m.pl.nom`; no number made `du seni` → `senį`), lemma_freq.tsv recomputed from freq.tsv (`du` 27k →
    60k: it now counts `dvi`, `dviejų`…). Two guards came with it: a word with an adverb reading (W) that agrees with the
    modifier only by a twin ends a phrase and is no head (`šių dviejų kartu veikiančių`, not `kartų`; a W word that can
    be genitive still goes through the genitive skip: `visa savo gyvenimą` → `visą`), and the pair rule's lone genitive
    is no head when a word up to 3 later (spaces and quotes between) agrees with the modifier (`tris saulės nutviekstus`).
    On 3.9M words of correct text (test, freq, both dialogue test sets, a dump file, every 8th subtitle training line):
    6 new flags, all real (`trys ratus`, `tris kraštinės`, `trijų tūkstančiu`, `dviejų kokiu nors`), 25 old ones gone,
    all false (`įkurtas Papilės`, `turintis labai`, `nuo visų tuo metu`); restore.py unchanged, keyboard_restore
    Wikipedia 75.7 → 75.9%, swipe_sim and predict_sim level, parity 100%. Unknown foreign words now get `du`/`abi`
    first more often (`de` → `du`, was `ne`; `baby` → `abi`), from the larger lemma counts.
11. **A line break ends a sentence**: words across `\n` or `\r` are not adjacent (`Aš⏎Pablogėjo.` is no subject
    error), as the sentence start already was. Hard-wrapped text inside a sentence pays for it (`buvo
    nedidele⏎mergaite` is a finished predicate), on 5.7M words: 260 cross-line flags gone, 8 new, 7 real.

