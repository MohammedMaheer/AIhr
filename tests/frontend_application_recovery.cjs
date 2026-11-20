const assert = require('node:assert/strict');
const fs = require('node:fs');
const {JSDOM} = require('jsdom');
const source = fs.readFileSync('static/js/job-applications.js','utf8');
const main = fs.readFileSync('static/js/main.js','utf8');
const binding = main.slice(main.indexOf('function bindScheduleDialog('),main.indexOf('function closeInterviewModal('));
const flush = () => new Promise(resolve => setImmediate(resolve));
const reply = (data, ok=true) => ({ok,headers:{get:()=> 'application/json'},json:async()=>data});
const esc = value => String(value ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const job = {id:11,title:'Fictional Engineer',description:'A sufficiently detailed fictional role description.',version:1,status:'draft',custom_questions:[]};

async function manager() {
    const dom = new JSDOM('<div id="app-shell"><section id="root"></section></div>',{url:'https://qa.invalid/',runScripts:'outside-only'});
    const w=dom.window, d=w.document, root=d.getElementById('root');
    w.currentUser={id:7,user_type:'tenant_admin'};
    w.escapeHtml=esc; w.escapeAttr=esc; w.eval(binding);
    let calls=0, complete;
    w.fetch=async (url,options={}) => {
        if (options.method==='PUT') { calls++; return new Promise(resolve => { complete=resolve; }); }
        return reply({success:true,pages:[job]});
    };
    w.eval(source); const dispose=w.JobApplications.mount(root); await flush();
    root.querySelector('[data-edit]').click();
    const modal=d.querySelector('[data-job-page-dialog]'), form=modal.querySelector('form');
    assert(form.checkValidity());
    form.dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));
    form.dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));
    assert.equal(calls,1,'Repeated submit events must not duplicate a page update');
    assert.equal(form.dataset.submitting,'true');
    assert.equal(form.getAttribute('aria-busy'),'true');
    assert([...modal.querySelectorAll('[data-close]')].every(button=>button.disabled));
    modal.dispatchEvent(new w.KeyboardEvent('keydown',{key:'Escape',bubbles:true}));
    assert(modal.isConnected,'Escape must not discard a pending save');
    complete(reply({detail:'Fictional save failure.'},false)); await flush();
    assert.equal(form.dataset.submitting,undefined);
    assert.equal(form.hasAttribute('aria-busy'),false);
    assert([...modal.querySelectorAll('[data-close]')].every(button=>!button.disabled));
    assert.equal(d.activeElement,modal.querySelector('[data-error]'),'Bring an offscreen error into keyboard focus');
    assert.equal(form.elements.title.value,job.title,'Preserve entered fields after a failed save');
    form.dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));
    assert.equal(calls,2); complete(reply({success:true})); await flush();
    assert(!modal.isConnected); assert.equal(d.getElementById('app-shell').inert,false);
    dispose(); dom.window.close();
}

async function candidate() {
    const dom=new JSDOM('<main id="candidate-application" data-public-token="'+'b'.repeat(42)+'"></main>',{url:'https://qa.invalid/',runScripts:'outside-only'});
    const w=dom.window,d=w.document;
    let calls=0,complete,loads=0;
    w.fetch=async (url,options={}) => {
        if (options.method==='POST') { calls++; return new Promise(resolve => {complete=resolve;}); }
        if (++loads===1) throw new Error('Offline');
        return reply({success:true,page:job});
    };
    w.eval(source); await flush();
    assert.match(d.body.textContent,/Could not load the application/);
    d.querySelector('button').click(); await flush();
    const form=d.querySelector('form');
    form.elements.candidate_name.value='Fictional Candidate';
    form.elements.email.value='applicant@example.invalid';
    form.elements.resume_url.value='https://example.invalid/cv.pdf';
    form.elements.consent.checked=true;
    form.dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));
    form.dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));
    assert.equal(calls,1,'Repeated submit events must not duplicate candidate applications');
    assert.equal(form.getAttribute('aria-busy'),'true');
    complete({ok:true,status:200,headers:{get:()=> 'text/html'}}); await flush();
    assert.equal(d.querySelector('.application-alert.is-success'),null,'An HTML response must not show a receipt');
    assert.equal(form.dataset.submitting,undefined); assert.equal(form.hasAttribute('aria-busy'),false);
    assert.equal(d.activeElement,d.querySelector('[data-alert]'));
    assert.equal(form.elements.email.value,'applicant@example.invalid');
    assert.equal(form.querySelector('[type="submit"]').disabled,false);
    form.dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));
    assert.equal(calls,2); complete(reply({success:true})); await flush();
    assert.match(d.querySelector('.application-alert.is-success').textContent,/Application received/);
    dom.window.close();
}

async function staleCompanyList() {
    const dom = new JSDOM('<main id="root"></main>',{url:'https://qa.invalid/',runScripts:'outside-only'});
    const w=dom.window,root=w.document.getElementById('root');
    w.currentUser={user_type:'super_admin'};w.escapeHtml=esc;w.escapeAttr=esc;
    let resolvePages, loads=0;
    w.fetch=async url => {
        if(url==='/api/companies') return ++loads===1 ? reply({detail:'Temporarily offline'},false) :
            reply({success:true,companies:[{id:1,company_name:'Fictional Hiring Co',is_active:true}]});
        return new Promise(resolve=>{resolvePages=resolve;});
    };
    w.eval(source); const dispose=w.JobApplications.mount(root); await flush();
    root.querySelector('[data-retry]').click();await flush();
    const picker=root.querySelector('select');assert.equal(picker.value,'1');
    picker.value='';picker.dispatchEvent(new w.Event('change'));
    resolvePages(reply({success:true,pages:[job]}));await flush();
    assert.match(root.textContent,/Choose a company/);
    assert.equal(root.querySelector('[data-edit]'),null);
    assert.equal(root.querySelector('[data-content]').getAttribute('aria-busy'),'false');
    dispose();dom.window.close();
}

manager().then(candidate).then(staleCompanyList).then(()=>console.log('Application recovery passed: single submissions, real receipts, retryable failures and stale workspace protection.'))
    .catch(error=>{console.error(error);process.exitCode=1;});
