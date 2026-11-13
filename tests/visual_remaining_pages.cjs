/* Run against tests/ui_preview.cjs only; never sends real email/calendar mutations. */
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
const {chromium}=require('playwright');
const base=process.argv[2];
assert(base && new URL(base).hostname==='127.0.0.1','Use the local fictional fixture server.');
const output=path.resolve(process.env.UI_SCREENSHOT_DIR || 'audit_out/remaining-ui-verification');
fs.mkdirSync(output,{recursive:true});
(async()=>{const browser=await chromium.launch({headless:true,...(process.env.UI_BROWSER_CHANNEL?{channel:process.env.UI_BROWSER_CHANNEL}:{})});try{
 for(const [width,height] of [[1440,900],[900,768],[390,844],[320,568]]){
  const page=await browser.newPage({viewport:{width,height},reducedMotion:'reduce'});
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  async function shot(name){
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Page overflow: '+name+' at '+width);
   for(const dialog of await page.locator('.workspace-dialog,.outreach-dialog,.schedule-dialog,#analysisModal > div').all()){
    if(!await dialog.isVisible())continue;
    assert(await dialog.evaluate(el=>{const r=el.getBoundingClientRect();return r.left>=0&&r.right<=innerWidth+1&&r.top>=0&&r.bottom<=innerHeight+1&&el.scrollWidth<=el.clientWidth+1;}),'Dialog overflow: '+name+' at '+width);
   }
   await page.screenshot({path:path.join(output,width+'-'+name+'.png'),fullPage:true});
  }
  async function close(selector){await page.locator(selector).first().click();await page.waitForFunction(()=>!document.getElementById('app-shell').inert);}
  for(const view of ['dashboard','history','jdBuilder','settings','administration']){
   await page.goto(base+'/#/'+view,{waitUntil:'networkidle'});await shot(view);
   if(view==='dashboard'){
    await page.getByRole('button',{name:'Add to schedule',exact:true}).click();await shot('general-schedule');
    await close('[data-modal="general-schedule"] [aria-label="Close schedule"]');
    await page.evaluate(()=>window.InterviewManager.list());await page.locator('[data-interview-list] table').waitFor();await shot('schedule-history');
    await close('[data-interview-list] [data-close]');
    await page.evaluate(()=>window.InterviewManager.open(1));await page.locator('[data-edit-form]').waitFor();await shot('interview-edit');
    await page.locator('[data-interview-manager] [data-cancel]').click();await shot('interview-cancel');
    await page.locator('[data-interview-manager] [data-close-form]').scrollIntoViewIfNeeded();await shot('interview-actions');
    await close('[data-interview-manager] [data-close]');
    await page.evaluate(()=>window.openCandidatesByStatus('shortlisted'));await page.locator('.candidate-status-table').waitFor();await shot('status-list');
    if(width<=900)assert.notEqual(await page.locator('[data-label="Score"]').evaluate(el=>getComputedStyle(el,'::before').content),'none');
    await page.locator('[data-action="schedule"]').click();await shot('status-schedule');
    assert((await page.locator('#gs-candidate-name').inputValue()).includes('Fictional'));
    await close('[data-modal="general-schedule"] [aria-label="Close schedule"]');
   }else if(view==='history'){
    await page.locator('#clear-history').click();await shot('delete-reports');await close('[data-history-confirm] [data-keep]');
    await page.locator('[title="View results"]').first().click();await page.locator('#results-area').waitFor();await shot('saved-results');
   }else if(view==='jdBuilder'){
    await page.locator('#jd-skill-input').fill('Very long infrastructure and information security certification name');await page.locator('#jd-skill-input').press('Enter');await shot('jd-skills');
   }else if(view==='settings'){
    await page.locator('#recruiter-integrations').waitFor();
    assert.equal(await page.locator('[data-provider="google"] [data-connect]').isDisabled(),true);
   }else if(view==='administration'){
    await page.locator('[data-add]').click();await shot('add-company');await close('[data-admin-dialog] [data-close]');
    await page.locator('[title="Edit company"]').first().click();await shot('edit-company');await close('[data-admin-dialog] [data-close]');
    await page.locator('[data-tab="users"]').click();await page.locator('[title="Edit user"]').first().waitFor();await shot('users');
    await page.locator('[data-add]').click();await page.locator('[data-admin-dialog]').waitFor();await shot('add-user');await close('[data-admin-dialog] [data-close]');
    await page.locator('[title="Edit user"]').first().click();await shot('edit-user');await close('[data-admin-dialog] [data-close]');
    await page.locator('[title="Delete user"]').first().click();await shot('delete-user');await close('[data-admin-dialog] [data-close]');
   }
  }
  await page.goto(base+'/#/dashboard',{waitUntil:'networkidle'});
  await page.evaluate(()=>window.RecruiterOutreach.open({useSearch:false,candidateName:'Fictional Candidate With A Long Name',candidateEmail:'candidate@example.invalid',position:'Senior Network and Information Security Team Lead',company:'Example Recruitment Company'}));
  await page.locator('[name="transport"]:not([disabled])').waitFor();await shot('compose-email');
  await page.locator('[data-manage-templates]').click();await shot('email-templates');
  assert(await page.locator('[data-template-manager] [data-save]').evaluate(el=>{const r=el.getBoundingClientRect();return r.bottom<=innerHeight&&r.top>=0;}),'Template save action must stay visible.');
  await page.locator('[data-template-manager] [data-back]').click();await close('[data-email-composer] [data-close]');
  await page.evaluate(()=>window.showInterviewScheduleModal('Fictional Candidate With A Long Name','candidate@example.invalid',{position:'Senior Network and Information Security Team Lead'}));await shot('interview-schedule');
  assert.equal(await page.locator('#interview-provider option[value="google"]').count(),0);
  await close('[data-modal="interview-schedule"] [aria-label="Close interview"]');
  await page.evaluate(()=>window.showAnalysisModal('Fictional Candidate With A Long Name',{summary:'Fictional analysis fixture only'}));await shot('analysis');
  assert.equal(await page.locator('#analysisModal').getAttribute('role'),'dialog');await page.keyboard.press('Escape');await page.waitForFunction(()=>!document.getElementById('app-shell').inert);
  await page.goto(base+'/#/resumeLibrary',{waitUntil:'networkidle'});
  for(const id of [1,2,5,6,9]){
   await page.locator('[data-preview="'+id+'"]').click();await page.locator('[data-library-dialog]').waitFor();
   if(id===9)await page.locator('[data-document] > pre').waitFor();
   else{
    const element=await page.locator('.cv-document-frame').elementHandle(),frame=await element.contentFrame();
    await frame.waitForFunction(()=>{const c=document.querySelector('.page canvas');if(!c||!c.width||!c.height)return false;const bytes=c.getContext('2d').getImageData(0,0,c.width,c.height).data;let ink=0;for(let i=0;i<bytes.length;i+=64)if(bytes[i+3]&&Math.min(bytes[i],bytes[i+1],bytes[i+2])<200)ink++;return ink>50;},null,{timeout:20000});
   }
   await shot('document-'+id);await page.locator('[data-mode="text"]').click();await shot('text-preview-'+id);await close('[data-library-dialog] [data-close]');
  }
  assert.deepEqual(errors,[],'Browser errors at '+width);await page.close();console.log('Remaining pages/dialogs and rendered document pixels passed at '+width+'x'+height);
 }
}finally{await browser.close();}})().catch(error=>{console.error(error);process.exitCode=1;});
