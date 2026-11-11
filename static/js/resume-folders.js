(function () {
    'use strict';
    let owner = null, selected = null, filters = {}, available = null, filterDialog = null;
    const listeners = new Set();
    const esc = value => (window.escapeAttr || window.escapeHtml)(String(value ?? ''));
    const folderName = item => (item.path || 'Unfiled').replace(/^email_attachments\//, 'Email imports / ');
    const dateValue = value => `${value.getFullYear()}-${String(value.getMonth()+1).padStart(2,'0')}-${String(value.getDate()).padStart(2,'0')}`;
    const dateLabel = value => {
        const parts = value.split('-').map(Number);
        return new Date(parts[0],parts[1]-1,parts[2]).toLocaleDateString(undefined,{day:'numeric',month:'short',year:'numeric'});
    };
    function resetOwner() {
        const key = JSON.stringify([window.currentUser?.id,window.currentUser?.company]);
        if(owner !== key){ owner=key; selected=null; filters={}; available=null; }
    }
    function getSelection(){ resetOwner(); return selected===null ? null : JSON.parse(JSON.stringify(selected)); }
    function getFilters(){
        resetOwner(); const value={};
        if(filters.tags?.length)value.tags=[...filters.tags];
        if(filters.date_from)value.date_from=filters.date_from;
        if(filters.date_to)value.date_to=filters.date_to;
        if(value.date_from||value.date_to)value.date_basis=filters.date_basis||'uploaded';
        return value;
    }
    function validate(){
        resetOwner();
        if(selected!==null&&!selected.length)throw new Error('Choose at least one folder, or select All folders.');
        if(selected?.length>50)throw new Error('Choose no more than 50 folders.');
        if(filters.date_from&&filters.date_to&&filters.date_from>filters.date_to)throw new Error('The start date must not be after the end date.');
    }
    function summary(){
        resetOwner();
        const parts=[selected===null?'All folders':selected.length+' folder'+(selected.length===1?'':'s')];
        if(filters.tags?.length)parts.push(filters.tags.length+' tag'+(filters.tags.length===1?'':'s'));
        if(filters.date_from||filters.date_to)parts.push('Date range');
        return parts.join(' | ');
    }
    function announce(){ listeners.forEach(listener=>listener()); }
    function subscribe(listener){ listeners.add(listener);listener();return()=>listeners.delete(listener); }

    function mount(root,options={}){
        if(!root)return()=>{};
        resetOwner();let disposed=false,cancelSync=()=>{};
        root.classList.add('cv-filter-view');
        root.innerHTML='<div class="workspace-loading" role="status"><i class="fas fa-circle-notch fa-spin" aria-hidden="true"></i>Loading CV filters...</div>';
        const alive=()=>!disposed&&root.isConnected;
        async function load(){
            try{
                const response=await fetch('/api/resume-folders'),data=await response.json();
                if(!response.ok||data.success!==true||!Array.isArray(data.folders))throw Error();
                if(!alive())return;
                available=data.supported===true;
                if(!available){root.textContent='';announce();return;}
                render(data);
            }catch(_){
                if(!alive())return;
                root.innerHTML='<div class="workspace-message is-error" role="alert"><i class="fas fa-exclamation-circle" aria-hidden="true"></i><span>CV filters unavailable.</span><button type="button" class="workspace-button" data-retry><i class="fas fa-redo" aria-hidden="true"></i>Retry</button></div>';
                root.querySelector('[data-retry]').onclick=load;
            }
        }
        function render(data){
            cancelSync();
            const folders=[...data.folders];
            for(const item of selected||[])if(!folders.some(f=>f.bucket===item.bucket&&f.path===item.path))folders.push({...item,total:0});
            const folderRows=folders.map((item,index)=>'<label class="cv-folder-option" title="'+esc(folderName(item))+'"><input type="checkbox" data-folder="'+index+'"><i class="fas fa-folder" aria-hidden="true"></i><span>'+esc(folderName(item))+'</span><small>'+Number(item.total||0).toLocaleString()+'</small></label>').join('');
            const tagRows=(data.tags||[]).map(tag=>{
                const count=data.tag_counts?.[tag]?.searchable;
                return '<label class="cv-tag-option"><input type="checkbox" data-tag="'+esc(tag)+'"><span>'+esc(tag)+'</span>'+
                    (Number.isSafeInteger(count)&&count>=0?'<small title="Searchable CVs in this workspace">'+count.toLocaleString()+'</small>':'')+'</label>';
            }).join('');
            const tagPicker=options.quickTags?'<label class="cv-tag-picker"><span><i class="fas fa-tags" aria-hidden="true"></i>Search by tag</span><select data-tag-choice><option value="">All tags</option><option value="__multiple__" data-multiple-tags disabled hidden></option>'+(data.tags||[]).map(tag=>{
                const count=data.tag_counts?.[tag]?.searchable;
                return '<option value="'+esc(tag)+'">'+esc(tag)+(Number.isSafeInteger(count)&&count>=0?' ('+count.toLocaleString()+')':'')+'</option>';
            }).join('')+'</select></label>':'';
            const controls='<div class="cv-filter-columns"><fieldset><legend>Folders</legend>'+
                '<label class="cv-folder-all"><input type="checkbox" data-all><i class="fas fa-folder-open" aria-hidden="true"></i><span>All folders</span></label>'+
                '<label class="workspace-search cv-folder-search"><i class="fas fa-search" aria-hidden="true"></i><input type="search" data-folder-query aria-label="Find a folder" placeholder="Find a folder" autocomplete="off"></label>'+
                '<div class="cv-folder-list" data-folders>'+folderRows+'</div><p data-folder-empty class="workspace-muted" hidden>No matching folders</p></fieldset>'+
                '<fieldset><legend>Role and skill tags</legend><label class="workspace-search cv-tag-search"><i class="fas fa-search" aria-hidden="true"></i><input type="search" data-tag-query aria-label="Find a tag" placeholder="Find a tag" autocomplete="off"></label><div class="cv-tag-list" data-tags>'+tagRows+'</div><p data-tag-empty class="workspace-muted" hidden>No matching tags</p></fieldset></div>'+
                '<fieldset class="cv-date-fields"><legend>Date range</legend><label>Date type<select data-basis aria-label="Date type"><option value="uploaded">Uploaded</option><option value="received">Email received</option></select></label>'+
                '<label>Period<select data-range aria-label="Period"><option value="any">Any time</option><option value="30">Last 30 days</option><option value="3">Last 3 months</option><option value="6">Last 6 months</option><option value="custom">Custom range</option></select></label>'+
                '<label>From<input data-from type="date" aria-label="From"></label><label>To<input data-to type="date" aria-label="To"></label></fieldset>';
            root.innerHTML=tagPicker+(options.expanded?'<div class="cv-filter-body">'+controls+'</div>':
                '<details class="cv-filter-disclosure"><summary><span class="cv-filter-title"><i class="fas fa-sliders-h" aria-hidden="true"></i>Folders, tags &amp; dates</span><span data-summary></span><i class="fas fa-chevron-down cv-filter-chevron" aria-hidden="true"></i></summary><div class="cv-filter-body">'+controls+'</div></details>')+
                '<div class="cv-filter-footer"><div data-chips class="cv-filter-chips" aria-label="Active CV filters"></div><button type="button" data-reset class="workspace-icon-button" aria-label="Clear CV filters" title="Clear CV filters"><i class="fas fa-undo" aria-hidden="true"></i></button></div><p data-filter-error class="workspace-inline-error" role="alert" tabindex="-1" hidden></p>';
            const all=root.querySelector('[data-all]');
            root.querySelector('[data-folder-empty]').hidden=folders.length>0;
            function sync(){
                if(!alive())return;
                all.checked=selected===null;all.closest('label').classList.toggle('is-selected',all.checked);
                const heading=root.querySelector('[data-summary]');if(heading)heading.textContent=summary();
                root.querySelectorAll('[data-folder]').forEach(input=>{
                    const item=folders[Number(input.dataset.folder)];
                    input.checked=selected!==null&&selected.some(f=>f.bucket===item.bucket&&f.path===item.path);
                    input.closest('label').classList.toggle('is-selected',input.checked);
                });
                root.querySelectorAll('[data-tag]').forEach(input=>{
                    input.checked=(filters.tags||[]).includes(input.dataset.tag);input.closest('label').classList.toggle('is-selected',input.checked);
                });
                const picker=root.querySelector('[data-tag-choice]');
                if(picker){
                    const tags=filters.tags||[],multiple=picker.querySelector('[data-multiple-tags]');
                    multiple.hidden=tags.length<2;multiple.textContent=tags.length+' tags selected';
                    picker.value=tags.length>1?'__multiple__':tags[0]||'';
                }
                root.querySelector('[data-from]').value=filters.date_from||'';
                root.querySelector('[data-to]').value=filters.date_to||'';
                root.querySelector('[data-basis]').value=filters.date_basis||'uploaded';
                if(!filters.date_from&&!filters.date_to)root.querySelector('[data-range]').value='any';
                const chips=[];
                (selected||[]).forEach((item,index)=>chips.push({kind:'folder',value:index,label:folderName(item)}));
                (filters.tags||[]).forEach(tag=>chips.push({kind:'tag',value:tag,label:tag}));
                if(filters.date_from||filters.date_to)chips.push({kind:'date',value:'',label:(filters.date_basis==='received'?'Received':'Uploaded')+': '+(filters.date_from?dateLabel(filters.date_from):'Any')+' to '+(filters.date_to?dateLabel(filters.date_to):'any date')});
                root.querySelector('[data-chips]').innerHTML=chips.map(chip=>'<span class="cv-filter-chip"><span>'+esc(chip.label)+'</span><button type="button" data-remove="'+chip.kind+'" data-value="'+esc(chip.value)+'" aria-label="Remove '+esc(chip.label)+'" title="Remove filter"><i class="fas fa-times" aria-hidden="true"></i></button></span>').join('');
                root.querySelector('[data-reset]').disabled=!chips.length&&selected===null;
                root.querySelector('.cv-filter-footer').hidden=!chips.length&&selected===null;
                const error=root.querySelector('[data-filter-error]');
                try{validate();error.hidden=true;error.textContent='';}catch(failure){error.textContent=failure.message;error.hidden=false;}
                root.querySelectorAll('[data-remove]').forEach(button=>button.onclick=()=>{
                    if(button.dataset.remove==='folder')selected.splice(Number(button.dataset.value),1);
                    if(button.dataset.remove==='tag')filters.tags=filters.tags.filter(tag=>tag!==button.dataset.value);
                    if(button.dataset.remove==='date'){delete filters.date_from;delete filters.date_to;}
                    announce();
                });
            }
            all.onchange=()=>{selected=all.checked?null:[];announce();};
            const picker=root.querySelector('[data-tag-choice]');
            if(picker)picker.onchange=()=>{
                if(picker.value && !(data.tags||[]).includes(picker.value))return;
                filters.tags=picker.value?[picker.value]:[];announce();
            };
            root.querySelectorAll('[data-folder]').forEach(input=>input.onchange=()=>{
                const item=folders[Number(input.dataset.folder)];
                selected=(selected||[]).filter(f=>!(f.bucket===item.bucket&&f.path===item.path));
                if(input.checked)selected.push({bucket:item.bucket,path:item.path});
                selected.sort((a,b)=>JSON.stringify(a).localeCompare(JSON.stringify(b)));announce();
            });
            root.querySelector('[data-folder-query]').oninput=event=>{
                const query=event.target.value.trim().toLocaleLowerCase();let count=0;
                root.querySelectorAll('[data-folder]').forEach(input=>{
                    const label=input.closest('label');label.hidden=!folderName(folders[Number(input.dataset.folder)]).toLocaleLowerCase().includes(query);
                    if(!label.hidden)count++;
                });
                root.querySelector('[data-folder-empty]').hidden=count>0;
            };
            root.querySelector('[data-tag-query]').oninput=event=>{
                const query=event.target.value.trim().toLocaleLowerCase();let count=0;
                root.querySelectorAll('[data-tag]').forEach(input=>{
                    const label=input.closest('label');label.hidden=!input.dataset.tag.toLocaleLowerCase().includes(query);
                    if(!label.hidden)count++;
                });
                root.querySelector('[data-tag-empty]').hidden=count>0;
            };
            function readFilters(){
                filters={tags:[...root.querySelectorAll('[data-tag]:checked')].map(input=>input.dataset.tag).sort(),
                    date_from:root.querySelector('[data-from]').value,date_to:root.querySelector('[data-to]').value,date_basis:root.querySelector('[data-basis]').value};announce();
            }
            root.querySelectorAll('[data-tag],[data-from],[data-to],[data-basis]').forEach(input=>input.onchange=()=>{
                if(input.matches('[data-from],[data-to]'))root.querySelector('[data-range]').value='custom';readFilters();
            });
            root.querySelector('[data-range]').onchange=event=>{
                if(event.target.value==='custom')return;
                const end=new Date(),start=new Date(end);
                if(event.target.value==='30')start.setDate(start.getDate()-29);
                else if(event.target.value!=='any'){
                    start.setDate(1);start.setMonth(start.getMonth()-Number(event.target.value));
                    start.setDate(Math.min(end.getDate(),new Date(start.getFullYear(),start.getMonth()+1,0).getDate()));
                }
                root.querySelector('[data-from]').value=event.target.value==='any'?'':dateValue(start);
                root.querySelector('[data-to]').value=event.target.value==='any'?'':dateValue(end);readFilters();
            };
            root.querySelector('[data-reset]').onclick=()=>{selected=null;filters={};announce();};
            cancelSync=subscribe(sync);announce();
        }
        load();return()=>{disposed=true;cancelSync();};
    }
    function closeDialog(){filterDialog?.remove();filterDialog=null;}
    function openDialog(){
        if(filterDialog?.isConnected)return;
        const modal=document.createElement('div');filterDialog=modal;modal.className='workspace-overlay';modal.dataset.cvFilterDialog='true';
        modal.innerHTML='<section class="workspace-dialog cv-filter-dialog"><header><h3>Search filters</h3><button type="button" data-close class="workspace-icon-button" aria-label="Close search filters" title="Close search filters"><i class="fas fa-times" aria-hidden="true"></i></button></header><div class="workspace-dialog-body" data-filter-content></div><footer><button type="button" data-done class="workspace-button is-primary"><i class="fas fa-check" aria-hidden="true"></i>Done</button></footer></section>';
        document.body.append(modal);
        const dispose=mount(modal.querySelector('[data-filter-content]'),{expanded:true});
        window.bindScheduleDialog(modal,'Search filters');
        modal.querySelector('[data-close]').onclick=closeDialog;
        modal.querySelector('[data-done]').onclick=()=>{try{validate();closeDialog();}catch(_){modal.querySelector('[data-filter-error]')?.focus();}};
        const observer=new MutationObserver(()=>{if(!modal.isConnected){observer.disconnect();dispose();if(filterDialog===modal)filterDialog=null;}});
        observer.observe(document.body,{childList:true});
    }
    window.ResumeFolders={mount,getSelection,getFilters,validate,summary,subscribe,openDialog,closeDialog,isAvailable:()=>available===true};
})();
