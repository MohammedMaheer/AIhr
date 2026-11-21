import { createPrivateKey, generateKeyPairSync, sign } from 'node:crypto';
import { availableParallelism, freemem, totalmem } from 'node:os';
import { setTimeout as sleep } from 'node:timers/promises';
import { readAssets, revision, sha } from './model.mjs';
import { encodeMiniLm } from './minilm.mjs';

const packagePrefix = '/api/managed-desktop';
const id = value => typeof value === 'string' && /^[a-f0-9-]{36}$/.test(value);
const hasRoom = () => availableParallelism() >= 4 && totalmem() >= 4 * 1024 ** 3 && freemem() >= 512 * 1024 ** 2;

function baseOrigin(value) {
  const dest = new URL(value);
  if (process.env.NODE_TLS_REJECT_UNAUTHORIZED === '0' || dest.protocol !== 'https:' ||
      dest.pathname !== '/' || dest.username || dest.password || dest.search || dest.hash) {
    throw new Error('Worker requires an HTTPS origin and normal certificate validation');
  }
  return dest.origin;
}

function api(origin, identity) {
  return async (path, body) => {
    const headers = { 'Content-Type': 'application/json' };
    if (identity) {
      headers.Authorization = `Bearer ${identity.credential}`;
      headers['X-SmartHR-Worker-Id'] = identity.workerId;
    }
    const response = await fetch(origin + packagePrefix + path, {
      method: 'POST', headers, body: JSON.stringify(body), redirect: 'error', signal: AbortSignal.timeout(12000),
    });
    return { status: response.status, data: response.status === 200 || response.status === 201 ? await response.json() : null };
  };
}

async function input() {
  let data = '';
  for await (const chunk of process.stdin) {
    data += chunk;
    if (data.length > 4096) throw new Error('Worker configuration too large');
  }
  return JSON.parse(data.trim());
}

async function nativeModel() {
  const [ort, { Tokenizer }, [graph, spec, config]] = await Promise.all([
    import('onnxruntime-node'), import('@huggingface/tokenizers'), readAssets(),
  ]);
  return { ort, tokenizer: new Tokenizer(JSON.parse(spec), JSON.parse(config)),
    model: await ort.InferenceSession.create(graph, { executionProviders: ['cpu'], intraOpNumThreads: 4, interOpNumThreads: 1 }) };
}

async function register() {
  const config = await input();
  const origin = baseOrigin(config.origin);
  const { privateKey, publicKey } = generateKeyPairSync('ed25519');
  const result = await api(origin)('/enroll', { enrollmentCode: config.enrollmentCode, name: config.name,
    publicKey: publicKey.export({ format: 'der', type: 'spki' }).toString('base64') });
  if (result.status !== 201 || result.data?.model !== revision) throw new Error('Enrollment failed');
  process.stdout.write(JSON.stringify({ origin, workerId: result.data.workerId, credential: result.data.credential,
    key: privateKey.export({ format: 'der', type: 'pkcs8' }).toString('base64') }));
}

async function execute(client, engine, signer, job, started) {
  const deadline = started + job.leaseMs;
  if (!id(job.jobId) || !id(job.leaseId) || job.model !== revision ||
      !Number.isInteger(job.leaseMs) || job.leaseMs > 7000 || !(deadline > performance.now()) ||
      !Array.isArray(job.texts) || job.texts.length < 2 || job.texts.length > 8 ||
      job.texts.some(text => typeof text !== 'string' || text.length < 30 || text.length > 160000) ||
      sha(job.texts.map(text => sha(text)).join('')) !== job.digest) return;
  const vectors = await encodeMiniLm(engine, job.texts);
  if (deadline <= performance.now()) return;
  const bytes = Buffer.alloc(vectors.length * 384 * 4);
  let offset = 0;
  for (const vector of vectors) for (const value of vector) { bytes.writeFloatLE(value, offset); offset += 4; }
  const packed = bytes.toString('base64');
  const message = Buffer.from(`managed-v1:${job.jobId}:${job.leaseId}:${revision}:${job.digest}:${packed}`, 'ascii');
  return client(`/jobs/${job.jobId}/complete`, { leaseId: job.leaseId, vectors: packed,
    signature: sign(null, message, signer).toString('base64') });
}

async function work(once) {
  const identity = await input();
  const origin = baseOrigin(identity.origin);
  if (!id(identity.workerId) || !/^[A-Za-z0-9_-]{43}$/.test(identity.credential)) throw new Error('Invalid worker configuration');
  const signer = createPrivateKey({ key: Buffer.from(identity.key, 'base64'), type: 'pkcs8', format: 'der' });
  if (signer.asymmetricKeyType !== 'ed25519') throw new Error('Invalid worker signing identity');
  const client = api(origin, identity);
  let engine, failures = 0;
  try {
    do {
      try {
        if (!engine && hasRoom()) engine = await nativeModel();
        const started = performance.now();
        const claim = await client('/claim', { model: revision, ready: Boolean(engine && hasRoom()) });
        if (claim.status === 401) return;
        if (![200, 204].includes(claim.status)) throw new Error('Coordinator unavailable');
        if (claim.status === 200) await execute(client, engine, signer, claim.data, started);
        failures = 0;
      } catch {
        if (once) throw new Error('Worker trial did not complete');
        failures++;
      }
      if (!once) await sleep(Math.min(30000, 2000 * 2 ** Math.min(failures, 4)) + Math.random() * 500);
    } while (!once);
  } finally { await engine?.model.release(); }
}

try {
  const mode = process.argv[2];
  if (mode === 'prepare') await readAssets(true);
  else if (mode === 'enroll') await register();
  else if (mode === 'run' || mode === 'once') await work(mode === 'once');
  else throw new Error('Unknown worker command');
} catch {
  process.stderr.write('SmartHR managed worker could not complete the requested action.\n');
  process.exitCode = 1;
}
