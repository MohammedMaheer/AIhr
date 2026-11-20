import { Tokenizer } from '/tokenizer/tokenizers.min.mjs';

const maxTokens = 256;
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

async function encode({ ort, tokenizer, model }, texts) {
  const rows = texts.map(text => {
    const { ids } = tokenizer.encode(text.trim(), { add_special_tokens: true });
    return ids.length <= maxTokens ? ids : [...ids.slice(0, maxTokens - 1), ids.at(-1)];
  });
  const width = Math.max(...rows.map(tokens => tokens.length));
  const ids = new BigInt64Array(rows.length * width);
  const mask = new BigInt64Array(ids.length);
  rows.forEach((tokens, i) => {
    ids.set(BigInt64Array.from(tokens, BigInt), i * width);
    mask.fill(1n, i * width, i * width + tokens.length);
  });
  const input = values => new ort.Tensor('int64', values, [rows.length, width]);
  const inputs = { input_ids: input(ids), attention_mask: input(mask) };
  if (model.inputNames.includes('token_type_ids')) inputs.token_type_ids = input(new BigInt64Array(ids.length));
  const output = await model.run(inputs);
  const tensor = output.last_hidden_state || output[model.outputNames[0]];
  if (tensor.dims.join(',') !== `${rows.length},${width},384`) throw new Error('Unexpected model shape');
  const data = tensor.data;
  // Right-padding is masked in the model and excluded from mean pooling.
  return rows.map((tokens, row) => {
    const sum = new Float64Array(384);
    for (let start = row * width * 384, stop = start + tokens.length * 384; start < stop; start += 384) {
      for (let j = 0; j < 384; j++) sum[j] += data[start + j];
    }
    const norm = Math.hypot(...sum);
    if (!(norm > 0) || !Number.isFinite(norm)) throw new Error('Invalid vector');
    return Float32Array.from(sum, v => v / norm);
  });
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
    const vectors = await encode(engine, items);
    const modelMs = performance.now() - start;
    const payload = batch ? { vectors, gpuVendor: engine.gpuVendor } : { vector: vectors[0] };
    self.postMessage({ id, ...payload, modelMs }, vectors.map(vector => vector.buffer));
  } catch (error) {
    self.postMessage({ id, error: benchmark ? String(error.message).slice(0, 240) : 'Local embedding unavailable' });
  }
});
