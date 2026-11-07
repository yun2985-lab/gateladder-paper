const test = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const puppeteer = require('puppeteer-core');

const ROOT = path.join(__dirname, '..');
const CHROME = '/usr/bin/google-chrome';

function startServer() {
  const types = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8' };
  const server = http.createServer(function (req, res) {
    const url = new URL(req.url, 'http://127.0.0.1');
    const rel = decodeURIComponent(url.pathname);
    const file = path.normalize(path.join(ROOT, rel === '/' ? 'index.html' : rel));
    if (!file.startsWith(ROOT) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) {
      res.writeHead(404); res.end('missing'); return;
    }
    res.writeHead(200, { 'content-type': types[path.extname(file)] || 'text/plain', 'cache-control': 'no-store' });
    fs.createReadStream(file).pipe(res);
  });
  return new Promise(function (resolve) {
    server.listen(0, '127.0.0.1', function () { resolve(server); });
  });
}

async function browser() {
  return puppeteer.launch({
    executablePath: CHROME,
    headless: true,
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  });
}

async function open(b, server, search) {
  const page = await b.newPage();
  const urls = [];
  page.on('request', function (req) { urls.push(req.url()); });
  const errors = [];
  page.on('pageerror', function (err) { errors.push(String(err)); });
  await page.goto('http://127.0.0.1:' + server.address().port + '/' + search, { waitUntil: 'domcontentloaded', timeout: 120000 });
  return { page: page, urls: urls, errors: errors };
}

test('v1 and v2 still load their own branches and the new tab is separate', { timeout: 180000 }, async function (t) {
  const server = await startServer();
  const b = await browser();
  t.after(async function () { await b.close(); server.close(); });
  const v1 = await open(b, server, '?v=1');
  await v1.page.waitForFunction(function () { return document.getElementById('v1note') && document.getElementById('v1note').style.display !== 'none' && document.getElementById('hk').textContent.includes('자산'); }, { timeout: 120000 });
  assert.equal(await v1.page.$eval('#tb1', function (el) { return el.textContent; }), '버전1 · 11/2~');
  assert.equal(await v1.page.$eval('#tb2', function (el) { return el.textContent; }), '버전2 · 1년 백테스트');
  assert.equal(await v1.page.$eval('#tb154', function (el) { return el.textContent; }), '0.9.154');
  assert.equal(await v1.page.$eval('#tb1', function (el) { return el.className; }), 'on');
  assert.equal(await v1.page.$eval('#prog', function (el) { return el.style.display; }), 'none');
  assert.equal(await v1.page.$eval('#p154', function (el) { return el.style.display; }), 'none');
  assert.ok(v1.urls.some(function (u) { return u.includes('/data_latest/data.json'); }));
  assert.equal(v1.urls.some(function (u) { return u.includes('/data_0154/'); }), false);
  assert.deepEqual(v1.errors, []);

  const v2 = await open(b, server, '?v=2');
  await v2.page.waitForFunction(function () { return document.getElementById('prog').style.display !== 'none' && document.getElementById('prog').textContent.includes('버전2 · 1년 백테스트'); }, { timeout: 120000 });
  assert.equal(await v2.page.$eval('#v1note', function (el) { return el.style.display; }), 'none');
  assert.equal(await v2.page.$eval('#tb2', function (el) { return el.className; }), 'on');
  assert.ok(v2.urls.some(function (u) { return u.includes('/data_y1/data.json'); }));
  assert.equal(v2.urls.some(function (u) { return u.includes('/data_0154/'); }), false);
  const prog = await v2.page.$eval('#prog', function (el) { return el.textContent; });
  assert.ok(prog.includes('재생 진행 중') || prog.includes('실시간 진행 중'));
  assert.deepEqual(v2.errors, []);
});

