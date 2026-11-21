import assert from 'node:assert/strict';
import { once } from 'node:events';
import { stat } from 'node:fs/promises';
import { chromium } from 'playwright';
import { corpus, pdf, queries } from './fixtures.mjs';
import { listen } from './server.mjs';
import { runBaseline } from './vps-baseline.mjs';

const batchSize = 8;
const longPdfs = Array.from({ length: 16 }, (_, i) => ({
  id: `long-${i + 1}`,
  bytes: pdf([
    [`Synthetic CV long-${i + 1}`, 40, 740],
    ...Array.from({ length: 6 + i }, (_, j) => [
      `${j + 1}. ${['React application delivery', 'Maintained Node.js services', 'Reconciled dashboard data',
        'Automated reporting and incident response'][j % 4]} and verified cross-team release notes.`, 40, 722 - j * 15,
    ]),
  ]),
}));
const probes = [
  { id: 'unicode', text: '  Lead développeur à Dubaï — العربية हिन्दी, C++, Node.js and SQL Server.  ' },
  { id: 'truncation', text: 'Senior analyst. '.repeat(160) + 'End-of-document token beyond model limit' },
];
const round = value => Number(value.toFixed(2));
const variants = {
  'wasm-1': 'model.onnx',
  'wasm-4': 'model.onnx',
  'wasm-o2': 'model_O2.onnx',
  'wasm-int8': 'model_quint8_avx2.onnx',
  'webgpu': 'model.onnx',
};

async function browserTrial(browser, url, variant, texts) {
  const context = await browser.newContext();
  try {
    const blocked = [];
    await context.route('**/*', route => {
      const req = route.request();
      if (req.method() === 'GET' && new URL(req.url()).origin === url) return route.continue();
      blocked.push(req.url());
      return route.abort();
    });
    const page = await context.newPage();
    await page.goto(url);
    const { eligible, isolated } = await page.evaluate(async () => ({
      eligible: !(await import('/eligibility.mjs')).deviceFallback(), isolated: crossOriginIsolated,
    }));
    assert(eligible && isolated, 'Benchmark needs an eligible desktop in an isolated local test origin');
    const result = await page.evaluate(async ({ variant, texts, batchSize }) => {
      const started = performance.now();
      const worker = new Worker(`/embed.worker.mjs?benchmark=${variant}`, { type: 'module' });
      let id = 0;
      const call = items => new Promise((resolve, reject) => {
        const deadline = setTimeout(() => finish(new Error('Worker timeout')), 25000);
        const onError = event => finish(new Error(event.message || 'Worker failed'));
        const onMessage = ({ data }) => {
          if (data.id === id) finish(data.error ? new Error(data.error) : null, data);
        };
        function finish(error, data) {
          clearTimeout(deadline);
          worker.removeEventListener('message', onMessage);
          worker.removeEventListener('error', onError);
          if (error) reject(error);
          else resolve(data);
        }
        worker.addEventListener('error', onError);
        worker.addEventListener('message', onMessage);
        worker.postMessage({ id: ++id, texts: items });
      });
      try {
        const { gpuVendor } = await call([texts[0]]);
        const coldMs = performance.now() - started;
        const median = values => {
          values.sort((a, b) => a - b);
          return (values[Math.floor((values.length - 1) / 2)] + values[Math.floor(values.length / 2)]) / 2;
        };
        const measure = async size => {
          const latencies = [], totals = [];
          let vectors;
          for (let i = 0; i < 3; i++) {
            vectors = [];
            const runStart = performance.now();
            for (let j = 0; j < texts.length; j += size) {
              const t0 = performance.now();
              const result = await call(texts.slice(j, j + size));
              latencies.push(performance.now() - t0);
              vectors.push(...result.vectors);
            }
            totals.push(performance.now() - runStart);
          }
          return { vectors: vectors.map(v => Array.from(v)), total: median(totals), latency: median(latencies) };
        };
        await call(texts.slice(0, batchSize));
        const single = await measure(1);
        const batch = await measure(batchSize);
        return { single, batch, coldMs, gpuVendor };
      } finally {
        worker.terminate();
      }
    }, { variant, texts, batchSize });
    assert.deepEqual(blocked, [], 'The browser attempted a non-local request');
    return result;
  } finally {
    await context.close();
  }
}

const vpsOptions = { cpus: 1.75, threads: 2 };
const source = [...corpus, ...longPdfs].map(({ id, bytes }) => ({ id, pdf: bytes.toString('base64') }));
const vps = await runBaseline('embedding_baseline', { files: source, probes, queries, batchSize }, vpsOptions);
assert.equal(vps.docs.length, 36);
assert.equal(new Set(vps.docs.map(doc => doc.id)).size, vps.docs.length);
const { server, url } = await listen(0, { isolated: true });
const timings = {};
const vectors = { 'vps-batch': vps.batchedVectors };
let browser;
try {
  browser = await chromium.launch({ channel: process.env.PILOT_BROWSER || 'chrome' });
  for (const [variant, asset] of Object.entries(variants)) {
    const bytes = (await stat(new URL(`./assets/${asset}`, import.meta.url))).size;
    try {
      const result = await browserTrial(browser, url, variant, vps.docs.map(doc => doc.text));
      timings[variant] = { modelBytes: bytes, coldMs: round(result.coldMs), singleMs: round(result.single.latency),
        sequentialCorpusMs: round(result.single.total), bulkCorpusMs: round(result.batch.total), gpuVendor: result.gpuVendor };
      vectors[`${variant}/single`] = result.single.vectors;
      vectors[`${variant}/bulk`] = result.batch.vectors;
    } catch (err) {
      if (variant === 'wasm-1') throw err;
      timings[variant] = { unavailable: err.message };
    }
    console.log(variant, timings[variant]);
  }
} finally {
  await browser?.close();
  server.close();
  await once(server, 'close');
}

const parity = await runBaseline('embedding_rank', { docs: vps.docs, candidateIds: corpus.map(row => row.id),
  baseline: 'vps-single', vectors: vps.vectors, queryVectors: vps.queryVectors, queries, variants: vectors }, vpsOptions);
assert(parity['wasm-1/single'].passesParity && parity['wasm-1/bulk'].passesParity, 'Reference browser model no longer matches');
const candidates = Object.fromEntries(Object.entries(timings).flatMap(([name, timing]) => {
  if (timing.unavailable) return [];
  const mode = timing.bulkCorpusMs < timing.sequentialCorpusMs ? 'bulk' : 'single';
  const ms = mode === 'bulk' ? timing.bulkCorpusMs : timing.sequentialCorpusMs;
  return [[name, { mode, parityAnd20PercentWarmGain: parity[`${name}/${mode}`].passesParity &&
    ms <= vps.batched_corpus_ms * 0.8, warmVsBatchedVps: round(vps.batched_corpus_ms / ms) }]];
}));
console.log(JSON.stringify({
  revision: vps.revision, probeCount: vps.docs.length, searchCases: queries.length, batchSize, vpsCpus: vpsOptions.cpus,
  vps: { singleMs: vps.single_ms, sequentialCorpusMs: vps.single_corpus_ms, bulkCorpusMs: vps.batched_corpus_ms },
  timings, parity, candidates, launchAuthorized: false,
}, null, 2));
