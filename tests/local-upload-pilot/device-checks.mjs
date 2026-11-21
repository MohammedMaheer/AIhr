import assert from 'node:assert/strict';
import { devices } from 'playwright';

const laptop = { deviceMemory: 8, hardwareConcurrency: 8, connection: { saveData: false, effectiveType: '4g' } };
const tabletDesktopUA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Version/18.6 Safari/605.1.15';
const cases = [
  { name: 'Android phone', context: devices['Pixel 7'], result: 'mobile-device' },
  { name: 'iPhone', context: devices['iPhone 13'], result: 'mobile-device' },
  { name: 'wide Android tablet', context: { ...devices['Pixel 7'], isMobile: false,
    userAgent: 'Mozilla/5.0 (Linux; Android 14; Tablet) AppleWebKit/537.36 Chrome/142.0.0.0 Safari/537.36',
    viewport: { width: 1280, height: 800 } }, result: 'mobile-device' },
  { name: 'desktop-mode iPad', context: { ...devices['iPad Pro 11'], isMobile: false,
    userAgent: tabletDesktopUA }, result: 'mobile-device' },
  { name: 'touch-first desktop UA', context: { hasTouch: true, isMobile: true,
    userAgent: 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/142.0.0.0 Safari/537.36' },
    result: 'mobile-device' },
  { name: 'low RAM', hints: { deviceMemory: 4 }, result: 'low-or-unknown-capacity' },
  { name: 'two logical cores', hints: { hardwareConcurrency: 2 }, result: 'low-or-unknown-capacity' },
  { name: 'no RAM hint', noMemory: true, result: 'low-or-unknown-capacity' },
  { name: 'data saver', hints: { connection: { saveData: true, effectiveType: '4g' } }, result: 'network-preference' },
  { name: 'slow connection', hints: { connection: { saveData: false, effectiveType: '3g' } }, result: 'network-preference' },
  { name: 'missing WebAssembly', noWasm: true, result: 'unsupported-runtime' },
  { name: 'offline signal', hints: { onLine: false }, result: 'offline' },
];

export async function checkDeviceFallbacks(browser, url, pdf) {
  const checked = [];
  for (const { name, context: options, hints, noWasm, noMemory, result } of cases) {
    const context = await browser.newContext(options);
    try {
      await context.addInitScript(({ signals, noWasm, noMemory }) => {
        for (const [key, value] of Object.entries(signals)) Object.defineProperty(navigator, key, { value, configurable: true });
        if (noWasm) delete window.WebAssembly;
        if (noMemory) Object.defineProperty(navigator, 'deviceMemory', { value: undefined });
      }, { signals: { ...laptop, ...hints }, noWasm, noMemory });
      const computeRequests = [];
      context.on('request', request => {
        if (/\/(?:assets|pdf|ort|tokenizer)\/|\/embed\.worker\.mjs$/.test(request.url())) computeRequests.push(request.url());
      });
      const page = await context.newPage();
      await page.goto(url);
      const observed = await page.evaluate(async data => {
        const file = new File([Uint8Array.from(atob(data), c => c.charCodeAt(0))], 'synthetic.pdf');
        const transfer = new DataTransfer();
        transfer.items.add(file);
        document.querySelector('#files').files = transfer.files;
        document.querySelector('form').dispatchEvent(new Event('submit', { cancelable: true }));
        const { processFile } = await import('/pilot.mjs');
        return { result: (await processFile(file)).fallback, width: innerWidth,
          content: document.documentElement.scrollWidth };
      }, pdf.toString('base64'));
      assert.equal(observed.result, result, name);
      const message = result === 'offline' ? 'Reconnect to the internet to continue. No files were uploaded.'
        : 'Use the regular upload on this device. No files were uploaded.';
      assert.equal(await page.getByRole('status').textContent(), message, name);
      assert.equal(await page.getByRole('button', { name: 'Process on this device' }).isDisabled(), true, name);
      assert(observed.content <= observed.width, `${name}: horizontal overflow`);
      assert.deepEqual(computeRequests, [], `${name}: fetched compute assets`);
      assert.equal(page.workers().length, 0, `${name}: started a local worker`);
      checked.push(name);
    } finally {
      await context.close();
    }
  }
  return checked;
}

export async function checkInterruptions(browser, url, pdf) {
  for (const { pattern, action } of [
    { pattern: '**/pdf/build/pdf.worker.mjs', action: 'hide' },
    { pattern: '**/assets/model.onnx', action: 'stop' },
    { pattern: '**/assets/model.onnx', action: 'offline' },
  ]) {
    const context = await browser.newContext();
    let release;
    const hold = new Promise(resolve => { release = resolve; });
    try {
      const page = await context.newPage();
      await page.route(pattern, async route => { await hold; await route.abort().catch(() => {}); });
      await page.goto(url);
      await page.locator('#files').setInputFiles({ name: 'synthetic.pdf', mimeType: 'application/pdf', buffer: pdf });
      const requested = page.waitForRequest(pattern);
      await page.getByRole('button', { name: 'Process on this device' }).click();
      await requested;
      if (action === 'hide') {
        await page.evaluate(() => {
          Object.defineProperty(document, 'hidden', { value: true, configurable: true });
          document.dispatchEvent(new Event('visibilitychange'));
        });
      } else if (action === 'offline') {
        await page.evaluate(() => {
          Object.defineProperty(navigator, 'onLine', { value: false, configurable: true });
          window.dispatchEvent(new Event('offline'));
        });
      } else {
        await page.getByRole('button', { name: 'Stop local processing' }).click();
      }
      await page.getByText(action === 'offline' ? 'Reconnect to the internet to continue. No files were uploaded.'
        : 'Local processing stopped. Use the regular upload to continue. No files were uploaded.').waitFor();
      release();
      await page.unroute(pattern);
      if (action === 'hide') await page.evaluate(() => Reflect.deleteProperty(document, 'hidden'));
      if (action === 'offline') await page.evaluate(() => {
        Reflect.deleteProperty(navigator, 'onLine');
        window.dispatchEvent(new Event('online'));
      });
      await page.getByRole('button', { name: 'Process on this device' }).click();
      await page.getByText('1 of 1 processed locally. No files were uploaded.').waitFor();
    } finally {
      release();
      await context.close();
    }
  }
}
