const assert=require('node:assert/strict');
const fs=require('node:fs');
const {JSDOM}=require('jsdom');
const flush=()=>new Promise(resolve=>setTimeout(resolve,15));
const moduleSource=name=>fs.readFileSync('static/js/'+name+'.js','utf8');
function setup(html='<div id="root"></div>'){
    const dom=new JSDOM(html,{url:'https://qa.invalid',runScripts:'outside-only'}),w=dom.window;
    w.escapeHtml=value=>String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    w.currentUser={id:7,company:{company_id:1}};return dom;
}
async function quickTags(){
    const dom=setup(),w=dom.window,root=w.document.getElementById('root');let calls=0;
    w.fetch=async url=>{calls++;assert.equal(url,'/api/resume-folders');return{ok:true,json:async()=>({success:true,supported:true,
        folders:[{bucket:'one',path:'Mailbox 2026',total:4}],tags:['UI design','Management'],
        tag_counts:{'UI design':{searchable:3},Management:{searchable:0}}})};};
    w.eval(moduleSource('resume-folders'));const dispose=w.ResumeFolders.mount(root,{quickTags:true});await flush();
    const picker=root.querySelector('[data-tag-choice]');
    assert(picker,'The main search must expose its tag selector');
    assert.equal(picker.closest('details'),null,'Tag selection must be visible without opening advanced filters');
    assert(picker.closest('label').textContent.includes('Search by tag'));
    assert.equal(picker.querySelector('[value="Management"]').textContent,'Management (0)');
    assert.equal(picker.querySelector('[value="Management"]').disabled,false,'A zero-count tag must remain an explicit empty scope');
    root.querySelector('[data-folder="0"]').click();
    for(const [selector,value] of [['[data-from]','2026-01-01'],['[data-to]','2026-12-31'],['[data-basis]','received']]){
        const field=root.querySelector(selector);field.value=value;field.dispatchEvent(new w.Event('change'));
    }
    picker.value='UI design';picker.dispatchEvent(new w.Event('change'));
    assert.deepEqual(JSON.parse(JSON.stringify(w.ResumeFolders.getFilters())),{
        tags:['UI design'],date_from:'2026-01-01',date_to:'2026-12-31',date_basis:'received'});
    assert(root.querySelector('[data-tag="UI design"]').checked);
    assert.equal(w.ResumeFolders.getSelection()[0].path,'Mailbox 2026');
    root.querySelector('[data-tag="Management"]').click();
    assert.equal(picker.value,'__multiple__');assert.equal(picker.selectedOptions[0].textContent,'2 tags selected');
    assert.equal(w.ResumeFolders.getFilters().tags.length,2,'Rendering a multiple selection must not silently widen or narrow it');
    root.querySelector('[data-remove="tag"][data-value="Management"]').click();assert.equal(picker.value,'UI design');
    picker.value='Management';picker.dispatchEvent(new w.Event('change'));
    assert.deepEqual(Array.from(w.ResumeFolders.getFilters().tags),['Management']);
    assert.equal(root.querySelector('[data-tag="UI design"]').checked,false);
    picker.value='';picker.dispatchEvent(new w.Event('change'));
    assert.equal(w.ResumeFolders.getFilters().tags,undefined);
    assert.equal(w.ResumeFolders.getFilters().date_basis,'received');
    assert.equal(w.ResumeFolders.getSelection()[0].path,'Mailbox 2026','All tags must not clear folder/date scope');
    root.querySelector('[data-reset]').click();assert.equal(picker.value,'');assert.equal(calls,1,'Selecting tags must not call AI or refetch inventory');
    dispose();dom.window.close();
}
async function run(){
    await quickTags();
    const dom=setup(),w=dom.window,d=w.document,root=d.getElementById('root');let calls=0;
    w.fetch=async()=>{calls++;return{ok:true,json:async()=>({success:true,supported:true,folders:[
        {bucket:'one',path:'New CVs',total:100},{bucket:'one',path:'<img src=x onerror=bad()>',total:5}],tags:['UI design','Management']})};};
    w.eval(moduleSource('resume-folders'));let dispose=w.ResumeFolders.mount(root);await flush();
    assert.equal(calls,1);assert.equal(w.ResumeFolders.getSelection(),null);assert(root.querySelector('[data-all]').checked);
    assert.equal(root.querySelectorAll('img,[onerror]').length,0);
    root.querySelector('[data-folder="0"]').click();assert.equal(w.ResumeFolders.getSelection()[0].path,'New CVs');
    root.querySelector('[data-folder="1"]').click();assert.equal(w.ResumeFolders.getSelection().length,2);
    root.querySelector('[data-folder="0"]').click();root.querySelector('[data-folder="1"]').click();
    assert.throws(()=>w.ResumeFolders.validate(),/Choose at least one/);
    assert.equal(root.querySelector('[data-all]').checked,false);
    root.querySelector('[data-all]').click();assert.equal(w.ResumeFolders.getSelection(),null);
    root.querySelector('[data-tag="UI design"]').click();assert.equal(w.ResumeFolders.getFilters().tags[0],'UI design');
    root.querySelector('[data-from]').value='2026-11-06';root.querySelector('[data-from]').dispatchEvent(new w.Event('change'));
    root.querySelector('[data-to]').value='2026-11-05';root.querySelector('[data-to]').dispatchEvent(new w.Event('change'));
    assert.throws(()=>w.ResumeFolders.validate(),/start date/);
    root.querySelector('[data-reset]').click();w.ResumeFolders.validate();dispose();
    w.currentUser={id:8,company:{company_id:2}};assert.equal(Object.keys(w.ResumeFolders.getFilters()).length,0);
    let resolve;w.fetch=()=>new Promise(r=>{resolve=r;});dispose=w.ResumeFolders.mount(root);dispose();root.textContent='Replacement';
    resolve({ok:true,json:async()=>({success:true,supported:true,folders:[],tags:[]})});await flush();assert.equal(root.textContent,'Replacement');
    dom.window.close();

    const lib=setup(),lw=lib.window,ld=lw.document,lroot=ld.getElementById('root');let notices=[];
    lw.showNotification=(...args)=>notices.push(args);lw.bindScheduleDialog=()=>{};
    lw.fetch=async url=>({ok:true,json:async()=>url.includes('/1')?{success:true,file_name:'<svg onload=bad()>',file_path:'gs://one/a.pdf',text:'<script>bad()</script>'}:
        {success:true,total:26,uploads:[{id:1,file_name:'<img src=x onerror=bad()>',file_path:'gs://one/New CVs/a.pdf',upload_timestamp:'2026-11-06T10:00:00'}]}});
    lw.eval(moduleSource('resume-library'));const close=lw.ResumeLibrary.mount(lroot);await flush();
    assert(lroot.textContent.includes('26 uploaded CVs'));assert.equal(lroot.querySelectorAll('img,svg,[onerror]').length,0);
    assert.equal(lroot.querySelector('[data-next]').disabled,false);lroot.querySelector('[data-preview]').click();await flush();
    const modal=ld.querySelector('[data-library-dialog]');assert(modal);assert(modal.querySelector('pre').textContent.includes('<script>'));
    assert.equal(modal.querySelectorAll('script,svg,[onload]').length,0);modal.querySelector('[data-close]').click();
    lw.fetch=async()=>{throw Error('Network unavailable');};lroot.querySelector('[data-refresh]').click();await flush();
    assert(lroot.textContent.includes('Count unavailable'));assert(!lroot.textContent.includes('No CVs match'));
    close();lib.window.close();
    console.log('CV scope UI passed: explicit multiselect, empty-scope blocking, dates, account reset, safe library/preview, pagination, errors and stale loads.');
}
run().catch(error=>{console.error(error);process.exitCode=1;});
