// Opt-in isolated browser/API/worker test. Never target production.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const {chromium} = require('playwright');
const [base, fixture] = process.argv.slice(2);
const scenarios = JSON.parse(fs.readFileSync(fixture, 'utf8'));
assert.equal(new URL(base).hostname, '127.0.0.1', 'Never run fixture writes against production.');

async function run() {
    const browser = await chromium.launch({headless: true,
        ...(process.env.UI_BROWSER_CHANNEL ? {channel: process.env.UI_BROWSER_CHANNEL} : {})});
    try {
        for (const [width, user] of [[1440, '7'], [390, '9']]) {
            const context = await browser.newContext({viewport: {width, height: 900},
                extraHTTPHeaders: {'X-Fixture-User': user}});
            const page = await context.newPage();
            let submitted = 0;
            page.on('request', request => {
                if (request.url().endsWith('/api/hr-scorecard-search') && request.method() === 'POST') submitted++;
            });
            await page.goto(base + '/#/searchResumes', {waitUntil: 'networkidle'});
            const reopenSearch = async () => {
                if (width <= 768) await page.locator('#navigation-toggle').click();
                await page.locator('#search-resumes-link').click();
                await page.locator('#chat-input').waitFor({state: 'visible'});
            };
            const checkSearch = async (trigger, scenario) => {
                const started = page.waitForResponse(response =>
                    response.url().endsWith('/api/hr-scorecard-search') && response.request().method() === 'POST');
                await trigger();
                const response = await started;
                assert.equal(response.status(), 200, await response.text());
                const taskId = (await response.json()).task_id;
                let status;
                for (let attempt = 0; attempt < 80; attempt++) {
                    status = await (await page.request.get(base + '/api/hr-scorecard-task-status/' + taskId)).json();
                    if (['completed', 'failed'].includes(status.status)) break;
                    await new Promise(resolve => setTimeout(resolve, 100));
                }
                assert.equal(status.status, 'completed', JSON.stringify(status));
                const data = await (await page.request.get(base + '/api/hr-scorecard-task-results/' + taskId)).json();
                const rows = data.results || data.data?.results || [];
                assert.deepEqual(rows.map(row => row.file_path).sort(), scenario.expected,
                    width + ' ' + scenario.name + ' scope mismatch');
                assert.equal(new Set(rows.map(row => row.file_path)).size, rows.length);
                if (rows.length) await page.waitForFunction(expected =>
                    document.querySelectorAll('#candidate-list .candidate-list-item').length === expected, rows.length);
            };
            for (const scenario of scenarios) {
                await reopenSearch();
                const filters = page.locator('#resume-search-filters');
                await filters.locator('summary').click();
                await filters.locator('[data-folder]').first().waitFor();
                if (await filters.locator('[data-reset]').isEnabled()) await filters.locator('[data-reset]').click();
                const choices = await filters.locator('[data-folder]').evaluateAll(inputs => inputs.map(input => ({
                    index: input.dataset.folder, name: input.closest('label').querySelector('span').textContent})));
                for (const name of scenario.folders) {
                    const choice = choices.find(item => item.name === name);
                    assert(choice, 'Missing folder ' + name);
                    await filters.locator('[data-folder="' + choice.index + '"]').check();
                }
                for (const tag of scenario.tags) await filters.locator('[data-tag="' + tag + '"]').check();
                await filters.locator('[data-basis]').selectOption(scenario.basis);
                for (const bound of ['from', 'to']) {
                    if (!scenario[bound]) continue;
                    await filters.locator('[data-' + bound + ']').fill(scenario[bound]);
                    await filters.locator('[data-' + bound + ']').press('Tab');
                }
                await page.locator('#chat-input').fill('candidate profiles');
                await checkSearch(() => page.locator('#send-button').click(), scenario);
                if (scenario.name === 'received') {
                    await page.locator('#result-search-filters').click();
                    const dialog = page.locator('[data-cv-filter-dialog]');
                    await dialog.locator('[data-folder]').first().waitFor();
                    assert.equal(await dialog.locator('[data-folder]:checked').count(), 1);
                    assert.equal(await dialog.locator('[data-tag]:checked').count(), 1);
                    assert.equal(await dialog.locator('[data-basis]').inputValue(), scenario.basis);
                    assert.equal(await dialog.locator('[data-from]').inputValue(), scenario.from);
                    assert.equal(await dialog.locator('[data-to]').inputValue(), scenario.to);
                    await dialog.locator('[data-done]').click();
                    await page.locator('#bottom-chat-input').fill('candidate profiles');
                    await checkSearch(() => page.locator('#bottom-send-button').click(), scenario);
                }
            }
            await reopenSearch();
            const filters = page.locator('#resume-search-filters');
            await filters.locator('summary').click();
            if (await filters.locator('[data-reset]').isEnabled()) await filters.locator('[data-reset]').click();
            await filters.locator('[data-all]').uncheck();
            await page.locator('#chat-input').fill('candidate profiles');
            const before = submitted;
            await page.locator('#send-button').click();
            assert.equal(submitted, before, 'An explicit empty folder selection must not submit a search');
            assert.equal(await page.locator('#chat-input').inputValue(), 'candidate profiles');
            assert(await page.locator('#chat-input').isVisible(), 'Invalid scope must keep the form visible');
            await filters.locator('[data-all]').check();
            await filters.locator('[data-from]').fill('2026-05-02');
            await filters.locator('[data-from]').press('Tab');
            await filters.locator('[data-to]').fill('2026-05-01');
            await filters.locator('[data-to]').press('Tab');
            await page.locator('#send-button').click();
            assert.equal(submitted, before, 'A reversed date range must not submit a search');
            assert.equal(await page.locator('#chat-input').inputValue(), 'candidate profiles');
            assert(await page.locator('#chat-input').isVisible());
            await context.close();
            console.log('Browser/HTTP/worker/SQL folder-tag-date isolation passed at ' + width + 'px.');
        }
    } finally {
        await browser.close();
    }
}
run().catch(error => { console.error(error); process.exitCode = 1; });
