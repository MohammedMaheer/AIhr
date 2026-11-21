const assert = require('node:assert/strict');
const fs = require('node:fs');
const {JSDOM} = require('jsdom');
const source = fs.readFileSync('static/js/main.js', 'utf8');
const dom = new JSDOM('', {runScripts:'outside-only', url:'https://qa.invalid'});
const w = dom.window;
w.eval(source.slice(source.indexOf('    function extractJobTitleFromQuery('),
    source.indexOf('    const pendingCandidateSearches')));
for (const [query, expected] of [
    ['HR Recruiter. Required skills: Recruitment.', 'Hr Recruiter'],
    ['Data Analyst. Required skills: SQL and Power BI.', 'Data Analyst'],
    ['Sales Manager. Required skills: Sales and CRM.', 'Sales Manager'],
    ['Accountant. Required skills: Accounts Payable and Excel.', 'Accountant'],
    ['Full Stack Developer with 2-4 years of experience. Required skills: React and Node.js.', 'Full Stack Developer'],
    ['DevOps Engineer with 4-6 years of experience. Required skills: Terraform and Azure.', 'Devops Engineer'],
    ['Graphic Designer. Required skills: Adobe Illustrator.', 'Graphic Designer'],
    ['Node.js Developer. Required skills: JavaScript.', 'Node.js Developer'],
    ['React.js Developer. Required skills: JavaScript.', 'React.js Developer'],
    ['.NET Developer. Required skills: SQL.', '.net Developer'],
    ['Required skills: Recruitment.', 'Position'],
    ['Required skills: JavaScript.', 'Position'],
    ['Required skills: Python.', 'Python Developer'],
    ['UI skills', 'UI/UX Designer'],
    ['', 'Position'],
]) {
    assert.equal(w.extractJobTitleFromQuery(query), expected, query);
}
dom.window.close();
console.log('Job titles passed: complete role names, bounded fallback keywords and no UI match inside required/recruitment.');
