import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { readFile, stat } from 'node:fs/promises';
import { once } from 'node:events';
import { chromium } from 'playwright';
import { checkDeviceFallbacks, checkInterruptions } from './device-checks.mjs';
import { corpus, negatives, queries } from './fixtures.mjs';
import { listen, revision } from './server.mjs';

const host = process.env.PILOT_BASELINE_SSH;
const image = process.env.PILOT_BASELINE_IMAGE;
const median = values => {
  const sorted = [...values].sort((a, b) => a - b);
  return (sorted[Math.floor((sorted.length - 1) / 2)] + sorted[Math.floor(sorted.length / 2)]) / 2;
};
const round = value => Number(value.toFixed(2));
const asInputs = fixtures => fixtures.map(({ id, bytes }) => ({ id, pdf: bytes.toString('base64') }));

async function vpsBaseline(files, probes) {
  assert(host && /^[\w.-]+@[\w.-]+$/.test(host), 'Set PILOT_BASELINE_SSH to an authorized SSH login');
  assert(image && /^[\w.-]+:[\w.-]+$/.test(image), 'Set PILOT_BASELINE_IMAGE to the verified cached SmartHR image');
  const payload = Buffer.from(JSON.stringify({ files, probes, queries, revision })).toString('base64');
  const source = await readFile(new URL('./baseline.py', import.meta.url), 'utf8');
  const result = spawnSync('ssh', [
    '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=8', host,
    'docker', 'run', '--rm', '-i', '--pull=never', '--network=none', '--read-only', '--user=65534:65534',
    '--cap-drop=ALL', '--security-opt=no-new-privileges', '--tmpfs=/tmp:rw,noexec,nosuid,size=96m',
    '--cpus=1', '--memory=1500m', '--memory-swap=1500m', '--pids-limit=64',
    '-e', 'HF_HUB_OFFLINE=1', '-e', 'TRANSFORMERS_OFFLINE=1', '-e', 'OMP_NUM_THREADS=1',
    '-e', 'MKL_NUM_THREADS=1', '-e', 'SMARTHR_QUERY_EMBED_CACHE_MAX=0',
    '-e', 'SMARTHR_EMBED_MODEL=sentence-transformers/all-MiniLM-L6-v2',
    '-e', 'SENTENCE_TRANSFORMERS_HOME=/app/.st_cache',
    '-v', 'smarthr_stcache:/app/.st_cache:ro', '--entrypoint=timeout', image, '120', 'python', '-',
  ], {
    input: `${source}\ncompare(json.loads(base64.b64decode('${payload}')))\n`,
    encoding: 'utf8', timeout: 135000,
  });
  if (result.error) throw result.error;
  assert.equal(result.status, 0, result.stderr || result.stdout);
  const report = result.stdout.split('\n').find(line => line.startsWith('PILOT_REPORT:'));
  assert(report, 'No isolated baseline report');
  return JSON.parse(report.slice('PILOT_REPORT:'.length));
}

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
      narrow_desktop_width: 412, stop_background_and_reconnect_recovery: true },
  };
  if (host || image) {
    const baseline = await vpsBaseline(files.map(({ id, pdf, text, vector }) => ({ id, pdf, browserText: text, browserVector: vector })), probes);
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
