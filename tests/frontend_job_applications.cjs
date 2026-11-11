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

    const managerDom = new JSDOM('<main id="job-applications-workspace"></main>', {
        url: 'https://app.example.invalid/#/jobApplications', runScripts: 'outside-only'
    });
    const manager = managerDom.window;
    manager.escapeHtml = escape;
    manager.escapeAttr = escape;
    let emailContext, interviewContext;
    manager.RecruiterOutreach = { open: context => { emailContext = context; } };
    manager.scheduleInterview = (name, email, context) => { interviewContext = { name, email, ...context }; };
    const applications = [{ id: 21, candidate_name: '<img src=x onerror=alert(1)> Candidate',
        normalized_email: 'candidate@example.invalid', phone: '', location: 'Remote', years_experience: 5,
        answers: {}, status: 'received', version: 1, vector_indexed: true, resume_upload_id: 42,
        created_at: '2026-11-11T00:00:00Z', interview_id: null }];
    manager.fetch = async url => {
        const payload = String(url).includes('/applications?')
            ? { success: true, applications, total: 1 }
            : { success: true, pages: [{ id: 11, title: 'Platform Engineer', location: 'Remote',
                employment_type: 'Full-time', status: 'published', version: 1, public_url: '/apply/' + 'b'.repeat(42),
                applicant_count: 1 }] };
        return { ok: true, headers: { get: () => 'application/json' }, json: async () => payload };
    };
    manager.eval(source);
    const workspace = manager.document.getElementById('job-applications-workspace');
    const dispose = manager.JobApplications.mount(workspace);
    await flush();
    workspace.querySelector('[data-applicants="11"]').click();
    await flush();
    assert.equal(workspace.querySelectorAll('img').length, 0);
    workspace.querySelector('[data-email-applicant="21"]').click();
    workspace.querySelector('[data-schedule-applicant="21"]').click();
    assert.equal(emailContext.jobApplicationId, '21');
    assert.equal(emailContext.candidateEmail, 'candidate@example.invalid');
    assert.equal(interviewContext.jobApplicationId, '21');
    assert.equal(interviewContext.jobApplicationPageId, '11');
    dispose();
    managerDom.window.close();
    console.log('Application flows passed: public validation, safe rendering, linked recruiter email/interview actions and accessible success state.');
}

run().catch(error => { console.error(error); process.exitCode = 1; });
