const assert=require('node:assert/strict');
const fs=require('node:fs');
const {JSDOM}=require('jsdom');
const flush=()=>new Promise(resolve=>setImmediate(resolve));
async function setup(kind='pdf',fail=false){
    const dom=new JSDOM('<div id="app-shell"><main id="root"></main></div>',{url:'https://qa.invalid/',runScripts:'outside-only'});
    const w=dom.window,d=w.document,requests=[],revoked=[];
    w.escapeAttr=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    w.escapeHtml=w.escapeAttr;w.bindScheduleDialog=modal=>modal.setAttribute('role','dialog');
    w.showNotification=()=>{throw new Error('Preview failures should be inline, not a blocking toast');};
    w.URL.createObjectURL=()=> 'blob:https://qa.invalid/fictional-document';w.URL.revokeObjectURL=url=>revoked.push(url);
    const original='Original full Unicode document: '+('Fictional candidate\n'.repeat(7000));
    w.fetch=async(url,options={})=>{
        requests.push([url,options]);assert(!options.method||options.method==='GET');
        if(url.startsWith('/api/resume-library?'))return{ok:true,json:async()=>({success:true,total:1,uploads:[{id:7,file_name:'Fictional CV.'+(kind==='text'?'txt':'docx'),file_path:'gs://fixture/cv.docx'}]})};
        if(url==='/api/resume-library/7')return{ok:true,json:async()=>({success:true,id:7,file_name:'Fictional CV',file_path:'gs://fixture/cv.docx',text:'Cached text excerpt',preview_kind:kind})};
        assert.equal(url,'/api/resume-library/7/document');
        return{ok:!fail,json:async()=>({detail:'<img src=x> Document unavailable'}),headers:{get:()=>kind==='text'?'text/plain':'application/pdf'},
            blob:async()=>new w.Blob(['%PDF-1.7\nfixture'],{type:'application/pdf'}),text:async()=>original};
    };
    w.eval(fs.readFileSync('static/js/resume-library.js','utf8'));
    const dispose=w.ResumeLibrary.mount(d.getElementById('root'));await flush();
    d.querySelector('[data-preview]').click();await flush();await flush();
    return{dom,w,d,requests,revoked,dispose,original};
}
(async()=>{
    let value=await setup();let {w,d}=value;
    const frame=d.querySelector('iframe');assert(frame);
    assert(frame.src.startsWith('https://qa.invalid/static/vendor/pdfjs-6.5.438/web/viewer.html?file=blob%3A'));
    assert(!frame.src.includes('officeapps.live.com')&&!frame.src.includes('docs.google'));
    const options=[];frame.contentWindow.PDFViewerApplicationOptions={set:(...args)=>options.push(args)};
    d.dispatchEvent(new w.CustomEvent('webviewerloaded',{detail:{source:frame.contentWindow}}));
    assert(options.some(([name,value])=>name==='enableScripting'&&value===false));
    assert(options.some(([name,value])=>name==='disablePreferences'&&value===true));
    assert(options.some(([name,value])=>name==='enableAltTextModelDownload'&&value===false));
    d.querySelector('[data-mode="text"]').click();assert.equal(d.querySelector('pre').hidden,false);
    assert.equal(d.querySelector('[data-document]').hidden,true);
    d.querySelector('[data-mode="document"]').click();await flush();
    assert.equal(value.requests.filter(([url])=>url.endsWith('/document')).length,1,'Switching views must not reconvert the document');
    d.querySelector('[data-close]').click();await flush();assert.equal(value.revoked.length,1);
    value.dispose();await flush();value.dom.window.close();
    value=await setup('text');({w,d}=value);
    assert.equal(d.querySelector('[data-document] pre').textContent,value.original);
    assert(value.original.length>80000,'Original text must not be limited to the cached excerpt');
    assert.equal(d.querySelector('iframe'),null);value.dispose();await flush();value.dom.window.close();
    value=await setup('pdf',true);({w,d}=value);
    assert.equal(d.querySelector('iframe'),null);assert.equal(d.querySelector('[data-document-error]').hidden,false);
    assert.equal(d.querySelectorAll('[data-document-error] img').length,0);
    d.querySelector('[data-mode="text"]').click();assert.equal(d.querySelector('pre').textContent,'Cached text excerpt');
    assert.equal(value.requests.filter(([url])=>url.endsWith('/document')).length,1,'Failures must not loop or create paid work');
    value.dispose();await flush();value.dom.window.close();
    console.log('Document previews passed: private lazy PDF viewer, disabled PDF scripting/AI downloads, full original text, safe inline errors, reusable modes and blob cleanup.');
})().catch(error=>{console.error(error);process.exitCode=1;});
