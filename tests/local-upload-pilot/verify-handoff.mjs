import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { createInterface } from 'node:readline';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';
import { corpus, queries } from './fixtures.mjs';
import { listen } from './server.mjs';

const pdfs = corpus.map(row => row.bytes.toString('base64'));
const fixtureQueries = [...queries, {
  name: 'scoped-full-stack', text: queries[0].text, limit: 10, tag: 'Software development',
}];
const round = n => Number(n.toFixed(2));
const median = values => [...values].sort((a, b) => a - b)[Math.floor(values.length / 2)];
const endpoint = (job, action) => `/__qa/desktop/${job.jobId}/${action}`;
const child = spawn(process.env.PILOT_PYTHON || 'python', [fileURLToPath(new URL('./stage_vps.py', import.meta.url))], {
  stdio: ['pipe', 'pipe', 'pipe'], windowsHide: true,
  env: { ...process.env, PYTHONUTF8: '1', PYTHONIOENCODING: 'utf-8' },
});
const terminal = once(child, 'exit');
const lines = createInterface({ input: child.stdout, crlfDelay: Infinity });
let stderr = '';
child.stderr.on('data', data => { stderr = (stderr + data.toString()).slice(-4000); });
child.stdin.on('error', () => {});
const replies = [];
let waiting;
lines.on('line', line => {
  if (!line.startsWith('HANDOFF:')) return;
  const result = JSON.parse(line.slice('HANDOFF:'.length));
  if (waiting) waiting(result);
  else replies.push(result);
});

async function response(timeoutMs = 70000) {
  assert(!waiting, 'Stage commands must be sequential');
  if (replies.length) return replies.shift();
  let timer;
  try {
    return await Promise.race([
      new Promise(resolve => { waiting = resolve; }),
      terminal.then(([code]) => { throw new Error(`Stage exited (${code})\n${stderr}`); }),
      new Promise((_, reject) => { timer = setTimeout(() => reject(new Error(`Stage response timed out\n${stderr}`)), timeoutMs); }),
    ]);
  } finally {
    waiting = null;
    clearTimeout(timer);
  }
}

function run(command) {
  child.stdin.write(JSON.stringify(command) + '\n');
  return response();
}

