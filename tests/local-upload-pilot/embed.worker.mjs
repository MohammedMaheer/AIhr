import * as ort from '/ort/ort.wasm.min.mjs';
import { Tokenizer } from '/tokenizer/tokenizers.min.mjs';

ort.env.wasm.numThreads = 1;
ort.env.wasm.wasmPaths = `${self.location.origin}/ort/`;
ort.env.wasm.proxy = false;
const maxTokens = 256;
let runtime;

async function load() {
  async function json(name) {
    const response = await fetch(`/assets/${name}`);
    if (!response.ok) throw new Error('Tokenizer unavailable');
    return response.json();
  }
  const [spec, config, model] = await Promise.all([
    json('tokenizer.json'),
    json('tokenizer_config.json'),
    ort.InferenceSession.create('/assets/model.onnx', { executionProviders: ['wasm'] }),
  ]);
  return { tokenizer: new Tokenizer(spec, config), model };
}

self.addEventListener('message', async ({ data: { id, text } }) => {
  try {
    const { tokenizer, model } = await (runtime ||= load());
    const start = performance.now();
    const { ids } = tokenizer.encode(text.trim(), { add_special_tokens: true });
    const tokens = ids.length <= maxTokens ? ids : [...ids.slice(0, maxTokens - 1), ids.at(-1)];
    const input = values => new ort.Tensor('int64', BigInt64Array.from(values, BigInt), [1, tokens.length]);
    const inputs = { input_ids: input(tokens), attention_mask: input(tokens.map(() => 1)) };
    if (model.inputNames.includes('token_type_ids')) inputs.token_type_ids = input(tokens.map(() => 0));
    const output = await model.run(inputs);
    const tensor = output.last_hidden_state || output[model.outputNames[0]];
    if (tensor.dims.join(',') !== `1,${tokens.length},384`) throw new Error('Unexpected model shape');
    // Single unpadded sequence: each token has attention mask 1.
    const average = new Float64Array(384);
    for (let i = 0; i < tensor.data.length; i++) average[i % 384] += tensor.data[i] / tokens.length;
    const norm = Math.hypot(...average);
    if (!(norm > 0) || !Number.isFinite(norm)) throw new Error('Invalid vector');
    const vector = Float32Array.from(average, v => v / norm);
    self.postMessage({ id, vector, modelMs: performance.now() - start }, [vector.buffer]);
  } catch (error) {
    console.error('Local embedding unavailable', error.name);
    self.postMessage({ id });
  }
});
