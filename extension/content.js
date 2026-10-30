// Varnelė in a page: finds the text field being used, checks its paragraphs, draws underlines and
// a card of suggestions. A contenteditable gets the CSS Highlight API, which leaves the page's DOM
// alone. A textarea or input has no ranges to highlight: a transparent copy of its text sits over it
// and carries the underlines, only while it has the focus.

const DEBOUNCE_MS = 250;
const MAX_CACHE = 2000;
/** a paragraph this long decides its language itself; a shorter one goes with the field */
const OWN_LANGUAGE_WORDS = 5;
const BLOCKS = new Set(["ADDRESS", "ARTICLE", "ASIDE", "BLOCKQUOTE", "DD", "DIV", "DL", "DT", "FIELDSET", "FIGURE",
  "FOOTER", "FORM", "H1", "H2", "H3", "H4", "H5", "H6", "HEADER", "HR", "LI", "MAIN", "NAV", "OL", "P", "PRE",
  "SECTION", "TABLE", "TD", "TH", "TR", "UL"]);
const TEXT_INPUTS = new Set(["text", "search"]);
const COPIED_STYLES = ["fontFamily", "fontSize", "fontWeight", "fontStyle", "fontVariant", "fontStretch", "fontKerning",
  "letterSpacing", "wordSpacing", "textIndent", "textTransform", "textAlign", "direction", "tabSize",
  "lineHeight", "paddingTop", "paddingRight", "paddingBottom", "paddingLeft", "wordBreak", "overflowWrap"];

let settings = { enabled: true, formal: false, offSites: [], ignored: [] };
const site = location.hostname;
const cache = new Map();
const fields = new Map(); // element -> Field, of this document
let active = null;
let card = null;

const fold = (word) => word.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase();
const on = () => settings.enabled && !settings.offSites.includes(site);

/** The text field `node` is in, if it is one to check. */
function editableOf(node) {
  if (!(node instanceof Element)) return null;
  if (node.localName === "textarea") return node.readOnly || node.disabled ? null : node;
  if (node.localName === "input") {
    return TEXT_INPUTS.has(node.type) && !node.readOnly && !node.disabled ? node : null;
  }
  if (!node.isContentEditable) return null;
  let root = node;
  for (let up = root.parentElement; up?.isContentEditable; up = up.parentElement) root = up;
  return root;
}

// ---------- Fields

class Field {
  constructor(el) {
    this.el = el;
    this.spellcheck = el.getAttribute("spellcheck");
    this.findings = [];
    this.hidden = [];
    this.typing = false;
    this.timer = 0;
    this.run = 0;
  }

  schedule(delay = DEBOUNCE_MS) {
    clearTimeout(this.timer);
    this.timer = setTimeout(() => this.check(), delay);
  }

  async check() {
    if (!this.el.isConnected) return this.drop();
    if (!on()) return this.clear();
    const run = ++this.run;
    const text = this.text();
    const paragraphs = [];
    for (let start = 0, i = 0; i <= text.length; i++) {
      if (i === text.length || text[i] === "\n") {
        if (i > start) paragraphs.push({ start, text: text.slice(start, i) });
        start = i + 1;
      }
    }
    const missing = [...new Set(paragraphs.map((p) => p.text))].filter((t) => !cache.has(key(t)));
    if (missing.length) {
      let results;
      try {
        results = await chrome.runtime.sendMessage({ type: "check", texts: missing, formal: settings.formal });
      } catch {
        return; // the extension was reloaded: this page's script is an orphan
      }
      if (cache.size > MAX_CACHE) cache.clear();
      missing.forEach((t, i) => cache.set(key(t), results[i]));
    }
    const sum = [0, 0, 0];
    for (const p of paragraphs) {
      p.found = cache.get(key(p.text));
      sum[0] += p.found.tally[0];
      sum[1] += p.found.tally[1];
      sum[2] ||= p.found.tally[2];
    }
    let languages;
    try {
      languages = await chrome.runtime.sendMessage({ type: "language", tallies: [sum, ...paragraphs.map((p) => p.found.tally)] });
    } catch {
      return;
    }
    if (run !== this.run || this.text() !== text) return;
    const language = languages[0];
    this.useChromeSpelling(language !== 1);
    const found = [];
    paragraphs.forEach((p, i) => {
      const own = p.found.tally[0] >= OWN_LANGUAGE_WORDS ? languages[i + 1] : language;
      if (own !== 1) return;
      for (const f of p.found.findings) {
        if (f.rule === "unknown" && settings.ignored.includes(fold(f.word))) continue;
        found.push(shifted(f, p));
      }
    });
    this.findings = found;
    this.show();
  }

