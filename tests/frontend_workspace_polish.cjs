const assert=require('node:assert/strict');
const fs=require('node:fs');
const {JSDOM}=require('jsdom');
const main=fs.readFileSync('static/js/main.js','utf8');
const bind=main.slice(main.indexOf('function bindScheduleDialog('),main.indexOf('function closeInterviewModal('));
const flush=()=>new Promise(resolve=>setImmediate(resolve));
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
function setup(module){
    const dom=new JSDOM('<div id="app-shell"><button id="opener">Filters</button><section id="root"></section></div>',{url:'https://qa.invalid/',runScripts:'outside-only'});
    const w=dom.window,d=w.document;
    w.escapeHtml=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    w.currentUser={id:7,user_type:'super_admin',company:{company_id:1}};w.showNotification=()=>{};w.loadPage=()=>{};
    w.eval(bind);w.eval(fs.readFileSync('static/js/'+module+'.js','utf8'));
    return{dom,w,d,root:d.getElementById('root')};
}
async function filters(){
    const {dom,w,d,root}=setup('resume-folders'),RealDate=w.Date;
    w.Date=class extends RealDate{constructor(...args){super(...(args.length?args:[2027,7,31,12]));}};
    let calls=0;
    w.fetch=async()=>{calls++;return{ok:true,json:async()=>({success:true,supported:true,
        folders:[{bucket:'fixture',path:'Design/New',total:10},{bucket:'fixture',path:'Network/New',total:20}],tags:['UI design','Management'],tag_counts:{'UI design':{total:10,searchable:8}}})};};
    let dispose=w.ResumeFolders.mount(root);await flush();
    assert.equal(root.querySelector('[data-range]').getAttribute('aria-label'),'Period');
    root.querySelector('[data-range]').value='6';root.querySelector('[data-range]').dispatchEvent(new w.Event('change'));
    assert.equal(w.ResumeFolders.getFilters().date_from,'2027-02-28','Month-end presets must clamp to a valid date');
    assert.equal(w.ResumeFolders.getFilters().date_to,'2027-08-31');
    root.querySelector('[data-folder="0"]').click();root.querySelector('[data-tag="UI design"]').click();
    assert.equal(root.querySelector('[data-tag="UI design"]').closest('label').querySelector('small').textContent,'8');
    root.querySelector('[data-tag-query]').value='Management';root.querySelector('[data-tag-query]').dispatchEvent(new w.Event('input'));
    assert(root.querySelector('[data-tag="UI design"]').closest('label').hidden);
    assert.equal(w.ResumeFolders.getFilters().tags[0],'UI design','Filtering tag choices must retain the selected tag');
    root.querySelector('[data-folder-query]').value='network';root.querySelector('[data-folder-query]').dispatchEvent(new w.Event('input'));
    assert.equal(root.querySelector('[data-folder="0"]').closest('label').hidden,true);
    assert.equal(w.ResumeFolders.getSelection()[0].path,'Design/New','Filtering visible folders must retain checked hidden selections');
    root.querySelector('[data-remove="folder"]').click();assert.throws(()=>w.ResumeFolders.validate(),/at least one/);
    assert.equal(root.querySelector('[data-filter-error]').hidden,false);
    root.querySelector('[data-reset]').click();assert.equal(w.ResumeFolders.getSelection(),null);
    d.getElementById('opener').focus();w.ResumeFolders.openDialog();await flush();
    const modal=d.querySelector('[data-cv-filter-dialog]');assert(modal);
    assert.equal(modal.getAttribute('role'),'dialog');assert.equal(d.getElementById('app-shell').inert,true);
    modal.querySelector('[data-folder="1"]').click();
    assert.equal(root.querySelector('[data-folder="1"]').checked,true,'The results dialog and main filter view must stay synchronized');
    modal.querySelector('[data-tag="Management"]').click();
    assert(w.ResumeFolders.summary().includes('1 tag'));
    modal.querySelector('[data-done]').click();await flush();
    assert(!modal.isConnected);assert.equal(d.getElementById('app-shell').inert,false);
    assert.equal(d.activeElement.id,'opener');
    dispose();root.innerHTML='';
    w.fetch=async()=>({ok:false,json:async()=>({})});dispose=w.ResumeFolders.mount(root);await flush();
    assert(root.textContent.includes('CV filters unavailable'));
    assert.equal(w.ResumeFolders.getSelection()[0].path,'Network/New','A load failure must not widen a prior scope');
    assert.equal(calls,2);dispose();dom.window.close();
}
async function library(){
    const {dom,w,d,root}=setup('resume-library');const requests=[];
    const rows=Array.from({length:55},(_,i)=>({id:i+1,file_name:'Fictional CV '+(i+1)+'.pdf',file_path:'gs://fixture/Design/cv-'+(i+1)+'.pdf',file_size:81920,upload_timestamp:'2026-11-06T10:00:00'}));
    const response=data=>({ok:true,json:async()=>data});
    w.fetch=async url=>{
        requests.push(url);const parsed=new URL(url,'https://qa.invalid');
        if(parsed.pathname==='/api/resume-library'){
            const query=parsed.searchParams.get('query')||'',offset=Number(parsed.searchParams.get('offset'))||0;
            const filtered=rows.filter(row=>row.file_name.includes(query));
            return response({success:true,total:filtered.length,uploads:filtered.slice(offset,offset+25)});
        }
        return response({success:true,file_name:'Fictional CV.pdf',file_path:'gs://fixture/cv.pdf',text:'Fictional preview'});
    };
    const dispose=w.ResumeLibrary.mount(root);await flush();
    assert(root.textContent.includes('80 KB'));assert.equal(root.querySelector('[data-page-number]').max,'3');
    root.querySelector('[data-page-number]').value='3';root.querySelector('[data-page-number]').dispatchEvent(new w.Event('change'));await flush();
    assert(root.querySelector('[data-page]').textContent.includes('51-55 of 55'));
    root.querySelector('#library-query').value='missing';root.querySelector('#library-query').dispatchEvent(new w.Event('input'));
    assert.equal(root.querySelector('[data-next]').disabled,true);await pause(270);await flush();
    assert(root.textContent.includes('No matching CVs'));assert.equal(root.querySelector('[data-page-number]').disabled,true);
    assert(requests.at(-1).includes('offset=0'));root.querySelector('[data-empty-clear]').click();await pause(270);await flush();
    assert(root.querySelector('[data-next]').disabled===false);
    const pending=[];w.fetch=url=>new Promise(resolve=>pending.push({url,resolve}));
    root.querySelector('[data-preview="1"]').click();root.querySelector('[data-preview="2"]').click();
    pending[1].resolve(response({success:true,file_name:'Latest.pdf',file_path:'gs://fixture/latest.pdf',text:'Latest preview'}));await flush();
    pending[0].resolve(response({success:true,file_name:'Stale.pdf',file_path:'gs://fixture/stale.pdf',text:'Stale preview'}));await flush();
    assert.equal(d.querySelectorAll('[data-library-dialog]').length,1);assert(d.querySelector('[data-library-dialog]').textContent.includes('Latest.pdf'));
    assert(!d.querySelector('[data-library-dialog]').textContent.includes('Stale.pdf'));dispose();await flush();dom.window.close();
}
async function administration(){
    const {dom,w,d,root}=setup('admin-workspace');let reads=0;
    const companies=[{id:1,company_name:'Fixture',company_code:'fixture',is_active:true,max_users:10,max_resumes:100,max_searches:200}];
    const users=[{id:7,full_name:'Self',email:'self@example.invalid',user_type:'super_admin',is_active:true},{id:8,full_name:'Fictional Recruiter',email:'fictional@example.invalid',user_type:'tenant_user',is_active:true}];
    w.fetch=async url=>{reads++;return{ok:true,json:async()=>url==='/api/companies'?{companies}:{users}};};
    let dispose=w.AdminWorkspace.mount(root);await flush();assert(root.querySelector('[data-count]').textContent.includes('1 company'));
    root.querySelector('[data-tab="companies"]').dispatchEvent(new w.KeyboardEvent('keydown',{key:'ArrowRight',bubbles:true}));await flush();
    assert.equal(root.querySelector('[data-tab="users"]').getAttribute('aria-selected'),'true');
    assert.equal(root.querySelector('[data-tab="companies"]').tabIndex,-1);
    const before=reads;root.querySelector('[data-query]').value='fictional';root.querySelector('[data-query]').dispatchEvent(new w.Event('input'));
    assert.equal(reads,before);assert(root.querySelector('[data-count]').textContent.includes('1 of 2 users'));
    let resolve;w.fetch=()=>new Promise(r=>{resolve=r;});root.querySelector('[data-add]').click();dispose();root.innerHTML='Replacement';
    resolve({ok:true,json:async()=>({companies})});await flush();assert.equal(d.querySelector('[data-admin-dialog]'),null,'A stale user-list load must not open a modal on another page');
    dom.window.close();
}
(async()=>{await filters();await library();await administration();console.log('Workspace polish passed: accessible date presets, month boundaries, retained hidden selections, synchronized dialogs, safe pagination/search, preview races, keyboard tabs and stale-modal cleanup.');})().catch(error=>{console.error(error);process.exitCode=1;});
