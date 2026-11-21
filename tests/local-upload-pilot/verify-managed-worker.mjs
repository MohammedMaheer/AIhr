import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { generateKeyPairSync, sign } from 'node:crypto';
import { once } from 'node:events';
import { createInterface } from 'node:readline';
import { fileURLToPath } from 'node:url';
import { corpus, queries } from './fixtures.mjs';

const file = name => fileURLToPath(new URL(name, import.meta.url));
function jsonChannel(program, args, prefix) {
  const proc = spawn(program, args, { windowsHide: true, stdio: ['pipe', 'pipe', 'pipe'],
    env: { ...process.env, PYTHONUTF8: '1', PYTHONIOENCODING: 'utf-8' } });
  const exited = once(proc, 'exit');
  // Observe spawn failures immediately, even if the other process is still starting.
  exited.catch(() => {});
  const lines = createInterface({ input: proc.stdout, crlfDelay: Infinity });
  const messages = [];
  let wake, stderr = '', closed = false;
  proc.stderr.on('data', bytes => { stderr = (stderr + bytes.toString()).slice(-4000); });
  proc.stdin.on('error', () => {});
  lines.on('line', line => {
    if (!line.startsWith(prefix)) return;
    const value = JSON.parse(line.slice(prefix.length));
    if (wake) wake(value);
    else messages.push(value);
  });
  async function receive() {
    assert(!wake, 'Concurrent fixture commands are not supported');
    if (messages.length) return messages.shift();
    let timer;
    try {
      return await Promise.race([
        new Promise(resolve => { wake = resolve; }),
        exited.then(([code]) => { throw new Error(`${prefix} process exited (${code})\n${stderr}`); }),
        new Promise((_, reject) => { timer = setTimeout(() => reject(new Error(`${prefix} timeout\n${stderr}`)), 66000); }),
      ]);
    } finally { wake = null; clearTimeout(timer); }
  }
  return {
    receive,
    send(data) { proc.stdin.write(JSON.stringify(data) + '\n'); return receive(); },
    async close() {
      if (!closed && proc.exitCode === null && proc.signalCode === null) proc.stdin.end('{"op":"close"}\n');
      closed = true;
      assert.equal((await exited)[0], 0, stderr);
    },
  };
}

const stage = jsonChannel(process.env.PILOT_PYTHON || 'python', [file('./stage_vps.py'), 'managed'], 'HANDOFF:');
const worker = jsonChannel(process.execPath, [file('./managed-worker.mjs')], 'MANAGED:');
const workers = new Map();
let spare;
let rankingComparisons = 0;
const stageCall = (op, fields = {}) => stage.send({ op, ...fields });
const workerCall = (id, op, fields = {}) => workers.get(id).send({ op, ...fields });
const pdfs = corpus.map(row => row.bytes.toString('base64'));
const searches = [...queries, { name: 'scoped-full-stack', text: queries[0].text, limit: 10, tag: 'Software development' }];
const upload = (state, actor = 'owner') => stageCall('upload', { state, actor, pdfs });
const offer = (job, saturate = true) => stageCall('offer', { jobId: job.jobId, saturate });
const accept = (job, result) => stageCall('accept', { jobId: job.jobId, result });
const recover = job => stageCall('recover', { jobId: job.jobId });
const search = job => stageCall('search', { jobId: job.jobId, queries: searches });
const round = value => Number(value.toFixed(2));
const median = values => [...values].sort((a, b) => a - b)[Math.floor(values.length / 2)];
const wait = ms => new Promise(resolve => setTimeout(resolve, ms));

async function claim(job, challenge) {
  assert.equal(challenge.state, 'offered');
  const proof = await workerCall(challenge.workerId, 'prove', challenge);
  assert(proof.signature);
  const result = await stageCall('prove', { jobId: job.jobId, signature: proof.signature });
  assert.equal(result.state, 'leased');
  assert.equal(result.texts.length, pdfs.length);
  return result;
}

async function enroll(channel, desktop, coordinator) {
  assert(desktop.ready);
  assert.equal((await channel.send({ op: 'configure', coordinator })).configured, true);
  const enrolled = await stageCall('enroll', { publicKey: desktop.publicKey, model: desktop.model });
  assert.equal(enrolled.state, 'enrolled-stage-only');
  workers.set(enrolled.workerId, channel);
  return enrolled.workerId;
}

async function heartbeat(workerId, ready = true) {
  const packet = await workerCall(workerId, 'heartbeat', { ready });
  const result = await stageCall('heartbeat', { workerId, ...packet });
  assert.equal(result.state, 'heartbeat');
  return { packet, vpsCpuMs: result.vpsCpuMs };
}

