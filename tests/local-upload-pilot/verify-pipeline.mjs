// No production credentials, files, or provider calls. Two agent identities on the test host.
import assert from 'node:assert/strict';
import { spawn, spawnSync } from 'node:child_process';
import { once } from 'node:events';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { createServer } from 'node:https';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createInterface } from 'node:readline';
import { setTimeout as sleep } from 'node:timers/promises';
import { fileURLToPath } from 'node:url';
import { corpus, queries } from './fixtures.mjs';
import { revision } from '../../desktop-worker/model.mjs';

const scratch = await mkdtemp(join(tmpdir(), 'smarthr-pipeline-'));
const worker = fileURLToPath(new URL('../../desktop-worker/agent.mjs', import.meta.url));
const launcher = fileURLToPath(new URL('./stage_vps.py', import.meta.url));
const cert = join(scratch, 'cert.pem'), key = join(scratch, 'key.pem');
const createCert = spawnSync('python', ['-c', `
import datetime, ipaddress, pathlib, sys
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'SmartHR isolated test')])
now = datetime.datetime.now(datetime.timezone.utc)
cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
    .serial_number(x509.random_serial_number()).not_valid_before(now - datetime.timedelta(hours=1))
    .not_valid_after(now + datetime.timedelta(hours=1))
    .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]), False)
    .add_extension(x509.BasicConstraints(ca=True, path_length=0), True).sign(key, hashes.SHA256()))
pathlib.Path(sys.argv[1]).write_bytes(cert.public_bytes(serialization.Encoding.PEM))
pathlib.Path(sys.argv[2]).write_bytes(key.private_bytes(serialization.Encoding.PEM,
    serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))`, cert, key], { stdio: 'inherit' });
assert.equal(createCert.status, 0, 'Python cryptography is required for the disposable HTTPS fixture');

const stage = spawn('python', ['-u', launcher, 'pipeline'], { stdio: ['pipe', 'pipe', 'inherit'] });
stage.stdin.on('error', error => { if (error.code !== 'EPIPE') throw error; });
const exited = once(stage, 'exit');
const lines = createInterface({ input: stage.stdout })[Symbol.asyncIterator]();
async function read() {
  for (;;) {
    const item = await lines.next();
    assert(!item.done, 'VPS staging process closed before returning a result');
    if (item.value.startsWith('HANDOFF:')) return JSON.parse(item.value.slice(8));
  }
}
let sequence = Promise.resolve();
function rpc(command) {
  const result = sequence.then(async () => {
    stage.stdin.write(JSON.stringify(command) + '\n');
    return read();
  });
  sequence = result;
  return result;
}
const statusLog = [];
const server = createServer({ cert: await readFile(cert), key: await readFile(key) }, async (req, res) => {
  try {
    const chunks = [];
    for await (const chunk of req) chunks.push(chunk);
    const result = await rpc({ op: 'http', path: req.url, body: JSON.parse(Buffer.concat(chunks)), headers: {
      ...(req.headers.authorization ? { authorization: req.headers.authorization } : {}),
      ...(req.headers['x-smarthr-worker-id'] ? { 'x-smarthr-worker-id': req.headers['x-smarthr-worker-id'] } : {}),
    } });
    statusLog.push([req.url, result.status]);
    res.writeHead(result.status, { 'Content-Type': 'application/json' }).end(result.body);
  } catch {
    res.writeHead(500).end();
  }
});

async function native(command, body) {
  const processOptions = { env: { ...process.env, NODE_EXTRA_CA_CERTS: cert }, stdio: ['pipe', 'pipe', 'inherit'] };
  const child = spawn(process.execPath, [worker, command], processOptions);
  const ended = once(child, 'exit');
  child.stdin.end(JSON.stringify(body));
  const data = [];
  for await (const chunk of child.stdout) data.push(chunk);
  assert.equal((await ended)[0], 0, `Native worker ${command} failed`);
  return data.length ? JSON.parse(Buffer.concat(data)) : undefined;
}

async function waitForJob(jobId, groups = 1) {
  for (let i = 0; i < 35; i++) {
    const status = await rpc({ op: 'status', jobId });
    if (status.jobs.length >= groups) return status.jobs;
    assert(!status.done, 'Upload finished without durable offload work');
    await sleep(180);
  }
  assert.fail('Durable offload work did not arrive');
}

