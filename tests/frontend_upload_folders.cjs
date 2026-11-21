const assert=require('node:assert/strict');
const fs=require('node:fs');
const {JSDOM}=require('jsdom');
const source=fs.readFileSync('static/js/main.js','utf8');
const flush=()=>new Promise(resolve=>setImmediate(resolve));
const ok=data=>({ok:true,json:async()=>data});
async function setup(lateConfig=false, manualUpload=null){
    const dom=new JSDOM('<main id="root"></main>',{url:'https://qa.invalid',runScripts:'outside-only'});
    const w=dom.window,d=w.document,requests=[],pending=[],notices=[],delays=[];
    w.Request=global.Request;w.Headers=global.Headers;w.showNotification=(...args)=>notices.push(args);
    if(manualUpload){const real=w.setTimeout.bind(w);w.setTimeout=(handler,ms)=>{delays.push(ms);return real(handler,0);};}
    w.fetch=async()=>ok({});
    w.eval(fs.readFileSync('static/js/security.js','utf8'));
    const start=source.indexOf('    const pages = {');
    w.eval(source.slice(source.indexOf('    // Search history storage'),start)+source.slice(start,source.indexOf('\n    };',start)+7)+';window.pages=pages;');
    d.getElementById('root').innerHTML=w.pages.uploadFiles;
    let resolveConfig;
    const config={configured:true,bucket_name:'fixture',default_folder:'resume/'};
    w.fetch=async(url,options={})=>{
        requests.push({url,options});
        if(url==='/api/gcs-status'){
            if(lateConfig){lateConfig=false;return new Promise(resolve=>{resolveConfig=()=>resolve(ok(config));});}
            return ok(config);
        }
        if(url==='/api/resume-folders')return new Promise(resolve=>pending.push(resolve));
        assert.equal(url,'/api/upload-files');
        if(manualUpload)return manualUpload(options.body.getAll('files').map(f=>f.name));
        return ok({results:[{success:true,vector_indexed:true}],batch_stats:{successful:1,failed:0,total:1},email_stats:{total_emails:1,total_attachments:1,successful_uploads:1,failed_uploads:0}});
    };
    w.eval(source.slice(source.indexOf('    function initializeUploadPage()'),source.indexOf('    // Navigation event listeners'))+';initializeUploadPage();');
    const folders=[{bucket:'fixture',path:'resume'},{bucket:'fixture',path:'email_attachments/Design'},{bucket:'fixture',path:'<img src=x onerror=bad()>'},{bucket:'other',path:'Other company'}];
    const inventory=extra=>ok({success:true,folders:[...folders,...(extra||[])]});
    return{dom,w,d,requests,pending,inventory,resolveConfig,notices,delays};
}

const rejected=(status,retryAfter=null)=>({ok:false,status,headers:new Headers(retryAfter?{'Retry-After':retryAfter}:{}),
    json:async()=>{throw new SyntaxError('non-JSON response');}});
