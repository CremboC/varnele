# Desktop app and browser extension

## Desktop app (macOS prototype, `rust/desktop`)

Autocorrect in every text field, no input method: the app watches the keys and types its fixes, like
Espanso; Grammarly and LanguageTool work the same way. Chosen over the spell-checker services (only apps
that ask, no autocorrect in Chrome or Electron) and an input method (a new input source, weeks of work).

- `engine.rs`, no OS in it, for Windows too: keeps the sentence typed so far (its own copy; nothing reads
  the field), and when whitespace, enter or tab finishes a token, fixes the word in it (`(sakini?` keeps
  its punctuation; a token with anything but letters inside is left alone: `www.x.lt`, `a1`), then runs the
  sentence fixer on the text so far (earlier words, commas, the app's own diacritics: `visą tai ateis` →
  `visa`, `sakė, kad`): the engine's decisions, as on the keyboard, key-shift off. Backspace right after a fix
  restores the word, keeps the space, and leaves that word alone until the app quits; an edit that would change
  such a word is dropped. Not yet: predictions, the user model, underlines.
- Other languages, since the desktop has one keyboard for all of them (owner: English stays exactly as
  typed): **only on the Lithuanian layout** (menu: "On every keyboard layout"), and an **English guard**.
  A word only English (the system dictionary, `NSSpellChecker`, 0.08 ms a word; Windows has `ISpellChecker`)
  stops the fixing at once (`lean` > 0, up to `MAX_LEAN` 2); a word only Lithuanian (valid, or short of its
  diacritics only) moves it back by 1; a word that is both says nothing; another app resets it. A word
  that is both and got fixed (`is` -> `iš`, needed for Lithuanian typed without diacritics) is taken back
  if the next word is only English (`is this` stays). On English prose (README, AGENTS.md, 5,186 words)
  words changed 25.9% -> 0.1%; on 2,570 stripped subtitle lines 1.2% of the words differ from no guard,
  mostly foreign names kept.
- `mac.rs`: a `CGEventTap` on the main thread (Accessibility permission, asked for at start, a timer waits
  for it). A tap holds the keys behind it, and `CGEventTapPostEvent` puts backspaces and text ahead of them,
  so typing on can't overtake a fix. Only the differing end of a word is retyped (`diff`). Another app, a
  click: forget the text. Arrows, shortcuts, dead keys, backspacing past the start: the next word is left
  alone too (the cursor may be inside a word). A click doesn't do that (a click into an empty field is
  more common), so a word finished after clicking into the middle of one is treated as whole. Secure
  input (password fields) delivers no keys. Off by default in terminals and code editors (`APPS_OFF`).
  ⌃⌥V switches it off and on. Settings in `~/Library/Application Support/Varnele/settings`. No text is
  stored or logged.
- `--selftest FILE` types into a window of its own with posted keys, through the real tap. Run it with
  `open -n -a ~/Applications/Varnele.app --args --selftest FILE` (so it is the app that has the permission),
  then `open -a ~/Applications/Varnele.app`: macOS doesn't let it take the focus from the front app, and it
  waits for that. The window takes the keyboard for a few seconds; the engine carries over between its
  cases, unlike `--sim`'s lines. Each line of FILE holds the text and the edits the app typed. Run on
  2026-10-30 (the installed build still swaps `t` and `y` in its key table, fixed in the source: rebuilding
  means granting the permission again): all fixes, the backspace undo and a fix taken back by the next word
  as in `--sim`. Mid-word typos: `yhe` -> `The` is a one-key slip onto a name, not an English problem.
- **Ad-hoc signed** (no signing identity on the Mac): macOS ties the Accessibility grant to the build, so
  every rebuild needs `bundle.sh --reset` and a new grant. Sharing it needs a $99/year Developer ID and
  notarization.
- Windows: same `engine.rs`, a `WH_KEYBOARD_LL` hook, `SendInput`, `ISpellChecker`.
- **Underlines in Chrome: a spell server doesn't work** (tried 2026-10-30, macOS 26, code removed). An
  `NSSpellServer` service in `~/Library/Services` registers (`pbs -dump` lists it, its port is
  `lt_LT (Varnele)_OpenStep`), but `NSSpellChecker`, which Chrome goes through, never reaches it:
  `availableLanguages` holds only Apple's, `setLanguage` turns `lt_LT` and `lt_LT (Varnele)` into `lt`,
  answered by AppleSpell (`maciau` -> `maliau`), a code Apple lacks (`ltg`) is refused, and neither
  `NSPreferredSpellServerVendors` nor `NSPreferredSpellServerLanguage` changed that. Not tried: a Developer
  ID signature, a fresh login. macOS has its own Lithuanian (`lt`, knows `visiškai`, `žodžius`); Chrome's
  underlines come from the system's spelling language or its own `en-GB`. Next way in: a browser extension
  (the core as WebAssembly, its own underlines, the whole field to read and change).

## Browser extension

`extension/build.sh` builds `extension/varnele.wasm` (17.8 MB, git-ignored; `rustup target add
wasm32-unknown-unknown` once), then chrome://extensions → Developer mode → Load unpacked → `extension/`.
No store listing yet. Test: `eval/extension/test.mjs` (its header says how). Why an extension: macOS 26's
`NSSpellChecker` never reaches a third-party spell server, and Chrome only offers its own dictionaries.

- `background.js`: the service worker holds the checker for all tabs; Chrome stops it when idle (60 MB
  freed) and it loads again at the next check. Page to result, no debugger attached (Mac): first check
  146 ms, warm 3 ms, after 40 s idle 178 ms. With a debugger the first check takes ~1 s (Playwright).
- `content.js`: checks a field's paragraphs (cached by text) 250 ms after typing stops. Contenteditable:
  CSS Highlight API, ranges over a text rebuilt with a line per block; the page's DOM is not touched, shadow
  roots get the stylesheet adopted. Textarea and input: a transparent copy of the text in a closed
  shadow root over the page, only while the field has the focus (so no drift, nothing over dropdowns; an
  unfocused one shows no underlines). The word being typed isn't marked.
- A fix goes through `execCommand("insertText")` with the word selected, so undo works and the page's
  own code sees an ordinary edit: a controlled field and Lexical (Reddit's editor), also in a shadow root.
- **Language** (`Tally` in `fix.rs`, through the worker): a line counts as Lithuanian when 70%+ of its words are
  known or short only of diacritics (names don't count); 3+ words, or one with Lithuanian letters. A paragraph of
  5+ words decides itself, a shorter one goes with the field. Lithuanian: Chrome's spellcheck goes off for that field (`spellcheck=false`,
  its marks go too), Varnelė's on. Otherwise Chrome's stay. Subtitle lines kept 97.3–97.8% (stripped of
  diacritics too), English lines let through 1.1–2.3% (at 60%: 5.6–6.3%).
- Not covered: Google Docs (canvas); English words inside Lithuanian text are marked red. Autocorrect
  stays with the Mac app; the extension only marks and offers.

