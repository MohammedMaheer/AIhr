const assert = require('node:assert/strict');
const fs = require('node:fs');
const {JSDOM} = require('jsdom');
const source = fs.readFileSync('static/js/main.js','utf8').replace(/\r\n/g,'\n');
const dates = source.slice(source.indexOf('function localDateInputValue('),source.indexOf('function setupResponsiveNavigation('));
const schedule = source.slice(source.indexOf('let upcomingEventsRequest ='),source.indexOf('async function loadResourceUsageData('));
const general = source.slice(source.indexOf('function openGeneralScheduleModal('),source.indexOf('function closeGeneralScheduleModal('));
const interview = source.slice(source.indexOf('function showInterviewScheduleModal('),source.indexOf('function bindScheduleDialog('));
const flush = () => new Promise(resolve=>setImmediate(resolve));

async function run(){
    const oldTZ = process.env.TZ;
    try {
        for(const [tz,now,today,tomorrow] of [
            ['Asia/Kolkata','2030-01-02T00:15:00+05:30','2030-01-02','2030-01-03'],
            ['Pacific/Kiritimati','2030-12-31T00:15:00+14:00','2030-12-31','2031-01-01'],
            ['America/Los_Angeles','2030-01-01T23:30:00-08:00','2030-01-01','2030-01-02']
        ]){
            process.env.TZ=tz;
            const dom=new JSDOM('<div id="upcoming-events"></div>',{url:'https://qa.invalid',runScripts:'outside-only'});
            const w=dom.window,d=w.document,RealDate=w.Date,fixed=RealDate.parse(now);
            w.Date=class extends RealDate{constructor(...args){super(...(args.length?args:[fixed]));}static now(){return fixed;}};
            w.bindScheduleDialog=()=>{};w.closeGeneralScheduleModal=()=>{};
            w.submitGeneralScheduleForm=()=>{};w.saveInterviewSchedule=()=>{};
            w.eval(dates+schedule+general+interview);
            assert.equal(w.localDateInputValue(),today,tz+' must not use the UTC date for a local date input');
            w.openGeneralScheduleModal();
            assert.equal(d.getElementById('gs-date').value,tomorrow);
            assert.equal(d.getElementById('gs-date').min,today);
            w.showInterviewScheduleModal('Synthetic','fictional@example.invalid');
            assert.equal(d.getElementById('interview-date').value,tomorrow);
            assert.equal(d.getElementById('interview-date').min,today);
            w.updateUpcomingEvents([{title:'Synthetic',date:'2030-01-02',type:'interview'}]);
            assert(d.getElementById('upcoming-events').textContent.includes(new w.Date(2030,0,2).toLocaleDateString()));
            dom.window.close();
        }
    } finally {
        if(oldTZ===undefined)delete process.env.TZ;else process.env.TZ=oldTZ;
    }

    const dom=new JSDOM('<div id="upcoming-events"></div>',{url:'https://qa.invalid',runScripts:'outside-only'});
    const w=dom.window,d=w.document;
    w.console.warn=()=>{};w.eval(schedule);
    const box=()=>d.getElementById('upcoming-events');
    w.updateUpcomingEvents([{title:'<img src=x onerror=bad()>',position:'<svg onload=bad()>',date:'2030-01-02',type:'interview'}]);
    assert.equal(box().querySelectorAll('img,svg,[onerror],[onload]').length,0);
    assert(box().textContent.includes('<img src=x onerror=bad()>'));
    let calls=0;
    w.fetch=async()=>{calls++;throw new TypeError('private-network-marker');};
    await w.loadUpcomingEvents();
    assert(box().textContent.includes('Schedule unavailable'));
    assert(!box().textContent.includes('No upcoming events'));
    assert(!box().textContent.includes('private-network-marker'));
    assert.equal(box().getAttribute('aria-busy'),'false');
    w.fetch=async()=>{calls++;return{ok:true,json:async()=>({success:true,events:[]})};};
    box().querySelector('button[aria-label="Retry upcoming events"]').click();await flush();
    assert.equal(calls,2);
    assert(box().textContent.includes('No upcoming events'));
    for(const payload of [{success:false,events:[]},{success:true,events:null},{success:true,events:[null]}]){
        w.fetch=async()=>({ok:true,json:async()=>payload});await w.loadUpcomingEvents();
        assert(box().textContent.includes('Schedule unavailable'));
    }
    let resolveOld;
    w.fetch=()=>new Promise(resolve=>{resolveOld=resolve;});
    const old=w.loadUpcomingEvents();
    w.fetch=async()=>({ok:true,json:async()=>({success:true,events:[{title:'Newest event',date:'2030-01-02'}]})});
    await w.loadUpcomingEvents();
    resolveOld({ok:true,json:async()=>({success:true,events:[{title:'Stale event',date:'2030-01-01'}]})});await old;
    assert(box().textContent.includes('Newest event')&&!box().textContent.includes('Stale event'));
    w.fetch=()=>new Promise(resolve=>{resolveOld=resolve;});
    const detached=w.loadUpcomingEvents();
    d.body.innerHTML='<div id="upcoming-events">Replacement view</div>';
    resolveOld({ok:true,json:async()=>({success:true,events:[]})});await detached;
    assert.equal(box().textContent,'Replacement view');
    dom.window.close();
    console.log('Dashboard regressions passed: local date boundaries, both scheduling defaults, escaped event text, honest failures, retry and stale-response isolation.');
}
run().catch(error=>{console.error(error);process.exitCode=1;});
