import assert from 'node:assert/strict';
import { stat } from 'node:fs/promises';
import { once } from 'node:events';
import { chromium } from 'playwright';
import { checkDeviceFallbacks, checkInterruptions } from './device-checks.mjs';
import { corpus, negatives, queries } from './fixtures.mjs';
import { listen } from './server.mjs';
import { host, image, runBaseline } from './vps-baseline.mjs';

const median = values => {
  const sorted = [...values].sort((a, b) => a - b);
  return (sorted[Math.floor((sorted.length - 1) / 2)] + sorted[Math.floor(sorted.length / 2)]) / 2;
};
const round = value => Number(value.toFixed(2));
const asInputs = fixtures => fixtures.map(({ id, bytes }) => ({ id, pdf: bytes.toString('base64') }));

const { server, url } = await listen();
let browser;
try {
  browser = await chromium.launch({ channel: process.env.PILOT_BROWSER || 'chrome' });
  const desktop = await browser.newContext();
  const requests = [];
  desktop.on('request', request => requests.push([request.method(), request.url()]));
  const page = await desktop.newPage();
  const pageErrors = [];
  page.on('pageerror', error => pageErrors.push(error.message));
  page.on('console', entry => { if (entry.type() === 'error') console.error(entry.text()); });
  await page.goto(url);
  const coldRoute = await page.evaluate(async () => {
    const { assistSavedJob } = await import('/failover.mjs');
    return (await assistSavedJob({ state: 'busy', saved: true, canAssist: true, jobId: 'fixture-lease',
      expiresAt: Date.now() + 5000, canonicalText: 'This is canonical text from a fictional saved CV.' }, { optedIn: true })).state;
  });
  assert.equal(coldRoute, 'vps');
  assert(!requests.some(([, request]) => new URL(request).pathname.startsWith('/assets/')), 'Cold assist downloaded the model');

  const files = await page.evaluate(async cases => {
    const { processFile } = await import('/pilot.mjs');
    const data = [];
    for (const { id, pdf } of cases) {
      const file = new File([Uint8Array.from(atob(pdf), c => c.charCodeAt(0))], `${id}.pdf`);
      const result = await processFile(file);
      if (!result.vector) throw new Error(`Unexpected fallback for ${id}: ${result.fallback}`);
      data.push({ id, pdf, ...result, vector: Array.from(result.vector) });
    }
    return data;
  }, asInputs(corpus));
  files.forEach(file => {
    assert.equal(file.vector.length, 384);
    assert(Math.abs(Math.hypot(...file.vector) - 1) < 1e-6);
  });

  const probes = await page.evaluate(async input => {
    const { embed } = await import('/pilot.mjs');
    const data = [];
    for (const text of input) data.push({ text, vector: Array.from((await embed(text)).vector) });
    return data;
  }, [...files.map(file => file.text),
    '  Lead développeur à Dubaï — العربية हिन्दी, C++, Node.js and SQL Server.  ',
    'Senior analyst. '.repeat(160) + 'End-of-document token beyond model limit']);

  const assist = await page.evaluate(async canonicalText => {
    const { assistSavedJob, selectAssistRoute } = await import('/failover.mjs');
    const { hasWarmModel } = await import('/pilot.mjs');
    const lease = { state: 'busy', saved: true, canAssist: true, jobId: 'fixture-lease',
      expiresAt: Date.now() + 5000, canonicalText };
    const states = [];
    for (const info of [
      { ...lease, state: 'healthy' }, { ...lease, state: 'unreachable' }, { ...lease, saved: false },
      { ...lease, canAssist: false }, { ...lease, expiresAt: Date.now() - 1 }, { ...lease, canonicalText: '' },
    ]) states.push((await assistSavedJob(info, { optedIn: true })).state);
    states.push((await assistSavedJob(lease)).state);
    states.push(selectAssistRoute(lease, { online: true, warm: true, optedIn: true, eligible: false }));
    states.push(selectAssistRoute(lease, { online: false, warm: true, optedIn: true, eligible: true }));
    const result = await assistSavedJob(lease, { optedIn: true });
    const stop = new AbortController();
    const pending = assistSavedJob(lease, { optedIn: true, signal: stop.signal });
    stop.abort();
    const interrupted = await pending;
    return { states, result: { ...result, vector: Array.from(result.vector || []) }, interrupted, warmAfterStop: hasWarmModel() };
  }, probes[0].text);
  assert.deepEqual(assist.states, ['vps', 'wait-for-vps', 'vps', 'vps', 'vps', 'vps', 'vps', 'vps', 'wait-for-vps']);
  assert.equal(assist.result.state, 'shadow-result');
  assert.equal(assist.result.jobId, 'fixture-lease');
  assert.deepEqual(assist.result.vector, probes[0].vector);
  assert.deepEqual(assist.interrupted, { state: 'vps' });
  assert.equal(assist.warmAfterStop, false);

  for (const { name, bytes, expected } of negatives) {
    await page.locator('#files').setInputFiles({ name, mimeType: 'application/octet-stream', buffer: bytes });
    const fallback = await page.evaluate(async () =>
      (await (await import('/pilot.mjs')).processFile(document.querySelector('#files').files[0])).fallback);
    assert.equal(fallback, expected, name);
  }
  assert.deepEqual(pageErrors, []);
  assert(requests.every(([method, request]) => method === 'GET' && new URL(request).origin === url));
  assert.equal((await fetch(url + '/api/upload-files', { method: 'POST' })).status, 405);
  const modelRequest = await page.request.get(url + '/assets/tokenizer.json');
  assert.match(modelRequest.headers()['content-security-policy'], /connect-src 'self'/);

  const skipped = await checkDeviceFallbacks(browser, url, corpus[0].bytes);
  await checkInterruptions(browser, url, corpus[0].bytes);

  const narrowDesktop = await browser.newContext({ viewport: { width: 412, height: 800 } });
  const narrowPage = await narrowDesktop.newPage();
  await narrowPage.goto(url);
  let failedLoads = 0;
  await narrowPage.route('**/assets/model.onnx', route => { failedLoads++; return route.abort(); });
  await narrowPage.locator('#files').setInputFiles([
    { name: 'synthetic.pdf', mimeType: 'application/pdf', buffer: corpus[0].bytes },
    { name: 'synthetic-2.pdf', mimeType: 'application/pdf', buffer: corpus[1].bytes },
    { name: 'word.docx', mimeType: 'application/octet-stream', buffer: negatives[1].bytes },
  ]);
  await narrowPage.getByRole('button', { name: 'Process on this device' }).click();
  await narrowPage.getByText('0 of 3 processed locally. No files were uploaded.').waitFor();
  assert.equal(await narrowPage.getByText('Use the regular upload').count(), 3);
  assert.equal(failedLoads, 1, 'A failed model should not be loaded again for the same batch');
  await narrowPage.unroute('**/assets/model.onnx');
  await narrowPage.getByRole('button', { name: 'Process on this device' }).click();
  await narrowPage.getByText('2 of 3 processed locally. No files were uploaded.').waitFor();
  assert.equal(await narrowPage.getByText('Use the regular upload').count(), 1);

  const modelBytes = (await stat(new URL('./assets/model.onnx', import.meta.url))).size;
  const warm = files.slice(1);
  const report = {
    browser_cold_ms: round(files[0].totalMs),
    browser_warm_median_ms: round(median(warm.map(file => file.totalMs))),
    browser_warm_extraction_median_ms: round(median(warm.map(file => file.extractMs))),
    browser_warm_inference_median_ms: round(median(warm.map(file => file.modelMs))),
    model_bytes: modelBytes,
    browser_tests: { pdfs: files.length, negative_cases: negatives.length, model_failure_and_retry: true,
      same_origin_read_only: true, device_fallbacks_without_download: skipped,
      narrow_desktop_width: 412, stop_background_and_reconnect_recovery: true,
      staged_desktop_failover_cases: 12 },
  };
  if (host || image) {
    const baseline = await runBaseline('compare', { files: files.map(({ id, pdf, text, vector }) => (
      { id, pdf, browserText: text, browserVector: vector })), probes, queries });
    Object.assign(report, baseline);
    const ten = baseline.rank_comparisons.find(r => r.case === 'ten-full-stack');
    assert.equal(ten.vps_count, 10);
    assert.equal(ten.vps_exact, 10);
    const noMatch = baseline.rank_comparisons.find(r => r.case === 'unmatched');
    assert.equal(noMatch.vps_exact, 0);
    report.gates = {
      same_text_vectors: baseline.same_input_min_cosine >= 0.9999,
      pdf_text: baseline.exact_pdf_text === baseline.pdf_count,
      ranking: baseline.rank_comparisons.every(r => r.ordered_match) && ten.browser_count === 10 && ten.browser_exact === 10,
      warm_speed_improves_at_least_20_percent: report.browser_warm_median_ms <= baseline.vps_warm_median_ms * 0.8,
    };
    report.canonical_offload_authorized = false;
    if (process.argv.includes('--require-parity') && !Object.values(report.gates).every(Boolean)) process.exitCode = 2;
  } else if (process.argv.includes('--require-parity')) {
    throw new Error('The parity gate requires a configured VPS baseline');
  }
  console.log(JSON.stringify(report, null, 2));
} finally {
  await browser?.close();
  server.close();
  await once(server, 'close');
}
