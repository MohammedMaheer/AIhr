import { Tokenizer } from '/tokenizer/tokenizers.min.mjs';
import { encodeMiniLm } from './minilm.mjs';

const variants = {
  'wasm-1': { threads: 1, asset: 'model.onnx' },
  'wasm-4': { threads: 4, asset: 'model.onnx' },
  'wasm-o2': { threads: 4, asset: 'model_O2.onnx' },
  'wasm-int8': { threads: 4, asset: 'model_quint8_avx2.onnx' },
  'webgpu': { threads: 1, asset: 'model.onnx', gpu: true },
};
const benchmark = new URL(self.location.href).searchParams.get('benchmark');
let runtime;

async function load() {
  if (benchmark && !self.crossOriginIsolated) throw new Error('Benchmark requires an isolated page');
  const variant = variants[benchmark || 'wasm-1'];
  const ort = variant.gpu ? await import('/ort/ort.webgpu.min.mjs') : await import('/ort/ort.wasm.min.mjs');
  ort.env.wasm.numThreads = variant.threads;
  ort.env.wasm.wasmPaths = `${self.location.origin}/ort/`;
  ort.env.wasm.proxy = false;
  let gpuVendor;
  if (variant.gpu) {
    const adapter = await navigator.gpu?.requestAdapter({ powerPreference: 'high-performance' });
    const info = adapter?.info;
    if (!info?.vendor || info.isFallbackAdapter || adapter.isFallbackAdapter ||
        /swiftshader|software|llvmpipe|microsoft/i.test(`${info.vendor} ${info.architecture} ${info.description}`)) {
      throw new Error('No identifiable hardware WebGPU adapter');
    }
    ort.env.webgpu.adapter = adapter;
    gpuVendor = info.vendor;
  }
  async function json(name) {
    const response = await fetch(`/assets/${name}`);
    if (!response.ok) throw new Error('Tokenizer unavailable');
    return response.json();
  }
  const [spec, config, model] = await Promise.all([
    json('tokenizer.json'),
    json('tokenizer_config.json'),
    ort.InferenceSession.create(`/assets/${variant.asset}`, { executionProviders: [variant.gpu ? 'webgpu' : 'wasm'] }),
  ]);
  return { ort, tokenizer: new Tokenizer(spec, config), model, gpuVendor };
}

self.addEventListener('message', async ({ data: { id, text, texts } }) => {
  try {
    const batch = benchmark && Array.isArray(texts);
    const items = batch ? texts : [text];
    if (!items.length || items.length > 16 || items.some(t => typeof t !== 'string' || t.length > 80000)) {
      throw new Error('Invalid input');
    }
    const engine = await (runtime ||= load());
    const start = performance.now();
    const vectors = await encodeMiniLm(engine, items);
    const modelMs = performance.now() - start;
    const payload = batch ? { vectors, gpuVendor: engine.gpuVendor } : { vector: vectors[0] };
    self.postMessage({ id, ...payload, modelMs }, vectors.map(vector => vector.buffer));
  } catch (error) {
    self.postMessage({ id, error: benchmark ? String(error.message).slice(0, 240) : 'Local embedding unavailable' });
  }
});
