const assert=require('node:assert/strict');
const fs=require('node:fs');
const {JSDOM}=require('jsdom');
const source=fs.readFileSync('static/js/main.js','utf8');
const binding=source.slice(source.indexOf('function bindScheduleDialog('),source.indexOf('function closeInterviewModal('));
const flush=()=>new Promise(resolve=>setImmediate(resolve));
const response=(value,ok=true)=>({ok,status:ok?200:503,json:async()=>value});
function setup(){
 const dom=new JSDOM('<div id="app-shell"><button id="opener">Open</button><main id="main-content"></main></div>',{url:'https://qa.invalid/',runScripts:'outside-only'});
 const w=dom.window,d=w.document;w.fetch=async()=>response({});w.Request=globalThis.Request;w.Headers=globalThis.Headers;
 w.eval(fs.readFileSync('static/js/security.js','utf8'));w.eval(binding);
 w.currentUser={id:7,full_name:'Fictional Recruiter',company:{company_id:1,company_name:'Fictional Company'}};
 return{dom,w,d};
}
async function dialogs(){
 const {dom,w,d}=setup(),shell=d.getElementById('app-shell'),opener=d.getElementById('opener');
 const add=label=>{const modal=d.createElement('div');modal.innerHTML='<button>Close</button><input aria-label="Example">';d.body.append(modal);w.bindScheduleDialog(modal,label);return modal;};
 opener.focus();let first=add('First'),second=add('Second');
 first.remove();second.remove();await flush();
 assert.equal(shell.inert,false,'Removing nested dialogs together must not leave the page inert');
 assert.equal(d.activeElement,opener);
 first=add('First');second=add('Second');first.remove();await flush();
 assert.equal(shell.inert,true,'Closing an older dialog must not unlock the background while another dialog is open');
 assert(second.contains(d.activeElement),'Focus must stay in the remaining dialog');
 second.remove();await flush();assert.equal(shell.inert,false);
 first=add('Pending');first.dataset.submitting='true';
 first.dispatchEvent(new w.KeyboardEvent('keydown',{key:'Escape',bubbles:true}));assert(first.isConnected);
 delete first.dataset.submitting;first.remove();await flush();
 w.generateAnalysisContent=()=>'<p>Fictional safe analysis</p>';
 w.eval(source.slice(source.indexOf('    window.showAnalysisModal = function'),source.indexOf('    function generateAnalysisContent(')));
 opener.focus();const overflow=d.body.style.overflow;
 w.showAnalysisModal('Fictional candidate',{});w.showAnalysisModal('Duplicate',{});
 const analysis=d.getElementById('analysisModal');assert.equal(d.querySelectorAll('#analysisModal').length,1);
 assert.equal(analysis.getAttribute('role'),'dialog');assert.equal(shell.inert,true);
 assert(analysis.querySelector('[aria-label="Close candidate analysis"]'));
 analysis.dispatchEvent(new w.KeyboardEvent('keydown',{key:'Escape',bubbles:true}));await flush();
 assert(!analysis.isConnected);assert.equal(shell.inert,false);assert.equal(d.body.style.overflow,overflow);assert.equal(d.activeElement,opener);
 dom.window.close();
}
async function candidateRaces(){
 const {dom,w,d}=setup();w.console.error=()=>{};
 w.eval(source.slice(source.indexOf('async function openCandidatesByStatus('),source.indexOf('function openGeneralScheduleModal(')));
 const pending=[];w.fetch=()=>new Promise(resolve=>pending.push(resolve));
 const old=w.openCandidatesByStatus('selected'),latest=w.openCandidatesByStatus('shortlisted');
 pending[1](response({candidates:[{candidate_name:'Latest candidate',match_score:82}]}));await latest;
 pending[0](response({candidates:[{candidate_name:'Stale candidate',match_score:91}]}));await old;
 assert(d.getElementById('main-content').textContent.includes('Latest candidate'));assert(!d.body.textContent.includes('Stale candidate'));
 const failed=w.openCandidatesByStatus('selected'),newer=w.openCandidatesByStatus('rejected');
 pending[3](response({candidates:[{candidate_name:'Newer result',match_score:50}]}));await newer;
 pending[2](response({},false));await failed;assert(d.body.textContent.includes('Newer result'));assert(!d.body.textContent.includes('Failed to load candidates'));
 const navigating=w.openCandidatesByStatus('selected');d.getElementById('main-content').innerHTML='<p>Another page</p>';
 pending[4](response({candidates:[]}));await navigating;assert.equal(d.getElementById('main-content').textContent,'Another page');
 dom.window.close();
}
async function templates(){
 const {dom,w,d}=setup();let load,save,writes=0;
 w.fetch=async(url,options={})=>{
  if(url==='/api/integrations/status')return response({success:true,microsoft:{connected:true,capabilities:{email:true}}});
  if(options.method){writes++;return new Promise(resolve=>{save=resolve;});}
  return new Promise(resolve=>{load=resolve;});
 };
 w.eval(fs.readFileSync('static/js/recruiter-outreach.js','utf8'));
 w.RecruiterOutreach.open({useSearch:false,candidateName:'Fictional Candidate',candidateEmail:'candidate@example.invalid',position:'Engineer'});await flush();
 const modal=d.querySelector('[data-email-composer]');modal.querySelector('[data-manage-templates]').click();
 const panel=modal.querySelector('[data-template-manager]'),name=panel.querySelector('[data-name]');
 name.value='Draft typed before the list arrived';name.dispatchEvent(new w.Event('input',{bubbles:true}));
 load(response({templates:[]}));await flush();assert.equal(name.value,'Draft typed before the list arrived','A late list response must not discard typed draft fields');
 panel.querySelector('[data-save]').click();assert.equal(writes,1);assert.equal(panel.dataset.submitting,'true');
 assert(modal.querySelector('.outreach-header [data-close]').disabled);
 modal.dispatchEvent(new w.KeyboardEvent('keydown',{key:'Escape',bubbles:true}));assert(modal.isConnected,'A pending template save must not be dismissed');
 panel.querySelector('[data-save]').click();assert.equal(writes,1);
 save(response({detail:'Fictional save failure'},false));await flush();assert.equal(panel.dataset.submitting,undefined);
 assert.equal(name.disabled,false);assert.equal(name.value,'Draft typed before the list arrived');assert.equal(d.activeElement,panel.querySelector('[data-feedback]'));
 modal.querySelector('.outreach-header [data-close]').click();await flush();assert(!modal.isConnected);assert.equal(d.getElementById('app-shell').inert,false);
 dom.window.close();
}
dialogs().then(candidateRaces).then(templates).then(()=>console.log('Dialog state passed: overlapping-modal focus/inert recovery, accessible analysis, stale candidate views and safe template loading/saving.'))
 .catch(error=>{console.error(error);process.exitCode=1;});