try {
  assert.deepEqual(await read(), { ready: true });
  server.listen(0, '127.0.0.1');
  await once(server, 'listening');
  const origin = `https://127.0.0.1:${server.address().port}`;
  const enroll = async name => native('enroll', { origin, name, enrollmentCode: (await rpc({ op: 'invite' })).enrollmentCode });
  const agentA = await enroll('Windows QA 1');
  const agentB = await enroll('Windows QA 2');
  assert.notEqual(agentA.workerId, agentB.workerId);
  const upload = async (selection, busy) => (await rpc({ op: 'upload', busy, pdfs: selection.map(doc => doc.bytes.toString('base64')) })).jobId;
  const result = jobId => rpc({ op: 'results', jobId });
  const reference = await upload(corpus, false);
  const normal = await result(reference);
  assert.deepEqual(normal.inferenceBatches, [8, 8, 2]);

  await native('once', agentA);
  await native('once', agentB);
  await sleep(1050);
  const assisted = await upload(corpus, true);
  await waitForJob(assisted);
  const lost = await rpc({ op: 'http', path: '/api/managed-desktop/claim', body: { model: revision, ready: true }, headers: {
    authorization: `Bearer ${agentA.credential}`, 'x-smarthr-worker-id': agentA.workerId,
  } });
  assert.equal(lost.status, 200, 'First worker must have a lease to abandon');
  const abandoned = JSON.parse(lost.body);
  assert(abandoned.leaseMs > 0 && abandoned.leaseMs <= 7000);
  await sleep(abandoned.leaseMs + 450);
  for (let i = 1; i <= 3; i++) {
    await waitForJob(assisted, i);
    for (let attempt = 0; attempt < 3; attempt++) {
      await native('once', i === 2 ? agentA : agentB);
      if (statusLog.at(-1)[1] === 202) break;
      await sleep(1100);
    }
    assert.equal(statusLog.at(-1)[1], 202, `Native batch ${i} must be accepted`);
    await sleep(1050);
  }
  const offload = await result(assisted);
  assert.equal(offload.indexed, normal.indexed);
  assert.deepEqual(offload.inferenceBatches, []);
  assert.deepEqual((await rpc({ op: 'status', jobId: assisted })).jobs, [
    { attempts: 2, published: true }, { attempts: 1, published: true }, { attempts: 1, published: true },
  ]);

  await native('once', agentA);
  const fallback = await upload(corpus.slice(0, 2), true);
  await waitForJob(fallback);
  assert.deepEqual((await result(fallback)).inferenceBatches, [2]);
  assert.deepEqual((await rpc({ op: 'status', jobId: fallback })).jobs, [{ attempts: 0, published: true }]);
  const all = [...queries, { ...queries[2], tag: 'Data and AI' }, { ...queries[2], tag: 'UI design' }];
  const before = await rpc({ op: 'search', jobId: reference, queries: all });
  const after = await rpc({ op: 'search', jobId: assisted, queries: all });
  assert.equal(before.count, 18);
  assert.equal(after.count, before.count);
  assert.equal(before.ranks[0].length, 10);
  assert(before.ranks.at(-2).length > 0);
  assert.equal(before.ranks.at(-1).length, 0);
  let compared = 0;
  before.ranks.forEach((ranks, i) => {
    assert.deepEqual(after.ranks[i].map(row => row.slice(0, 2)), ranks.map(row => row.slice(0, 2)));
    ranks.forEach((row, j) => {
      assert(Math.abs(row[2] - after.ranks[i][j][2]) <= 1e-5);
      compared++;
    });
  });
  console.log(JSON.stringify({ identities: 2, physicalDesktops: 1, indexed: offload.indexed,
    queryCount: all.length, compared, normal, offload, fallback: { indexed: 2, localBatches: [2] }, paidCalls: 0 }, null, 2));
} finally {
  if (!stage.stdin.destroyed && stage.exitCode === null) stage.stdin.end('{"op":"close"}\n');
  server.close();
  await exited;
  await rm(scratch, { recursive: true, force: true });
}
