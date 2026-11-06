const assert=require('node:assert/strict');
const fs=require('node:fs');
const {JSDOM}=require('jsdom');
const flush=()=>new Promise(resolve=>setTimeout(resolve,40));
async function boot(role,hash=''){
    const dom=new JSDOM(fs.readFileSync('templates/index.html','utf8'),{url:'https://qa.invalid/'+hash,runScripts:'outside-only'}),w=dom.window;
    const events=[],calls=[];w.console.log=()=>{};w.console.warn=()=>{};w.console.error=()=>{};
    w.matchMedia=()=>({matches:false,addEventListener:()=>{}});
    w.Request=globalThis.Request;w.Headers=globalThis.Headers;
    const original=w.document.addEventListener.bind(w.document);
    w.document.addEventListener=(name,callback,...rest)=>{if(name==='DOMContentLoaded')events.push(callback);else original(name,callback,...rest);};
    w.fetch=async(url,options={})=>{
        calls.push([String(url),options.method||'GET']);
        const data=String(url)==='/api/me'?{success:true,user:{id:7,full_name:'Synthetic recruiter',email:'fictional@example.invalid',user_type:role,company:{company_id:1}}}:
            String(url).includes('/dashboard-stats')?{success:true,candidate_stats:{selected:1,rejected:0,shortlisted:2,interviewed:0},activity_stats:{total_resumes:4191,total_searches:139}}:
            String(url).includes('/search-history')?{success:true,history:[],total:0}:
            String(url).includes('/resume-folders')?{success:true,supported:true,folders:[],tags:[]}:
            String(url).includes('/resume-library')?{success:true,uploads:[],total:0}:
            String(url).includes('/api/companies')?{success:true,companies:[]}:
            String(url).includes('/api/users')?{success:true,users:[]}:
            String(url).includes('/upcoming-events')?{success:true,events:[]}:
            String(url).includes('/integrations/status')?{success:true,microsoft:{connected:false},google:{connected:false}}:{success:true,templates:[]};
        return{ok:true,json:async()=>data};
    };
    for(const name of ['security','candidate-state','admin-workspace','resume-folders','resume-library','main'])w.eval(fs.readFileSync('static/js/'+name+'.js','utf8'));
    for(const callback of events)callback.call(w.document,new w.Event('DOMContentLoaded'));
    await flush();return{dom,w,d:w.document,calls};
}
async function run(){
    for(const role of ['super_admin','tenant_admin','tenant_user']){
        const {dom,w,d,calls}=await boot(role);
        assert.equal(d.getElementById('main-content').dataset.workspacePage,'dashboard');
        assert.equal(d.getElementById('administration-link').hidden,role==='tenant_user');
        assert.equal(d.getElementById('selected-count').textContent,'1');
        assert.equal(d.getElementById('activity-total-resumes').textContent,'4,191');
        d.querySelector('[data-workspace-target="resumeLibrary"]').click();await flush();
        assert.equal(d.getElementById('main-content').dataset.workspacePage,'resumeLibrary');
        w.loadPage('dashboard');await flush();
        if(role!=='tenant_user'){
            d.getElementById('administration-link').click();await flush();
            assert(d.getElementById('administration-workspace').textContent.includes('Administration'));
            assert.equal(Boolean(d.querySelector('[data-tab="companies"]')),role==='super_admin');
            w.history.back();await flush();assert.equal(d.getElementById('main-content').dataset.workspacePage,'dashboard');
            w.history.forward();await flush();assert.equal(d.getElementById('main-content').dataset.workspacePage,'administration');
        }else{
            w.loadPage('administration');await flush();assert.equal(d.getElementById('main-content').dataset.workspacePage,'dashboard');
            assert(!calls.some(([url])=>url==='/api/users'||url==='/api/companies'));
        }
        assert.equal(w.location.pathname,'/');assert(!calls.some(([,method])=>method==='POST'));
        dom.window.close();
    }
    const alias=await boot('super_admin','#/users');
    assert.equal(alias.d.getElementById('main-content').dataset.workspacePage,'administration');
    alias.dom.window.close();
    console.log('Full workspace bootstrap passed: auth-before-render, correct totals, clickable library, role-specific controls, aliases, Back/Forward and no paid startup submissions.');
}
run().catch(error=>{console.error(error);process.exitCode=1;});
