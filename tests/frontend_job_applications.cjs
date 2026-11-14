const assert = require('node:assert/strict');
const fs = require('node:fs');
const { JSDOM } = require('jsdom');

const source = fs.readFileSync('static/js/job-applications.js', 'utf8');
const styles = fs.readFileSync('static/css/style.css', 'utf8');
assert.match(styles, /\.job-page-dialog > form\s*\{[^}]*display:flex[^}]*min-height:0/s);
assert.match(styles, /\.job-page-dialog \.job-page-form\s*\{[^}]*flex:1[^}]*overflow-y:auto/s);
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
                application_settings:{banner:{headline:'Create what is next',color:'#245f52',image_url:''},
                    work_arrangement:'remote',resume_policy:'either',
                    pay:{show:true,minimum:'12000',maximum:'18000',currency:'AED',period:'month',note:'Based on experience'},
                    fields:{phone:false,location:false,experience:false,linkedin:false,portfolio:true}},
                custom_questions: ['<svg onload=bad()>Availability?']
            } })
        };
        return { ok: true, headers: { get: () => 'application/json' }, json: async () => ({ success: true }) };
    };
    w.eval(source);
    await flush();

    const root = document.getElementById('candidate-application');
    assert(root.textContent.includes('<img src=x onerror=alert(1)> Engineer'));
    assert.equal(root.querySelectorAll('script,svg').length, 0);
    assert.equal(root.querySelectorAll('[data-banner-image]').length, 1);
    assert.match(root.querySelector('.application-consent').textContent, /AI-assisted tools/);
    assert.equal(root.querySelectorAll('[data-question]').length, 1);
    assert.equal(root.querySelector('[data-banner-headline]').textContent, 'Create what is next');
    assert.match(root.querySelector('[data-pay]').textContent, /per month/);
    assert.equal(root.querySelector('[data-field="phone"]').hidden, true);
    assert.equal(root.querySelector('[data-field="portfolio"]').hidden, false);
    assert.match(root.querySelector('[data-meta]').textContent, /Remote/);

    const form = root.querySelector('[data-form]');
    form.reportValidity = () => true;
    form.elements.candidate_name.value = 'Fictional Candidate';
    form.elements.email.value = 'candidate@example.invalid';
    form.elements.consent.checked = true;
    form.reportValidity = () => form.checkValidity();
    form.dispatchEvent(new w.Event('submit', {bubbles:true,cancelable:true}));
    assert.match(form.elements.file.validationMessage, /Upload a CV or provide a resume link/);
    assert.equal(calls.some(call => call.options.method === 'POST'), false);
    form.elements.resume_url.value = 'https://files.example.com/candidate.pdf';
    form.elements.resume_url.dispatchEvent(new w.Event('input', {bubbles:true}));
    assert.equal(form.elements.file.validationMessage, '', 'Adding a link must clear the previous missing-resume error before native validation');
    Object.defineProperty(form.elements.file, 'files', {configurable:true, value:[{name:'notes.exe',size:10}]});
    form.elements.file.dispatchEvent(new w.Event('change'));
    assert.match(form.elements.file.validationMessage, /PDF or Word/);
    Object.defineProperty(form.elements.file, 'files', {configurable:true, value:[{name:'resume.pdf',size:10*1024*1024+1}]});
    form.elements.file.dispatchEvent(new w.Event('change'));
    assert.match(form.elements.file.validationMessage, /10 MB/);
    Object.defineProperty(form.elements.file, 'files', {configurable:true, value:[]});
    form.elements.file.dispatchEvent(new w.Event('change'));
    assert.equal(form.elements.file.validationMessage, '');
    form.querySelector('[data-question]').value = 'Two weeks';
    form.dispatchEvent(new w.Event('submit', { bubbles: true, cancelable: true }));
    await flush();

    const submission = calls.find(call => call.options.method === 'POST');
    assert(submission);
    assert.equal(submission.options.credentials, 'omit');
    assert.equal(submission.options.body.get('candidate_name'), 'Fictional Candidate');
    assert.equal(submission.options.body.get('resume_url'), 'https://files.example.com/candidate.pdf');
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
        created_at: '2026-11-11T00:00:00Z', interview_id: null },
        { id: 22, candidate_name: 'Indexing Needs Attention', normalized_email: 'second@example.invalid',
            answers: {}, status: 'received', version: 1, vector_indexed: false, resume_upload_id: 43,
            created_at: '2026-11-11T00:00:00Z', interview_id: null }];
    manager.fetch = async url => {
        const payload = String(url).includes('/generate-questions')
            ? {success:true,company_name:'Fictional Hiring Co',questions:[
                'Describe a relevant project you delivered.', 'How do you approach production incidents?'
            ]}
            : String(url).includes('/applications?')
            ? { success: true, applications, total: 1 }
            : { success: true, pages: [{ id: 11, title: 'Platform Engineer', location: 'Remote',
                employment_type: 'Full-time', status: 'published', version: 1, public_url: '/apply/' + 'b'.repeat(42),
                applicant_count: 2, indexing_pending: 1 }] };
        return { ok: true, headers: { get: () => 'application/json' }, json: async () => payload };
    };
    manager.eval(source);
    const workspace = manager.document.getElementById('job-applications-workspace');
    const dispose = manager.JobApplications.mount(workspace);
    await flush();
    assert.match(workspace.textContent, /1 CV needs indexing/);
    assert.match(workspace.querySelector('[title="Preview candidate page"]').href,
        /\/job-application-pages\/11\/preview$/);
    workspace.querySelector('[data-applicants="11"]').click();
    await flush();
    assert.equal(workspace.querySelectorAll('img').length, 0);
    assert.match(workspace.textContent, /Uploaded; not searchable/);
    workspace.querySelector('[data-email-applicant="21"]').click();
    workspace.querySelector('[data-schedule-applicant="21"]').click();
    assert.equal(emailContext.jobApplicationId, '21');
    assert.equal(emailContext.candidateEmail, 'candidate@example.invalid');
    assert.equal(interviewContext.jobApplicationId, '21');
    assert.equal(interviewContext.jobApplicationPageId, '11');
    manager.fetch = async url => ({ok:!String(url).includes('/applications?'),
        headers:{get:()=> 'application/json'},json:async()=>String(url).includes('/applications?')
            ? {detail:'Fictional temporary outage'} : {success:true,pages:[]}});
    manager.dispatchEvent(new manager.CustomEvent('job-application-interview-scheduled', {detail:{pageId:11}}));
    await flush();
    assert.match(workspace.textContent, /Applications unavailable/);
    workspace.querySelector('[data-back]').click();
    await flush();
    assert.match(workspace.textContent, /No job pages yet/, 'The error-state back button must actually return to job pages');
    dispose();
    managerDom.window.close();

    const adminDom = new JSDOM('<main id="job-applications-workspace"></main>', {
        url: 'https://app.example.invalid/#/jobApplications', runScripts: 'outside-only'
    });
    const admin = adminDom.window;
    admin.currentUser = {user_type:'super_admin', company:null};
    admin.escapeHtml = escape;
    admin.escapeAttr = escape;
    const adminCalls = [];
    admin.fetch = async (url, options = {}) => {
        adminCalls.push({url:String(url), options});
        const data = String(url) === '/api/companies'
            ? {companies:[{id:1,company_name:'Fictional One',is_active:true},{id:2,company_name:'Fictional Two',is_active:true}]}
            : String(url).startsWith('/api/job-application-pages/generate-questions')
                ? {success:true,company_name:'Fictional Two',questions:[
                    'Describe a role-relevant project.', 'How do you troubleshoot a service issue?'
                ]}
            : {success:true,pages:[]};
        return {ok:true,headers:{get:()=> 'application/json'},json:async()=>data};
    };
    admin.eval(source);
    const adminRoot = admin.document.getElementById('job-applications-workspace');
    admin.JobApplications.mount(adminRoot);
    await flush();
    const companyPicker = adminRoot.querySelector('[aria-label="Company workspace for job applications"]');
    assert(companyPicker);
    assert.equal(companyPicker.options.length,3);
    assert.equal(adminRoot.querySelector('[data-create]').disabled,true);
    companyPicker.value = '2';
    companyPicker.dispatchEvent(new admin.Event('change', {bubbles:true}));
    await flush();
    assert(adminCalls.some(call => call.url === '/api/job-application-pages?company_id=2'));
    assert.equal(adminRoot.querySelector('[data-create]').disabled,false);
    adminRoot.querySelector('[data-create]').click();
    const pageForm = admin.document.querySelector('[data-job-page-dialog] form');
    pageForm.elements.title.value = 'Fictional Role';
    pageForm.elements.description.value = 'A sufficiently detailed fictional role description.';
    pageForm.elements.work_arrangement.value = 'hybrid';
    pageForm.elements.show_pay.checked = true;
    pageForm.elements.show_pay.dispatchEvent(new admin.Event('change',{bubbles:true}));
    pageForm.elements.pay_minimum.value = '10000';
    pageForm.elements.pay_maximum.value = '15000';
    pageForm.elements.pay_currency.value = 'AED';
    pageForm.elements.pay_maximum.setCustomValidity('Maximum pay must be at least the minimum pay.');
    pageForm.elements.pay_minimum.dispatchEvent(new admin.Event('input',{bubbles:true}));
    assert.equal(pageForm.elements.pay_maximum.validationMessage,'','Changing either end of the range must clear stale range validation');
    pageForm.elements.pay_note.setCustomValidity('Enter a pay range or compensation note to show pay.');
    pageForm.elements.pay_minimum.dispatchEvent(new admin.Event('input',{bubbles:true}));
    assert.equal(pageForm.elements.pay_note.validationMessage,'','Adding a range must clear stale missing-pay validation');
    pageForm.elements.field_portfolio.checked = true;
    admin.document.querySelector('[data-generate-questions]').click();
    await flush();
    const preview = admin.document.querySelector('[data-question-preview]');
    assert(preview);
    assert.match(preview.querySelector('[data-preview-company]').textContent,/Fictional Two/);
    const draftInputs = preview.querySelectorAll('textarea');
    assert.equal(draftInputs.length,2);
    draftInputs[0].value = 'Edited after human review.';
    draftInputs[0].dispatchEvent(new admin.Event('input',{bubbles:true}));
    preview.querySelector('[data-use-questions]').click();
    assert.equal(admin.document.querySelectorAll('[data-job-page-dialog] [data-question-index]').length,2);
    assert.equal(admin.document.querySelector('[data-job-page-dialog] [data-question-index]').value,'Edited after human review.');
    const questionFields = admin.document.querySelectorAll('[data-job-page-dialog] [data-question-index]');
    questionFields[1].value = questionFields[0].value;
    questionFields[1].dispatchEvent(new admin.Event('input',{bubbles:true}));
    pageForm.dispatchEvent(new admin.Event('submit', {bubbles:true,cancelable:true}));
    await flush();
    assert.equal(adminCalls.some(call => call.url.startsWith('/api/job-application-pages?company_id=2') && call.options.method === 'POST'),false);
    questionFields[1].value = 'How do you troubleshoot a service issue?';
    questionFields[1].dispatchEvent(new admin.Event('input',{bubbles:true}));
    pageForm.dispatchEvent(new admin.Event('submit', {bubbles:true,cancelable:true}));
    await flush();
    const createCall = adminCalls.find(call => call.url.startsWith('/api/job-application-pages?company_id=2') && call.options.method === 'POST');
    assert(createCall);
    assert.equal(JSON.parse(createCall.options.body).company_id,2);
    assert.deepEqual(JSON.parse(createCall.options.body).custom_questions,[
        'Edited after human review.','How do you troubleshoot a service issue?'
    ]);
    assert.equal(JSON.parse(createCall.options.body).application_settings.work_arrangement,'hybrid');
    assert.deepEqual(JSON.parse(createCall.options.body).application_settings.pay,
        {show:true,minimum:'10000',maximum:'15000',currency:'AED',period:'month',note:''});
    assert.equal(JSON.parse(createCall.options.body).application_settings.fields.portfolio,true);
    adminDom.window.close();

    const previewDom = new JSDOM('<main id="candidate-application" data-public-token="" data-preview-page-id="11" data-preview-company-id="1"></main>', {
        url:'https://app.example.invalid/job-application-pages/11/preview',runScripts:'outside-only'
    });
    const previewWindow = previewDom.window;
    previewWindow.escapeHtml = escape;
    previewWindow.escapeAttr = escape;
    const previewCalls = [];
    previewWindow.fetch = async (url, options = {}) => {
        previewCalls.push({url:String(url),options});
        return {ok:true,headers:{get:()=> 'application/json'},json:async()=>({page:{
            title:'Draft Preview Engineer',company_name:'Fictional Hiring Team',
            description:'A saved draft preview for checking candidate presentation.',location:'Dubai',
            employment_type:'Part-time',custom_questions:[],
            application_settings:{banner:{headline:'Preview only',color:'#245f52',image_url:''},
                work_arrangement:'hybrid',resume_policy:'link',
                pay:{show:true,minimum:'8000',maximum:'12000',currency:'AED',period:'month',note:''},
                fields:{phone:true,location:true,experience:true,linkedin:true,portfolio:false}}
        }})};
    };
    previewWindow.eval(source);
    await flush();
    const previewRoot = previewWindow.document.getElementById('candidate-application');
    assert.match(previewRoot.querySelector('.application-preview-note').textContent,/not accepting applications/);
    assert.equal(previewRoot.querySelector('[name="file"]').disabled,true);
    assert.equal(previewRoot.querySelector('[name="resume_url"]').required,true);
    assert.equal(previewRoot.querySelector('[type="submit"]').textContent,'Preview only');
    assert(previewCalls.some(call=>call.url.includes('/api/job-application-pages/11/preview-data')));
    previewRoot.querySelector('[data-form]').dispatchEvent(new previewWindow.Event('submit',{bubbles:true,cancelable:true}));
    await flush();
    assert.equal(previewCalls.some(call=>call.options.method==='POST'),false);
    previewDom.window.close();
    console.log('Application flows passed: configurable candidate page, resume links, compensation, validation, safe rendering and recruiter workflows.');
}

run().catch(error => { console.error(error); process.exitCode = 1; });
