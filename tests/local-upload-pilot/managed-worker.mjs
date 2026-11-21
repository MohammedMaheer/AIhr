import { createHash, createPublicKey, generateKeyPairSync, sign, verify } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import { createInterface } from 'node:readline';
import { Tokenizer } from '@huggingface/tokenizers';
import * as ort from 'onnxruntime-node';
import { encodeMiniLm } from '../../desktop-worker/minilm.mjs';
import { revision } from './server.mjs';

// This lab worker is isolated from recruiter/browser sessions and has no network client.
const tenant = 'owner';
const { privateKey, publicKey } = generateKeyPairSync('ed25519');
const publicDer = publicKey.export({ type: 'spki', format: 'der' });
const assets = [
  { sha256: '6fd5d72fe4589f189f8ebc006442dbb529bb7ce38f8082112682524616046452', name: 'model.onnx' },
  { sha256: 'be50c3628f2bf5bb5e3a7f17b1f74611b2561a3a27eeab05e5aa30f411572037', name: 'tokenizer.json' },
  { sha256: 'acb92769e8195aabd29b7b2137a9e6d6e25c476a4f15aa4355c233426c61576b', name: 'tokenizer_config.json' },
];
const [graph, spec, config] = await Promise.all(assets.map(async ({ name, sha256 }) => {
  const bytes = await readFile(new URL(`./assets/${name}`, import.meta.url));
  if (createHash('sha256').update(bytes).digest('hex') !== sha256) throw new Error('Model asset checksum mismatch');
  return bytes;
}));
const engine = { ort, tokenizer: new Tokenizer(JSON.parse(spec), JSON.parse(config)),
  model: await ort.InferenceSession.create(graph, { executionProviders: ['cpu'], intraOpNumThreads: 4, interOpNumThreads: 1 }) };
await encodeMiniLm(engine, ['Warm managed worker with synthetic text.']);

function write(data) { process.stdout.write(`MANAGED:${JSON.stringify(data)}\n`); }
function signText(label, value) { return sign(null, Buffer.from(`${label}:${value}`, 'ascii'), privateKey).toString('base64'); }
function digest(bytes) { return createHash('sha256').update(bytes).digest('hex'); }

async function calculate(lease, coordinator) {
  const manifest = Buffer.from(lease.manifest, 'base64');
  const claims = JSON.parse(manifest.toString('utf8'));
  if (!verify(null, Buffer.concat([Buffer.from('lease:'), manifest]), coordinator, Buffer.from(lease.auth, 'base64')) ||
      digest(manifest) !== lease.binding || claims.model !== revision || claims.tenant !== tenant || claims.workerId !== digest(publicDer) ||
      !(claims.expiresAt > Date.now()) || !Array.isArray(lease.texts) || !lease.texts.length || lease.texts.length > 32 ||
      claims.documents.length !== lease.texts.length || lease.texts.some((text, i) => typeof text !== 'string' ||
        text.length < 30 || text.length > 80000 || digest(text) !== claims.documents[i])) {
    throw new Error('Invalid or expired job');
  }
  const started = performance.now();
  const vectors = [];
  for (let offset = 0; offset < lease.texts.length; offset += 8) {
    vectors.push(...await encodeMiniLm(engine, lease.texts.slice(offset, offset + 8)));
  }
  const bytes = Buffer.alloc(vectors.length * 384 * 4);
  let offset = 0;
  for (const vector of vectors) for (const value of vector) { bytes.writeFloatLE(value, offset); offset += 4; }
  const packed = bytes.toString('base64');
  return { packed, binding: lease.binding, signature: signText('result', `${lease.binding}:${packed}`),
    managedEmbeddingMs: performance.now() - started };
}

write({ ready: true, publicKey: publicDer.toString('base64'), model: revision });
let last = '';
let coordinator;
let heartbeat = 0;
try {
  for await (const line of createInterface({ input: process.stdin, crlfDelay: Infinity })) {
    const command = JSON.parse(line);
    if (command.op === 'close') break;
    try {
      if (command.op === 'configure' && !coordinator) {
        const key = createPublicKey({ key: Buffer.from(command.coordinator, 'base64'), format: 'der', type: 'spki' });
        if (key.asymmetricKeyType !== 'ed25519') throw new Error('Invalid coordinator identity');
        coordinator = key;
        write({ configured: true });
      } else if (command.op === 'heartbeat' && coordinator && typeof command.ready === 'boolean') {
        const sequence = ++heartbeat;
        write({ sequence, ready: command.ready, signature: signText('presence', `${sequence}:${Number(command.ready)}`) });
      } else if (command.op === 'prove' && coordinator && /^[a-f0-9]{64}$/.test(command.challenge) &&
          verify(null, Buffer.from(`offer:${command.challenge}`, 'ascii'), coordinator, Buffer.from(command.auth, 'base64'))) {
        write({ signature: signText('claim', command.challenge) });
      } else if (command.op === 'embed' && coordinator && command.lease.binding !== last) {
        const result = await calculate(command.lease, coordinator);
        last = command.lease.binding;
        write(result);
      } else write({ refused: true });
    } catch { write({ refused: true }); }
  }
} finally {
  await engine.model.release();
}
