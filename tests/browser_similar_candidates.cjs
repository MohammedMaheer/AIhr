// Isolated QA only. Never use this fixture runner against a live deployment.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {chromium}=require('playwright');
const base=process.argv[2];assert.equal(new URL(base).hostname,'127.0.0.1');
async function run(){
 const browser=await chromium.launch({headless:true,...(process.env.UI_BROWSER_CHANNEL?{channel:process.env.UI_BROWSER_CHANNEL}:{})});
 const shots=path.resolve('audit_out/similar-qa-screenshots');fs.mkdirSync(shots,{recursive:true});
 try{
  for(const width of [1440,390]){
   const context=await browser.newContext({viewport:{width,height:900}}),page=await context.newPage();
   let suggestions=0;
   page.on('request',r=>{if(r.url().endsWith('/api/similar-candidates'))suggestions++;});
   await page.goto(base+'/#/searchResumes',{waitUntil:'networkidle'});
   if(width<=768)await page.locator('#navigation-toggle').click();
   await page.locator('#search-resumes-link').click();
   const filters=page.locator('#resume-search-filters');await filters.locator('summary').click();
   await filters.locator('[data-folder]').first().waitFor();
   const choices=await filters.locator('[data-folder]').evaluateAll(nodes=>nodes.map(n=>({id:n.dataset.folder,label:n.closest('label').querySelector('span').textContent})));
   const choice=choices.find(c=>c.label==='Campaign/November 2026');assert(choice);
   await filters.locator('[data-folder="'+choice.id+'"]').check();
   await filters.locator('[data-tag="UI design"]').check();
   await filters.locator('[data-basis]').selectOption('received');
   for(const [bound,value] of [['from','2026-04-01'],['to','2026-04-30']]){
    await filters.locator('[data-'+bound+']').fill(value);await filters.locator('[data-'+bound+']').press('Tab');
   }
   const query='Designer based in Dubai with 20-25 years of experience. Required skills: Figma.';
   await page.locator('#chat-input').fill(query);await page.locator('#result-count').fill('10');
   await page.locator('#send-button').click();
   const button=page.locator('[data-find-similar]');await button.waitFor();
   assert.equal(suggestions,0,'No automatic relaxed search');assert.equal(await page.locator('#candidate-count').innerText(),'0 results');
   const received=page.waitForResponse(r=>r.url().endsWith('/api/similar-candidates'));
   await button.click();const response=await received;assert.equal(response.status(),200,await response.text());
   const data=await response.json();assert.equal(data.paid_ai_calls,0);assert.equal(data.requested_result_count,10);
   assert.equal(data.results.length,1);assert.equal(data.resume_filters.date_basis,'received');
   assert.equal(data.folder_filters[0].path,'Campaign/November 2026');
   assert.equal(data.results[0].experience_years,5);assert.equal(data.results[0].verification,'indexed_profile_only');
   assert(data.results[0].unmet_criteria.some(m=>m.criterion==='experience_years'));
   assert(!data.results[0].unmet_criteria.some(m=>m.criterion==='location'),'Role name must not become a required location');
   assert(data.results[0].file_path.includes('Campaign/November 2026/graph_'));
   const modal=page.locator('[data-similar-dialog]');await modal.locator('.similar-candidates-list > li').waitFor();
   assert((await modal.innerText()).includes('not verified exact matches'));
   assert.equal(await modal.locator('.hr-checkbox,.professional-resume-card').count(),0);
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth));
   const box=await modal.locator('.workspace-dialog').boundingBox();assert(box.x>=0&&box.x+box.width<=width+1);
   await page.screenshot({path:path.join(shots,'similar-'+width+'.jpg'),type:'jpeg'});
   await modal.getByRole('button',{name:'Close similar candidates',exact:true}).click();
   assert.equal(await page.locator('#candidate-count').innerText(),'0 results');
   assert.equal(suggestions,1);await context.close();
  }
 }finally{await browser.close();}
 console.log('Similar candidate HTTP/SQL/worker and desktop/mobile scope preview passed.');
}
run().catch(e=>{console.error(e);process.exitCode=1;});
