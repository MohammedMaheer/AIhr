/* Run with Playwright installed, after building static/css/tailwind.css. Uses fictional local fixtures only. */
const assert = require('node:assert/strict');
const {spawn} = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require('playwright');
const root = path.resolve(__dirname, '..');
const screenshots = path.resolve(process.env.UI_SCREENSHOT_DIR || path.join(root, 'audit_out/recent-ui-verification'));
const token = 'b'.repeat(42);

async function run() {
    assert(fs.existsSync(path.join(root, 'static/css/tailwind.css')), 'Build the Tailwind asset before visual verification.');
    fs.mkdirSync(screenshots, {recursive:true});
    const server = spawn(process.execPath, [path.join(__dirname, 'ui_preview.cjs')], {cwd:root, stdio:['ignore','pipe','pipe']});
    let browser;
    try {
        const base = await new Promise((resolve, reject) => {
            const timeout = setTimeout(() => reject(new Error('Fixture server did not start.')), 10000);
            server.once('error', error => { clearTimeout(timeout); reject(error); });
            server.once('exit', code => { clearTimeout(timeout); reject(new Error('Fixture server exited: ' + code)); });
            server.stdout.on('data', chunk => {
                const match = String(chunk).match(/UI_PREVIEW_URL=(http:\/\/127\.0\.0\.1:\d+)/);
                if (match) { clearTimeout(timeout); resolve(match[1]); }
            });
        });
        browser = await chromium.launch({headless:true, ...(process.env.UI_BROWSER_CHANNEL ? {channel:process.env.UI_BROWSER_CHANNEL} : {})});
        for (const [width, height] of [[1440,900],[1280,720],[900,768],[600,800],[390,844],[320,568]]) {
            const page = await browser.newPage({viewport:{width,height},reducedMotion:'reduce'});
            const errors = [];
            page.on('pageerror', error => errors.push(error.message));
            const shot = name => page.screenshot({path:path.join(screenshots,width+'-'+name+'.png'),fullPage:true});
            const contained = async selector => {
                assert(await page.locator(selector).evaluate(el => el.scrollWidth <= el.clientWidth + 1), selector+' overflows at '+width);
                assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'Page overflows at '+width);
            };
            await page.route('**/api/job-application-pages/generate-questions**', route => route.fulfill({json:{success:true,company_name:'Example Recruitment Company',questions:['Describe a relevant project you delivered.','How do you troubleshoot a service issue?']}}));
            await page.goto(base+'/#/jobApplications', {waitUntil:'networkidle'});
            await page.locator('[data-edit="11"]').waitFor();
            await contained('.workspace-header');
            await contained('[data-content]');
            assert(await page.locator('.job-pages-table .workspace-row-actions').evaluate(el => {
                const boundary = el.closest('table').getBoundingClientRect();
                return [...el.children].every(child => { const r=child.getBoundingClientRect(); return r.left>=boundary.left && r.right<=boundary.right; });
            }), 'Job actions are clipped at '+width);
            await shot('job-pages');
            await page.locator('[data-edit="11"]').click();
            const dialog = page.locator('[data-job-page-dialog]');
            assert(await dialog.locator('select').evaluateAll(elements => elements.every(el => el.getBoundingClientRect().height >= 40)));
            await contained('.job-page-dialog');
            assert(await dialog.evaluate(el => { const r=el.getBoundingClientRect(); return r.top>=0 && r.bottom<=innerHeight; }));
            await shot('job-dialog');
            await dialog.locator('[name="pay_minimum"]').fill('20000');
            await dialog.locator('footer [type="submit"]').click();
            assert.match(await dialog.locator('[name="pay_maximum"]').evaluate(el => el.validationMessage), /Maximum pay/);
            await dialog.locator('[name="pay_minimum"]').fill('9000');
            assert.equal(await dialog.locator('[name="pay_maximum"]').evaluate(el => el.validationMessage), '', 'Correcting the minimum must unblock native validation.');
            await dialog.locator('[data-generate-questions]').click();
            await page.locator('[data-question-preview] textarea').first().waitFor();
            await contained('.job-question-preview');
            await shot('question-review');
            await page.locator('[data-question-preview] [data-preview-close]').first().click();
            await dialog.locator('.job-page-form').evaluate(el => { el.scrollTop=el.scrollHeight; });
            assert(await dialog.locator('footer [type="submit"]').isVisible());
            await shot('job-dialog-bottom');
            await dialog.locator('[data-close]').first().click();
            await page.locator('[data-applicants="11"]').click();
            await page.locator('[data-application-status]').first().waitFor();
            await contained('[data-content]');
            if (await page.locator('.job-applications-view').evaluate(el => el.clientWidth <= 1000)) {
                assert.notEqual(await page.locator('.job-candidates-table td[data-label="Experience"]').first().evaluate(el => getComputedStyle(el,'::before').content), 'none');
            }
            await shot('applicants');
            for (const view of ['uploadFiles','resumeLibrary','searchResumes']) {
                await page.goto(base+'/#/'+view, {waitUntil:'networkidle'});
                if (view==='uploadFiles') {
                    await page.locator('#upload-folder-choice option[value="Design/November 2026"]').waitFor({state:'attached'});
                    await page.locator('#upload-folder-choice').selectOption('Design/November 2026');
                    await shot('bulk-upload');
                    await page.locator('#email-scrape-tab').click();
                    await page.locator('#email-provider').selectOption('outlook');
                    await page.locator('#outlook-connection-row').waitFor();
                    await page.waitForFunction(() => [...document.querySelectorAll('#file-upload-tab,#email-scrape-tab')].every(button => getComputedStyle(button).color===getComputedStyle(button.querySelector('i')).color), null, {timeout:2000});
                    await shot('email-import');
                } else if (view==='searchResumes') {
                    await page.locator('#resume-search-filters [data-tag-choice]').waitFor();
                    await page.locator('#resume-search-filters [data-tag-choice]').selectOption('IT infrastructure');
                    await page.locator('#resume-search-filters summary').click();
                    await page.locator('#resume-search-filters [data-folder="0"]').check();
                    await page.locator('#resume-search-filters [data-range]').selectOption('30');
                    await shot('search-scope');
                } else { await page.locator('.cv-library-table').waitFor(); await shot('library'); }
                assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), view+' page overflows at '+width);
            }
            await page.goto(base+'/apply/'+token, {waitUntil:'networkidle'});
            await page.locator('[data-form]').waitFor();
            await page.locator('[name="candidate_name"]').fill('Fictional Applicant');
            await page.locator('[name="email"]').fill('applicant@example.invalid');
            await page.locator('[name="consent"]').check();
            await page.locator('[type="submit"]').click();
            assert.match(await page.locator('[name="file"]').evaluate(el => el.validationMessage), /Upload a CV/);
            await page.locator('[name="resume_url"]').fill('https://example.invalid/resume.pdf');
            assert.equal(await page.locator('[name="file"]').evaluate(el => el.validationMessage), '');
            await page.route('**/api/public/application-pages/'+token+'/applications', route => route.fulfill({status:503,json:{detail:'Fictional temporary failure. Please try again.'}}));
            await page.locator('[type="submit"]').click();
            await page.locator('[data-alert]:not([hidden])').waitFor();
            assert(await page.locator('[data-alert]').evaluate(el => el===document.activeElement), 'Failure must be focused, not hidden above the form.');
            await shot('candidate-failure');
            await page.route('**/api/public/application-pages/'+token+'/applications', route => route.fulfill({json:{success:true}}));
            await page.locator('[type="submit"]').click();
            await page.locator('.application-alert.is-success').waitFor();
            await shot('candidate-success');
            assert.deepEqual(errors, [], 'Browser errors at '+width);
            await page.close();
            console.log('Visual and native-flow checks passed at '+width+'x'+height);
        }
    } finally {
        if (browser) await browser.close();
        if (server.exitCode===null) {
            const stopped = new Promise(resolve => server.once('exit', resolve));
            server.kill(); await stopped;
        }
    }
}
run().catch(error => { console.error(error); process.exitCode=1; });
