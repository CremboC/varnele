# Ideas and open problems (backlog)

- **Next: next-word prediction with ghost text** (owner's pick, 2026-10-22, after the swipe
  prototype). Started: `lm.rs` (bigrams + paragraph lemma cache, see docs/keyboard.md),
  used by swipe ranking and `predict_words`; the owner wants context from the whole sentence and
  paragraph. Done: the full Wikipedia dump, conversational text, predictions and the ghost in the
  strip, the grammar steering them (docs/keyboard.md), trigrams. Next: phone-test the strip, inline ghost
  text, more grammar in predictions (verb government: `laukiu` + genitive, objects after
  TRANSITIVE_VERBS, numbers + genitive plural), a small neural model later. Build a language-model layer in the Rust core, not a separate system:
  corpus bigrams/trigrams with backoff to unigram frequency (in `varnele.bin` or a sibling file)
  plus a per-user overlay learned on the phone from the *final* text (done 2026-10-22: "User
  language model" in docs/keyboard.md; next: per-user trigrams if trigrams land, learning which
  autocorrections the user reverts, a phone test over days of real use). Expose one
  `P(word | context)` via JNI that next-word suggestions, ghost text (inline completion of the
  current prefix + predicted next word, new UI in the fork), swipe ranking and tap autocorrect
  all use; it also breaks frequency ties (`žmones`/`žmonės`). Predictions keep diacritics through
  the analyzer. Needs a bigger, more conversational corpus than the 600 Wikipedia articles.
- **Formal mode**: done (2026-10-22), see "Varnelė settings screen" in docs/keyboard.md. Still
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
  the walk now also yields spoken shortenings, see the gesture decoder in docs/keyboard.md. Seen in the
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
  sets, done (`eval/extract_conv.py`, baseline in docs/numbers.md): 40 stretches of 500 subtitle
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
  weight 1, see "Conversational counts" in docs/numbers.md; credits in README.md and the
  keyboard's About screen. Still open: the keyboard's false alarms on dialogue (4 and 10 correct
  words changed in the test sets), HPLT/Leipzig for more breadth.

## Phone-testing list of 2026-10-19: done, and what was left on purpose

Done (rules in docs/rules.md, tests in tests/test_grammar.py): relative case from the
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

## Smaller notes and open items

