import { createReadStream } from 'node:fs';
import { stat } from 'node:fs/promises';
import { createServer } from 'node:http';
import { extname, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

export const revision = '1110a243fdf4706b3f48f1d95db1a4f5529b4d41';
const here = fileURLToPath(new URL('.', import.meta.url));
const pdf = fileURLToPath(new URL('../../static/vendor/pdfjs-6.5.438/', import.meta.url));
const types = { '.html': 'text/html', '.mjs': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.wasm': 'application/wasm' };
const paths = new Set(['index.html', 'pilot.css', 'pilot.mjs', 'eligibility.mjs', 'embed.worker.mjs', 'failover.mjs', 'minilm.mjs']);
const roots = new Map([
  ['pdf', pdf],
  ['assets', resolve(here, 'assets')],
  ['ort', resolve(here, 'node_modules/onnxruntime-web/dist')],
  ['tokenizer', resolve(here, 'node_modules/@huggingface/tokenizers/dist')],
]);

export async function listen(port = 0, { isolated = false } = {}) {
  const server = createServer(async (req, res) => {
    try {
      if (req.method !== 'GET') return res.writeHead(405).end();
      const pathname = new URL(req.url, 'http://127.0.0.1').pathname;
      const [, namespace, ...parts] = pathname.split('/');
      let path;
      if (pathname === '/minilm.mjs') {
        path = fileURLToPath(new URL('../../desktop-worker/minilm.mjs', import.meta.url));
      } else if (pathname === '/' || (!parts.length && paths.has(namespace))) {
        path = resolve(here, namespace || 'index.html');
      } else {
        const root = roots.get(namespace);
        if (!root || !parts.length || parts.some(p => !/^[\w.-]+$/.test(p) || p.startsWith('.'))) return res.writeHead(404).end();
        path = resolve(root, ...parts);
        if (!path.startsWith(resolve(root) + sep)) return res.writeHead(404).end();
      }
      const file = await stat(path);
      if (!file.isFile()) return res.writeHead(404).end();
      res.writeHead(200, {
        'Content-Type': types[extname(path)] || 'application/octet-stream',
        'Content-Length': file.size,
        'Content-Security-Policy': "default-src 'none'; script-src 'self' 'wasm-unsafe-eval'; worker-src 'self'; style-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
        'X-Content-Type-Options': 'nosniff',
        'Cache-Control': namespace === 'assets' || namespace === 'ort' ? 'private, max-age=3600' : 'no-store',
        ...(isolated ? { 'Cross-Origin-Opener-Policy': 'same-origin', 'Cross-Origin-Embedder-Policy': 'require-corp' } : {}),
      });
      createReadStream(path).on('error', () => res.destroy()).pipe(res);
    } catch {
      res.writeHead(404).end();
    }
  });
  await new Promise((ok, fail) => server.once('error', fail).listen(port, '127.0.0.1', ok));
  return { server, url: `http://127.0.0.1:${server.address().port}` };
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const { url } = await listen(8765);
  console.log(`CV processing pilot: ${url}`);
}
