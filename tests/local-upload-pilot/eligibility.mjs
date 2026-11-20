export function deviceFallback() {
  const { userAgent, userAgentData, maxTouchPoints, deviceMemory, hardwareConcurrency, connection, onLine } = navigator;
  if (onLine === false) return 'offline';
  const touchDevice = maxTouchPoints > 0 && (
    matchMedia('(pointer: coarse)').matches || /Macintosh/i.test(userAgent)
  );
  if (userAgentData?.mobile || /Android|Mobile|iP(?:hone|ad|od)/i.test(userAgent) || touchDevice) {
    return 'mobile-device';
  }
  // These hints are deliberately conservative: they do not measure free RAM or CPU speed.
  if (!(deviceMemory >= 8 && hardwareConcurrency >= 4)) return 'low-or-unknown-capacity';
  if (connection?.saveData || /^(?:slow-2g|2g|3g)$/.test(connection?.effectiveType ?? '')) return 'network-preference';
  if (!globalThis.isSecureContext || typeof Worker !== 'function' ||
      typeof globalThis.WebAssembly?.instantiate !== 'function' || typeof globalThis.crypto?.randomUUID !== 'function') {
    return 'unsupported-runtime';
  }
  return null;
}
