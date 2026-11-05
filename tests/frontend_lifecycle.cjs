const assert=require('node:assert/strict');
const fs=require('node:fs');
const {JSDOM}=require('jsdom');
const main=fs.readFileSync('static/js/main.js','utf8');
const flush=()=>new Promise(resolve=>setImmediate(resolve));
async function run(){
 const dom=new JSDOM('<div id="app-shell"><button id="opener">Open</button></div>',{url:'https://qa.invalid',runScripts:'outside-only'});
 const w=dom.window,d=w.document,calls=[];
 w.showNotification=()=>{};w.loadUpcomingEvents=()=>{};
 w.localDateInputValue=()=> '2026-11-05';w.scheduleZoneOptions=()=>'<option value="Asia/Dubai">Dubai</option>';
 w.eval(main.slice(main.indexOf('function bindScheduleDialog('),main.indexOf('function closeInterviewModal()')));
 w.eval(fs.readFileSync('static/js/interview-manager.js','utf8'));
 let unknown=false,resolve;
 const row={id:1,candidate_name:'Fictional Candidate',candidate_email:'fixture@example.invalid',position:'Engineer" autofocus onfocus="bad()',interview_date:'2030-01-02',interview_time:'10:00:00',time_zone:'Asia/Dubai',duration_minutes:60,interview_type:'video',notes:'</textarea><script>bad()</script>',status:'scheduled',meeting_provider:'teams',version:'synthetic-version'};
 w.fetch=async(url,options={})=>{
  calls.push({url,options});
  if(!options.method)return{ok:true,json:async()=>({success:true,interview:{...row}})};
  return new Promise(done=>{resolve=()=>done({ok:!unknown,status:unknown?502:200,json:async()=>unknown?{success:false,sync_unknown:true,error:'Check calendar before retrying'}:{success:true}});});
 };
 await w.InterviewManager.open(1);
 let modal=d.querySelector('[data-interview-manager]');
 assert.equal(modal.querySelectorAll('[onfocus],script').length,0);
 assert.equal(modal.querySelector('[name="position"]').value,row.position);
 modal.querySelector('[data-cancel]').click();assert.equal(calls.length,1,'Opening confirmation must not cancel');
 modal.querySelector('[data-keep]').click();assert.equal(modal.querySelector('[data-cancel-panel]').hidden,true);
 modal.querySelector('[data-cancel]').click();modal.querySelector('[data-confirm-cancel]').click();modal.querySelector('[data-confirm-cancel]').click();
 assert.equal(calls.filter(call=>call.options.method==='DELETE').length,1);
 assert.equal(JSON.parse(calls.at(-1).options.body).confirm_calendar_change,true);
 resolve();await flush();assert.equal(d.querySelector('[data-interview-manager]'),null);
 unknown=true;await w.InterviewManager.open(1,true);modal=d.querySelector('[data-interview-manager]');
 modal.querySelector('[data-confirm-cancel]').click();resolve();await flush();
 assert.equal(modal.querySelector('[data-confirm-cancel]').disabled,true);
 assert.equal(modal.querySelector('[data-reconcile]').hidden,false);
 modal.querySelector('[data-close]').click();await flush();
 w.fetch=async(url)=>({ok:true,json:async()=>url.startsWith('/api/interviews?')
  ?{success:true,total:1,interviews:[{...row,status:'cancelled'}]}
  :{success:true,interview:{...row,status:'cancelled',history:[{action:'cancel',state:'completed',created_at:'2026-11-05T10:00:00Z'}]}}});
 await w.InterviewManager.list();await flush();
 const history=d.querySelector('[data-interview-list]');
 assert(history.textContent.includes('cancelled'));
 assert.equal(history.querySelector('[data-previous]').disabled,true);
 assert.equal(history.querySelector('[data-next]').disabled,true);
 history.querySelector('[data-open]').click();await flush();await flush();
 modal=d.querySelector('[data-interview-manager]');
 assert.equal(modal.querySelector('[data-save]').disabled,true);
 assert([...modal.querySelectorAll('input,select,textarea')].every(field=>field.disabled));
 assert(modal.textContent.includes('Cancellation - completed'));
 const warning=[];w.console.warn=(...args)=>warning.push(args);
 const historyButton=d.createElement('button');historyButton.setAttribute('onclick','InterviewManager.list()');d.body.append(historyButton);
 const missingButton=d.createElement('button');missingButton.setAttribute('onclick','missingFixtureHandler()');d.body.append(missingButton);
 const auditStart=main.indexOf('function auditOnclickHandlers()');
 w.eval(main.slice(auditStart,main.indexOf("if (document.readyState === 'loading')",auditStart))+'\nauditOnclickHandlers();');
 assert.equal(warning.length,1);
 assert.deepEqual(Array.from(warning[0][1]),['missingFixtureHandler'],'Namespaced handlers must not be falsely flagged');
 modal.querySelector('[data-close]').click();
 const invalidJson=async()=>{throw new w.SyntaxError('Unexpected token < in provider HTML');};
 w.fetch=async(url,options={})=>options.method?{ok:false,status:502,json:invalidJson}:{ok:true,json:async()=>({success:true,interview:{...row}})};
 await w.InterviewManager.open(1,true);modal=d.querySelector('[data-interview-manager]');
 modal.querySelector('[data-confirm-cancel]').click();await flush();
 assert(modal.textContent.includes('Check the calendar before trying again'));
 assert(!modal.textContent.includes('Unexpected token'));
 assert.equal(modal.querySelector('[data-confirm-cancel]').disabled,true,'Non-JSON mutation failures must retain the uncertain-outcome guard');
 modal.querySelector('[data-close]').click();
 w.fetch=async()=>({ok:false,status:502,json:invalidJson});
 await w.InterviewManager.open(1);modal=d.querySelector('[data-interview-manager]');
 assert(modal.textContent.includes('temporarily unavailable'));
 assert(!modal.textContent.includes('Unexpected token'));
 dom.window.close();

 const templates=new JSDOM('<div id="app-shell"><button>Open</button></div>',{url:'https://qa.invalid',runScripts:'outside-only'}),tw=templates.window,td=tw.document;
 tw.currentUser={id:7,full_name:'Fixture Recruiter'};tw.showNotification=()=>{};
 tw.eval(main.slice(main.indexOf('function bindScheduleDialog('),main.indexOf('function closeInterviewModal()')));
 tw.eval(fs.readFileSync('static/js/recruiter-outreach.js','utf8'));
 let saved=[],mutations=[];
 tw.fetch=async(url,options={})=>{
  if(url==='/api/integrations/status')return{ok:true,json:async()=>({success:true,microsoft:{connected:true,capabilities:{email:true},account_email:'fixture@example.invalid'},google:{connected:false},smtp:{configured:false}})};
  if(url==='/api/outreach-templates'&&!options.method)return{ok:true,json:async()=>({success:true,templates:saved})};
  mutations.push({url,options});const data=JSON.parse(options.body);
  if(options.method==='POST'&&!url.endsWith('/draft')){const record={...data,id:1,version:1};saved=[record];return{ok:true,json:async()=>({success:true,template:record})};}
  if(options.method==='PUT'){saved=[{...data,id:1,version:2}];return{ok:true,json:async()=>({success:true,template:saved[0]})};}
  if(options.method==='DELETE'){saved=[];return{ok:true,json:async()=>({success:true})};}
  throw new Error('Unexpected request '+url);
 };
 tw.RecruiterOutreach.open({candidateName:'Fictional Candidate',candidateEmail:'fixture@example.invalid',position:'Engineer'});await flush();
 td.querySelector('[data-manage-templates]').click();await flush();
 const panel=td.querySelector('[data-template-manager]');
 panel.querySelector('[data-name]').value='Fixture reusable template';panel.querySelector('[data-name]').dispatchEvent(new tw.Event('input',{bubbles:true}));
 panel.querySelector('[data-save]').click();await flush();await flush();
 assert.equal(saved.length,1);assert.equal(panel.querySelector('[data-delete]').disabled,false);
 assert(saved[0].message.includes('{{ candidate_name }}'),'Reusable templates should not store a specific candidate name by default');
 panel.querySelector('[data-subject]').value='Updated subject';panel.querySelector('[data-subject]').dispatchEvent(new tw.Event('input',{bubbles:true}));
 panel.querySelector('[data-save]').click();await flush();await flush();
 assert(mutations.some(call=>call.options.method==='PUT'));
 panel.querySelector('[data-delete]').click();assert.equal(mutations.filter(call=>call.options.method==='DELETE').length,0);
 panel.querySelector('[data-confirm-delete]').click();await flush();await flush();
 assert.equal(saved.length,0);assert.equal(mutations.filter(call=>call.options.method==='DELETE').length,1);
 templates.window.close();
 console.log('Lifecycle UI passed: safe edit fields, explicit calendar cancellation, pending-send lock, uncertain-outcome recovery and saved-template create/edit/delete confirmations.');
}
run().catch(error=>{console.error(error);process.exitCode=1;});
