// Isolated fictional fixture server only. No live browser sessions or provider calls.
const assert=require('node:assert/strict');
const {spawn}=require('node:child_process');
const fs=require('node:fs'),path=require('node:path');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'..');
async function run(){
 const server=spawn(process.execPath,[path.join(__dirname,'ui_preview.cjs')],{cwd:root,stdio:['ignore','pipe','pipe']});
 let browser;
 try{
  const base=await new Promise((resolve,reject)=>{
   const timer=setTimeout(()=>reject(new Error('Fixture startup timed out')),10000);
   server.once('error',e=>{clearTimeout(timer);reject(e);});
   server.once('exit',code=>{clearTimeout(timer);reject(new Error('Fixture exited: '+code));});
   server.stdout.on('data',chunk=>{const m=String(chunk).match(/UI_PREVIEW_URL=(http:\/\/127\.0\.0\.1:\d+)/);if(m){clearTimeout(timer);resolve(m[1]);}});
  });
  browser=await chromium.launch({headless:true,...(process.env.UI_BROWSER_CHANNEL?{channel:process.env.UI_BROWSER_CHANNEL}:{})});
  const shots=path.join(root,'audit_out/chart-asset-verification');fs.mkdirSync(shots,{recursive:true});
  for(const width of [1440,390]){
   const page=await browser.newPage({viewport:{width,height:900}}),errors=[];
   page.on('pageerror',e=>errors.push(e.message));
   await page.route('https://cdn.jsdelivr.net/**',route=>route.abort());
   await page.route('**/api/search-results/*',route=>route.fulfill({json:{success:true,
    query:'Network Engineer in Dubai with 3-5 years',total_results:1,results:[{id:1,document_name:'Fictional Candidate',
     file_path:'gs://fixture-bucket/cv.pdf',gemini_analysis:{success:true,input_source:'full_document',scorecard_type:'comprehensive_hr',match_score:82,
      hr_scorecard:{candidate_overview:{name:'Fictional Candidate',email:'candidate@example.invalid',location:'Dubai',position_applied_for:'Network Engineer',experience_years:5,overall_match_score:82},
       ai_summary:'Fictional local chart compatibility check.',score_breakdown:{},keyword_coverage:{matched_keywords:['Monitoring','Troubleshooting'],missing_keywords:['Documentation']}}}}]}}));
   await page.goto(base+'/#/history',{waitUntil:'networkidle'});
   assert.equal(await page.evaluate(()=>window.Chart?.version),'4.6.1');
   await page.locator('[title="View results"]').first().click();
   const canvas=page.locator('canvas[id^="keywordChart"]');await canvas.waitFor();
   await page.waitForFunction(()=>{const c=document.querySelector('canvas[id^="keywordChart"]');
    if(!c||!window.Chart.getChart(c))return false;const data=c.getContext('2d').getImageData(0,0,c.width,c.height).data;
    let colored=0;for(let i=0;i<data.length;i+=4)if(data[i+3]>0&&Math.max(data[i],data[i+1],data[i+2])-Math.min(data[i],data[i+1],data[i+2])>60)colored++;
    return colored>100;});
   assert.deepEqual(await canvas.evaluate(c=>window.Chart.getChart(c).data.datasets[0].data),[2,1]);
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
   await canvas.scrollIntoViewIfNeeded();
   await page.screenshot({path:path.join(shots,'chart-'+width+'.jpg'),type:'jpeg'});
   assert.deepEqual(errors,[]);await page.close();
  }
 }finally{await browser?.close();server.kill();}
 console.log('Local Chart.js renders the actual candidate chart with its CDN blocked at desktop/mobile widths.');
}
run().catch(error=>{console.error(error);process.exitCode=1;});
