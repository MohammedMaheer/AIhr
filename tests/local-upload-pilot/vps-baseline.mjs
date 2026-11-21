import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { readFile } from 'node:fs/promises';
import { revision } from './server.mjs';

export const host = process.env.PILOT_BASELINE_SSH;
export const image = process.env.PILOT_BASELINE_IMAGE;

export async function runBaseline(operation, data, { cpus = 1, threads = 1 } = {}) {
  assert(['compare', 'embedding_baseline', 'embedding_rank'].includes(operation));
  assert(host && /^[\w.-]+@[\w.-]+$/.test(host), 'Set PILOT_BASELINE_SSH to an authorized SSH login');
  assert(image && /^[\w.-]+:[\w.-]+$/.test(image), 'Set PILOT_BASELINE_IMAGE to the verified cached SmartHR image');
  const payload = Buffer.from(JSON.stringify({ ...data, revision })).toString('base64');
  const source = await readFile(new URL('./baseline.py', import.meta.url), 'utf8');
  const result = spawnSync('ssh', [
    '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=8', host,
    'docker', 'run', '--rm', '-i', '--pull=never', '--network=none', '--read-only', '--user=65534:65534',
    '--cap-drop=ALL', '--security-opt=no-new-privileges', '--tmpfs=/tmp:rw,noexec,nosuid,size=96m',
    `--cpus=${cpus}`, '--memory=1500m', '--memory-swap=1500m', '--pids-limit=64',
    '-e', 'HF_HUB_OFFLINE=1', '-e', 'TRANSFORMERS_OFFLINE=1', '-e', `OMP_NUM_THREADS=${threads}`,
    '-e', `MKL_NUM_THREADS=${threads}`, '-e', 'OPENBLAS_NUM_THREADS=1', '-e', 'SMARTHR_QUERY_EMBED_CACHE_MAX=0',
    '-e', 'SMARTHR_EMBED_MODEL=sentence-transformers/all-MiniLM-L6-v2',
    '-e', 'SENTENCE_TRANSFORMERS_HOME=/app/.st_cache',
    '-v', 'smarthr_stcache:/app/.st_cache:ro', '--entrypoint=timeout', image, '120', 'python', '-',
  ], {
    input: `${source}\n${operation}(json.loads(base64.b64decode('${payload}')))\n`,
    encoding: 'utf8', timeout: 135000, maxBuffer: 8 * 1024 * 1024,
  });
  if (result.error) throw result.error;
  assert.equal(result.status, 0, result.stderr || result.stdout);
  const report = result.stdout.split('\n').find(line => line.startsWith('PILOT_REPORT:'));
  assert(report, 'No isolated baseline report');
  return JSON.parse(report.slice('PILOT_REPORT:'.length));
}
