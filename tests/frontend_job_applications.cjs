const assert = require('node:assert/strict');
const fs = require('node:fs');
const { JSDOM } = require('jsdom');

const source = fs.readFileSync('static/js/job-applications.js', 'utf8');
const flush = () => new Promise(resolve => setImmediate(resolve));
const escape = value => String(value ?? '').replace(/[&<>"']/g, character => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
}[character]));

async function run() {
    const dom = new JSDOM('<main id="candidate-application" data-public-token="' + 'a'.repeat(42) + '"></main>', {
        url: 'https://apply.example.invalid/apply/' + 'a'.repeat(42), runScripts: 'outside-only'
    });
    const { window: w } = dom;
    const { document } = w;
    w.escapeHtml = escape;
    w.escapeAttr = escape;

    const calls = [];
    w.fetch = async (url, options = {}) => {
        calls.push({ url, options });
        if (!options.method) return {
            ok: true,
            headers: { get: () => 'application/json' },
            json: async () => ({ page: {
                title: '<img src=x onerror=alert(1)> Engineer',
                company_name: 'Fictional Hiring Team',
                description: '<script>bad()</script>Build useful software.',
                location: 'Remote', employment_type: 'Full-time',
                custom_questions: ['<svg onload=bad()>Availability?']
            } })
        };
        return { ok: true, headers: { get: () => 'application/json' }, json: async () => ({ success: true }) };
    };
    w.eval(source);
    await flush();

    const root = document.getElementById('candidate-application');
    assert(root.textContent.includes('<img src=x onerror=alert(1)> Engineer'));
    assert.equal(root.querySelectorAll('img,script,svg').length, 0);
    assert.match(root.querySelector('.application-consent').textContent, /AI-assisted tools/);
    assert.equal(root.querySelectorAll('[data-question]').length, 1);

    const form = root.querySelector('[data-form]');
    form.reportValidity = () => true;
    form.elements.candidate_name.value = 'Fictional Candidate';
    form.elements.email.value = 'candidate@example.invalid';
    form.elements.consent.checked = true;
    form.querySelector('[data-question]').value = 'Two weeks';
    form.dispatchEvent(new w.Event('submit', { bubbles: true, cancelable: true }));
    await flush();

    const submission = calls.find(call => call.options.method === 'POST');
    assert(submission);
    assert.equal(submission.options.credentials, 'omit');
    assert.equal(submission.options.body.get('candidate_name'), 'Fictional Candidate');
    assert.deepEqual(JSON.parse(submission.options.body.get('answers')), { '0': 'Two weeks' });
    assert.equal(root.querySelector('[role="status"] strong').textContent, 'Application received');
    assert.equal(document.activeElement, root.querySelector('[role="status"]'));
    dom.window.close();
    console.log('Candidate application page passed: safe rendering, transparent consent, custom questions and accessible success state.');
}

run().catch(error => { console.error(error); process.exitCode = 1; });
