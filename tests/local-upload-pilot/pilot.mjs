const byteLimit = 10 * 1024 * 1024;
const pageLimit = 20;
const textLimit = 80000;
const deadlineMs = 30000;
let pdf;
let parser;
let embedder;

async function extractPdf(file) {
  const data = new Uint8Array(await file.arrayBuffer());
  pdf ||= await import('/pdf/build/pdf.mjs');
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
  let timedOut = false;
  try {
    return await Promise.race([
      (async () => {
        const doc = await task.promise;
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
      })(),
      new Promise((_, reject) => {
        timer = setTimeout(() => {
          timedOut = true;
          reject(new Error('timeout'));
        }, deadlineMs);
      }),
    ]);
  } finally {
    clearTimeout(timer);
    if (timedOut) {
      currentParser.worker.destroy();
      currentParser.port.terminate();
      if (parser === currentParser) parser = null;
    } else {
      await task.destroy();
    }
  }
}

export async function embed(text) {
  const worker = embedder ||= new Worker('/embed.worker.mjs', { type: 'module' });
  return new Promise((resolve, reject) => {
    const id = crypto.randomUUID();
    function cleanup() {
      clearTimeout(timer);
      worker.removeEventListener('message', onMessage);
      worker.removeEventListener('error', onError);
    }
    function onError() {
      cleanup();
      worker.terminate();
      if (embedder === worker) embedder = null;
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
    worker.postMessage({ id, text });
  });
}

export async function processFile(file) {
  if (!/\.pdf$/i.test(file.name)) return { fallback: 'unsupported-type' };
  if (!file.size || file.size > byteLimit) return { fallback: 'file-size' };
  const start = performance.now();
  let text;
  try {
    text = await extractPdf(file);
  } catch (error) {
    return { fallback: error.message === 'page-limit' ? 'page-limit' : 'pdf-unavailable' };
  }
  const extracted = performance.now();
  if (text.trim().length < 30) return { fallback: 'insufficient-text' };
  try {
    const { vector, modelMs } = await embed(text);
    return { text, vector, modelMs, extractMs: extracted - start, totalMs: performance.now() - start };
  } catch {
    return { fallback: 'model-unavailable' };
  }
}

const form = document.querySelector('form');
const input = document.querySelector('#files');
const button = form.querySelector('button');
const status = document.querySelector('#status');
const results = document.querySelector('#results');
form.addEventListener('submit', async event => {
  event.preventDefault();
  if (button.disabled) return;
  const files = [...input.files];
  if (files.length > 20) {
    status.textContent = 'Choose 20 files or fewer for this test.';
    return;
  }
  input.disabled = button.disabled = true;
  results.replaceChildren();
  let completed = 0;
  try {
    for (const [i, file] of files.entries()) {
      status.textContent = `Processing ${i + 1} of ${files.length} on this device...`;
      const result = await processFile(file);
      const li = document.createElement('li');
      if (!result.fallback) completed++;
      li.textContent = `${file.name}: ${result.fallback ? 'Use the regular upload' : `Processed locally in ${Math.round(result.totalMs)} ms`}`;
      results.append(li);
    }
    status.textContent = `${completed} of ${files.length} processed locally. No files were uploaded.`;
  } finally {
    input.disabled = button.disabled = false;
  }
});
