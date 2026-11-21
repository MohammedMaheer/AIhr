const assert = require('node:assert/strict');
const fs = require('node:fs');
const {JSDOM} = require('jsdom');
const source = fs.readFileSync('static/js/main.js', 'utf8');
const dom = new JSDOM('', {url:'https://qa.invalid', runScripts:'outside-only'});
const w = dom.window, d = w.document;
w.eval(source.slice(source.indexOf('    // Make showLoadingMessage available globally'),
    source.indexOf('    // Update the progress UI')));
w.eval(source.slice(source.indexOf('    // Make hideLoadingMessage available globally'),
    source.indexOf('    // Make showFinalResultsNotification')));
d.body.innerHTML = '<span id="candidate-count">10 results</span><button id="export-all-btn">Export All</button>' +
    '<div id="candidate-list"><button>Old candidate</button></div><div id="results-container">Old scorecard</div>';
w.showLoadingMessage();
assert.equal(d.getElementById('candidate-count').textContent, 'Searching...');
assert.equal(d.getElementById('candidate-count').getAttribute('aria-busy'), 'true');
assert.equal(d.getElementById('export-all-btn'), null, 'A pending search must not export old results');
assert(!d.getElementById('candidate-list').textContent.includes('Old candidate'));
w.hideLoadingMessage();
assert.equal(d.getElementById('candidate-count').textContent, '0 results');
assert(!d.getElementById('candidate-count').hasAttribute('aria-busy'));
assert.equal(d.querySelector('#candidate-list .ai-search-state'), null, 'A failed request must stop the list spinner');
d.getElementById('candidate-count').textContent = '1 result';
d.getElementById('candidate-list').innerHTML = '<button>Verified result</button>';
w.hideLoadingMessage();
assert.equal(d.getElementById('candidate-count').textContent, '1 result', 'Cleanup must preserve rendered results');
assert.equal(d.getElementById('candidate-list').textContent, 'Verified result');
d.body.innerHTML = '';
assert.doesNotThrow(() => { w.showLoadingMessage(); w.hideLoadingMessage(); });
dom.window.close();
console.log('Search loading state passed: fresh count, stale export removal, failure cleanup and safe repeated cleanup.');