test('0.9.154 tab reads the live manifest, keeps final files closed, and switches A-E', { timeout: 180000 }, async function (t) {
  const server = await startServer();
  const b = await browser();
  t.after(async function () { await b.close(); server.close(); });
  const view = await open(b, server, '?v=154&a=A');
  await view.page.setViewport({ width: 1280, height: 900 });
  await view.page.waitForFunction(function () { return document.querySelector('[data-region="status"]') && document.querySelector('[data-region="status"]').textContent.includes('매니페스트를 받았습니다'); }, { timeout: 120000 });
  assert.ok(view.urls.some(function (u) { return u.includes('/data_0154/data.json'); }));
  ['A', 'B', 'C', 'D', 'E'].forEach(function (id) {
    assert.ok(view.urls.some(function (u) { return u.includes('/data_0154/' + id + '/data.json'); }), id);
  });
  assert.equal(view.urls.some(function (u) { return u.includes('/data_latest/'); }), false);
  assert.equal(view.urls.some(function (u) { return u.includes('/data_y1/'); }), false);
  const status = await view.page.$eval('[data-region="status"]', function (el) { return el.textContent; });
  assert.equal(status.includes('아직 게시되지 않음'), false);
  const phase = await view.page.$eval('[data-variant="A"]', function (el) { return el.textContent; });
  assert.ok(phase.includes('재생 중') || phase.includes('실시간') || phase.includes('동결'));
  assert.match(phase, /진행 [0-9.]+%/);
  const downloads = await view.page.$eval('[data-region="downloads"]', function (el) { return el.innerHTML; });
  const manifest = await (await fetch('https://raw.githubusercontent.com/yun2985-lab/gateladder-paper/data_0154/data.json?t=' + Date.now())).json();
  const selected = manifest.variants.find(function (v) { return v.id === 'A'; });
  if (selected.availability.entries !== true) {
    assert.equal(downloads.includes(selected.entries_path), false);
    assert.match(downloads, /진입 CSV: 없음/);
  }
  if (selected.availability.monthly !== true) assert.match(downloads, /월별 CSV: 없음/);
  if (selected.availability.report !== true) assert.match(downloads, /보고서 JSON: 없음/);
  const frozenText = await view.page.$eval('[data-region="frozen"]', function (el) { return el.textContent; });
  if (selected.availability.report === true) assert.match(frozenText, /동결 보고서|보고서를 불러오지 못했습니다|보고서 파일/);
  else assert.match(frozenText, /동결 보고서가 아직 없습니다/);
  const sample = await (await fetch('https://raw.githubusercontent.com/yun2985-lab/gateladder-paper/data_0154/A/data.json?t=' + Date.now())).json();
  const lpc = await view.page.$eval('#lpc', function (el) { return el.textContent; });
  if (!Array.isArray(sample.candles) || !sample.candles.length) assert.match(lpc, /가격 봉이 이 페이로드에 없습니다/);
  const equity = await view.page.$eval('#hk', function (el) { return el.textContent; });
  assert.match(equity, /자산/);
  assert.equal(await view.page.$eval('#entriesNote', function (el) { return el.style.display; }), '');
  assert.match(await view.page.$eval('[data-region="config"]', function (el) { return el.textContent; }), /0\.9\.152/);
  assert.equal((await view.page.$eval('[data-region="config"]', function (el) { return el.textContent; })).includes('0.9.153이 아닙니다'), true);
  await view.page.click('button[data-sel="B"]');
  await view.page.waitForFunction(function () {
    const h = document.querySelector('[data-region="selected"] h3');
    const st = document.querySelector('[data-region="status"]');
    const cmp = document.querySelector('[data-region="compare"]');
    return h && h.textContent.indexOf('B') >= 0 && st && st.textContent.indexOf('매니페스트를 받았습니다') >= 0 && cmp && cmp.textContent.indexOf('환급') >= 0 && document.getElementById('hk').textContent.indexOf('자산') >= 0;
  }, { timeout: 120000 });
  assert.equal(await view.page.$eval('button[data-sel="B"]', function (el) { return el.className; }), 'on');
  const compare = await view.page.$eval('[data-region="compare"]', function (el) { return el.textContent; });
  assert.match(compare, /A \(앱 기본\)/);
  assert.match(compare, /E/);
  assert.deepEqual(view.errors, []);

  await view.page.setViewport({ width: 390, height: 844 });
  const box = await view.page.$eval('#tb154', function (el) { const r = el.getBoundingClientRect(); return { w: r.width, h: r.height, text: el.textContent }; });
  assert.equal(box.text, '0.9.154');
  assert.ok(box.w > 40 && box.h > 20);
});

test('missing data_0154 manifest stays not ready', { timeout: 90000 }, async function (t) {
  const server = await startServer();
  const b = await browser();
  t.after(async function () { await b.close(); server.close(); });
  const page = await b.newPage();
  const urls = [];
  await page.setRequestInterception(true);
  page.on('request', function (req) {
    urls.push(req.url());
    if (req.url().includes('/data_0154/data.json')) req.respond({ status: 404, contentType: 'text/plain', headers: { 'access-control-allow-origin': '*', 'content-type': 'text/plain' }, body: '404: Not Found' });
    else req.continue();
  });
  await page.goto('http://127.0.0.1:' + server.address().port + '/?v=154', { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForFunction(function () { return document.body.textContent.includes('아직 게시되지 않음'); }, { timeout: 30000 });
  assert.equal(await page.$eval('#live', function (el) { return el.style.display; }), 'none');
  assert.equal(await page.$eval('[data-region="downloads"]', function (el) { return el.querySelectorAll('a').length; }), 0);
  assert.equal(urls.some(function (u) { return u.includes('/data_0154/A/data.json'); }), false);
  assert.equal(urls.some(function (u) { return u.includes('/data_latest/'); }), false);
});
