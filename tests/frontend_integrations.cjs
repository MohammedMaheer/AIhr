const assert = require('node:assert/strict');
const fs = require('node:fs');
const {JSDOM} = require('jsdom');
const source = fs.readFileSync('static/js/main.js','utf8').replace(/\r\n/g,'\n');
const settings = source.match(/settings: `([\s\S]*?)`/)[1];
const init = source.slice(source.indexOf('async function initializeRecruiterIntegrations()'), source.indexOf('// Load current user information'));
const flush = () => new Promise(resolve => setImmediate(resolve));

async function run() {
    const dom = new JSDOM(settings, {url:'https://qa.invalid',runScripts:'outside-only'});
    const w = dom.window, d = w.document, calls=[];
    let connected=true, fail=false, failRead=false;
    const notice=d.querySelector('[data-connection-notice]');
    notice.textContent='Sign-in returned. Checking your saved connection...';
    w.confirm=()=>true;
    w.Headers=global.Headers;w.Request=global.Request;
    d.cookie='csrf_token=synthetic-csrf';
    w.fetch=async(url,options={})=>{
        calls.push({url,options});
        if (url.includes('/disconnect')) {
            if(!fail) connected=false;
            return {ok:!fail,json:async()=>({success:!fail})};
        }
        if(failRead) throw new TypeError('synthetic network failure');
        return {ok:true,json:async()=>({success:true,microsoft:{client_configured:true,connected,
            account_email:'<img src=x onerror=bad()>@example.invalid',reconnect_required:connected},
            google:{client_configured:false,connected:false},smtp:{configured:false}})};
    };
    w.eval(fs.readFileSync('static/js/security.js','utf8'));
    w.eval(init);
    await w.initializeRecruiterIntegrations();
    const ms=d.querySelector('[data-provider="microsoft"]');
    assert.equal(notice.textContent,'');
    assert(ms.querySelector('[data-account-state]').textContent.includes('Reconnect required'));
    assert.equal(ms.querySelectorAll('img').length,0);
    assert.equal(ms.querySelector('[data-connect]').disabled,false);
    assert.equal(d.querySelector('[data-provider="google"] [data-connect]').disabled,true);
    assert.equal(calls.length,1);
    assert(!calls[0].options.method);
    w.confirm=()=>false;
    ms.querySelector('[data-disconnect]').click();await flush();
    assert.equal(calls.length,1);
    w.confirm=()=>true;
    ms.querySelector('[data-disconnect]').click();await flush();
    assert.equal(calls.filter(x=>x.options.method==='POST').length,1);
    assert.equal(calls.find(x=>x.options.method==='POST').options.headers.get('X-CSRF-Token'),'synthetic-csrf');
    assert.equal(ms.querySelector('[data-account-state]').textContent,'Not connected');
    assert.equal(ms.querySelector('[data-disconnect]').disabled,true);
    connected=true;
    d.querySelector('[data-refresh-connections]').click();await flush();
    fail=true;
    ms.querySelector('[data-disconnect]').click();await flush();
    assert(notice.textContent.includes('could not be disconnected'));
    assert.equal(ms.querySelector('[data-disconnect]').disabled,false);
    failRead=true;
    d.querySelector('[data-refresh-connections]').click();await flush();
    assert(notice.textContent.includes('unavailable'));
    assert([...d.querySelectorAll('[data-connect],[data-disconnect]')].every(x=>x.disabled));
    dom.window.close();

    const dialogDom=new JSDOM('<div id="app-shell"><button id="opener">Open</button></div><div id="dialog"><button id="first">Close</button><label>Name<input id="name"></label><button id="last">Save</button></div>',{url:'https://qa.invalid',runScripts:'outside-only'});
    const dw=dialogDom.window, dd=dw.document;
    dw.eval(source.slice(source.indexOf('function bindScheduleDialog('),source.indexOf('function closeInterviewModal()')));
    dd.getElementById('opener').focus();
    const dialog=dd.getElementById('dialog');
    dw.bindScheduleDialog(dialog,'Synthetic dialog');
    assert.equal(dialog.getAttribute('role'),'dialog');
    assert.equal(dd.querySelector('label').htmlFor,'name');
    assert(dd.getElementById('app-shell').inert);
    dd.getElementById('first').dispatchEvent(new dw.KeyboardEvent('keydown',{key:'Tab',shiftKey:true,bubbles:true}));
    assert.equal(dd.activeElement.id,'last');
    dd.getElementById('last').dispatchEvent(new dw.KeyboardEvent('keydown',{key:'Tab',bubbles:true}));
    assert.equal(dd.activeElement.id,'first');
    dialog.dispatchEvent(new dw.KeyboardEvent('keydown',{key:'Escape',bubbles:true}));
    await flush();
    assert.equal(dd.getElementById('app-shell').inert,false);
    assert.equal(dd.activeElement.id,'opener');
    dialogDom.window.close();

    const scheduleDom=new JSDOM('<form id="f"><button type="submit">Save</button></form>',{url:'https://qa.invalid',runScripts:'outside-only'});
    const sw=scheduleDom.window, sd=sw.document, events=[],requests=[];
    for(const id of ['type','date','time','duration','location','interviewer','notes','provider']){
        const input=sd.createElement('input');input.id='interview-'+id;input.value=id==='date'?'2030-01-02':id==='time'?'10:00':id==='duration'?'30':id==='provider'?'teams':'synthetic';sd.getElementById('f').append(input);
    }
    sw.showNotification=(...args)=>events.push(args);sw.closeInterviewModal=()=>{};
    sw.fetch=async(url,options)=>{requests.push({url,options});return{ok:true,json:async()=>({success:true,meeting:{success:false,error:'Link unavailable'},email:{success:false,error:'Email skipped'}})}};
    sw.eval(source.slice(source.indexOf('async function saveInterviewSchedule('),source.indexOf('// =============================================================================\n// GLOBAL HANDLER SAFETY NET')));
    await sw.saveInterviewSchedule({preventDefault(){},target:sd.getElementById('f')},'Synthetic Candidate','fictional@example.invalid');
    assert.equal(requests.length,1);
    assert.equal(requests[0].url,'/api/schedule-interview');
    assert.equal(events.filter(x=>x[1]==='warning').length,2);
    assert(events.some(x=>x[1]==='success'));
    assert(!source.slice(source.indexOf('async function saveInterviewSchedule(')).includes('actionForm.append'));
    scheduleDom.window.close();

    for (const kind of ['general','candidate']) {
        const dom=new JSDOM('<div id="user-dashboard"></div><form id="f"><button type="submit">Original submit label</button></form>',{url:'https://qa.invalid',runScripts:'outside-only'});
        const w=dom.window,d=w.document,form=d.getElementById('f'),notices=[];
        const fields=kind==='general'?['candidate-name','candidate-email','type','date','time','duration','location','interviewer','notes','provider']:['type','date','time','duration','location','interviewer','notes','provider'];
        for(const field of fields){
            const input=d.createElement('input');input.id=(kind==='general'?'gs-':'interview-')+field;
            input.value=field==='date'?'2030-01-02':field==='time'?'10:00':field==='duration'?'30':field==='provider'?'teams':field==='candidate-email'?'fictional@example.invalid':'Synthetic';form.append(input);
        }
        w.showNotification=(...args)=>notices.push(args);
        w.closeInterviewModal=w.closeGeneralScheduleModal=()=>{};
        w.loadUpcomingEvents=async()=>{throw new Error('Synthetic refresh failure after confirmation');};
        w.console.error=()=>{};
        const start=kind==='general'?'async function submitGeneralScheduleForm(':'async function saveInterviewSchedule(';
        const end=kind==='general'?'function showInterviewScheduleModal(':'// =============================================================================\n// GLOBAL HANDLER SAFETY NET';
        w.eval(source.slice(source.indexOf(start),source.indexOf(end)));
        let requests=0,resolve;
        w.fetch=()=>{requests++;return new Promise(done=>{resolve=done;});};
        const submit=()=>kind==='general'?w.submitGeneralScheduleForm({preventDefault(){},target:form}):w.saveInterviewSchedule({preventDefault(){},target:form},'Synthetic','fictional@example.invalid');
        const pending=submit();await submit();
        assert.equal(requests,1,kind+' must not submit a second pending request');
        assert.equal(form.querySelector('button').disabled,true);
        resolve({ok:true,json:async()=>({success:true})});await pending;
        assert(notices.some(n=>n[1]==='success'));
        assert(!notices.some(n=>n[1]==='error'),kind+' must not call a confirmed schedule a failure when refresh fails');
        assert.equal(form.querySelector('button').disabled,false);
        assert.equal(form.querySelector('button').textContent,'Original submit label');
        notices.length=0;
        w.fetch=async()=>{requests++;throw new TypeError('Synthetic connection loss');};
        await submit();
        assert.equal(requests,2,kind+' must not auto-retry an unconfirmed POST');
        assert(notices.some(n=>n[1]==='error'&&n[0].includes('Check your schedule before trying again')));
        assert.equal(form.querySelector('button').disabled,false);
        assert.equal(form.dataset.submitting,undefined);
        dom.window.close();
    }
    console.log('Integration DOM workflows passed: authoritative status, safe text, CSRF disconnect, errors, focus, duplicate-submit guards and honest scheduling outcomes.');
}
run().catch(error=>{console.error(error);process.exitCode=1;});