- Rare twins in different cases when the grammar doesn't decide: the verb right next to the word decides by its
  valency counts on that side (`Masina stovi kieme`, `Mano masina neveikia` → `mašina`; `vairuoja masina` →
  `mašiną`; `Grammar.verb_fit`, 2026-11-05), else frequency (`Masina kieme`: both offered, the keyboard takes
  `Mašiną`); the verb's count must be 10+ and 3× the other twins' (`Grįžau masina` stays undecided), an infinitive's
  or gerund's "before" counts don't count (they are the main clause's subject: `Masina vairuoti sunku`). Since 2026-11-08 the language model breaks the remaining ties (`Mano masina` → `mašina`, `Sita knyga` → `Šita`; see
  docs/keyboard.md). Was not reached before: a verb further away (`Sita knyga buvo išversta` got `Šitą knygą`: autocorrect
  takes `Šitą` for the unknown `Sita` by frequency, then makes `knyga` agree with its own guess when it commits it;
  the sentence fixer's soft re-decision comes too late. The 4 correct Tatoeba words the keyboard changes in 2,000
  sentences are all this. A fix needs autocorrect's context to show the keyboard's guesses as typed: the JNI `word`
  call would need the fixer's soft words; tried in the fixer alone, it changed nothing).
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
- Agreement across a whole phrase: done (2026-10-22, see docs/rules.md; autocorrected on the
  keyboard). A phrase that agrees with itself in the wrong case gets it from its verb: the valency rule
  (done 2026-10-22, see docs/rules.md), which the sentence fixer applies when the verb arrives
  (diacritic fixes; the phrase rule then re-inflects: `guli viena nukritusia sagute` → `nukritusi
  sagutė` on the emulator). Open: coordinated objects are left alone (`rinko tautosaka ir etnografine
  medžiaga`), 3rd person verbs and infinitives need ratio 30 (`pasakyti tiesa` is 11×: missed), the
  phrase before the verb only at a clause start (`BLB apylinke veikia`: missed), a capitalised word at a
  sentence start (`Bare auga`, a city: gone with the name guard), compound tenses whose fix needs more than
  diacritics (`Nesu girdėjęs tokia istorija` → `tokios istorijos`). The negation and object rules take a compound
  past as the participle's verb in the auxiliary's person and negation (2026-11-05: `nesu praradusi viltį` →
  `vilties`), not when the participle agrees with the next word (`esi suaugęs vyras`: 18 false alarms on 5.7M
  words without that guard), negation then only by an accusative (`nesu jojusi drambliu` stays). The pair rule's old `pirmasis mūrinis pastatas` → `mūrinys`
  is gone (2026-11-05): every `-ys` noun got the plural i-stem paradigm meant for `durys/MK`, `ašmenys/VK`
  (`mūrinis` an accusative plural of `mūrinys`, `petys`, `arklis`); now only nouns with M (feminine) or V
  (masculine) do, and no singular one. 37 bogus flags on 5.7M words of correct text gone.
  Seen while building it, older rules: negation stops at a pronoun object (`Neturiu tą gražią knygą`
  fixes only `tą`); the object rule takes `pirmiausia` as an object (`Filmai turi pirmiausia didelę
  vertę` → `pirmiausią`).
- Lexicon: `didelis` declined like `-inis` (`dideliai`, and `dideli` unknown); now like `-esnis`
  (`dideli`, `dideliems`). Other `-is` adjectives are `-inis`/`-ytis` and right (`mediniai`, `mažyčiai`).
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
- Reviewed en.wikipedia Lithuanian_grammar (2026-10-20). Added from it: numbers + genitive plural,
  genitive-governing verbs. Not added: `arti` + genitive (also the verb "to plough"), dual
  agreement (optional in modern use), word order/aspect (tendencies), neuter predicates
  (`buvo vėsu`). The article has no usable sections on comma rules or verb government beyond
  what is in docs/rules.md; a Lithuanian source (VLKK rules) would be the next step.
- `ziuri` on its own now suggests `žiūri` first (with the dump: `žiūri` 185 times, the jury `žiuri`
  421, the ranking's lemma frequency decides); with the 600 articles it was `žiuri`.
- Lexicon gaps: loanwords and names (`klipas`, `singlas`); induce stems from a corpus by finding multiple
  forms of a guessed paradigm. Done: spoken `eime` ("let's go", no ending shortening: `SPOKEN_WORDS` in
  analyzer.py/analyzer.rs, colloquial for `eikime`; predictions gave its name reading `Eime`), slang
  `bičas`/`biče` (data/extra.txt). The name rule capitalises little else in the subtitle test set: of 2,953
  capitalised predictions shown, 29 are words the subtitles write lowercase, English (`Oh`, `You`, `Of`,
  `Ho`, as written in the context) and `Bičas`. Frequent lowercase subtitle words still unknown:
  `nesijaudink` (822), `nesijaudinu`: done 2026-11-05, `-si-` after `ne-`/`nebe-` is allowed for a verb with a
  reflexive flag (R, O) and N, after `tebe-` with R/O and X, after `be-` so only for participles and gerunds (`besijaudinantis`, not `besijaudink`), S or not (`_allowed` / `analyzer::allowed`): 664
  tokens in half the 4.5M-word subtitle sample stop being unknown, all real (`nesikandžioja`, `nesikraustyti`); `didžiuojuosi` done (2026-11-04, data/extra.txt: other verbs listed in ispell-lt only
  as bare `word/R` entries may lack a paradigm the same way);
  spoken vocatives `drauguži`, `brolau`, `berniuk`, `mergyt`, `vyruti`, `brangute`; `bliamba`, `vistiek`, `nėr`.
- Keyboard: completions for half-typed words (now we show corrections);
  speed up unknown-word suggestions (6–17 ms on phone); interplay of the
  sentence fixer with HeliBoard's backspace-reverts-autocorrect is untested.
- Typo detection/ranking still behind Hunspell; keyboard-adjacency weights could
  be tuned on real typing data.
- iOS later: the Rust core is portable; keyboard extensions have tight memory limits.

