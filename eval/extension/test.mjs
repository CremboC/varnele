// The extension in a real Chromium, on page.html: underlines, the card, undo, language, the switch.
// Clicks go by position (the card is in a closed shadow root). Needs extension/build.sh, then here:
//   npm i && npx esbuild lexical-fields.js --bundle --format=iife --outfile=lexical-fields.bundle.js && node test.mjs
// Chrome's branded builds ignore --load-extension: this runs Playwright's Chromium (`npx playwright install chromium`, or $CHROMIUM).
// Timing means nothing here: with the debugger attached the first check takes 1 s, without it 0.15 s.
import { chromium } from 'playwright';
import { mkdtempSync, readFileSync } from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';

const here = path.dirname(new URL(import.meta.url).pathname);
const ext = path.resolve(here, '../../extension');
const server = http.createServer((q, r) => {
  const js = q.url.endsWith('.js');
  r.setHeader('content-type', js ? 'text/javascript' : 'text/html');
  r.end(readFileSync(path.join(here, js ? 'lexical-fields.bundle.js' : 'page.html')));
}).listen(8766);
const ctx = await chromium.launchPersistentContext(mkdtempSync(path.join(os.tmpdir(), 'varnele-')), {
  headless: false, executablePath: process.env.CHROMIUM, args: [`--disable-extensions-except=${ext}`, `--load-extension=${ext}`], viewport: { width: 900, height: 800 } });
