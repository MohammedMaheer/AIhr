const assert=require('node:assert/strict');
const fs=require('node:fs');
const {JSDOM}=require('jsdom');
const source=fs.readFileSync('static/js/main.js','utf8');
const poll=source.slice(source.indexOf('function pollHRScorecardTask('),source.indexOf('// Make generateEnhancedResults available globally'));

async function run(){
    const dom=new JSDOM('',{url:'https://qa.invalid',runScripts:'outside-only'});
    const w=dom.window,calls=[],delays=[];
    w.console.log=()=>{};
    w.setTimeout=(fn,ms)=>{delays.push(ms);if(ms!==15000)queueMicrotask(fn);return 1;};
    w.clearTimeout=()=>{};
    const result={results:[{id:'synthetic'}],total_results:1};
    const response=(data,status=200,retryAfter=null)=>({ok:status===200,status,
        headers:{get:()=>retryAfter},json:async()=>data});
    let queue=[];
    w.fetch=async(url,options)=>{calls.push({url,options});const next=queue.shift();if(next instanceof Error)throw next;assert(next,'Unexpected extra request');return next;};
    w.eval(poll+';window.testPoll=pollHRScorecardTask;');
    queue=[new TypeError('synthetic network failure'),response({},429,'2'),response({},503),
        response({status:'processing'}),response({status:'completed'}),response({},503),response(result)];
    assert.equal((await w.testPoll('synthetic/task')).total_results,1);
    assert.equal(calls.length,7);
    assert(calls.every(x=>x.options.method==='GET'&&x.url.includes('synthetic%2Ftask')));
    assert(delays.includes(2000));
    calls.length=0;
    for(const code of [401,403,404]){
        queue=[response({},code)];
        const before=calls.length;
        await assert.rejects(w.testPoll('permanent'),/Session expired|unavailable/);
        assert.equal(calls.length,before+1);
    }
    queue=[response({status:'failed',error_message:'Synthetic permanent job failure'})];
    await assert.rejects(w.testPoll('failed'),/Synthetic permanent job failure/);
    calls.length=0;
    queue=[response({status:'completed'}),...Array.from({length:6},()=>response({},503))];
    await assert.rejects(w.testPoll('results-error'),/unavailable/);
    assert.equal(calls.length,7);
    calls.length=0;
    const malformed=response({});malformed.json=async()=>{throw new SyntaxError('HTML instead of JSON');};
    queue=[malformed,response({status:'completed'}),response(result)];
    assert.equal((await w.testPoll('malformed')).total_results,1);
    assert.equal(calls.length,3);

    const submit=source.slice(source.indexOf('const pendingCandidateSearches = new Map();'),
        source.indexOf('// Poll an HR-scorecard Cloud Task'));
    w.document.body.innerHTML='<input id="result-count" value="10">';
    w.currentUser={id:1,user_type:'tenant_admin',company:{company_id:7}};
    w.extractJobTitleFromQuery=()=> 'Synthetic role';
    let posts=0,polls=0,releases=[];
    w.fetch=async(url,options)=>{
        assert.equal(url,'/api/hr-scorecard-search');assert.equal(options.method,'POST');
        posts++;
        return new Promise(resolve=>releases.push(()=>resolve(response({task_id:'same-job',status:'pending'}))));
    };
    w.eval(submit+';window.submitSearch=performRealSearch;');
    w.pollHRScorecardTask=async()=>{polls++;return{results:[{id:'synthetic',score:90}]};};
    const first=w.submitSearch('Full unchanged requirements');
    const duplicate=w.submitSearch('Full unchanged requirements');
    assert.equal(posts,1);
    releases.splice(0).forEach(release=>release());
    const [a,b]=await Promise.all([first,duplicate]);
    assert.equal(polls,1);assert.deepEqual(a,b);
    a.results[0].score=0;assert.equal(b.results[0].score,90,'Consumers must not share mutable scorecards');
    const again=w.submitSearch('Full unchanged requirements');
    assert.equal(posts,2,'Completed requests must not remain cached');
    releases.splice(0).forEach(release=>release());await again;
    const original=w.submitSearch('Original requirements');
    const changed=w.submitSearch('Different requirements');
    w.document.getElementById('result-count').value='11';
    const count=w.submitSearch('Original requirements');
    w.currentUser={...w.currentUser,id:2};
    const otherUser=w.submitSearch('Original requirements');
    w.currentUser={...w.currentUser,company:{company_id:8}};
    const otherCompany=w.submitSearch('Original requirements');
    assert.equal(posts,7,'Different criteria, counts and identities must never be coalesced');
    releases.splice(0).forEach(release=>release());
    await Promise.all([original,changed,count,otherUser,otherCompany]);

    w.document.body.insertAdjacentHTML('beforeend','<div id="scope-controls"></div>');
    w.escapeHtml=value=>String(value).replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
    w.fetch=async()=>response({success:true,supported:true,folders:[
        {bucket:'fixture',path:'Campaign/Design',total:2},
        {bucket:'fixture',path:'Campaign/Network',total:1}],tags:['UI design','Management']});
    w.eval(fs.readFileSync('static/js/resume-folders.js','utf8'));
    const controls=w.document.getElementById('scope-controls');
    const dispose=w.ResumeFolders.mount(controls,{quickTags:true});
    await new Promise(resolve=>setImmediate(resolve));
    controls.querySelector('[data-folder="0"]').click();
    controls.querySelector('[data-folder="1"]').click();
    const tagChoice=controls.querySelector('[data-tag-choice]');
    tagChoice.value='UI design';tagChoice.dispatchEvent(new w.Event('change'));
    for(const [selector,value] of [['[data-from]','2026-04-01'],['[data-to]','2026-04-30'],['[data-basis]','received']]){
        const field=controls.querySelector(selector);field.value=value;field.dispatchEvent(new w.Event('change'));
    }
    const bodies=[];
    w.fetch=async(url,options)=>{
        assert.equal(url,'/api/hr-scorecard-search');
        bodies.push(Object.fromEntries(options.body.entries()));
        return new Promise(resolve=>releases.push(()=>resolve(response({task_id:'scoped-job',status:'pending'}))));
    };
    const selected=w.submitSearch('Scoped unchanged requirements');
    const sameScope=w.submitSearch('Scoped unchanged requirements');
    controls.querySelector('[data-folder="1"]').click();
    const differentFolder=w.submitSearch('Scoped unchanged requirements');
    controls.querySelector('[data-tag="Management"]').click();
    assert.equal(tagChoice.value,'__multiple__');
    const differentTags=w.submitSearch('Scoped unchanged requirements');
    controls.querySelector('[data-to]').value='2026-05-01';
    controls.querySelector('[data-to]').dispatchEvent(new w.Event('change'));
    const differentDates=w.submitSearch('Scoped unchanged requirements');
    assert.equal(bodies.length,4,'Folder, tag and date changes must not reuse a pending wider request');
    assert.deepEqual(JSON.parse(bodies[0].folders),[
        {bucket:'fixture',path:'Campaign/Design'},{bucket:'fixture',path:'Campaign/Network'}]);
    assert.deepEqual(JSON.parse(bodies[0].filters),{
        tags:['UI design'],date_from:'2026-04-01',date_to:'2026-04-30',date_basis:'received'});
    assert.equal(JSON.parse(bodies[1].folders).length,1);
    assert.equal(JSON.parse(bodies[2].filters).tags.length,2);
    assert.equal(JSON.parse(bodies[3].filters).date_to,'2026-05-01');
    releases.splice(0).forEach(release=>release());
    const scopedResults=await Promise.all([selected,sameScope,differentFolder,differentTags,differentDates]);
    assert.equal(scopedResults[0].folder_filters.length,2,'Editing current controls must not change an earlier request');
    assert.equal(scopedResults[0].resume_filters.date_to,'2026-04-30');
    controls.querySelector('[data-folder="0"]').click();
    await assert.rejects(w.submitSearch('No folder selected'),/Choose at least one/);
    assert.equal(bodies.length,4,'An explicit empty selection must not send a wider search');
    controls.querySelector('[data-all]').click();
    controls.querySelector('[data-reset]').click();
    const all=w.submitSearch('All folders explicitly selected');
    assert.equal(bodies[4].folders,undefined);
    assert.equal(bodies[4].filters,undefined);
    releases.splice(0).forEach(release=>release());await all;
    dispose();
    let failures=0;
    w.fetch=async()=>{failures++;throw new TypeError('Synthetic unavailable transport');};
    await assert.rejects(w.submitSearch('Retryable request'),/Synthetic unavailable/);
    await assert.rejects(w.submitSearch('Retryable request'),/Synthetic unavailable/);
    assert.equal(failures,2,'A failed request must release its exact-request guard');
    const coalescedProgress=[];
    w.fetch=async()=>new Promise(resolve=>releases.push(()=>resolve(response({task_id:'shared-progress',status:'pending'}))));
    w.pollHRScorecardTask=async(_task,opts)=>{
        opts.onProgress({step:'reviewing'});
        return {results:[]};
    };
    const progressFirst=w.submitSearch('Shared progress',status=>coalescedProgress.push('first:'+status.step));
    const progressSecond=w.submitSearch('Shared progress',status=>coalescedProgress.push('second:'+status.step));
    releases.splice(0).forEach(release=>release());
    await Promise.all([progressFirst,progressSecond]);
    assert.deepEqual(coalescedProgress,['first:reviewing','second:reviewing'],'Each coalesced consumer must receive progress without starting another job');
    dom.window.close();
    console.log('Polling regressions passed: GET recovery, bounded failures, exact-request coalescing, real folder/tag/date controls to POST payloads, scope isolation, validation and retry cleanup.');
}
run().catch(error=>{console.error(error);process.exitCode=1;});