  /** The findings to draw: not the word still being typed. */
  visible() {
    const caret = this.typing ? this.caret() : -1;
    const typed = (f) => caret >= f.start && caret <= f.end;
    this.hidden = this.findings.filter(typed);
    return this.findings.filter((f) => !typed(f));
  }

  useChromeSpelling(yes) {
    if (yes) {
      if (this.spellcheck === null) this.el.removeAttribute("spellcheck");
      else this.el.setAttribute("spellcheck", this.spellcheck);
    } else {
      this.el.setAttribute("spellcheck", "false");
    }
  }

  clear() {
    this.findings = [];
    this.useChromeSpelling(true);
    this.show();
  }

  drop() {
    clearTimeout(this.timer);
    this.findings = [];
    this.show();
    fields.delete(this.el);
  }

  /** Put the text of [start, end) right, as if typed: the page's own code sees an ordinary edit. */
  replace(start, end, word) {
    this.select(start, end);
    if (!document.execCommand("insertText", false, word)) return;
    this.typing = false;
    this.schedule(0);
  }
}

const key = (text) => `${settings.formal ? 1 : 0}${text}`;

/** A finding at its place in the field. A comma goes in before the space: `sakė kad` -> `sakė, kad`. */
function shifted(f, p) {
  const start = p.start + f.start;
  const before = f.suggestions[0]?.startsWith(",") && p.text[f.start - 1] === " " ? 1 : 0;
  return { ...f, start, end: p.start + f.end, replaceStart: start - before };
}

/** A contenteditable. Its text is rebuilt with a line for each block, and each DOM text node's place. */
class RichField extends Field {
  constructor(el) {
    super(el);
    this.nodes = [];
    this.ranges = [];
    const root = el.getRootNode();
    if (root instanceof ShadowRoot) addStyles(root);
  }

  text() {
    const nodes = [];
    let text = "";
    const newLine = () => {
      if (text && !text.endsWith("\n")) text += "\n";
    };
    const visit = (parent) => {
      for (let n = parent.firstChild; n; n = n.nextSibling) {
        if (n.nodeType === Node.TEXT_NODE) {
          nodes.push({ node: n, start: text.length });
          text += n.data.replaceAll(" ", " ");
        } else if (n.nodeType === Node.ELEMENT_NODE) {
          if (n.localName === "br") text += "\n";
          else if (n.getAttribute("contenteditable") === "false") text += "￼";
          else {
            const block = BLOCKS.has(n.tagName);
            if (block) newLine();
            visit(n);
            if (block) newLine();
          }
        }
      }
    };
    visit(this.el);
    this.nodes = nodes;
    return text;
  }

  /** The DOM place of a text offset. */
  point(offset, end) {
    let i = this.nodes.length - 1;
    while (i > 0 && (end ? this.nodes[i].start >= offset : this.nodes[i].start > offset)) i--;
    const n = this.nodes[i];
    return n ? [n.node, Math.min(offset - n.start, n.node.length)] : null;
  }

  range(start, end) {
    const from = this.point(start, false);
    const to = this.point(end, true);
    if (!from || !to) return null;
    const r = new Range();
    r.setStart(...from);
    r.setEnd(...to);
    return r;
  }

  show() {
    this.ranges = this.visible().map((f) => ({ finding: f, range: this.range(f.start, f.end) })).filter((x) => x.range);
    paintHighlights();
  }

  selection() {
    const root = this.el.getRootNode();
    return root.getSelection?.() ?? document.getSelection();
  }

  caret() {
    const s = this.selection();
    if (!s?.focusNode || !this.el.contains(s.focusNode)) return -1;
    this.text();
    const n = this.nodes.find((x) => x.node === s.focusNode);
    return n ? n.start + s.focusOffset : -1;
  }

  at(x, y) {
    for (const { finding, range } of this.ranges) {
      for (const r of range.getClientRects()) {
        if (x >= r.left && x <= r.right && y >= r.top - 2 && y <= r.bottom + 3) return { finding, rect: r };
      }
    }
    return null;
  }

  select(start, end) {
    this.text();
    const r = this.range(start, end);
    const s = this.selection();
    s.removeAllRanges();
    s.addRange(r);
  }
}