const { server, url } = await listen();
let browser;
try {
  assert.deepEqual(await response(), { ready: true });
  browser = await chromium.launch({ channel: process.env.PILOT_BROWSER || 'chrome' });
  const page = await browser.newPage();
  await page.route(`${url}/__qa/desktop/**`, async route => {
    const req = route.request();
    assert.equal(req.method(), 'POST');
    const reply = await run({ op: 'http', actor: req.headers()['x-qa-second-tenant'] === '1' ? 'second' : 'owner',
      path: new URL(req.url()).pathname, body: req.postDataJSON() });
    await route.fulfill({ status: reply.status, json: reply.json });
  });
  await page.goto(url);

  const post = (job, action, body, second = false) => page.evaluate(async ({ path, body, second }) => {
    const r = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json',
      ...(second ? { 'X-QA-Second-Tenant': '1' } : {}) }, body: JSON.stringify(body) });
    return { status: r.status, body: await r.json() };
  }, { path: endpoint(job, action), body, second });

  async function warmModel() {
    await page.evaluate(async () => {
      const { embed } = await import('/pilot.mjs');
      await embed('Synthetic warm-up text for the isolated desktop release gate.');
    });
  }
  const grant = (job, warm) => post(job, 'claim', { optedIn: true, warm });
  const getRanks = job => run({ op: 'search', jobId: job.jobId, queries: fixtureQueries });
  const finish = job => run({ op: 'finish', jobId: job.jobId });
  const checkIndex = result => {
    assert.equal(result.count, pdfs.length);
    assert.equal(result.ranks[0].length, 10);
    assert(result.ranks[0].every(row => row[1] === 'exact'));
    assert.equal(result.ranks.at(-1).length, 10, 'Folder, tag and date scoped test must find ten');
  };

  const references = [], safeTrials = [];
  let referenceRanks, recordedVectors;
  for (let i = 0; i < 3; i++) {
    const started = performance.now();
    const direct = await run({ op: 'upload', state: 'reference', pdfs });
    references.push({ ...direct, elapsedMs: round(performance.now() - started) });
    assert.equal(direct.saved, pdfs.length);
    referenceRanks = await getRanks(direct);
    checkIndex(referenceRanks);

    const handedOffAt = performance.now();
    const busy = await run({ op: 'upload', state: 'busy', pdfs });
    assert.deepEqual(busy.inferenceBatches, [], 'Files should be saved first in the staged handoff');
    assert.equal(busy.saved, pdfs.length);
    if (!i) {
      assert.equal((await getRanks(busy)).count, 0);
      assert.equal((await grant(busy, false)).body.canAssist, false);
      const wrongTenant = await post(busy, 'claim', { optedIn: true, warm: true }, true);
      assert.equal(wrongTenant.status, 404);
      assert(!('texts' in wrongTenant.body));
      await warmModel();
    }
    const { body: lease, status } = await grant(busy, true);
    assert.equal(status, 200);
    assert.equal(lease.canAssist, true);
    const vectorResult = await page.evaluate(async lease => {
      const { assistSavedJob } = await import('/failover.mjs');
      const vectors = [];
      const start = performance.now();
      for (const canonicalText of lease.texts) {
        const output = await assistSavedJob({ ...lease, canonicalText }, { optedIn: true });
        if (output.state !== 'shadow-result') throw new Error(`Unexpected desktop route: ${output.state}`);
        vectors.push(Array.from(output.vector));
      }
      return { vectors, desktopMs: performance.now() - start };
    }, lease);
    if (!i) {
      const denied = await post(busy, 'submit', { lease: lease.lease, vectors: [] }, true);
      assert.equal(denied.status, 404);
    }
    const accepted = await post(busy, 'submit', { lease: lease.lease, vectors: vectorResult.vectors });
    assert.equal(accepted.body.state, 'waiting-for-verification');
    if (!i) assert.equal((await getRanks(busy)).count, 0, 'A submitted vector must not be searchable before verification');
    const checked = await finish(busy);
    assert.equal(checked.desktopAgreed, true);
    assert.equal(checked.indexed, pdfs.length);
    safeTrials.push({ ...checked, desktopMs: round(vectorResult.desktopMs),
      elapsedMs: round(performance.now() - handedOffAt), comparableWallTime: i !== 0 });
    const retrieved = await getRanks(busy);
    checkIndex(retrieved);
    assert.deepEqual(retrieved.ranks, referenceRanks.ranks);
    assert.deepEqual(checked.inferenceBatches, direct.inferenceBatches);
    assert.equal((await finish(busy)).state, 'already-indexed');
    if (!i) assert.equal((await post(busy, 'submit', { lease: lease.lease, vectors: vectorResult.vectors })).status, 409);
    recordedVectors = vectorResult.vectors;
  }

  for (const condition of ['healthy', 'expired', 'lost', 'incorrect']) {
    const job = await run({ op: 'upload', state: condition === 'healthy' ? 'healthy' : 'busy', pdfs });
    const { body: lease } = await grant(job, true);
    if (condition === 'healthy') {
      assert.equal(lease.canAssist, false);
    } else if (condition === 'expired') {
      await run({ op: 'expire', jobId: job.jobId });
      assert.equal((await post(job, 'submit', { lease: lease.lease, vectors: recordedVectors })).status, 409);
    } else if (condition === 'incorrect') {
      assert.equal((await post(job, 'submit', { lease: lease.lease, vectors: [] })).status, 422);
      const wrong = recordedVectors.map((_, i) => recordedVectors[(i + 1) % recordedVectors.length]);
      assert.equal((await post(job, 'submit', { lease: lease.lease, vectors: wrong })).body.state, 'waiting-for-verification');
    }
    if (condition === 'lost') await run({ op: 'expire', jobId: job.jobId });
    const result = await finish(job);
    assert.equal(result.indexed, pdfs.length);
    assert.equal(result.desktopAgreed, condition === 'incorrect' ? false : null);
    assert.deepEqual((await getRanks(job)).ranks, referenceRanks.ranks);
  }

  const cpu = key => round(median(key.map(row => row.embeddingCpuMs)));
  const comparable = safeTrials.filter(row => row.comparableWallTime);
  const work = run => run.inferenceBatches.reduce((sum, batch) => sum + batch, 0);
  const gates = { rankingUnchanged: true, fallbackVerified: true,
    reducedVpsInference: safeTrials.every((trial, i) => work(trial) < work(references[i])),
    independentBrowserVectorTrust: false };
  const report = {
    cvsPerTrial: pdfs.length, comparedOrders: fixtureQueries.length * (safeTrials.length + 4),
    canonicalModelCalls: { vps: references[0].inferenceBatches, offloadWithVerification: safeTrials[0].inferenceBatches },
    medianEmbeddingCpuMs: { vps: cpu(references), offloadWithVerification: cpu(safeTrials) },
    directWallMs: references.map(row => row.elapsedMs), verifiedHandoffWallMs: comparable.map(row => row.elapsedMs),
    warmDesktopMs: safeTrials.map(row => row.desktopMs),
    guardsPassed: ['cold', 'other-tenant', 'unverified-not-searchable', 'healthy', 'expired', 'lost', 'bad-shape', 'incorrect-vector', 'replay'],
    gates, launchAuthorized: Object.values(gates).every(Boolean),
  };
  console.log(JSON.stringify(report, null, 2));
} finally {
  await browser?.close();
  server.close();
  await once(server, 'close');
  if (child.exitCode === null && child.signalCode === null) child.stdin.end('{"op":"close"}\n');
  const [code] = await terminal;
  assert.equal(code, 0, stderr);
}
