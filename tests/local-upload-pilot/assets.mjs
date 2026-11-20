import { createHash } from 'node:crypto';
import { createReadStream, createWriteStream } from 'node:fs';
import { mkdir, rename, rm } from 'node:fs/promises';
import { pipeline } from 'node:stream/promises';
import { revision } from './server.mjs';

const modelURL = `https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2/resolve/${revision}/`;
const assets = new URL('./assets/', import.meta.url);
const files = [
  { sha256: '6fd5d72fe4589f189f8ebc006442dbb529bb7ce38f8082112682524616046452', path: 'onnx/model.onnx' },
  { sha256: 'be50c3628f2bf5bb5e3a7f17b1f74611b2561a3a27eeab05e5aa30f411572037', path: 'tokenizer.json' },
  { sha256: 'acb92769e8195aabd29b7b2137a9e6d6e25c476a4f15aa4355c233426c61576b', path: 'tokenizer_config.json' },
];
if (process.argv.includes('--benchmark')) {
  files.push(
    { sha256: '1de3905029190b398c7d300b530e320cf4b5e7d3dfb9af1429ebd73fd9a16faf', path: 'onnx/model_O2.onnx' },
    { sha256: 'b941bf19f1f1283680f449fa6a7336bb5600bdcd5f84d10ddc5cd72218a0fd21', path: 'onnx/model_quint8_avx2.onnx' },
  );
}

await mkdir(assets, { recursive: true });
for (const { path, sha256 } of files) {
  const name = path.split('/').at(-1);
  const destination = new URL(name, assets);
  const temp = new URL(`${name}.part`, assets);
  async function matches(url) {
    const hash = createHash('sha256');
    for await (const bytes of createReadStream(url)) hash.update(bytes);
    return hash.digest('hex') === sha256;
  }
  if (await matches(destination).catch(() => false)) {
    console.log(`${name}: verified (cached)`);
    continue;
  }
  try {
    const response = await fetch(modelURL + path, { signal: AbortSignal.timeout(240000) });
    if (!response.ok) throw new Error(`Download failed: ${name} (${response.status})`);
    await pipeline(response.body, createWriteStream(temp));
    if (!await matches(temp)) throw new Error(`Checksum mismatch: ${name}`);
    await rename(temp, destination);
    console.log(`${name}: verified`);
  } finally {
    await rm(temp, { force: true });
  }
}
