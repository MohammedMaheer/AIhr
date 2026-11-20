import { deviceFallback } from './eligibility.mjs';

const byteLimit = 10 * 1024 * 1024;
const pageLimit = 20;
const textLimit = 80000;
const deadlineMs = 30000;
let pdf;
let parser;
let embedder;

function closeParser(current = parser) {
  if (!current || parser !== current) return;
  current.worker.destroy();
  current.port.terminate();
  parser = null;
}

function closeEmbedder(worker = embedder) {
  if (!worker || embedder !== worker) return;
  worker.terminate();
  embedder = null;
}

async function readPages(doc) {
  if (doc.numPages > pageLimit) throw new Error('page-limit');
  const pages = [];
  let remaining = textLimit;
  for (let n = 1; n <= doc.numPages && remaining > 0; n++) {
    const page = await doc.getPage(n);
    const content = await page.getTextContent();
    const parts = [];
    for (const item of content.items) {
      if (typeof item.str !== 'string') continue;
      const part = item.str + (item.hasEOL ? '\n' : '');
      parts.push(part.slice(0, remaining));
      remaining -= part.length;
      if (remaining <= 0) break;
    }
    pages.push(parts.join('').trim());
    remaining--;
    page.cleanup();
  }
  return Array.from(pages.join('\n')).slice(0, textLimit).join('');
}

async function extractPdf(file, signal) {
  signal?.throwIfAborted();
  const data = new Uint8Array(await file.arrayBuffer());
  signal?.throwIfAborted();
  pdf ||= await import('/pdf/build/pdf.mjs');
  signal?.throwIfAborted();
  if (!parser) {
    const port = new Worker('/pdf/build/pdf.worker.mjs', { type: 'module' });
    parser = { port, worker: pdf.PDFWorker.create({ port }) };
  }
  const currentParser = parser;
  const task = pdf.getDocument({
    data, worker: currentParser.worker, stopAtErrors: true, useWasm: false,
    disableWorkerRendering: true, disableFontFace: true,
    isOffscreenCanvasSupported: false, isImageDecoderSupported: false,
    cMapUrl: `${location.origin}/pdf/web/cmaps/`, standardFontDataUrl: `${location.origin}/pdf/web/standard_fonts/`,
  });
  let timer;
  let interrupted = false;
  let interrupt;
  try {
    return await Promise.race([
      (async () => {
        try {
          return await readPages(await task.promise);
        } finally {
          if (!interrupted) await task.destroy();
        }
      })(),
      new Promise((_, reject) => {
        interrupt = () => {
          interrupted = true;
          reject(new Error('interrupted'));
        };
        signal?.addEventListener('abort', interrupt, { once: true });
        timer = setTimeout(interrupt, deadlineMs);
      }),
    ]);
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener('abort', interrupt);
    if (interrupted) closeParser(currentParser);
  }
}

export async function embed(text, signal) {
  signal?.throwIfAborted();
  if (document.hidden || deviceFallback()) throw new Error('Use the regular upload');
  const worker = embedder ||= new Worker('/embed.worker.mjs', { type: 'module' });
  return new Promise((resolve, reject) => {
    const id = crypto.randomUUID();
    function cleanup() {
      clearTimeout(timer);
      worker.removeEventListener('message', onMessage);
      worker.removeEventListener('error', onError);
      signal?.removeEventListener('abort', onError);
    }
    function onError() {
      cleanup();
      closeEmbedder(worker);
      reject(new Error('model-unavailable'));
    }
    function onMessage(event) {
      if (event.data.id !== id) return;
      if (!event.data.vector) return onError();
      cleanup();
      resolve(event.data);
    }
    const timer = setTimeout(onError, deadlineMs);
    worker.addEventListener('message', onMessage);
    worker.addEventListener('error', onError);
    signal?.addEventListener('abort', onError, { once: true });
    worker.postMessage({ id, text });
  });
}

export async function processFile(file, signal) {
  if (document.hidden || signal?.aborted) return { fallback: 'interrupted' };
  const fallback = deviceFallback();
  if (fallback) return { fallback };
  if (!/\.pdf$/i.test(file.name)) return { fallback: 'unsupported-type' };
  if (!file.size || file.size > byteLimit) return { fallback: 'file-size' };
  const start = performance.now();
  let text;
  try {
    text = await extractPdf(file, signal);
  } catch (error) {
    if (signal?.aborted) return { fallback: 'interrupted' };
    return { fallback: error.message === 'page-limit' ? 'page-limit' : 'pdf-unavailable' };
  }
  const extracted = performance.now();
  if (text.trim().length < 30) return { fallback: 'insufficient-text' };
  try {
    const { vector, modelMs } = await embed(text, signal);
    return { text, vector, modelMs, extractMs: extracted - start, totalMs: performance.now() - start };
  } catch {
    return { fallback: signal?.aborted ? 'interrupted' : 'model-unavailable' };
  }
}

const form = document.querySelector('form');
const input = document.querySelector('#files');
const button = form.querySelector('[type="submit"]');
const stop = document.querySelector('#stop');
const status = document.querySelector('#status');
const results = document.querySelector('#results');
const ready = status.textContent;
const regularUpload = 'Use the regular upload on this device. No files were uploaded.';
const offline = 'Reconnect to the internet to continue. No files were uploaded.';
let active;

function resetControls() {
  const fallback = deviceFallback();
  input.disabled = button.disabled = Boolean(fallback);
  stop.hidden = true;
  if (fallback) status.textContent = fallback === 'offline' ? offline : regularUpload;
  else if ([regularUpload, offline].includes(status.textContent)) status.textContent = ready;
}

function stopProcessing() {
  active?.abort();
  closeParser();
  closeEmbedder();
}

stop.addEventListener('click', stopProcessing);
document.addEventListener('visibilitychange', () => { if (document.hidden) stopProcessing(); });
window.addEventListener('pagehide', stopProcessing);
function connectionChanged() {
  if (!active) resetControls();
  else if (deviceFallback()) stopProcessing();
}
window.addEventListener('online', connectionChanged);
window.addEventListener('offline', connectionChanged);
navigator.connection?.addEventListener?.('change', connectionChanged);
resetControls();

form.addEventListener('submit', async event => {
  event.preventDefault();
  if (active || document.hidden) return;
  if (deviceFallback()) return resetControls();
  const files = [...input.files];
  if (files.length > 20) {
    status.textContent = 'Choose 20 files or fewer for this test.';
    return;
  }
  input.disabled = button.disabled = true;
  stop.hidden = false;
  active = new AbortController();
  results.replaceChildren();
  let completed = 0;
  let modelFailed = false;
  try {
    for (const [i, file] of files.entries()) {
      if (active.signal.aborted) break;
      status.textContent = `Processing ${i + 1} of ${files.length} on this device...`;
      const result = modelFailed ? { fallback: 'model-unavailable' } : await processFile(file, active.signal);
      if (active.signal.aborted) break;
      modelFailed ||= result.fallback === 'model-unavailable';
      const li = document.createElement('li');
      if (!result.fallback) completed++;
      li.textContent = `${file.name}: ${result.fallback ? 'Use the regular upload' : `Processed locally in ${Math.round(result.totalMs)} ms`}`;
      results.append(li);
    }
    status.textContent = active.signal.aborted
      ? 'Local processing stopped. Use the regular upload to continue. No files were uploaded.'
      : `${completed} of ${files.length} processed locally. No files were uploaded.`;
  } finally {
    active = null;
    resetControls();
  }
});
