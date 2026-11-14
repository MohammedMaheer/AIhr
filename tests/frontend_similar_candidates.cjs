const assert=require('node:assert/strict');
const fs=require('node:fs');
const {JSDOM}=require('jsdom');
const flush=()=>new Promise(resolve=>setImmediate(resolve));
async function run(){
 const dom=new JSDOM('<div id="results"><section>No exact matches</section></div>',{url:'https://qa.invalid',runScripts:'outside-only'});
 const w=dom.window,d=w.document,root=d.getElementById('results');
 w.currentUser={id:7,company:{company_id:1}};
 w.bindScheduleDialog=modal=>{modal.setAttribute('role','dialog');};
 let calls=0,resolve,payload;
 w.fetch=(url,options)=>{assert.equal(url,'/api/similar-candidates');calls++;payload=options.body;return new Promise(r=>{resolve=r;});};
 w.eval(fs.readFileSync('static/js/similar-candidates.js','utf8'));
 const data={query:'Engineer in Dubai with 3-5 years. Required skills: Python',results:[],requested_result_count:10,
   similar_scope_identity:JSON.stringify([7,undefined,{company_id:1}]),
   folder_filters:[{bucket:'fixture',path:'selected'}],resume_filters:{tags:['Data and AI'],date_basis:'received',date_from:'2026-01-01'}};
 w.SimilarCandidates.offer(root,{...data,results:[{}]});assert.equal(root.querySelector('button'),null);
 w.SimilarCandidates.offer(root,{query:data.query,results:[]});assert.equal(root.querySelector('button'),null,'Legacy history without scope must not broaden');
 w.SimilarCandidates.offer(root,{...data,similar_scope_identity:undefined});assert.equal(root.querySelector('button'),null,'Saved search without original live identity must not broaden tenant scope');
 w.SimilarCandidates.offer(root,{...data,similar_scope_identity:'another workspace'});assert.equal(root.querySelector('button'),null);
 w.SimilarCandidates.offer(root,data);w.SimilarCandidates.offer(root,data);
 const button=root.querySelector('[data-find-similar]');assert(button);assert.equal(root.querySelectorAll('button').length,1);
 assert.equal(calls,0,'Suggestions must require explicit opt-in');
 data.folder_filters[0].path='changed-after-render';data.resume_filters.tags=[];
 button.click();button.click();assert.equal(calls,1);assert(button.disabled);
 assert.deepEqual(JSON.parse(payload.get('folders')),[{bucket:'fixture',path:'selected'}]);
 assert.equal(JSON.parse(payload.get('filters')).date_basis,'received');
 assert.deepEqual(JSON.parse(payload.get('filters')).tags,['Data and AI']);
 assert.equal(payload.get('query'),data.query);assert.equal(payload.get('result_count'),'10');
 resolve({ok:true,json:async()=>({success:true,results:[{file_name:'CV "><img src=x onerror=alert(1)>.pdf',file_path:'gs://fixture/selected/cv.pdf',
  location:'<script>bad()</script>',experience_years:2,unmet_criteria:[{criterion:'experience_years',required:'>=3 <img src=x>'}]}]})});
 await flush();await flush();
 let modal=d.querySelector('[data-similar-dialog]');
 assert(modal.textContent.includes('not verified exact matches'));
 assert(modal.textContent.includes('2 years'));assert(modal.textContent.includes('Experience: >=3'));
 assert.equal(modal.querySelectorAll('img,script,[onerror]').length,0,'Candidate fields must be escaped in text and attributes');
 assert(modal.querySelector('a').getAttribute('href').startsWith('/api/download-resume?file_path=gs%3A'));
 assert(root.textContent.includes('No exact matches'),'A near match must not overwrite the original exact search');
 modal.querySelector('[data-close]').click();await flush();assert.equal(d.querySelector('[data-similar-dialog]'),null);
 button.click();resolve({ok:true,json:async()=>({success:true,results:[]})});await flush();await flush();
 modal=d.querySelector('[data-similar-dialog]');assert(modal.textContent.includes('within the selected folders, tags and dates'));
 modal.querySelector('[data-close]').click();await flush();
 button.click();const late=resolve;root.remove();await flush();
 late({ok:true,json:async()=>({success:true,results:[{file_name:'Stale private result'}]})});await flush();await flush();
 assert(!d.body.textContent.includes('Stale private result'));assert.equal(d.querySelector('[data-similar-dialog]'),null);
 d.body.append(root);root.innerHTML='<section>No exact matches</section>';
 w.SimilarCandidates.offer(root,{...data,folder_filters:[],resume_filters:{tags:['Data and AI'],date_from:'2026-01-01'}});
 root.querySelector('[data-find-similar]').click();
 assert.equal(payload.has('folders'),false,'All authorized folders must omit the explicit-empty selection');
 assert.deepEqual(JSON.parse(payload.get('filters')).tags,['Data and AI']);
 assert.equal(JSON.parse(payload.get('filters')).date_from,'2026-01-01');
 resolve({ok:true,json:async()=>({success:true,results:[]})});await flush();await flush();
 d.querySelector('[data-close]').click();await flush();
 dom.window.close();
 console.log('Similar previews passed: explicit opt-in, frozen scope, double-submit guard, escaping, honest labels, empty scope and navigation cleanup.');
}
run().catch(e=>{console.error(e);process.exitCode=1;});
