/* Real browser UI; the loopback server and intercepted uploads are synthetic. */
const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');
const { once } = require('node:events');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');

async function main() {
    const root = path.resolve(__dirname, '..');
    assert(fs.existsSync(path.join(root, 'static/css/tailwind.css')), 'Build the Tailwind asset first.');
    const host = spawn(process.execPath, [path.join(__dirname, 'ui_preview.cjs')], {cwd:root, stdio:['ignore','pipe','ignore']});
    let browser;
    try {
        const base = await new Promise((resolve, reject) => {
            const timer = setTimeout(() => reject(new Error('Fixture server did not start')), 10000);
            host.once('error', error => { clearTimeout(timer); reject(error); });
            host.stdout.on('data', bytes => {
                const url = String(bytes).match(/UI_PREVIEW_URL=(http:\/\/127\.0\.0\.1:\d+)/)?.[1];
                if (url) { clearTimeout(timer); resolve(url); }
            });
        });
        browser = await chromium.launch({channel:process.env.UI_BROWSER_CHANNEL || 'chrome'});
        for (const [width,height] of [[1440,900],[768,1024],[390,844],[320,568]]) {
            const context = await browser.newContext({viewport:{width,height},reducedMotion:'reduce'});
            const post = [];
            await context.route('**/*', route => new URL(route.request().url()).origin === base ? route.continue() : route.abort());
            const page = await context.newPage();
            const errors = [];
            page.on('pageerror', error => errors.push(error.message));
            await page.route('**/api/upload-files', async route => {
                const req = route.request();
                const form = await new Response(req.postDataBuffer(), {headers:{'Content-Type':req.headers()['content-type']}}).formData();
                const names = form.getAll('files').map(file => file.name);
                post.push(names);
                if (post.length===1) return route.fulfill({status:429,headers:{'Retry-After':'0'},json:{detail:'Busy'}});
                if (post.length===2) return route.abort('connectionreset');
                return route.fulfill({json:{results:names.map(filename=>({filename,success:true,vector_indexed:true}))}});
            });
            await page.goto(base+'/#/uploadFiles');
            const input = page.locator('#file-input');
            const start = page.locator('#start-upload');
            const cv = name => ({name,mimeType:'application/pdf',buffer:Buffer.from('%PDF-Synthetic fixture')});
            const original = 'Synthetic_Candidate_With_A_Very_Long_Professional_Filename_For_Mobile_Layout.pdf';
            await input.setInputFiles(cv(original));
            await start.click();
            await page.getByText('Unconfirmed',{exact:true}).waitFor();
            assert.equal(await page.locator('#overall-progress-text').textContent(),'0%');
            assert(await start.isDisabled());
            assert.deepEqual(post,[[original],[original]],'An unconfirmed upload must not be resent');
            for (const selector of ['#upload-queue','#overall-progress-container']) {
                assert(await page.locator(selector).evaluate(el=>el.scrollWidth<=el.clientWidth+1),`${selector} overflow at ${width}`);
            }
            assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`Page overflow at ${width}`);
            if (process.env.UI_SCREENSHOT_DIR) {
                fs.mkdirSync(process.env.UI_SCREENSHOT_DIR,{recursive:true});
                await page.locator('#upload-queue').screenshot({path:path.join(process.env.UI_SCREENSHOT_DIR,`upload-recovery-${width}.png`)});
            }
            await input.setInputFiles(cv('Another synthetic CV.pdf'));
            await start.click();
            await page.getByText('Uploaded',{exact:true}).waitFor();
            assert.deepEqual(post[2],['Another synthetic CV.pdf']);
            assert.deepEqual(errors,[]);
            await context.close();
        }
        console.log('Browser upload recovery passed at 1440, 768, 390 and 320 px.');
    } finally {
        await browser?.close();
        if (host.exitCode===null && host.signalCode===null) {
            const done = once(host,'exit');
            host.kill();
            await done;
        }
    }
}
main().catch(error=>{console.error(error);process.exitCode=1;});
