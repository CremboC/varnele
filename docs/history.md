# History (commits on varnele/main)

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
26. agreement across a phrase (least-cost case/number/gender, eval/agreement.py), phrases across
    `mano/tavo/savo`, the object rule leaves number/gender errors to the pair rule, `dideli`; on the
    keyboard the phrase rule autocorrects (fork `paulius/varnele-phrase`), predictions use its costs,
    an unknown modifier is ranked by agreement (`visa šita`)
27. verb valency counted on the training text (eval/build_valency.py, data/valency.tsv, 17.2 MB) and the
    valency rule; the phrase rule never changes a typed diacritic; emulator crash dialog skipped
28. valency: compound past (`esu girdėjęs`), ambiguous person counts as 3rd, name / adverbial-instrumental /
    unknown-term guards shared with the counts, 1st/2nd person ratio 5 and minimum 10
29. predicate adjectives in clauses without a verb, degree adverbs, `teisės` as a subject, unknown subjects
    ranked by their predicate; the genitive-before-noun rule after conjunctions; copulas without other
    prefixes; the keyboard re-decides its own diacritics (`keyboard_soft`, fork `paulius/varnele-soft-words`)
30. a word inside a sentence is checked with the rest of it (`keyboard_word_in`, JNI `word(…, after, …)`): a
    touched word gets the sentence's fix (`rimtesne` → `rimtesnė`), a retyped one is ranked by the words after
    it; finger slips onto w/q/x are typos (`ziwma` → `žiema`)
31. w/q/x slips: an extra key press (`ziewma` → `žiema`), a capital at a sentence start (`Gwrai` → `Gerai`)
32. demo videos (eval/demo_videos.py, eval/emulator_touch.py), `kiškiakopūsteliauti`, `kiškiakopūstlapiauti`,
    local `main` and `origin/main` kept on one commit
33. the neuter `visa tai`; a seen word takes a diacritic twin 10× as frequent as its form and lemma (`veliau`
    → `vėliau`), twins chosen by the words before
34. an unknown word after a pronoun: a verb of that person only near the best suggestion (`ji pries` → `prieš`)
35. desktop autocorrect, macOS prototype (`rust/desktop`): an event tap watches the keys, `engine.rs` fixes each
    finished word, only on the Lithuanian layout, an English guard, a self-test; a spell server doesn't work
36. Chrome extension: the core as WebAssembly, underlines and a card of suggestions in every text field
37. one engine: `rare` and key-shift in `check_text`, autocorrect and the sentence fixer in `fix.rs` (the fork, the Mac
    app and the sim call it, the Mac gets earlier words and commas), a typed diacritic stays, the language tally
38. valency for a phrase with no case: a vocative-only noun far rarer than its twin (`įprasta dydi` → `įprastą dydį`)
39. valency: question words end the phrase (`Žinau kur mašina`), `didžiuotis` a verb, counts rebuilt
40. ispell-lt's bare R/O lines read as verbs (reflexive-only flag `Z`: `didžiuojuosi`, no `didžiuoju` "I am proud";
    no particle reading for `buvo`, `saugo`), negation keeps an instrumental the verb governs (`netikiu Dievu`)
41. known issues with a review each: the subject rule by corpus pairs (`aš kalba`) and likely verbs, būti's present; a
    line break ends adjacency; degree `per` and `kas … per`; `šis` declined; object/negation/agreement guards; twins
    ordered like suggestions (`musu` → `mūsų`); the whole sentence around the cursor in the sentence fixer (fork too);
    the verb next to a rare word chooses its case; `ne-si-` without S; names stay names in autocorrect (fork: context
    after a comma); compound past; `verb_of`; plural-only `-ys` nouns; `tas knygas` under negation
42. the distributive `po` + numeral (`po dvi sėdynes`); `du`, `trys`, `abu` declined as numerals; the language model in
    typed autocorrect (`mano masina` → `mašina`); both words of a pair whose noun has no case (`visa skrydi` → `visą skrydį`)
