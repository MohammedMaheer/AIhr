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
    let failures=0;
    w.fetch=async()=>{failures++;throw new TypeError('Synthetic unavailable transport');};
    await assert.rejects(w.submitSearch('Retryable request'),/Synthetic unavailable/);
    await assert.rejects(w.submitSearch('Retryable request'),/Synthetic unavailable/);
    assert.equal(failures,2,'A failed request must release its exact-request guard');
    dom.window.close();
    console.log('Polling regressions passed: same-job GET recovery, bounded failures, exact-request coalescing, result isolation, identity/count separation and retry cleanup.');
}
run().catch(error=>{console.error(error);process.exitCode=1;});
