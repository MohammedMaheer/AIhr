// DOM-level security regression checks; these are not browser E2E tests.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { JSDOM } = require('jsdom');

const dom = new JSDOM('', { url: 'https://qa.invalid', runScripts: 'outside-only' });
const { window } = dom;
window.fetch = async () => ({ ok: true });
window.Request = global.Request;
window.Headers = global.Headers;
window.eval(fs.readFileSync('static/vendor/dompurify/purify-3.4.17.min.js', 'utf8'));
window.eval(fs.readFileSync('static/js/security.js', 'utf8'));

const unsafe = [
    '<script>alert(1)</script><p>CV</p>',
    '<img src=x onerror=alert(1)>',
    '<a href="java\nscript:alert(1)">CV</a>',
    '<svg><g onload=alert(1)></g></svg>',
    '<math><mtext><img src=x onerror=alert(1)></mtext></math>',
    '<iframe srcdoc="<script>alert(1)</script>"></iframe>',
    '<form id=fetch><input name=constructor></form>',
    '<a href="data:text/html,<script>alert(1)</script>">CV</a>',
];
for (const value of unsafe) {
    const output = window.sanitizeGeneratedHtml(value);
    const doc = new JSDOM(output).window.document;
    assert.equal(doc.querySelectorAll('script,svg,math,iframe,form,input,object').length, 0);
    for (const node of doc.querySelectorAll('*')) {
        for (const attr of node.attributes) assert(!attr.name.startsWith('on'));
    }
    for (const anchor of doc.querySelectorAll('a[href]')) {
        assert(!/^(javascript|data):/i.test(anchor.getAttribute('href').replace(/[\s\u0000-\u001f]/g, '')));
    }
}
const safe = '<h2>Requirements</h2><ul><li><strong>Python</strong></li></ul><p>R&amp;D</p>';
assert.equal(window.sanitizeGeneratedHtml(safe), safe);
assert.equal(window.escapeHtml('<CV>'), '&lt;CV&gt;');
window.DOMPurify = null;
assert.equal(window.sanitizeGeneratedHtml('<script>bad</script>'), '&lt;script&gt;bad&lt;/script&gt;');

const mainBundle = fs.readFileSync('static/js/main.js', 'utf8');
assert(!/\beval\s*\(/.test(mainBundle), 'main bundle must not dynamically evaluate handler names');
const failureStart = mainBundle.indexOf('    function renderSearchFailure(');
const failureEnd = mainBundle.indexOf('    function handleSendMessage()', failureStart);
assert(failureStart >= 0 && failureEnd > failureStart, 'search failure renderer must remain independently testable');
window.eval(mainBundle.slice(failureStart, failureEnd) + ';window.qaRenderSearchFailure = renderSearchFailure;');
const failureContainer = window.document.createElement('div');
const injectedMessage = '<img src=x onerror=alert(1)> maximum search limit';
window.qaRenderSearchFailure(failureContainer, { message: injectedMessage });
assert.equal(failureContainer.querySelectorAll('img,script').length, 0, 'API error text must not become markup');
assert(failureContainer.textContent.includes(injectedMessage));

window.document.body.innerHTML = '<div id="results-container"></div>';
const resultsStart = mainBundle.indexOf('    window.generateEnhancedResults = function (data) {');
const resultsEnd = mainBundle.indexOf('    // Helper function to extract candidate name', resultsStart);
assert(resultsStart >= 0 && resultsEnd > resultsStart, 'candidate results renderer must remain independently testable');
window.eval(mainBundle.slice(resultsStart, resultsEnd));
window.generateEnhancedResults({
    results: [],
    total_results: 0,
    empty_datastore: true,
    message: '<img src=x onerror=alert(1)> No resumes uploaded',
});
assert.equal(window.document.querySelectorAll('#results-container img,[onerror]').length, 0, 'empty search messages must not become markup');
assert(window.document.getElementById('results-container').textContent.includes('No resumes uploaded'));
window.generateEnhancedResults({ results: [], total_results: 0, message: { unexpected: true } });
assert(window.document.getElementById('results-container').textContent.includes('No resumes found matching your search criteria.'));

const legacyDashboard = fs.readFileSync('templates/dashboard.html', 'utf8');
const legacyDownloadStart = legacyDashboard.indexOf('        function downloadJD()');
const legacyDownloadEnd = legacyDashboard.indexOf('        // Save JD as template', legacyDownloadStart);
const legacyDownload = legacyDashboard.slice(legacyDownloadStart, legacyDownloadEnd);
assert(legacyDownload.includes('const safeTitle = escapeHtml(jobTitle);'));
assert(legacyDownload.includes('const safeContent = typeof window.sanitizeGeneratedHtml'));
assert(!legacyDownload.includes('>${jobTitle}</h1>'));
console.log('Frontend DOM security checks passed; safe formatting and error boundaries preserved.');
