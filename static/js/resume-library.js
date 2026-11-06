(function () {
    'use strict';
    const esc=value=>(window.escapeAttr||window.escapeHtml)(String(value??''));
    const folderName=path=>{
        const parts=String(path||'').replace(/^gs:\/\/[^/]+\//,'').split('/');parts.pop();
        return (parts.join('/')||'Unfiled').replace(/^email_attachments\//,'Email imports / ');
    };
    function fileType(name){
        const extension=String(name||'').split('.').pop().toLowerCase();
        return {pdf:['PDF','fa-file-pdf','is-pdf'],doc:['Word','fa-file-word','is-word'],docx:['Word','fa-file-word','is-word'],txt:['Text','fa-file-alt','is-text']}[extension]||['Document','fa-file-alt','is-text'];
    }
    function fileSize(value){
        if(!Number.isFinite(value)||value<0)return'';
        if(value<1024)return value+' B';
        if(value<1048576)return (value/1024).toLocaleString(undefined,{maximumFractionDigits:1})+' KB';
        return (value/1048576).toLocaleString(undefined,{maximumFractionDigits:1})+' MB';
    }
    function uploadDate(value){
        const date=value?new Date(value):null;
        return date&&!isNaN(date)?date.toLocaleDateString(undefined,{day:'numeric',month:'short',year:'numeric'}):'Unavailable';
    }
    async function read(url){
        let response;
        try{response=await fetch(url);}
        catch(_){throw new Error('The CV library could not be reached. Please try again.');}
        const data=await response.json().catch(()=>({}));
        if(!response.ok||data.success!==true)throw new Error(typeof data.detail==='string'?data.detail:'CV library is temporarily unavailable.');
        return data;
    }
    function mount(root){
        let disposed=false,sequence=0,previewSequence=0,offset=0,query='',timer,modal,total=0;
        const limit=25;
        root.classList.add('recruiter-workspace','cv-library-view');
        root.innerHTML='<header class="workspace-header"><h2>CV Library</h2><button type="button" data-upload class="workspace-button is-primary"><i class="fas fa-upload" aria-hidden="true"></i>Upload CVs</button></header>'+
            '<div class="workspace-toolbar"><p data-count role="status" class="workspace-count">Loading library...</p><div class="workspace-toolbar-actions">'+
            '<label class="workspace-search"><i class="fas fa-search" aria-hidden="true"></i><input id="library-query" aria-label="Search filenames" type="search" maxlength="200" placeholder="Search filenames" autocomplete="off"><button type="button" data-clear-query class="workspace-icon-button" aria-label="Clear filename search" title="Clear search" hidden><i class="fas fa-times" aria-hidden="true"></i></button></label>'+
            '<button type="button" data-refresh class="workspace-icon-button" aria-label="Refresh CV library" title="Refresh CV library"><i class="fas fa-sync-alt" aria-hidden="true"></i></button></div></div><div data-list class="workspace-table-region"></div>'+
            '<footer class="workspace-pagination"><span data-page class="workspace-muted"></span><div class="workspace-page-controls"><label class="workspace-page-label">Page <input type="number" data-page-number aria-label="CV library page" min="1" value="1" step="1"><span data-page-total></span></label>'+
            '<button type="button" data-prev class="workspace-icon-button" aria-label="Previous CV page" title="Previous page"><i class="fas fa-chevron-left" aria-hidden="true"></i></button>'+
            '<button type="button" data-next class="workspace-icon-button" aria-label="Next CV page" title="Next page"><i class="fas fa-chevron-right" aria-hidden="true"></i></button></div></footer>';
        const alive=id=>!disposed&&root.isConnected&&id===sequence;
        const upload=()=>window.loadPage('uploadFiles');
        async function preview(id,button){
            const requestId=++previewSequence,icon=button.querySelector('i'),originalIcon=icon?.className;
            button.disabled=true;button.setAttribute('aria-busy','true');if(icon)icon.className='fas fa-circle-notch fa-spin';
            try{
                const data=await read('/api/resume-library/'+id);
                if(disposed||!root.isConnected||requestId!==previewSequence)return;
                modal?.remove();modal=document.createElement('div');modal.dataset.libraryDialog='true';modal.className='workspace-overlay';
                const type=fileType(data.file_name);
                modal.innerHTML='<section class="workspace-dialog cv-preview-dialog"><header><span class="workspace-file-icon '+type[2]+'"><i class="fas '+type[1]+'" aria-hidden="true"></i></span><h3>'+esc(data.file_name)+'</h3>'+
                    '<button type="button" data-close class="workspace-icon-button" aria-label="Close CV preview" title="Close preview"><i class="fas fa-times" aria-hidden="true"></i></button></header>'+
                    '<pre class="workspace-dialog-body cv-preview-text"></pre><footer><span class="workspace-muted">'+esc(type[0])+'</span>'+
                    (data.file_path?'<a class="workspace-button is-primary" href="/api/download-resume?file_path='+encodeURIComponent(data.file_path)+'"><i class="fas fa-download" aria-hidden="true"></i>Download original</a>':'')+'</footer></section>';
                modal.querySelector('pre').textContent=data.text||'Text preview unavailable.';
                document.body.append(modal);window.bindScheduleDialog(modal,'CV preview');
                modal.querySelector('[data-close]').onclick=()=>modal.remove();
                modal.addEventListener('click',event=>{if(event.target===modal)modal.remove();});
            }catch(error){if(!disposed&&requestId===previewSequence)window.showNotification?.(error.message,'error');}
            finally{button.disabled=false;button.removeAttribute('aria-busy');if(icon)icon.className=originalIcon;}
        }
        function emptyState(list){
            list.innerHTML='<div class="workspace-empty"><span class="workspace-empty-icon"><i class="fas '+(query?'fa-search':'fa-folder-open')+'" aria-hidden="true"></i></span><h3>'+(query?'No matching CVs':'No CVs uploaded')+'</h3>'+
                (query?'<p>'+esc(query)+'</p><button type="button" data-empty-clear class="workspace-button"><i class="fas fa-times" aria-hidden="true"></i>Clear search</button>':
                '<button type="button" data-empty-upload class="workspace-button is-primary"><i class="fas fa-upload" aria-hidden="true"></i>Upload CVs</button>')+'</div>';
            if(query)list.querySelector('[data-empty-clear]').onclick=()=>{root.querySelector('#library-query').value='';setQuery('');};
            else list.querySelector('[data-empty-upload]').onclick=upload;
        }
        function renderRows(list,rows){
            list.innerHTML='<table class="workspace-table cv-library-table"><thead><tr><th scope="col">CV</th><th scope="col" class="cv-library-folder">Folder</th><th scope="col">Uploaded</th><th scope="col" class="workspace-actions-column">Actions</th></tr></thead><tbody>'+
                rows.map(row=>{
                    const path=String(row.file_path||''),folder=folderName(path),type=fileType(row.file_name),size=fileSize(row.file_size),id=Number(row.id);
                    return '<tr><td class="cv-library-name"><div class="workspace-file"><span class="workspace-file-icon '+type[2]+'"><i class="fas '+type[1]+'" aria-hidden="true"></i></span><div class="workspace-file-info">'+
                        '<button type="button" data-open-cv="'+id+'" class="workspace-file-name" title="'+esc(row.file_name)+'">'+esc(row.file_name)+'</button><div class="workspace-file-meta">'+esc(type[0]+(size?' | '+size:''))+'</div><div class="cv-library-folder-mobile">'+esc(folder)+'</div></div></div></td>'+
                        '<td class="cv-library-folder"><span class="workspace-folder-label"><i class="fas fa-folder" aria-hidden="true"></i><span>'+esc(folder)+'</span></span></td>'+
                        '<td class="cv-library-date"><time datetime="'+esc(row.upload_timestamp||'')+'">'+esc(uploadDate(row.upload_timestamp))+'</time></td>'+
                        '<td class="workspace-row-actions"><button type="button" data-preview="'+id+'" class="workspace-icon-button" aria-label="Preview '+esc(row.file_name)+'" title="Preview CV"><i class="fas fa-eye" aria-hidden="true"></i></button>'+
                        (path?'<a class="workspace-icon-button" href="/api/download-resume?file_path='+encodeURIComponent(path)+'" aria-label="Download '+esc(row.file_name)+'" title="Download original"><i class="fas fa-download" aria-hidden="true"></i></a>':'')+'</td></tr>';
                }).join('')+'</tbody></table>';
            list.querySelectorAll('[data-preview],[data-open-cv]').forEach(button=>button.onclick=()=>preview(Number(button.dataset.preview||button.dataset.openCv),button));
        }
        async function load(){
            const id=++sequence,list=root.querySelector('[data-list]');
            list.setAttribute('aria-busy','true');
            list.innerHTML='<div class="workspace-loading" role="status"><i class="fas fa-circle-notch fa-spin" aria-hidden="true"></i>Loading CVs...</div>';
            root.querySelectorAll('[data-prev],[data-next],[data-page-number]').forEach(control=>{control.disabled=true;});
            try{
                const data=await read('/api/resume-library?limit='+limit+'&offset='+offset+'&query='+encodeURIComponent(query));
                if(!alive(id))return;
                if(!Array.isArray(data.uploads)||!Number.isSafeInteger(data.total)||data.total<0)throw new Error('CV library is temporarily unavailable.');
                total=data.total;
                if(offset>0&&offset>=total){offset=Math.floor(Math.max(0,total-1)/limit)*limit;return load();}
                root.querySelector('[data-count]').textContent=total.toLocaleString()+' uploaded CV'+(total===1?'':'s');
                if(data.uploads.length)renderRows(list,data.uploads);else emptyState(list);
                root.querySelector('[data-page]').textContent=total?(offset+1)+'-'+(offset+data.uploads.length)+' of '+total.toLocaleString():'0 CVs';
                const pages=Math.max(1,Math.ceil(total/limit)),page=root.querySelector('[data-page-number]');
                page.value=Math.floor(offset/limit)+1;page.max=pages;page.disabled=total===0;
                root.querySelector('[data-page-total]').textContent='of '+pages.toLocaleString();
                root.querySelector('[data-prev]').disabled=offset===0;
                root.querySelector('[data-next]').disabled=offset+limit>=total;
            }catch(error){
                if(alive(id)){
                    root.querySelector('[data-count]').textContent='Count unavailable';root.querySelector('[data-page]').textContent='';
                    list.innerHTML='<div class="workspace-empty is-error" role="alert"><span class="workspace-empty-icon"><i class="fas fa-exclamation-circle" aria-hidden="true"></i></span><h3>Library unavailable</h3><p>'+esc(error.message)+'</p><button type="button" data-retry class="workspace-button"><i class="fas fa-redo" aria-hidden="true"></i>Retry</button></div>';
                    list.querySelector('[data-retry]').onclick=load;
                }
            }finally{if(alive(id))list.setAttribute('aria-busy','false');}
        }
        function setQuery(value){
            clearTimeout(timer);query=value.trim();offset=0;++sequence;
            root.querySelectorAll('[data-prev],[data-next],[data-page-number]').forEach(control=>{control.disabled=true;});
            root.querySelector('[data-count]').textContent='Searching...';
            root.querySelector('[data-clear-query]').hidden=!value;
            timer=setTimeout(load,250);
        }
        root.querySelector('[data-upload]').onclick=upload;
        root.querySelector('[data-refresh]').onclick=()=>{clearTimeout(timer);load();};
        root.querySelector('[data-prev]').onclick=()=>{offset=Math.max(0,offset-limit);load();};
        root.querySelector('[data-next]').onclick=()=>{offset+=limit;load();};
        root.querySelector('[data-page-number]').onchange=event=>{
            if(!event.target.reportValidity())return;
            offset=(Number(event.target.value)-1)*limit;load();
        };
        root.querySelector('#library-query').oninput=event=>setQuery(event.target.value);
        root.querySelector('[data-clear-query]').onclick=()=>{const input=root.querySelector('#library-query');input.value='';setQuery('');input.focus();};
        load();return()=>{disposed=true;++previewSequence;clearTimeout(timer);modal?.remove();};
    }
    window.ResumeLibrary={mount};
})();