const indexed=names=>ok({results:names.map(filename=>({filename,success:true,vector_indexed:true}))});
async function queueWith(handler,count){
    const env=await setup(false,handler);
    const {w,d,pending,inventory}=env;
    pending.shift()(inventory());await flush();await flush();
    const input=d.getElementById('file-input');
    Object.defineProperty(input,'files',{value:Array.from({length:count},(_,i)=>new w.File(['%PDF-fixture'],`safe-${i}.pdf`))});
    input.dispatchEvent(new w.Event('change'));
    return {...env,start:d.getElementById('start-upload'),text:()=>d.getElementById('upload-queue').textContent};
}
async function until(check){
    for(let i=0;i<70;i++){if(check())return;await new Promise(resolve=>setTimeout(resolve,5));}
    assert.fail('Upload state did not settle');
}
async function checkRecovery(){
    const busyCalls=[];
    const busy=await queueWith(names=>{busyCalls.push(names);return busyCalls.length===1?rejected(429,'3'):indexed(names);},2);
    Object.defineProperty(busy.w.navigator,'onLine',{value:false,configurable:true});
    busy.start.click();await flush();assert.equal(busyCalls.length,0);
    assert.match(busy.notices.at(-1)[0],/offline/);
    Reflect.deleteProperty(busy.w.navigator,'onLine');
    busy.start.click();await until(()=>busyCalls.length===2 && busy.text().includes('completed'));
    assert.deepEqual(busyCalls[0],busyCalls[1]);assert(busy.delays.includes(3000));assert(busy.start.disabled);
    busy.dom.window.close();

    const splitCalls=[];
    const split=await queueWith(names=>{splitCalls.push(names);return names.length>1?rejected(413):indexed(names);},3);
    split.start.click();await until(()=>splitCalls.length===4 && split.notices.length);
    assert.deepEqual(splitCalls.slice(1).flat(),splitCalls[0]);assert(split.start.disabled);
    split.dom.window.close();

    const lostCalls=[];
    const lost=await queueWith(names=>{lostCalls.push(names);if(lostCalls.length===1)throw new TypeError('connection dropped');return indexed(names);},51);
    lost.start.click();await until(()=>lost.text().includes('Unconfirmed') && !lost.start.disabled);
    assert.equal(lostCalls.length,1);assert.equal(lostCalls[0].length,50);
    assert.equal(lost.d.getElementById('overall-progress-text').textContent,'0%');
    lost.start.click();await until(()=>lostCalls.length===2 && lost.text().includes('completed'));
    assert.deepEqual(lostCalls[1],['safe-50.pdf']);assert(lost.text().includes('Unconfirmed'));
    lost.dom.window.close();

    for(const response of [rejected(503),rejected(408),ok({results:[]})]){
        let attempts=0;
        const uncertain=await queueWith(()=>{attempts++;return response;},1);
        uncertain.start.click();await until(()=>uncertain.text().includes('Unconfirmed'));
        assert.equal(attempts,1);assert(uncertain.start.disabled);
        uncertain.dom.window.close();
    }

    let delayedCalls=0;
    const delayed=await queueWith(()=>{delayedCalls++;return rejected(429,'60');},1);
    delayed.start.click();await until(()=>delayed.notices.length);
    assert.equal(delayedCalls,1);assert(!delayed.start.disabled);
    assert.match(delayed.notices.at(-1)[0],/pending files/);
    delayed.dom.window.close();
}
(async()=>{
    const {dom,w,d,requests,pending,inventory}=await setup();
    pending.shift()(inventory());await flush();await flush();
    const choice=d.getElementById('upload-folder-choice'),field=d.getElementById('upload-folder'),editor=d.getElementById('upload-folder-editor');
    assert.equal(choice.value,'resume');assert(editor.hidden);
    assert(![...choice.options].some(option=>option.value==='Other company'),'Folder choices must match the destination bucket');
    assert.equal(d.querySelectorAll('#upload-folder-choice img,[onerror]').length,0);
    choice.value='email_attachments/Design';choice.dispatchEvent(new w.Event('change'));
    assert.equal(field.value,'email_attachments/Design');assert(editor.hidden);
    d.getElementById('upload-folder-add').click();assert.equal(field.value,'');assert(!editor.hidden);assert(!field.checkValidity());
    field.value='Networking/Nov 2026';field.dispatchEvent(new w.Event('input'));assert(field.checkValidity());
    choice.value='resume';choice.dispatchEvent(new w.Event('change'));
    choice.value='';choice.dispatchEvent(new w.Event('change'));assert.equal(field.value,'Networking/Nov 2026','Switching modes must retain the new-folder draft');
    for(const invalid of ['   ','../secret','/root','a//b','a\\b']){
        field.value=invalid;field.dispatchEvent(new w.Event('input'));assert(!field.checkValidity(),invalid);
    }
    field.value='Networking/Nov 2026';field.dispatchEvent(new w.Event('input'));
    const files=d.getElementById('file-input');Object.defineProperty(files,'files',{value:[new w.File(['%PDF-fixture'],'fictional.pdf')]});
    files.dispatchEvent(new w.Event('change'));d.getElementById('start-upload').click();await flush();await flush();
    const upload=requests.find(item=>item.options.method==='POST');assert.equal(upload.options.body.get('folder_path'),'Networking/Nov 2026');
    pending.shift()(inventory([{bucket:'fixture',path:'Networking/Nov 2026'}]));await flush();
    assert.equal(choice.value,'Networking/Nov 2026','A successfully created destination becomes an existing choice');assert(editor.hidden);
    d.getElementById('email-provider').value='outlook';d.getElementById('email-address').value='fixture@example.invalid';
    d.getElementById('start-email-scrape').click();await flush();await flush();
    const email=requests.filter(item=>item.options.method==='POST').at(-1);
    assert.equal(email.options.body.get('folder_path'),'Networking/Nov 2026');assert.equal(email.options.body.get('scrape_email'),'true');
    pending.shift()(inventory());await flush();
    d.getElementById('upload-folder-refresh').click();pending.shift()({ok:false,json:async()=>({})});await flush();
    assert(d.getElementById('upload-folder-status').textContent.includes('unavailable'));assert.equal(field.value,'Networking/Nov 2026');
    dom.window.close();
    const late=await setup(true);
    late.d.getElementById('upload-folder-add').click();const draft=late.d.getElementById('upload-folder');
    draft.value='My new folder';draft.dispatchEvent(new late.w.Event('input'));
    late.resolveConfig();late.pending.shift()(late.inventory());await flush();await flush();
    assert.equal(draft.value,'My new folder','Late defaults must not replace user input');
    const pendingRead=[];late.w.fetch=()=>new Promise(resolve=>pendingRead.push(resolve));
    late.d.getElementById('upload-folder-refresh').click();late.d.getElementById('root').innerHTML='Replacement page';
    pendingRead[0](late.inventory());await flush();assert.equal(late.d.getElementById('root').textContent,'Replacement page');
    late.dom.window.close();
    await checkRecovery();
    console.log('Upload folder picker passed: explicit existing/new modes, safe options, validation, retained drafts, exact bulk/email payloads, created-folder refresh, error recovery and stale-page protection.');
    console.log('Upload recovery passed: offline hold, bounded busy retry, size split, unconfirmed response, and resume only untouched files.');
})().catch(error=>{console.error(error);process.exitCode=1;});
