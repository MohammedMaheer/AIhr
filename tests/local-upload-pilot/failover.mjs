import { deviceFallback } from './eligibility.mjs';
import { embed, hasWarmModel } from './pilot.mjs';

// A staged lease represents an original already saved by the coordinator.
// Browser output is evidence for comparison, never a write to the shared index.
export function selectAssistRoute(lease, settings, now = Date.now()) {
  if (!settings.online || ['unreachable', 'offline'].includes(lease?.state)) return 'wait-for-vps';
  if (!settings.optedIn || !settings.eligible || !settings.warm ||
      lease?.state !== 'busy' || lease.saved !== true || lease.canAssist !== true ||
      typeof lease.jobId !== 'string' || !/^[\w-]{8,80}$/.test(lease.jobId) ||
      !Number.isFinite(lease.expiresAt) || lease.expiresAt <= now ||
      typeof lease.canonicalText !== 'string' || lease.canonicalText.trim().length < 30 ||
      lease.canonicalText.length > 80000) {
    return 'vps';
  }
  return 'desktop';
}

export async function assistSavedJob(lease, { optedIn = false, signal } = {}) {
  const settings = () => ({ optedIn, online: navigator.onLine !== false,
    eligible: !document.hidden && !deviceFallback() && !signal?.aborted, warm: hasWarmModel() });
  const route = selectAssistRoute(lease, settings());
  if (route !== 'desktop') return { state: route };

  const controller = new AbortController();
  const abort = () => controller.abort();
  const timer = setTimeout(abort, Math.min(1500, lease.expiresAt - Date.now()));
  function visibilityChanged() { if (document.hidden) abort(); }
  signal?.addEventListener('abort', abort, { once: true });
  document.addEventListener('visibilitychange', visibilityChanged);
  window.addEventListener('offline', abort, { once: true });
  window.addEventListener('pagehide', abort, { once: true });
  try {
    const { vector } = await embed(lease.canonicalText, controller.signal);
    if (!controller.signal.aborted && selectAssistRoute(lease, settings()) === 'desktop') {
      return { state: 'shadow-result', jobId: lease.jobId, vector };
    }
    return { state: navigator.onLine === false ? 'wait-for-vps' : 'vps' };
  } catch {
    return { state: navigator.onLine === false ? 'wait-for-vps' : 'vps' };
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener('abort', abort);
    document.removeEventListener('visibilitychange', visibilityChanged);
    window.removeEventListener('offline', abort);
    window.removeEventListener('pagehide', abort);
  }
}
