const assert=require('node:assert/strict');
const fs=require('node:fs');
const {JSDOM}=require('jsdom');
const source=fs.readFileSync('static/js/main.js','utf8');
const flush=()=>new Promise(resolve=>setImmediate(resolve));
const ok=data=>({ok:true,json:async()=>data});
async function setup(lateConfig=false){
    const dom=new JSDOM('<main id="root"></main>',{url:'https://qa.invalid',runScripts:'outside-only'});
    const w=dom.window,d=w.document,requests=[],pending=[];
    w.Request=global.Request;w.Headers=global.Headers;w.showNotification=()=>{};
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
        return ok({results:[{success:true,vector_indexed:true}],batch_stats:{successful:1,failed:0,total:1},email_stats:{total_emails:1,total_attachments:1,successful_uploads:1,failed_uploads:0}});
    };
    w.eval(source.slice(source.indexOf('    function initializeUploadPage()'),source.indexOf('    // Navigation event listeners'))+';initializeUploadPage();');
    const folders=[{bucket:'fixture',path:'resume'},{bucket:'fixture',path:'email_attachments/Design'},{bucket:'fixture',path:'<img src=x onerror=bad()>'},{bucket:'other',path:'Other company'}];
    const inventory=extra=>ok({success:true,folders:[...folders,...(extra||[])]});
    return{dom,w,d,requests,pending,inventory,resolveConfig};
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
    console.log('Upload folder picker passed: explicit existing/new modes, safe options, validation, retained drafts, exact bulk/email payloads, created-folder refresh, error recovery and stale-page protection.');
})().catch(error=>{console.error(error);process.exitCode=1;});
