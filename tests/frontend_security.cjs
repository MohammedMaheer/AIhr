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
console.log('11 frontend DOM security checks passed; safe formatting preserved.');
