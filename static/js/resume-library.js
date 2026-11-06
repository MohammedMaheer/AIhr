(function () {
    'use strict';
    const esc = value => (window.escapeAttr || window.escapeHtml)(String(value ?? ''));
    async function read(url) {
        const response = await fetch(url), data = await response.json().catch(()=>({}));
        if(!response.ok || data.success !== true)throw new Error(typeof data.detail === 'string' ? data.detail : 'CV library is temporarily unavailable.');
        return data;
    }
    function mount(root) {
        let disposed=false, sequence=0, previewSequence=0, offset=0, query='', timer, modal;
        const limit=25;
        root.innerHTML=`<div class="flex flex-wrap justify-between items-center gap-4 mb-5"><h2 class="text-2xl font-bold">CV Library</h2>
            <div class="flex gap-2 items-center"><label class="sr-only" for="library-query">Search filenames</label><input id="library-query" type="search" maxlength="200" placeholder="Search filenames" class="border rounded-md p-2 w-full sm:w-64">
            <button type="button" data-refresh class="p-2" aria-label="Refresh CV library" title="Refresh CV library"><i class="fas fa-sync-alt" aria-hidden="true"></i></button></div></div>
            <p data-count role="status" class="text-sm text-gray-500 mb-3"></p><div data-list></div>
            <div class="flex justify-between items-center gap-3 mt-4"><button type="button" data-prev class="border rounded-md p-2" aria-label="Previous CV page" title="Previous page"><i class="fas fa-chevron-left" aria-hidden="true"></i></button>
            <span data-page class="text-sm text-gray-600"></span><button type="button" data-next class="border rounded-md p-2" aria-label="Next CV page" title="Next page"><i class="fas fa-chevron-right" aria-hidden="true"></i></button></div>`;
        const alive=id=>!disposed&&root.isConnected&&id===sequence;
        async function preview(id, button) {
            const requestId=++previewSequence;
            button.disabled=true;
            try {
                const data=await read(`/api/resume-library/${id}`);if(disposed||!root.isConnected||requestId!==previewSequence)return;
                modal?.remove();
                modal=document.createElement('div');modal.dataset.libraryDialog='true';
                modal.className='fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4';
                modal.innerHTML=`<div class="bg-white rounded-lg shadow-xl w-full max-w-4xl max-h-[90vh] flex flex-col min-w-0">
                    <div class="flex items-center justify-between gap-4 border-b p-4"><h3 class="font-semibold break-all">${esc(data.file_name)}</h3><button type="button" data-close class="p-2 shrink-0" aria-label="Close CV preview" title="Close preview"><i class="fas fa-times" aria-hidden="true"></i></button></div>
                    <pre class="p-5 overflow-auto whitespace-pre-wrap break-words text-sm font-sans flex-1"></pre>
                    <div class="border-t p-4 text-right"><a class="text-blue-700" href="/api/download-resume?file_path=${encodeURIComponent(data.file_path)}"><i class="fas fa-download mr-2" aria-hidden="true"></i>Download original</a></div></div>`;
                modal.querySelector('pre').textContent=data.text||'Text preview is not available for this CV. The original file is available to download.';
                document.body.append(modal);window.bindScheduleDialog(modal,'CV preview');
                modal.querySelector('[data-close]').onclick=()=>modal.remove();
            }catch(error){window.showNotification?.(error.message,'error');}finally{button.disabled=false;}
        }
        async function load() {
            const id=++sequence,list=root.querySelector('[data-list]');
            list.setAttribute('aria-busy','true');list.innerHTML='<p role="status" class="py-8 text-gray-500">Loading CVs...</p>';
            root.querySelectorAll('[data-prev],[data-next]').forEach(button=>{button.disabled=true;});
            try {
                const data=await read(`/api/resume-library?limit=${limit}&offset=${offset}&query=${encodeURIComponent(query)}`);
                if(!alive(id))return;if(!Array.isArray(data.uploads)||!Number.isInteger(data.total))throw new Error('CV library is temporarily unavailable.');
                root.querySelector('[data-count]').textContent=`${data.total.toLocaleString()} uploaded CV${data.total===1?'':'s'}`;
                list.innerHTML=data.uploads.length?`<div class="overflow-x-auto"><table class="w-full text-sm"><thead class="border-b text-left text-gray-500"><tr><th class="p-3">CV</th><th class="p-3">Uploaded</th><th class="p-3 text-right">Actions</th></tr></thead><tbody>${data.uploads.map(row=>{
                    const path=String(row.file_path||''), parts=path.replace(/^gs:\/\/[^/]+\//,'').split('/');parts.pop();
                    const uploaded=row.upload_timestamp?new Date(row.upload_timestamp):null;
                    return `<tr class="border-b"><td class="p-3 max-w-md"><div class="font-medium break-all">${esc(row.file_name)}</div><div class="text-gray-500 text-xs break-all mt-1">${esc(parts.join('/')||'Unfiled')}</div></td><td class="p-3 whitespace-nowrap">${uploaded&&!isNaN(uploaded)?esc(uploaded.toLocaleDateString()):'Unavailable'}</td>
                    <td class="p-3 text-right whitespace-nowrap"><button type="button" data-preview="${Number(row.id)}" class="p-2 text-blue-700" aria-label="Preview ${esc(row.file_name)}" title="Preview CV"><i class="fas fa-eye" aria-hidden="true"></i></button>
                    <a class="inline-block p-2 text-gray-600" href="/api/download-resume?file_path=${encodeURIComponent(path)}" aria-label="Download ${esc(row.file_name)}" title="Download original"><i class="fas fa-download" aria-hidden="true"></i></a></td></tr>`;
                }).join('')}</tbody></table></div>`:'<p class="py-8 text-gray-500">No CVs match this view.</p>';
                root.querySelector('[data-page]').textContent=data.total?`${offset+1}-${Math.min(offset+limit,data.total)} of ${data.total.toLocaleString()}`:'0 CVs';
                root.querySelector('[data-prev]').disabled=offset===0;
                root.querySelector('[data-next]').disabled=offset+limit>=data.total;
                list.querySelectorAll('[data-preview]').forEach(button=>button.onclick=()=>preview(Number(button.dataset.preview),button));
            }catch(error){if(alive(id)){root.querySelector('[data-count]').textContent='Count unavailable';list.innerHTML=`<p role="alert" class="py-8 text-red-700">${esc(error.message)}</p>`;}}
            finally{if(alive(id))list.setAttribute('aria-busy','false');}
        }
        root.querySelector('[data-refresh]').onclick=()=>load();
        root.querySelector('[data-prev]').onclick=()=>{offset=Math.max(0,offset-limit);load();};
        root.querySelector('[data-next]').onclick=()=>{offset+=limit;load();};
        root.querySelector('#library-query').oninput=event=>{clearTimeout(timer);query=event.target.value.trim();offset=0;timer=setTimeout(load,250);};
        load();return()=>{disposed=true;clearTimeout(timer);modal?.remove();};
    }
    window.ResumeLibrary={mount};
})();