const page = ctx.pages()[0] ?? await ctx.newPage();
const errors = [];
page.on('pageerror', (e) => errors.push(String(e)));
await page.goto('http://localhost:8766/');
await page.waitForTimeout(500);
const sw = ctx.serviceWorkers()[0] ?? await ctx.waitForEvent('serviceworker');
let failed = 0;
const ok = (name, got, want) => {
  if (got !== want) failed++;
  console.log(got === want ? 'ok  ' : 'FAIL', name, got === want ? '' : JSON.stringify({ got, want }));
};
const val = s => page.$eval(s, e => e.value);
const html = s => page.$eval(s, e => e.textContent.replaceAll('\u00a0', ' '));
// a suggestion in the card: the card is at a known place under the word, row 0 or after the message
async function pick(word, row, hasMessage) {
  await page.mouse.click(word.x, word.y);
  await page.waitForTimeout(120);
  await page.mouse.click(word.x + 20, word.y + 12 + (hasMessage ? 50 : 14) + row * 28);
  await page.waitForTimeout(450);
}
const b = await (await page.$('#ta')).boundingBox();
await page.click('#ta'); await page.keyboard.type('Grįžau pries pora dienų, sakė kad ateis ', { delay: 3 });
await page.waitForFunction(() => document.querySelector('#ta').spellcheck === false, null, { timeout: 8000 });
await page.waitForTimeout(400);
await pick({ x: b.x + 75, y: b.y + 21 }, 0, false);
ok('card replaces a word', await val('#ta'), 'Grįžau prieš pora dienų, sakė kad ateis ');
await pick({ x: b.x + 115, y: b.y + 21 }, 0, true);
ok('grammar fix', await val('#ta'), 'Grįžau prieš porą dienų, sakė kad ateis ');
await pick({ x: b.x + 232, y: b.y + 21 }, 0, true);
ok('comma before the space', await val('#ta'), 'Grįžau prieš porą dienų, sakė, kad ateis ');
await page.keyboard.press('Meta+z'); await page.waitForTimeout(300);
ok('undo', await val('#ta'), 'Grįžau prieš porą dienų, sakė kad ateis ');
await page.keyboard.press('Meta+Shift+z'); await page.waitForTimeout(300);
await page.click('#ctl'); await page.keyboard.type('Vakar pries pora dienų ', { delay: 3 }); await page.waitForTimeout(500);
const c = await (await page.$('#ctl')).boundingBox();
await pick({ x: c.x + 60, y: c.y + 12 }, 0, false);
ok('controlled field', [await val('#ctl'), await page.evaluate(() => window.state)].join('|'), 'Vakar prieš pora dienų |Vakar prieš pora dienų ');
await page.click('#ce'); await page.keyboard.type('Vakar pries pora dienų ', { delay: 3 }); await page.waitForTimeout(500);
const d = await (await page.$('#ce')).boundingBox();
await pick({ x: d.x + 65, y: d.y + 20 }, 0, false);
ok('contenteditable', await html('#ce'), 'Vakar prieš pora dienų ');
await page.keyboard.press('Meta+z'); await page.waitForTimeout(300);
ok('contenteditable undo', await html('#ce'), 'Vakar pries pora dienų ');
await page.keyboard.press('Meta+a'); await page.keyboard.press('Backspace');
await page.keyboard.type('Pirma eilutė\nAntra pries eilutė', { delay: 3 }); await page.waitForTimeout(500);
await page.click('#sce'); await page.keyboard.type('Vakar pries pora dienų ', { delay: 3 }); await page.waitForTimeout(500);
const e = await (await page.$('#host')).boundingBox();
await pick({ x: e.x + 65, y: e.y + 20 }, 0, false);
ok('shadow root', await page.evaluate(() => host.shadowRoot.getElementById('sce').textContent.replaceAll('\u00a0', ' ')), 'Vakar prieš pora dienų ');
await page.evaluate(() => lexhost.shadowRoot.getElementById('lex').focus()); await page.keyboard.type('Vakar pries pora dienų ', { delay: 8 }); await page.waitForTimeout(600);
const lx = await (await page.$('#lexhost')).boundingBox();
await page.mouse.click(lx.x + 75, lx.y + 34); await page.waitForTimeout(150);
await page.mouse.click(lx.x + 85, lx.y + 62); await page.waitForTimeout(500);
ok('lexical in a shadow root', await page.evaluate(() => lexical()), 'Vakar prieš pora dienų ');
await page.click('#lex2'); await page.keyboard.type('Vakar pries pora dienų ', { delay: 8 }); await page.waitForTimeout(600);
const ly = await (await page.$('#lexlight')).boundingBox();
await page.mouse.click(ly.x + 75, ly.y + 34); await page.waitForTimeout(150);
await page.mouse.click(ly.x + 85, ly.y + 62); await page.waitForTimeout(500);
ok('lexical', await page.evaluate(() => lexical2()), 'Vakar prieš pora dienų ');
await page.click('#inp'); await page.keyboard.type('Grįžau pries pora dienų ', { delay: 3 }); await page.waitForTimeout(500);
const f = await (await page.$('#inp')).boundingBox();
await pick({ x: f.x + 75, y: f.y + 22 }, 0, false);
ok('input', await val('#inp'), 'Grįžau prieš pora dienų ');
await page.click('#en'); await page.keyboard.type('The quick brown fox is in the house ', { delay: 3 }); await page.waitForTimeout(500);
ok('english keeps chrome spelling', await page.$eval('#en', e => e.spellcheck), true);
await page.keyboard.press('Meta+a'); await page.keyboard.type('Labas, kaip tau sekasi šiandien ', { delay: 3 }); await page.waitForTimeout(500);
ok('then lithuanian', await page.$eval('#en', e => e.spellcheck), false);
await page.keyboard.press('Meta+a'); await page.keyboard.type('Thanks a lot for the great help ', { delay: 3 }); await page.waitForTimeout(500);
ok('then english again', await page.$eval('#en', e => e.spellcheck), true);
await page.keyboard.press('Meta+a'); await page.keyboard.press('Backspace');
await sw.evaluate(() => chrome.storage.local.set({ enabled: false })); await page.waitForTimeout(400);
ok('off: chrome spelling back', await page.$eval('#ta', e => e.spellcheck), true);
await sw.evaluate(() => chrome.storage.local.set({ enabled: true })); await page.waitForTimeout(400);
ok('on again', await page.$eval('#ta', e => e.spellcheck), false);
await ctx.close();
server.close();
console.log(failed ? `${failed} failed` : 'all passed', errors);
process.exit(failed ? 1 : 0);
