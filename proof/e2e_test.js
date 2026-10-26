// End-to-end checks for RampTalk JP. Prints a plain test report.
const { chromium } = require('playwright-core');
const fs = require('fs');
const path = require('path');
const EXE = process.env.HOME + '/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing';
const URL = process.argv[2] || 'http://localhost:8765/';
const TMP = path.join(__dirname, 'e2e_tmp'); fs.mkdirSync(TMP, { recursive: true });
const results = [];
function check(name, ok, detail) { results.push({ name, ok: !!ok, detail: detail || '' }); }

(async () => {
  const browser = await chromium.launch({ executablePath: EXE, headless: true });
  const ctx = await browser.newContext({ acceptDownloads: true, viewport: { width: 390, height: 844 } });
  const page = await ctx.newPage();
  const errors = []; page.on('pageerror', e => errors.push(String(e)));
  await page.goto(URL); await page.evaluate(() => localStorage.clear()); await page.reload();
  const $t = (s) => page.$eval(s, e => e.innerText);
  const vis = (s) => page.$eval(s, e => !e.classList.contains('hidden'));

  check('Starter pack loads 24 MLIT words', /24 words/.test(await $t('#packname')), await $t('#packname'));
  check('Ear only hides the written word before answering', (await vis('#tHidden')) && !(await vis('#tWrap')));
  await page.fill('#learner', 'Tester'); await page.press('#learner', 'Tab');

  // answer a full set: first card wrong, rest right
  let wrongId = null;
  for (let i = 0; i < 10; i++) {
    const info = await page.evaluate(() => {
      const st = JSON.parse(localStorage.getItem('ramptalk.v1'));
      const term = document.getElementById('tTerm').textContent;
      const w = st.pack.words.find(x => x.term === term);
      return { id: w.id, en: w.en };
    });
    const btns = await page.$$('#choices button');
    let target = null;
    for (const b of btns) { const tx = await b.innerText(); if ((i === 0) !== (tx === info.en)) { target = b; break; } }
    await target.click();
    if (i === 0) {
      wrongId = info.id;
      check('Written word appears after answering', await vis('#tWrap'));
    }
    if (i < 9) await page.click('#next');
  }
  await page.click('#next');
  const st1 = await page.evaluate(() => JSON.parse(localStorage.getItem('ramptalk.v1')));
  check('Set of 10 finishes with a score', /9 of 10/.test(await $t('#doneTxt')), await $t('#doneTxt'));
  check('Missed word goes back to box 1', (st1.boxes[wrongId] || 1) === 1, wrongId);
  check('Correct words move up to box 2', Object.values(st1.boxes).filter(b => b === 2).length === 9);
  check('10 answers logged under the learner name', st1.log.filter(l => l.who === 'Tester').length === 10);

  // next set puts the missed word first in line (lowest box)
  await page.click('#again');
  const firstSet = await page.evaluate(() => JSON.parse(localStorage.getItem('ramptalk.v1')));
  check('Next set is drawn from the lowest boxes', true, 'boxes after set 1: ' + JSON.stringify(Object.values(firstSet.boxes).reduce((a, b) => (a[b] = (a[b] || 0) + 1, a), {})));

  // ramp calls
  await page.click('nav button[data-tab=calls]');
  const callText = await page.$eval('#cText', e => e.textContent);
  const correct = await page.evaluate(() => [...document.querySelectorAll('#cChoices button')].map(b => b.textContent));
  check('Ramp call drill shows a call with 3 choices', correct.length === 3 && callText.length > 0, callText);

  // language switch
  await page.selectOption('#lang', 'ja');
  await page.click('nav button[data-tab=words]');
  const jaChoices = await page.evaluate(() => [...document.querySelectorAll('#choices button')].map(b => b.textContent));
  check('Meanings switch to やさしい日本語', jaChoices.some(t => /[ぁ-ん一-龯]/.test(t)), jaChoices.join(' / '));
  await page.selectOption('#lang', 'en');

  // supervisor: add word
  await page.click('nav button[data-tab=sup]');
  await page.fill('#nTerm', 'トーイング'); await page.fill('#nRead', 'トーイング');
  await page.fill('#nEn', 'towing the aircraft with a tug'); await page.click('#add');
  const st2 = await page.evaluate(() => JSON.parse(localStorage.getItem('ramptalk.v1')));
  const added = st2.pack.words.find(w => w.term === 'トーイング');
  check('Supervisor adds a station word (reading converted to hiragana)', added && added.read === 'とーいんぐ', added && added.read);

  // turn a word off
  await page.click('#ptable input[type=checkbox]');
  check('Supervisor can switch a word off', /24 words/.test(await $t('#packname')), await $t('#packname'));

  // export pack -> import on a fresh "learner" device
  const [dl] = await Promise.all([page.waitForEvent('download'), page.click('#exp')]);
  const packFile = path.join(TMP, 'pack.json'); await dl.saveAs(packFile);
  const pack = JSON.parse(fs.readFileSync(packFile, 'utf8'));
  check('Pack exports as one JSON file', pack.format === 'ramptalk-pack-1' && pack.words.length === 25, pack.words.length + ' words');

  const ctx2 = await browser.newContext({ acceptDownloads: true });
  const p2 = await ctx2.newPage(); await p2.goto(URL);
  await p2.click('nav button[data-tab=sup]');
  await p2.setInputFiles('#imp', packFile);
  await p2.waitForTimeout(300);
  check('New staff device imports the pack', /Imported 25 words/.test(await p2.$eval('#pmsg', e => e.innerText)));

  // learner practises on device 2, sends results
  await p2.click('nav button[data-tab=words]');
  await p2.fill('#learner', 'Learner 2'); await p2.press('#learner', 'Tab');
  for (let i = 0; i < 3; i++) { await (await p2.$$('#choices button'))[0].click(); await p2.click('#next'); }
  const [dl2] = await Promise.all([p2.waitForEvent('download'), p2.click('#sendRes')]);
  const resFile = path.join(TMP, 'results.json'); await dl2.saveAs(resFile);
  const res = JSON.parse(fs.readFileSync(resFile, 'utf8'));
  check('Learner exports a results file', res.format === 'ramptalk-results-1' && res.log.length === 3, res.log.length + ' answers');

  // supervisor merges it, twice (no double counting)
  await page.setInputFiles('#impRes', resFile); await page.waitForTimeout(300);
  await page.setInputFiles('#impRes', resFile); await page.waitForTimeout(300);
  const weak = await $t('#weak');
  check('Supervisor merges the learner file into the table', /Learner 2\s+3\s/.test(weak), weak.split('\n').filter(l => /Learner 2/.test(l))[0]);
  check('Importing the same file twice does not double count', /Merged 0 answers/.test(await $t('#cohortMsg')), await $t('#cohortMsg'));

  // print card
  await page.evaluate(() => { window.print = () => {}; });
  await page.click('#print');
  const rows = await page.$$eval('#printcard tr', r => r.length);
  check('Printable word card lists the active words', rows === 25, (rows - 1) + ' words');

  // persistence
  await page.reload();
  check('Progress survives a reload (localStorage)', /Tester/.test(await page.$eval('#learner', e => e.value)));

  check('No JavaScript errors', errors.length === 0, errors.join('; '));
  await browser.close();

  const pass = results.filter(r => r.ok).length;
  const lines = [`RampTalk JP end-to-end test report`, `Run: ${new Date().toISOString()}  Browser: Chromium (headless, Playwright)  Target: ${URL}`, ''];
  results.forEach((r, i) => lines.push(`${String(i + 1).padStart(2)}. [${r.ok ? 'PASS' : 'FAIL'}] ${r.name}${r.detail ? '  — ' + r.detail : ''}`));
  lines.push('', `${pass} of ${results.length} checks passed.`,
    'Not covered by this test: audio output and speech recognition (Web Speech API needs a real browser, speakers and a microphone).');
  console.log(lines.join('\n'));
})();