function paintHighlights() {
  const spelling = new Highlight();
  const grammar = new Highlight();
  for (const f of fields.values()) {
    for (const { finding, range } of f.ranges ?? []) (finding.rule === "unknown" ? spelling : grammar).add(range);
  }
  CSS.highlights.set("varnele-spelling", spelling);
  CSS.highlights.set("varnele-grammar", grammar);
}

const shadowStyles = new CSSStyleSheet();
shadowStyles.replaceSync(`
  ::highlight(varnele-spelling) { text-decoration: underline wavy #d92d20; text-decoration-skip-ink: none; }
  ::highlight(varnele-grammar) { text-decoration: underline wavy #2563eb; text-decoration-skip-ink: none; }`);

function addStyles(root) {
  if (!root.adoptedStyleSheets.includes(shadowStyles)) root.adoptedStyleSheets = [...root.adoptedStyleSheets, shadowStyles];
}

/** A textarea or input, and the copy of its text over it. */
class PlainField extends Field {
  text() {
    return this.el.value;
  }

  caret() {
    return document.activeElement === this.el || this.el.getRootNode().activeElement === this.el ? this.el.selectionStart : -1;
  }

  show() {
    if (active === this) drawMirror(this);
  }

  at(x, y) {
    for (const span of mirror.text.querySelectorAll("[data-i]")) {
      for (const r of span.getClientRects()) {
        if (x >= r.left && x <= r.right && y >= r.top - 2 && y <= r.bottom + 3) {
          return { finding: this.shown[span.dataset.i], rect: r };
        }
      }
    }
    return null;
  }

  select(start, end) {
    this.el.focus();
    this.el.setSelectionRange(start, end);
  }
}

// ---------- The copy of a text field's text, and the card, in one shadow root over the page

const overlay = document.createElement("varnele-overlay");
const shadow = overlay.attachShadow({ mode: "closed" });
shadow.innerHTML = `<style>
  :host { all: initial; }
  #mirror { position: fixed; display: none; overflow: hidden; pointer-events: none; z-index: 2147483646;
    box-sizing: border-box; color: transparent; }
  #mirror span { text-decoration: underline wavy #d92d20; text-decoration-skip-ink: none; }
  #mirror span.grammar { text-decoration-color: #2563eb; }
  #card { position: fixed; display: none; z-index: 2147483647; max-width: 320px; min-width: 160px; padding: 6px;
    border-radius: 10px; background: #fff; color: #1c1c1e; border: 1px solid #0002;
    box-shadow: 0 6px 24px #0003; font: 13px/1.35 system-ui, sans-serif; }
  #card .message { padding: 4px 8px 6px; color: #666; }
  #card button { all: unset; display: block; box-sizing: border-box; width: 100%; padding: 5px 8px; border-radius: 6px;
    cursor: pointer; }
  #card button:hover, #card button:focus-visible { background: #0000000f; }
  #card button.word { font-weight: 600; }
  #card button.ignore { color: #666; }
  #card hr { border: 0; border-top: 1px solid #0001; margin: 4px 0; }
  @media (prefers-color-scheme: dark) {
    #card { background: #2c2c2e; color: #f2f2f7; border-color: #fff2; }
    #card .message, #card button.ignore { color: #aaa; }
    #card button:hover, #card button:focus-visible { background: #ffffff1a; }
    #card hr { border-top-color: #fff2; }
  }
</style><div id="mirror"><div id="text"></div></div><div id="card" role="menu"></div>`;
const mirror = { box: shadow.getElementById("mirror"), text: shadow.getElementById("text") };
const cardEl = shadow.getElementById("card");
cardEl.addEventListener("mousedown", (e) => e.preventDefault()); // the field keeps the focus

function drawMirror(f) {
  const text = f.text();
  mirror.text.textContent = "";
  f.shown = f.visible();
  let at = 0;
  f.shown.forEach((finding, i) => {
    mirror.text.append(text.slice(at, finding.start));
    const span = document.createElement("span");
    span.textContent = text.slice(finding.start, finding.end);
    span.dataset.i = i;
    if (finding.rule !== "unknown") span.className = "grammar";
    mirror.text.append(span);
    at = finding.end;
  });
  mirror.text.append(`${text.slice(at)}​`); // a last empty line has a height
  placeMirror(f);
}

