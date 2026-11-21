// DOM workflow checks with deferred responses, not live provider tests.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const {JSDOM} = require('jsdom');
const source = fs.readFileSync('static/js/main.js', 'utf8');
const handlers = source.slice(source.indexOf('    let candidateSearchView = null;'),
    source.indexOf('    // Make animateChatToResults available globally'));
const flush = () => new Promise(resolve => setImmediate(resolve));

async function run() {
    const dom = new JSDOM('', {url:'https://qa.invalid', runScripts:'outside-only'});
    const w = dom.window, d = w.document;
    const mount = () => {
        d.body.innerHTML = '<input id="result-count" value="10"><input id="chat-input">' +
            '<input id="bottom-chat-input"><div id="bottom-chat-container"></div>' +
            '<div id="results-area"><div id="results-container"></div></div>';
    };
    mount();
    w.currentUser = {id:7, user_type:'tenant_user', company:{company_id:1}};
    w.animateChatToResults = w.addUserMessage = w.showLoadingMessage = w.hideLoadingMessage = () => {};
    w.console.error = () => {};
    const animations = [], pending = [], rendered = [], progress = [], saved = [];
    w.setTimeout = (fn, ms) => { if (ms === 300) animations.push(fn); else fn(); };
    w.generateEnhancedResults = data => rendered.push(data.query);
    w.updateSearchProgress = data => progress.push(data.step);
    w.saveSearchToHistory = query => saved.push(query);
    w.performRealSearch = (query, onProgress) => new Promise((resolve, reject) =>
        pending.push({query, onProgress, resolve, reject}));
    w.eval(handlers);
    const search = (query, main = false) => {
        d.getElementById(main ? 'chat-input' : 'bottom-chat-input').value = query;
        (main ? w.handleSendMessage : w.handleBottomSendMessage)();
        if (main) animations.shift()();
    };

    search('First request', true);
    search('Second request');
    pending[0].onProgress({step:'old'});
    pending[1].onProgress({step:'latest'});
    assert.deepEqual(progress, ['latest']);
    pending[1].resolve({query:'Second request', results:[]});
    await flush();
    pending[0].resolve({query:'First request', results:[]});
    await flush();
    assert.deepEqual(rendered, ['Second request'], 'An older response must not overwrite newer results');
    assert.deepEqual(saved, ['Second request']);

    search('Detached request');
    mount();
    pending[2].onProgress({step:'detached'});
    pending[2].reject(new Error('Old request failed'));
    await flush();
    assert.equal(d.getElementById('results-container').textContent, '');
    assert.deepEqual(progress, ['latest']);

    d.getElementById('chat-input').value = 'Navigate during animation';
    w.handleSendMessage();
    mount();
    animations.shift()();
    assert.equal(pending.length, 3, 'Navigation before submission must not start a paid backend search');

    search('Identity changed');
    w.currentUser = {...w.currentUser, company:{company_id:2}};
    pending[3].resolve({query:'Identity changed', results:[]});
    await flush();
    assert.deepEqual(rendered, ['Second request'], 'A changed workspace must not receive the previous identity response');
    const warnings = [];
    w.showNotification = (message, type) => warnings.push({message, type});
    w.ResumeFolders = {validate: () => {throw new Error('Choose at least one folder.');}};
    for (const [field, handler] of [['chat-input', w.handleSendMessage], ['bottom-chat-input', w.handleBottomSendMessage]]) {
        d.getElementById(field).value = 'Keep my draft';
        handler();
        assert.equal(d.getElementById(field).value, 'Keep my draft');
    }
    assert.equal(pending.length, 4, 'Invalid scope must not start an API request');
    assert.equal(animations.length, 0, 'Invalid scope must not animate away the search form');
    assert.equal(warnings.length, 2);
    assert(warnings.every(item => item.type === 'warning' && item.message.includes('Choose at least one')));
    dom.window.close();
    console.log('Search view isolation passed: out-of-order responses, stale progress/errors, navigation before submit and changed workspace identity.');
}
run().catch(error => { console.error(error); process.exitCode = 1; });
