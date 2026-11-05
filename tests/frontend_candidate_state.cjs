const assert = require('node:assert/strict');
const fs = require('node:fs');
const { JSDOM } = require('jsdom');

async function run() {
    const dom = new JSDOM('', { url: 'https://qa.invalid', runScripts: 'outside-only' });
    const w = dom.window;
    const calls = [], notifications = [];
    w.showNotification = (...args) => notifications.push(args);
    w.showStatusNotification = (...args) => notifications.push(['success', ...args]);
    let handle = async (url) => ({ success: true, candidates: [{search_result_id:Number(url.split('=')[1]),status:'shortlisted',comments:'Server note'}] });
    w.fetch = async (url, options={}) => {
        calls.push({url,options});
        const body = await handle(url, options);
        return {ok:body.httpOk!==false, json:async()=>body};
    };
    w.Request=global.Request;
    w.Headers=global.Headers;
    w.document.cookie='csrf_token=synthetic-csrf';
    w.eval(fs.readFileSync('static/js/security.js','utf8'));
    w.eval(fs.readFileSync('static/js/candidate-state.js','utf8'));
    const card = id => {
        const element=w.document.createElement('div');
        element.className='professional-resume-card';
        element.dataset.searchResultId=String(id);
        element.dataset.candidateName='Same synthetic name';
        element.innerHTML=['selected','shortlisted','rejected','interviewed'].map(status=>
            `<input type="checkbox" class="hr-checkbox" data-status="${status}">`).join('')+
            '<textarea class="hr-comments-textarea"></textarea>';
        w.document.body.appendChild(element);
        return element;
    };
    const first=card(101), second=card(102);
    w.localStorage.setItem('candidateStatuses',JSON.stringify({'Same synthetic name':{status:'selected'}}));
    assert(await w.CandidateState.load(first));
    assert.equal(calls.length,1);
    assert(!calls[0].options.method); // Restoring state is read-only.
    assert(first.querySelector('[data-status="shortlisted"]').checked);
    assert.equal(first.querySelector('textarea').value,'Server note');
    assert(await w.CandidateState.load(second));

    handle=async()=>({success:true});
    const selected=first.querySelector('[data-status="selected"]');
    selected.checked=true;
    const before=calls.length;
    assert(await w.CandidateState.setStatus(first,'selected',selected));
    assert.equal(calls.length,before+1); // One atomic POST, not four independent writes.
    assert.equal(calls.at(-1).options.body.get('search_result_id'),'101');
    assert.equal(calls.at(-1).options.headers.get('X-CSRF-Token'),'synthetic-csrf');
    assert(selected.checked);
    assert(!first.querySelector('[data-status="shortlisted"]').checked);
    assert(second.querySelector('[data-status="shortlisted"]').checked);

    handle=async()=>({httpOk:false,success:false});
    const rejected=first.querySelector('[data-status="rejected"]');
    rejected.checked=true;
    const notices=notifications.length;
    assert.equal(await w.CandidateState.setStatus(first,'rejected',rejected),false);
    assert(selected.checked && !rejected.checked);
    assert.equal(notifications.length,notices+1);
    assert.equal(notifications.at(-1)[1],'error');
    assert(!selected.disabled);

    const textarea=second.querySelector('textarea');
    textarea.value='Unsaved fictional note';
    assert.equal(await w.CandidateState.saveNotes(second,textarea),false);
    assert.equal(textarea.value,'Unsaved fictional note');
    assert.equal(textarea.getAttribute('aria-invalid'),'true');

    handle=async()=>({success:true});
    assert(await w.CandidateState.saveNotes(second,textarea));
    assert.equal(calls.at(-1).url,'/api/candidate-notes/102');
    assert.equal(calls.at(-1).options.method,'PATCH');
    assert.equal(textarea.getAttribute('aria-invalid'),null);
    assert.equal(w.localStorage.getItem('candidateComments'),null);

    let release;
    const order=[];
    handle=async (url, options)=>{
        const value=JSON.parse(options.body).comments;
        order.push(value);
        if (value==='First draft') await new Promise(resolve=>{release=resolve;});
        return {success:true};
    };
    textarea.value='First draft';
    const one=w.CandidateState.saveNotes(second,textarea);
    await new Promise(resolve=>setImmediate(resolve));
    textarea.value='Latest draft';
    const two=w.CandidateState.saveNotes(second,textarea);
    assert.deepEqual(order,['First draft']);
    release();
    assert(await one && await two);
    assert.deepEqual(order,['First draft','Latest draft']);
    assert.equal(textarea.value,'Latest draft');

    const third=card(103);
    let finishLoad;
    handle=async()=>new Promise(resolve=>{finishLoad=resolve;});
    const loading=w.CandidateState.load(third);
    const draft=third.querySelector('textarea');
    draft.value='New typing during load';
    draft.dispatchEvent(new w.Event('input'));
    finishLoad({success:true,candidates:[{search_result_id:103,status:null,comments:'Old saved text'}]});
    await loading;
    assert.equal(draft.value,'New typing during load');

    const fourth=card(104);
    let finishOldRead;
    handle=async (url)=>url.startsWith('/api/candidate-state')
        ? new Promise(resolve=>{finishOldRead=resolve;}) : {success:true};
    const oldRead=w.CandidateState.load(fourth);
    const newest=fourth.querySelector('textarea');
    newest.value='Saved while an older read was pending';
    newest.dispatchEvent(new w.Event('input'));
    assert(await w.CandidateState.saveNotes(fourth,newest));
    finishOldRead({success:true,candidates:[{search_result_id:104,status:null,comments:'Stale read'}]});
    await oldRead;
    assert.equal(newest.value,'Saved while an older read was pending');

    const bad=card('not-a-saved-id');
    const count=calls.length;
    assert.equal(await w.CandidateState.load(bad),false);
    assert.equal(calls.length,count);
    assert(bad.querySelector('input').disabled);
    const events=w.document.addEventListener.bind(w.document);
    w.document.addEventListener=(name,...args)=>{ if(name!=='DOMContentLoaded') events(name,...args); };
    w.eval(fs.readFileSync('static/js/main.js','utf8'));
    const canvas=w.document.createElement('canvas');
    w.document.body.appendChild(canvas);
    let destroyed=0;
    w.Chart={getChart:node=>node===canvas?{destroy:()=>{destroyed++;}}:undefined};
    w.destroyCanvasCharts(w.document.body);
    assert.equal(destroyed,1);
    const mainSource=fs.readFileSync('static/js/main.js','utf8');
    assert(mainSource.includes('aria-label="Candidate search requirements"'));
    assert(mainSource.includes('aria-label="Search candidates"'));
    assert(mainSource.includes("listItem.tabIndex = 0"));
    assert(mainSource.includes("event.key === 'Enter' || event.key === ' '"));
    dom.window.close();
    console.log('Candidate DOM workflows passed: read-only restoration, atomic status save, failure rollback, same-name isolation, notes without decisions, preserved drafts, ordered saves, invalid-ID protection.');
}
run().catch(error=>{console.error(error);process.exitCode=1;});