function placeMirror(f) {
  const { el } = f;
  const r = el.getBoundingClientRect();
  const style = getComputedStyle(el);
  const box = mirror.box.style;
  if (!f.shown?.length || r.width === 0) {
    box.display = "none";
    return;
  }
  box.display = "block";
  box.left = `${r.left + el.clientLeft}px`;
  box.top = `${r.top + el.clientTop}px`;
  box.width = `${el.clientWidth}px`;
  box.height = `${el.clientHeight}px`;
  for (const name of COPIED_STYLES) box[name] = style[name];
  const single = el.localName === "input";
  box.whiteSpace = single ? "pre" : "pre-wrap";
  if (single) {
    // an input centres its line
    const inner = el.clientHeight - parseFloat(style.paddingTop) - parseFloat(style.paddingBottom);
    box.lineHeight = `${inner}px`;
  }
  mirror.box.scrollTop = el.scrollTop;
  mirror.box.scrollLeft = el.scrollLeft;
}

function followField() {
  if (active instanceof PlainField && document.hasFocus()) {
    placeMirror(active);
    requestAnimationFrame(followField);
  }
}

function closeCard() {
  card = null;
  cardEl.style.display = "none";
}

function openCard(f, finding, rect) {
  card = finding;
  cardEl.textContent = "";
  if (finding.message) {
    const m = document.createElement("div");
    m.className = "message";
    m.textContent = finding.message;
    cardEl.append(m);
  }
  for (const word of finding.suggestions) {
    const b = document.createElement("button");
    b.className = "word";
    b.textContent = word.replace(/^, /, ", ");
    b.addEventListener("click", () => {
      closeCard();
      f.replace(finding.replaceStart, finding.end, word);
    });
    cardEl.append(b);
  }
  if (finding.rule === "unknown") {
    if (finding.suggestions.length) cardEl.append(document.createElement("hr"));
    const b = document.createElement("button");
    b.className = "ignore";
    b.textContent = "Don't mark this word";
    b.addEventListener("click", () => {
      closeCard();
      chrome.storage.local.set({ ignored: [...settings.ignored, fold(finding.word)] });
    });
    cardEl.append(b);
  }
  cardEl.style.display = "block";
  const box = cardEl.getBoundingClientRect();
  const below = rect.bottom + 4 + box.height <= innerHeight;
  cardEl.style.left = `${Math.max(4, Math.min(rect.left, innerWidth - box.width - 4))}px`;
  cardEl.style.top = `${below ? rect.bottom + 4 : Math.max(4, rect.top - box.height - 4)}px`;
}

// ---------- Events

function fieldFor(el) {
  let f = fields.get(el);
  if (!f) {
    f = el.localName === "textarea" || el.localName === "input" ? new PlainField(el) : new RichField(el);
    fields.set(el, f);
  }
  return f;
}

function focusField(el) {
  const f = fieldFor(el);
  if (!overlay.isConnected) document.documentElement.append(overlay);
  if (active !== f) {
    active = f;
    f.typing = false;
    f.schedule(0);
    if (f instanceof PlainField) followField();
  }
  return f;
}

document.addEventListener("focusin", (e) => {
  const el = editableOf(e.composedPath()[0]);
  if (el) focusField(el);
}, true);

document.addEventListener("focusout", () => {
  closeCard();
  const f = active;
  active = null;
  mirror.box.style.display = "none";
  if (f) {
    f.typing = false;
    f.schedule(0);
  }
}, true);

document.addEventListener("input", (e) => {
  const el = editableOf(e.composedPath()[0]);
  if (!el) return;
  closeCard();
  const f = focusField(el);
  f.typing = true;
  f.schedule();
}, true);

document.addEventListener("selectionchange", () => {
  // the caret left the word that was hidden while typed
  if (!active?.hidden.length) return;
  const caret = active.caret();
  if (active.hidden.some((f) => caret < f.start || caret > f.end)) active.show();
});

document.addEventListener("click", (e) => {
  if (e.composedPath().includes(overlay)) return;
  closeCard();
  const el = editableOf(e.composedPath()[0]);
  if (!el) return;
  const f = focusField(el);
  if (f.typing) {
    f.typing = false;
    f.show();
  }
  const hit = f.at(e.clientX, e.clientY);
  if (hit) openCard(f, hit.finding, hit.rect);
}, true);

document.addEventListener("keydown", (e) => {
  if (card && e.key === "Escape") closeCard();
}, true);
addEventListener("scroll", closeCard, true);

chrome.storage.local.get(settings).then((stored) => {
  settings = stored;
  const el = editableOf(document.activeElement);
  if (el) focusField(el);
});

chrome.storage.onChanged.addListener((changes) => {
  for (const [name, { newValue }] of Object.entries(changes)) settings[name] = newValue;
  for (const f of fields.values()) f.schedule(0);
});
