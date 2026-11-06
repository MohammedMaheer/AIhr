/* Local-only visual fixture server. Never forwards requests to production APIs. */
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const staticRoot = fs.realpathSync(path.join(root, 'static'));
const user = {id:7, full_name:'Preview Administrator', email:'review@example.invalid', user_type:'super_admin', company:{company_id:1}};
const companies = [{id:1,company_name:'Example Recruitment Company',company_code:'example',subscription_plan:'enterprise',max_users:100,max_resumes:100000,max_searches:1000000,is_active:true},
    {id:2,company_name:'Regional Hiring Office',company_code:'regional',subscription_plan:'premium',max_users:20,max_resumes:5000,max_searches:500,is_active:false}];
const users = [{...user,is_active:true,company_name:'Example Recruitment Company'},
    {id:8,full_name:'Recruiter One',email:'recruiter.one@example.invalid',user_type:'tenant_admin',company_name:'Example Recruitment Company',is_active:true},
    {id:9,full_name:'Recruiter Two',email:'recruiter.two@example.invalid',user_type:'tenant_user',company_name:'Regional Hiring Office',is_active:false}];
const tags = ['IT infrastructure','Graphic design','UI design','Web design','Software development','Data and AI','Management','Finance and accounting','HR and recruitment','Sales and marketing'];
const folders = [{bucket:'fixture-bucket',path:'Network Engineers/Riyadh/November 2026',total:100},
    {bucket:'fixture-bucket',path:'Design/November 2026',total:42},
    {bucket:'fixture-bucket',path:'email_attachments/IT Infrastructure',total:64},
    ...Array.from({length:8},(_,i)=>({bucket:'fixture-bucket',path:'Previous campaigns/Batch '+(i+1),total:20+i}))];
const uploads = Array.from({length:63},(_,i)=>({id:i+1,file_name:i===2?'Senior_Infrastructure_Engineer_With_An_Intentionally_Long_Professional_Filename_For_Layout_Review.docx':
    i===3?'Portfolio – مصمم واجهات.pdf':
    ['Example Network Engineer CV.pdf','Example Designer Profile.docx','Example Candidate Notes.txt'][i%3],
    file_path:'gs://fixture-bucket/'+folders[i%folders.length].path+'/example-'+(i+1)+'.pdf',file_size:83421+i*2000,mime_type:'application/pdf',upload_timestamp:'2026-11-06T10:30:00'}));
function json(response,value,status=200){response.writeHead(status,{'Content-Type':'application/json','Cache-Control':'no-store'});response.end(JSON.stringify(value));}
const server = http.createServer((request,response)=>{
    const url = new URL(request.url,'http://127.0.0.1');
    if(request.method==='POST' && url.pathname==='/api/hr-scorecard-search'){
        request.resume();return json(response,{success:true,results:[],total_results:0,query:'Fictional UI review search'});
    }
    if(request.method!=='GET' && request.method!=='HEAD'){request.resume();return json(response,{detail:'Writes are disabled in the UI preview.'},405);}
    if(url.pathname==='/'){
        const html=fs.readFileSync(path.join(root,'templates/index.html'),'utf8')
            .replace(/\{\{\s*asset_v\.[a-z_]+\s*\}\}/g,'preview')
            .replace('{{ ui_limits | tojson }}',JSON.stringify({search_results:25,email_scan:100}))
            .replace('href="/static/css/tailwind.css"','href="https://effortsairecruiter.tech/static/css/tailwind.css"')
            .replace('<title>Smart HR</title>','<title>SmartHR UI review - fictional data</title>');
        response.writeHead(200,{'Content-Type':'text/html','Cache-Control':'no-store'});return response.end(html);
    }
    if(url.pathname.startsWith('/static/')){
        const target=path.resolve(root,'.'+decodeURIComponent(url.pathname));
        if(!fs.existsSync(target)||!fs.statSync(target).isFile())return json(response,{detail:'Not found'},404);
        const real=fs.realpathSync(target);
        if(!real.startsWith(staticRoot+path.sep))return json(response,{detail:'Not found'},404);
        const type={'.js':'text/javascript','.css':'text/css','.png':'image/png','.svg':'image/svg+xml'}[path.extname(real)]||'application/octet-stream';
        response.writeHead(200,{'Content-Type':type,'Cache-Control':'no-store'});return response.end(fs.readFileSync(real));
    }
    if(url.pathname==='/api/me')return json(response,{success:true,user});
    if(url.pathname==='/api/companies')return json(response,{success:true,companies});
    if(url.pathname==='/api/users')return json(response,{success:true,users});
    if(url.pathname==='/api/resume-folders')return json(response,{success:true,supported:true,folders,tags});
    if(url.pathname==='/api/resume-library'){
        const query=(url.searchParams.get('query')||'').toLowerCase(),offset=Math.max(0,Number(url.searchParams.get('offset'))||0),limit=Math.max(1,Math.min(100,Number(url.searchParams.get('limit'))||25));
        const filtered=uploads.filter(row=>row.file_name.toLowerCase().includes(query));
        return json(response,{success:true,total:filtered.length,uploads:filtered.slice(offset,offset+limit),limit,offset});
    }
    const preview=url.pathname.match(/^\/api\/resume-library\/(\d+)$/);
    if(preview){const row=uploads.find(row=>row.id===Number(preview[1]));return row?json(response,{success:true,...row,text:'FICTIONAL CV - UI REVIEW ONLY\n\nProfessional profile\nExample candidate with experience in network operations and infrastructure support.\n\nExperience\nAll details in this preview are fictional.\n\nSkills\nNetwork monitoring, troubleshooting, documentation.'}):json(response,{detail:'CV not found'},404);}
    if(url.pathname==='/api/dashboard-stats')return json(response,{success:true,candidate_stats:{selected:1,rejected:0,shortlisted:2,interviewed:0},activity_stats:{total_resumes:63,total_searches:12}});
    if(url.pathname==='/api/search-history')return json(response,{success:true,history:[],total:0});
    if(url.pathname==='/api/upcoming-events')return json(response,{success:true,events:[]});
    if(url.pathname==='/api/integrations/status')return json(response,{success:true,microsoft:{connected:false},google:{connected:false}});
    if(url.pathname==='/api/gcs-status')return json(response,{success:true,configured:true,bucket_name:'fixture-bucket',default_folder:'resume'});
    return json(response,{success:true,templates:[],results:[],data:[]});
});
server.listen(0,'127.0.0.1',()=>process.stdout.write('UI_PREVIEW_URL=http://127.0.0.1:'+server.address().port+'\n'));
process.on('SIGINT',()=>server.close(()=>process.exit(0)));
