import { createHash } from 'node:crypto';
import { createWriteStream } from 'node:fs';
import { mkdir, readFile, rename, rm } from 'node:fs/promises';
import { pipeline } from 'node:stream/promises';

export const revision = '1110a243fdf4706b3f48f1d95db1a4f5529b4d41';
export const sha = bytes => createHash('sha256').update(bytes).digest('hex');
export const files = [
  { sha256: '6fd5d72fe4589f189f8ebc006442dbb529bb7ce38f8082112682524616046452', path: 'onnx/model.onnx' },
  { sha256: 'be50c3628f2bf5bb5e3a7f17b1f74611b2561a3a27eeab05e5aa30f411572037', path: 'tokenizer.json' },
  { sha256: 'acb92769e8195aabd29b7b2137a9e6d6e25c476a4f15aa4355c233426c61576b', path: 'tokenizer_config.json' },
];
const dir = new URL('./assets/', import.meta.url);

export async function readAssets(download = false) {
  const bytes = [];
  if (download) await mkdir(dir, { recursive: true });
  for (const item of files) {
    const target = new URL(item.path.split('/').at(-1), dir);
    let data = await readFile(target).catch(() => null);
    if (!data || sha(data) !== item.sha256) {
      if (!download) throw new Error('Pinned model is missing or damaged');
      const part = new URL(target.href + '.part');
      try {
        const url = `https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2/resolve/${revision}/${item.path}`;
        const response = await fetch(url, { signal: AbortSignal.timeout(240000) });
        if (!response.ok) throw new Error('Model download unavailable');
        await pipeline(response.body, createWriteStream(part));
        data = await readFile(part);
        if (sha(data) !== item.sha256) throw new Error('Pinned model integrity check failed');
        await rename(part, target);
      } finally { await rm(part, { force: true }); }
    }
    bytes.push(data);
  }
  return bytes;
}
