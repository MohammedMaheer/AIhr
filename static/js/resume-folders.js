(function () {
    'use strict';
    let owner = null, selected = null, filters = {};
    const esc = value => (window.escapeAttr || window.escapeHtml)(String(value ?? ''));
    function resetOwner() {
        const key = JSON.stringify([window.currentUser?.id, window.currentUser?.company]);
        if (owner !== key) { owner = key; selected = null; filters = {}; }
    }
    function getSelection() { resetOwner(); return selected === null ? null : JSON.parse(JSON.stringify(selected)); }
    function getFilters() {
        resetOwner(); const value={};
        if(filters.tags?.length)value.tags=[...filters.tags];
        if(filters.date_from)value.date_from=filters.date_from;
        if(filters.date_to)value.date_to=filters.date_to;
        if(value.date_from||value.date_to)value.date_basis=filters.date_basis||'uploaded';
        return value;
    }
    function validate() {
        if (selected !== null && !selected.length) throw new Error('Choose at least one folder, or select All folders.');
        if (filters.date_from && filters.date_to && filters.date_from > filters.date_to) throw new Error('The start date must not be after the end date.');
    }
    function mount(root) {
        if (!root) return () => {};
        resetOwner();
        let disposed = false;
        root.innerHTML = '<p role="status" class="text-sm text-gray-500">Loading CV filters...</p>';
        fetch('/api/resume-folders').then(async response => {
            const data = await response.json();
            if (!response.ok || data.success !== true || !Array.isArray(data.folders)) throw new Error();
            if (disposed || !root.isConnected) return;
            if (!data.supported) { root.textContent = ''; return; }
            root.innerHTML = `<details class="border-t border-gray-200 pt-3 mt-3">
                <summary class="cursor-pointer text-sm font-medium text-gray-700"><i class="fas fa-filter mr-2" aria-hidden="true"></i><span data-summary></span></summary>
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4 pt-4">
                <fieldset class="min-w-0"><legend class="text-sm font-medium mb-2">Folders</legend>
                    <label class="flex gap-2 items-center text-sm mb-2"><input type="checkbox" data-all>All folders</label>
                    <div class="max-h-48 overflow-y-auto space-y-2" data-folders></div></fieldset>
                <fieldset class="min-w-0"><legend class="text-sm font-medium mb-2">Role and skill tags</legend>
                    <div class="max-h-48 overflow-y-auto space-y-2" data-tags></div></fieldset>
                <div class="md:col-span-2 flex flex-wrap gap-3 items-end">
                    <label class="text-sm">Date basis<select data-basis class="block border rounded-md p-2 mt-1"><option value="uploaded">Uploaded</option><option value="received">Email received</option></select></label>
                    <label class="text-sm">From<input data-from type="date" class="block border rounded-md p-2 mt-1"></label>
                    <label class="text-sm">To<input data-to type="date" class="block border rounded-md p-2 mt-1"></label>
                    <button type="button" data-reset class="p-2 text-gray-600 hover:text-blue-600" aria-label="Clear CV filters" title="Clear CV filters"><i class="fas fa-undo" aria-hidden="true"></i></button>
                </div></div></details>`;
            const all = root.querySelector('[data-all]');
            const summary = () => {
                const count = selected === null ? 'All folders' : `${selected.length} folder${selected.length === 1 ? '' : 's'}`;
                root.querySelector('[data-summary]').textContent = `${count}${filters.tags?.length ? ` | ${filters.tags.length} tags` : ''}${filters.date_from || filters.date_to ? ' | Date range' : ''}`;
            };
            const folders = data.folders;
            // Keep stale selections visible instead of silently widening the search.
            for (const item of selected || []) if (!folders.some(f => f.bucket === item.bucket && f.path === item.path)) folders.push({...item, total:0});
            root.querySelector('[data-folders]').innerHTML = folders.map((item,index) => `<label class="flex gap-2 items-start text-sm break-words"><input type="checkbox" data-folder="${index}" class="mt-1"><span>${esc(item.path || 'Unfiled')} <span class="text-gray-500">(${Number(item.total) || 0})</span></span></label>`).join('') || '<p class="text-sm text-gray-500">No folders yet</p>';
            root.querySelector('[data-tags]').innerHTML = (data.tags || []).map(tag => `<label class="flex gap-2 items-center text-sm"><input type="checkbox" data-tag="${esc(tag)}">${esc(tag)}</label>`).join('');
            const sync = () => {
                all.checked = selected === null;
                root.querySelectorAll('[data-folder]').forEach(input => { const item=folders[Number(input.dataset.folder)]; input.checked = selected !== null && selected.some(f=>f.bucket===item.bucket&&f.path===item.path); });
                root.querySelectorAll('[data-tag]').forEach(input => { input.checked = (filters.tags || []).includes(input.dataset.tag); });
                root.querySelector('[data-from]').value = filters.date_from || '';
                root.querySelector('[data-to]').value = filters.date_to || '';
                root.querySelector('[data-basis]').value = filters.date_basis || 'uploaded'; summary();
            };
            all.addEventListener('change', () => { selected = all.checked ? null : []; sync(); });
            root.querySelectorAll('[data-folder]').forEach(input => input.addEventListener('change', () => {
                const item=folders[Number(input.dataset.folder)], key=f=>f.bucket===item.bucket&&f.path===item.path;
                selected=(selected || []).filter(f=>!key(f)); if(input.checked)selected.push({bucket:item.bucket,path:item.path});
                selected.sort((a,b)=>JSON.stringify(a).localeCompare(JSON.stringify(b))); sync();
            }));
            const readFilters = () => {
                filters={tags:[...root.querySelectorAll('[data-tag]:checked')].map(input=>input.dataset.tag).sort(),
                    date_from:root.querySelector('[data-from]').value, date_to:root.querySelector('[data-to]').value,
                    date_basis:root.querySelector('[data-basis]').value}; summary();
            };
            root.querySelectorAll('[data-tag],[data-from],[data-to],[data-basis]').forEach(input => input.addEventListener('change',readFilters));
            root.querySelector('[data-reset]').addEventListener('click',()=>{selected=null;filters={};sync();});
            sync();
        }).catch(()=>{
            if(disposed || !root.isConnected)return;
            root.innerHTML='<p role="alert" class="text-sm text-red-700">CV filters unavailable. <button type="button" class="underline" data-retry>Retry</button></p>';
            root.querySelector('[data-retry]').onclick=()=>{disposed=true;mount(root);};
        });
        return ()=>{disposed=true;};
    }
    window.ResumeFolders={mount,getSelection,getFilters,validate};
})();
