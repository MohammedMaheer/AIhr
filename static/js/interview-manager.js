(function(){
    'use strict';
    const esc=value=>{const node=document.createElement('div');node.textContent=String(value??'');return node.innerHTML.replace(/"/g,'&quot;').replace(/'/g,'&#39;');};
    const humanError=(error,fallback)=>error?.name==='Error'&&error.message?error.message:fallback;
    async function open(id, cancelFirst=false){
        if(!/^[1-9]\d*$/.test(String(id))||document.querySelector('[data-interview-manager]'))return;
        const modal=document.createElement('div');modal.className='outreach-overlay';modal.dataset.interviewManager='';
        modal.innerHTML='<div class="outreach-dialog"><header class="outreach-header"><h2>Manage interview</h2><button type="button" data-close aria-label="Close interview details"><i class="fas fa-times" aria-hidden="true"></i></button></header><div class="outreach-body" data-content><p role="status">Loading interview...</p></div></div>';
        document.body.append(modal);window.bindScheduleDialog(modal,'Manage interview');
        let busy=false;
        const close=()=>{if(!busy)modal.remove();};
        modal.querySelector('[data-close]').addEventListener('click',close);
        modal.addEventListener('keydown',event=>{if(busy&&event.key==='Escape')event.stopImmediatePropagation();},{capture:true});
        try{
            const response=await fetch('/api/interviews/'+id);const data=await response.json();
            if(!response.ok||!data.success)throw new Error(data.detail||'Interview could not be loaded.');
            if(!modal.isConnected)return;
            const row=data.interview;
            const external=row.meeting_provider&&!['none','in_person','in-person','phone'].includes(row.meeting_provider);
            const zoneOptions=window.scheduleZoneOptions();
            modal.querySelector('[data-content]').innerHTML=`<p class="mb-4"><strong>${esc(row.candidate_name)}</strong><br>${esc(row.candidate_email||'')}<br>Status: ${esc(row.status)}</p>
                <form data-edit-form><div class="outreach-fields">
                <label>Job title<input name="position" maxlength="500" required value="${esc(row.position||'')}"></label>
                <label>Interview type<select name="interview_type">${[['phone','Phone screening'],['video','Video interview'],['in-person','In-person interview'],['technical','Technical interview'],['final','Final interview']].map(([value,label])=>`<option value="${value}" ${value===row.interview_type?'selected':''}>${label}</option>`).join('')}</select></label>
                <label>Date<input name="interview_date" type="date" required value="${esc(String(row.interview_date||'').slice(0,10))}" min="${window.localDateInputValue()}"></label>
                <label>Time<input name="interview_time" type="time" required value="${esc(String(row.interview_time||'').slice(0,5))}"></label>
                <label>Time zone<select name="time_zone" required><option value="">Choose time zone</option>${zoneOptions}</select></label>
                <label>Duration (minutes)<input name="duration" type="number" min="5" max="480" required value="${esc(row.duration_minutes||60)}"></label>
                <label>Location<input name="location" maxlength="2000" value="${esc(row.location||'')}"></label>
                <label>Interviewer<input name="interviewer" maxlength="500" value="${esc(row.interviewer||'')}"></label></div>
                <label>Private notes<textarea name="notes" maxlength="10000" rows="3">${esc(row.notes||'')}</textarea></label>
                ${external?'<label><input name="confirm_calendar_change" type="checkbox" required> Update the linked calendar event and notify attendees</label>':''}
                <p data-status role="status" aria-live="polite"></p>
                <div data-cancel-panel ${cancelFirst?'':'hidden'}><p>Cancel this interview${external?' and its linked calendar event? Attendees will receive a cancellation.':'?'} The audit record will remain.</p><button type="button" data-keep>Keep interview</button><button type="button" data-confirm-cancel>Cancel interview</button></div>
                <div class="outreach-footer"><button type="button" data-cancel aria-label="Cancel interview" title="Cancel interview" ${row.status==='cancelled'?'disabled':''}><i class="fas fa-trash" aria-hidden="true"></i></button><button type="button" data-reconcile ${row.pending_change?'':'hidden'}>Check calendar</button><button type="button" data-close-form>Close</button><button type="submit" data-save ${row.pending_change||row.status==='cancelled'?'disabled':''}>Save changes</button></div></form>
                ${(row.history||[]).length?'<h3 class="text-base font-semibold mt-4">Change history</h3><ul>'+row.history.map(item=>'<li class="text-sm py-2">'+esc(item.action==='cancel'?'Cancellation':'Interview edit')+' - '+esc(item.state)+' - '+esc(new Date(item.created_at).toLocaleString())+'</li>').join('')+'</ul>':''}`;
            const form=modal.querySelector('form'),status=modal.querySelector('[data-status]');
            if(row.status==='cancelled')form.querySelectorAll('input,select,textarea').forEach(field=>field.disabled=true);
            const zone=form.elements.time_zone;
            if(row.time_zone&&![...zone.options].some(option=>option.value===row.time_zone))zone.add(new Option(row.time_zone,row.time_zone));
            zone.value=row.time_zone||'';
            if(row.pending_change)status.textContent='A previous change needs confirmation. Check the calendar before making another change.';
            const cancelPanel=modal.querySelector('[data-cancel-panel]');
            modal.querySelector('[data-cancel]').addEventListener('click',()=>{cancelPanel.hidden=false;});
            modal.querySelector('[data-keep]').addEventListener('click',()=>{cancelPanel.hidden=true;});
            modal.querySelector('[data-close-form]').addEventListener('click',close);
            async function submit(action){
                if(busy||row.pending_change)return;
                if(action==='edit'&&!form.reportValidity())return;
                const body={version:row.version,confirm_calendar_change:action==='cancel'||!!form.elements.confirm_calendar_change?.checked};
                if(action==='edit')for(const name of ['position','interview_type','interview_date','interview_time','time_zone','duration','location','interviewer','notes'])body[name]=form.elements[name].value;
                busy=true;modal.querySelectorAll('button').forEach(button=>button.disabled=true);status.textContent=action==='cancel'?'Cancelling interview...':'Saving interview changes...';
                try{
                    const response=await fetch('/api/interviews/'+id,{method:action==='cancel'?'DELETE':'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
                    const data=await response.json();if(!response.ok||!data.success){const error=new Error(data.error||data.detail||'The change could not be confirmed. Check the calendar before trying again.');error.pending=data.sync_unknown??(response.status>=500);throw error;}
                    window.showNotification(action==='cancel'?'Interview cancelled. Its audit record has been retained.':'Interview updated.','success');busy=false;modal.remove();window.loadUpcomingEvents?.();
                }catch(error){status.textContent=humanError(error,'The change could not be confirmed. Check the calendar before trying again.');row.pending_change=error.pending!==false;modal.querySelector('[data-reconcile]').hidden=!row.pending_change;}
                finally{busy=false;modal.querySelectorAll('button').forEach(button=>button.disabled=false);modal.querySelector('[data-save]').disabled=!!row.pending_change;modal.querySelector('[data-confirm-cancel]').disabled=!!row.pending_change;}
            }
            form.addEventListener('submit',event=>{event.preventDefault();submit('edit');});
            modal.querySelector('[data-confirm-cancel]').addEventListener('click',()=>submit('cancel'));
            modal.querySelector('[data-reconcile]').addEventListener('click',async()=>{
                if(busy)return;busy=true;
                try{
                    const response=await fetch('/api/interviews/'+id+'/reconcile',{method:'POST'});const data=await response.json();
                    if(!response.ok||!data.success)throw new Error(data.detail||data.error||'The calendar change is still unconfirmed.');
                    busy=false;modal.remove();window.loadUpcomingEvents?.();if(data.message)window.showNotification(data.message,'info');
                }catch(error){status.textContent=humanError(error,'The calendar could not be checked. Please try again later.');}finally{busy=false;}
            });
        }catch(error){modal.querySelector('[data-content]').textContent=humanError(error,'Interview details are temporarily unavailable. Close this window and try again.');}
    }
    async function list(){
        if(document.querySelector('[data-interview-list]'))return;
        const modal=document.createElement('div');modal.className='outreach-overlay';modal.dataset.interviewList='';
        modal.innerHTML='<div class="outreach-dialog"><header class="outreach-header"><h2>Schedule history</h2><button type="button" data-close aria-label="Close schedule history"><i class="fas fa-times" aria-hidden="true"></i></button></header><div class="outreach-body"><label>Status<select data-filter><option value="all">All interviews</option><option value="scheduled">Scheduled</option><option value="cancelled">Cancelled</option></select></label><div data-records role="region" aria-label="Interview history" tabindex="0" style="overflow-x:auto"></div><div class="outreach-footer"><button type="button" data-previous aria-label="Previous schedule page"><i class="fas fa-chevron-left" aria-hidden="true"></i></button><span data-page></span><button type="button" data-next aria-label="Next schedule page"><i class="fas fa-chevron-right" aria-hidden="true"></i></button></div></div></div>';
        document.body.append(modal);window.bindScheduleDialog(modal,'Schedule history');
        modal.querySelector('[data-close]').addEventListener('click',()=>modal.remove());
        let page=1,epoch=0;
        const filter=modal.querySelector('[data-filter]'),records=modal.querySelector('[data-records]'),previous=modal.querySelector('[data-previous]'),next=modal.querySelector('[data-next]');
        async function load(){
            const request=++epoch;previous.disabled=next.disabled=true;records.textContent='Loading schedule...';
            try{
                const response=await fetch('/api/interviews?page='+page+'&page_size=25&status='+filter.value);const data=await response.json();
                if(!response.ok||!data.success)throw new Error();
                if(!modal.isConnected||request!==epoch)return;
                records.innerHTML=data.interviews.length?'<table class="schedule-history-table"><thead><tr><th>Candidate</th><th>Date and time</th><th>Status</th><th></th></tr></thead><tbody>'+data.interviews.map(row=>`<tr><td>${esc(row.candidate_name)}<br><span class="text-xs text-gray-500">${esc(row.position||'')}</span></td><td>${esc(row.interview_date)} ${esc(String(row.interview_time||'').slice(0,5))}<br><span class="text-xs text-gray-500">${esc(row.time_zone||'Time zone not recorded')}</span></td><td>${esc(row.status)}</td><td><button type="button" data-open="${esc(row.id)}" aria-label="View interview details" title="View interview details"><i class="fas fa-pen" aria-hidden="true"></i></button></td></tr>`).join('')+'</tbody></table>':'No interviews in this view.';
                previous.disabled=page<=1;next.disabled=page*25>=data.total;modal.querySelector('[data-page]').textContent='Page '+page;
                records.querySelectorAll('[data-open]').forEach(button=>button.addEventListener('click',()=>{const id=button.dataset.open;modal.remove();queueMicrotask(()=>open(id));}));
            }catch(_){if(request===epoch&&modal.isConnected){records.textContent='The schedule could not be loaded.';const retry=document.createElement('button');retry.type='button';retry.textContent='Retry';retry.addEventListener('click',load);records.append(retry);}}
        }
        filter.addEventListener('change',()=>{page=1;load();});previous.addEventListener('click',()=>{page--;load();});next.addEventListener('click',()=>{page++;load();});load();
    }
    window.InterviewManager={open,list};
}());
