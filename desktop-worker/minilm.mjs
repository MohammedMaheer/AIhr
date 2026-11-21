const maxTokens = 256;

export async function encodeMiniLm({ ort, tokenizer, model }, texts) {
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
  // Right-padding is masked in the model and excluded from normalized pooling.
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
