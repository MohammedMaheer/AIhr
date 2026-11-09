const assert=require('node:assert/strict');
const fs=require('node:fs');
const {JSDOM}=require('jsdom');
const source=fs.readFileSync('static/js/main.js','utf8');
const dom=new JSDOM('<div id="results-container"></div>',{url:'https://qa.invalid',runScripts:'outside-only'});
const w=dom.window,d=w.document;
w.fetch=async()=>{throw Error('Rendering a saved result must not make an AI call');};
w.Request=global.Request;w.Headers=global.Headers;
w.eval(fs.readFileSync('static/js/security.js','utf8'));
w.destroyCanvasCharts=()=>{};w.loadCandidateData=()=>{};w.console.log=w.console.debug=()=>{};
const errors=[];w.console.error=(...args)=>errors.push(args);
w.eval(source.slice(source.indexOf('    window.generateDetailedCandidateCard ='),source.indexOf('    function initializeVectorSearchPage()')));
function render(experience,keywords={}){
    w.generateDetailedCandidateCard({id:7,gemini_analysis:{hr_scorecard:{
        candidate_overview:{name:'Fictional Candidate',email:'candidate@example.invalid',location:'Dubai',experience_years:experience,overall_match_score:82},
        keyword_coverage:keywords}}},0);
    assert.equal(errors.length,0);
    assert.equal(d.querySelector('.professional-score-text').textContent,'82%','Presentation must preserve the saved match score');
}
for(const [value,expected] of [[5,'5 years of experience'],[1,'1 year of experience'],[0,'0 years of experience'],['5+','5+ years of experience'],['3-5 years','3-5 years experience'],[null,'Experience not specified']]){
    render(value);assert(d.querySelector('.professional-candidate-location').textContent.includes(expected));
    assert.equal(d.querySelector('canvas'),null,'Missing keyword data must not reserve a blank chart');
    assert(d.body.textContent.includes('Keyword details are unavailable'));
    assert(!d.body.textContent.includes('No Missing Keywords'));
}
render(5,{matched_keywords:'malformed',missing_keywords:null});assert.equal(d.querySelector('canvas'),null);
render(5,{matched_keywords:['Python','<img src=x onerror=bad()>'],missing_keywords:['SQL']});
assert(d.querySelector('canvas'));assert.equal(d.querySelectorAll('.professional-keyword-tag').length,3);
assert.equal(d.querySelectorAll('img,[onerror]').length,0);
assert(d.body.textContent.includes('Matched Keywords (2)'));assert(d.body.textContent.includes('Missing Keywords (1)'));
render(5,{matched_keywords:['Python'],missing_keywords:[]});
assert(d.body.textContent.includes('No missing keywords were reported'));
dom.window.close();
console.log('Candidate presentation passed: numeric experience including zero, unchanged scores, honest missing-keyword states, no blank charts and safe keyword text.');