function assertSameOrder(from, to) {
  assert.equal(from.count, pdfs.length);
  assert.equal(to.count, pdfs.length);
  assert.equal(to.ranks[0].length, 10);
  assert(to.ranks[0].every(row => row[1] === 'exact'));
  assert.equal(to.ranks.at(-1).length, 10, 'Scoped search should contain ten exact candidates');
  let delta = 0;
  for (const [i, expected] of from.ranks.entries()) {
    assert.deepEqual(to.ranks[i].map(row => row.slice(0, 2)), expected.map(row => row.slice(0, 2)), searches[i].name);
    expected.forEach((row, k) => { delta = Math.max(delta, Math.abs(to.ranks[i][k][2] - row[2])); });
  }
  assert(delta <= 0.00001, `Search score drift ${delta}`);
  rankingComparisons += searches.length;
  return delta;
}

try {
  const [remote, desktop] = await Promise.all([stage.receive(), worker.receive()]);
  assert(remote.ready && desktop.ready);
  const coordinator = await stageCall('coordinator');
  const unapproved = await stageCall('enroll', { actor: 'owner', publicKey: desktop.publicKey, model: desktop.model });
  assert.equal(unapproved.status, 403);
  const primary = await enroll(worker, desktop, coordinator.publicKey);
  assert.equal((await stageCall('revoke', { actor: 'second-admin', workerId: primary })).status, 404);
  const base = [], offload = [], similarities = [];
  let referenceRanks, scoreDelta = 0;
  for (let i = 0; i < 3; i++) {
    let start = performance.now();
    const vps = await upload('reference');
    base.push({ ...vps, ms: round(performance.now() - start) });
    assert.equal(vps.saved, pdfs.length);
    assert.deepEqual(vps.inferenceBatches, [8, 8, 2]);
    referenceRanks = await search(vps);

    start = performance.now();
    const saved = await upload('busy');
    assert.deepEqual(saved.inferenceBatches, []);
    const pulse = await heartbeat(primary);
    const challenge = await offer(saved);
    assert.equal(challenge.workerId, primary);
    const lease = await claim(saved, challenge);
    const result = await workerCall(primary, 'embed', { lease });
    const landed = await accept(saved, result);
    assert.equal(landed.state, 'indexed-by-managed-worker');
    assert.equal(landed.indexed, pdfs.length);
    assert.deepEqual(landed.inferenceBatches, []);
    offload.push({ vpsCpuMs: saved.vpsCpuMs + pulse.vpsCpuMs + challenge.vpsCpuMs + lease.vpsCpuMs + landed.vpsCpuMs,
      ms: round(performance.now() - start), desktopMs: round(result.managedEmbeddingMs) });
    assert.equal((await accept(saved, result)).state, 'denied');
    assert.equal((await recover(saved)).state, 'already-indexed');
    scoreDelta = Math.max(scoreDelta, assertSameOrder(referenceRanks, await search(saved)));
    const pairs = await stageCall('compare', { before: vps.jobId, after: saved.jobId });
    assert.equal(pairs.compared, pdfs.length);
    assert(pairs.same && pairs.cosine >= 0.999999);
    similarities.push(pairs.cosine);
  }

  const healthy = await upload('healthy');
  assert.equal((await offer(healthy, false)).state, 'vps');
  assert.equal((await recover(healthy)).indexed, pdfs.length);
  assertSameOrder(referenceRanks, await search(healthy));
  const other = await upload('busy', 'second');
  assert.equal((await offer(other)).state, 'vps');
  assert.equal((await recover(other)).indexed, pdfs.length);
  assertSameOrder(referenceRanks, await search(other));

  const paused = await upload('busy');
  const { packet } = await heartbeat(primary, false);
  assert.equal((await stageCall('heartbeat', { workerId: primary, ...packet })).state, 'denied');
  assert.equal((await offer(paused)).state, 'vps');
  assert.equal((await recover(paused)).indexed, pdfs.length);
  assertSameOrder(referenceRanks, await search(paused));

  spare = jsonChannel(process.execPath, [file('./managed-worker.mjs')], 'MANAGED:');
  const secondary = await enroll(spare, await spare.receive(), coordinator.publicKey);
  assert.notEqual(primary, secondary);
  await heartbeat(primary);
  await heartbeat(secondary);

  const lost = await upload('busy');
  const challenge = await offer(lost);
  const wrong = generateKeyPairSync('ed25519');
  const wrongProof = sign(null, Buffer.from(`claim:${challenge.challenge}`), wrong.privateKey).toString('base64');
  assert.equal((await stageCall('prove', { jobId: lost.jobId, signature: wrongProof })).state, 'denied');
  const lease = await claim(lost, challenge);
  const wrongText = { ...lease, texts: lease.texts.map((text, i) => i ? text : text + ' Different fixture.') };
  assert.equal((await workerCall(challenge.workerId, 'embed', { lease: wrongText })).refused, true);
  const held = await workerCall(challenge.workerId, 'embed', { lease });
  const modified = { ...held, packed: (held.packed[0] === 'A' ? 'B' : 'A') + held.packed.slice(1) };
  assert.equal((await accept(lost, modified)).state, 'denied');
  assert.equal((await search(lost)).count, 0);
  assert.equal((await recover(lost)).state, 'lease-active');

  const overlapped = await upload('busy');
  const overlapOffer = await offer(overlapped);
  assert.equal(overlapOffer.state, 'offered');
  assert.notEqual(overlapOffer.workerId, challenge.workerId, 'A full worker must be skipped');
  const overlapLease = await claim(overlapped, overlapOffer);
  const overflow = await upload('busy');
  assert.equal((await offer(overflow)).state, 'vps', 'A fully occupied pool should fall back immediately');
  const fallback = await recover(overflow);
  assert.deepEqual(fallback.inferenceBatches, [8, 8, 2]);
  assertSameOrder(referenceRanks, await search(overflow));
  assert.equal((await accept(overlapped, await workerCall(overlapOffer.workerId, 'embed', { lease: overlapLease }))).indexed, pdfs.length);
  assertSameOrder(referenceRanks, await search(overlapped));

  await workers.get(challenge.workerId).close();
  assert.equal((await stageCall('reset-coordinator-memory')).state, 'reloaded');
  assert.equal((await recover(lost)).state, 'lease-active', 'A reloaded broker must respect a durable lease');
  const { remainingMs } = await stageCall('remaining-lease', { jobId: lost.jobId });
  assert(remainingMs <= 12000);
  await wait(remainingMs + 60);
  assert.equal((await accept(lost, held)).state, 'denied');
  await heartbeat(overlapOffer.workerId);
  const reassigned = await offer(lost);
  assert.equal(reassigned.workerId, overlapOffer.workerId);
  const replacement = await claim(lost, reassigned);
  assert.equal((await accept(lost, held)).state, 'denied');
  assert.equal((await accept(lost, await workerCall(reassigned.workerId, 'embed', { lease: replacement }))).indexed, pdfs.length);
  assertSameOrder(referenceRanks, await search(lost));

  assert.equal((await stageCall('revoke', { workerId: challenge.workerId })).state, 'revoked');
  const revoked = await upload('busy');
  const revokedOffer = await offer(revoked);
  assert.equal(revokedOffer.workerId, reassigned.workerId);
  const revokedLease = await claim(revoked, revokedOffer);
  const revokedResult = await workerCall(revokedOffer.workerId, 'embed', { lease: revokedLease });
  assert.equal((await stageCall('revoke', { workerId: revokedOffer.workerId })).state, 'revoked');
  assert.equal((await offer(revoked)).state, 'vps');
  assert.equal((await accept(revoked, revokedResult)).state, 'denied');
  assert.equal((await recover(revoked)).indexed, pdfs.length);
  assertSameOrder(referenceRanks, await search(revoked));

  const directCpu = median(base.map(run => run.vpsCpuMs));
  const managedCpu = median(offload.map(run => run.vpsCpuMs));
  const cpuSaved = round(100 * (1 - managedCpu / directCpu));
  const report = { cvsPerTrial: pdfs.length, trials: base.length, rankingComparisons, managedWorkerIdentities: workers.size,
    vpsModelCalls: { direct: [8, 8, 2], managed: [] },
    medianVpsProcessCpuMs: { direct: round(directCpu), managed: round(managedCpu) }, cpuReductionPercent: cpuSaved,
    stagedWallMs: { direct: base.map(row => row.ms), managed: offload.map(row => row.ms) },
    nativeComputeMs: offload.map(row => row.desktopMs),
    minCosine: Math.min(...similarities), maxRankingScoreDelta: scoreDelta,
    guardsPassed: ['healthy', 'real-upload-slot-saturation', 'tenant-assignment', 'admin-only-enrollment',
      'cross-tenant-revocation', 'not-enrolled-signature', 'text-binding',
      'result-signature', 'duplicate-submit', 'late-submit', 'paused-worker', 'heartbeat-replay', 'full-worker',
      'all-workers-full', 'worker-stopped', 'coordinator-memory-loss', 'reassigned-after-expiry', 'vps-fallback', 'revoked'],
    testGates: { rankingUnchanged: true, fallbackVerified: true, reducedVpsLoad: cpuSaved >= 30 },
    productionWorkerEnrolled: false, launchAuthorized: false };
  console.log(JSON.stringify(report, null, 2));
  assert(report.testGates.reducedVpsLoad, 'End-to-end VPS CPU reduction did not meet the 30% gate');
} finally {
  await Promise.all([worker.close(), spare?.close(), stage.close()]);
}
