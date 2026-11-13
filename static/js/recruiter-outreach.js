(function () {
    'use strict';
    const drafts = new Map();
    const clean = value => String(value || '').trim();
    const humanError = (error, fallback) => error?.name === 'Error' && error.message ? error.message : fallback;
    const esc = value => { const node = document.createElement('div'); node.textContent = String(value ?? ''); return node.innerHTML; };
    const generic = value => !clean(value) || /^(position|not specified|unknown|the role)$/i.test(clean(value));

    function context(values = {}) {
        const result = values.useSearch === false ? {} : (window.searchResultsData || {});
        const user = window.currentUser || {};
        const query = clean(values.query ?? result.query);
        const prefix = query.replace(/^(?:please\s+)?(?:find|show|search for|looking for|i need|we need)\s+/i, '')
            .replace(/^(?:me\s+)?(?:\d+\s+)?(?:candidates?|profiles?|resumes?)\s+(?:for\s+)?/i, '')
            .split(/\b(?:with|who|based|located|having|in|from|onsite|on-site)\b|[;\n]/i)[0].trim();
        const literalRole = prefix.length <= 120 && /\b(engineer|developer|analyst|manager|architect|accountant|designer|consultant|lead|specialist|administrator|recruiter|technician|nurse)\b/i.test(prefix) ? prefix : '';
        const position = literalRole || (!generic(result.job_title) ? result.job_title : '') || (!generic(values.position) ? values.position : '');
        const location = query.match(/\b(?:location\s*[:=]\s*|(?:based|located|onsite|on-site)\s+in\s+)([A-Za-z][A-Za-z ,.-]{1,70}?)(?=[;\n]|\s+(?:with|who|and|salary|experience)\b|$)/i)
            || query.match(/\bin\s+(Dubai|Abu Dhabi|Riyadh|Jeddah|Chennai|Bengaluru|Bangalore|Mumbai|London|New York)(?:,?\s+(UAE|KSA|Saudi Arabia|India))?\b/i);
        const salary = query.match(/\b(?:AED|SAR|USD|INR)\s*[\d,]+(?:\s*[-\u2013]\s*[\d,]+)?(?:\s*(?:\/|per)\s*(?:month|year))?/i);
        return { ...values, query, position: clean(position),
            company: clean(values.company || user.company?.company_name || 'Efforts Solutions'),
            recruiter: /^(super admin|admin|administrator)$/i.test(clean(user.full_name)) ? 'Recruitment Team' : clean(user.full_name || 'Recruitment Team'),
            location: clean(values.location || (location ? [location[1], location[2]].filter(Boolean).join(', ') : '')),
            salary: salary ? salary[0] : '',
            shifts: /24\s*[x/]\s*7|rotating shifts/i.test(query), onsite: /on[- ]?site/i.test(query) };
    }

    async function connections() {
        const response = await fetch('/api/integrations/status', {credentials: 'same-origin'});
        if (!response.ok) throw new Error('Connected accounts are temporarily unavailable.');
        const data = await response.json();
        if (data.success !== true) throw new Error('Connected accounts are temporarily unavailable.');
        return data;
    }
    const ready = (data, provider, capability) => data[provider]?.connected === true
        && !data[provider].reconnect_required && data[provider].capabilities?.[capability] === true;

    async function configureSchedule(modal) {
        const general = !!modal.querySelector('#gs-provider');
        const prefix = general ? 'gs-' : 'interview-';
        const select = modal.querySelector('#' + prefix + 'provider');
        if (!select) return;
        select.replaceChildren(new Option('Use a location or phone call', 'none'));
        select.disabled = true;
        const hint = select.parentElement.querySelector('p');
        if (hint) hint.textContent = 'Checking available meeting options...';
        try {
            const data = await connections();
            if (!modal.isConnected) return;
            if (ready(data, 'microsoft', 'calendar')) select.add(new Option('Microsoft Teams', 'teams'));
            if (ready(data, 'google', 'calendar')) select.add(new Option('Google Meet', 'meet'));
            select.disabled = false;
            if (hint) hint.textContent = select.options.length > 1
                ? 'Creating an online meeting also sends a calendar invitation.'
                : 'No online meeting account is connected. Use a location or phone call.';
        } catch (_) {
            if (hint) hint.textContent = 'Meeting options could not be checked. You can still use a location or phone call.';
        }
    }

    const templates = [
        ['details', 'Candidate details request'], ['availability', 'Interview availability'],
        ['followup', 'Follow-up'], ['shortlist', 'Shortlist update'],
        ['application', 'Application update'], ['custom', 'Custom message']
    ];
    function message(kind, value, options = {}) {
        const role = value.position || 'the opportunity';
        const where = value.location ? ' in ' + value.location : '';
        const greeting = 'Hi ' + (value.candidateName || 'there') + ',\n\n';
        const signature = '\n\nBest regards,\n' + value.recruiter + '\n' + value.company;
        let subject = role + ' - ' + value.company;
        let body = '';
        if (kind === 'details') {
            const questions = ['Current location', 'Relevant years of experience', 'Educational qualifications and relevant certifications', 'Availability / notice period', 'Expected salary'];
            if (/network|security/i.test(role)) questions.splice(2, 0, 'Relevant network / information-security experience');
            if (/\b(lead|manager|head)\b/i.test(role)) questions.splice(2, 0, 'Team leadership experience');
            if (value.onsite) questions.push('Willingness to work onsite' + where);
            if (value.shifts) questions.push('Willingness to work rotating shifts');
            if (options.authorization) questions.push('Work authorization / residency status for the role location');
            if (options.currentSalary) questions.push('Current salary, if you wish to disclose it');
            const introduction = /^recruitment team$/i.test(value.recruiter)
                ? 'Our recruitment team at ' + value.company + ' is contacting you.'
                : 'I am ' + value.recruiter + ' from ' + value.company + '.';
            body = introduction + '\n\nWe have reviewed your profile for our ' + role + ' position' + where + '.\n\nPlease share the following details:\n\n'
                + questions.map(item => '- ' + item).join('\n')
                + (value.salary ? '\n\nThe salary range stated for this role is ' + value.salary + '.' : '')
                + '\n\nIf you are interested, please reply with your updated CV and the details above. We will review your response and contact you about the next step.';
            subject = 'Opportunity: ' + role + where + ' | ' + value.company;
        } else if (kind === 'availability') {
            subject = 'Interview availability: ' + role + ' | ' + value.company;
            body = 'We would like to arrange a conversation about the ' + role + ' opportunity' + where + '. Please share two or three suitable times, your time zone and your preferred contact number.\n\nWe will confirm the interview details separately.';
        } else if (kind === 'followup') {
            subject = 'Following up: ' + role + ' | ' + value.company;
            body = 'I am following up regarding the ' + role + ' opportunity' + where + '. Please let us know whether you are still interested and share any updates to your availability or CV.\n\nThank you for your time.';
        } else if (kind === 'shortlist') {
            subject = 'Application update: ' + role + ' | ' + value.company;
            body = 'We are pleased to let you know that your profile has been shortlisted for further review for the ' + role + ' position' + where + '.\n\nPlease confirm your interest and availability. Our recruitment team will share the next steps separately.';
        } else if (kind === 'application') {
            subject = 'Your application: ' + role + ' | ' + value.company;
            body = 'Thank you for your interest in the ' + role + ' opportunity' + where + '. Your application is under review. We will contact you when there is an update.\n\nPlease reply with any changes to your contact details or availability.';
        }
        return {subject, body: greeting + body + signature};
    }

    function open(input) {
        if (document.querySelector('[data-email-composer]')) return;
        const ctx = context(input);
        const identity = JSON.stringify([window.currentUser?.id, window.currentUser?.company]);
        const key = JSON.stringify([identity, ctx.jobApplicationId || ctx.searchResultId || ctx.candidateEmail,
            ctx.position, ctx.query]);
        const saved = drafts.get(key);
        const modal = document.createElement('div');
        modal.dataset.emailComposer = '';
        modal.className = 'outreach-overlay';
        modal.innerHTML = `<form class="outreach-dialog" aria-label="Compose candidate email">
            <header class="outreach-header"><div><h2>Compose email</h2><p>${esc(ctx.candidateName)}</p></div><button type="button" data-close aria-label="Close email composer" title="Close"><i class="fas fa-times" aria-hidden="true"></i></button></header>
            <div class="outreach-body">
                <div class="outreach-fields">
                    <label>To<input name="recipient" type="email" maxlength="320" required></label>
                    <label>Send from<select name="transport" required disabled><option value="">Checking connected accounts...</option></select></label>
                    <label>Job title<input name="position" maxlength="500" required></label>
                    <label>Company<input name="company" maxlength="255" required></label>
                    <label>Work location<input name="location" maxlength="200" placeholder="Optional"></label>
                    <label>Recruiter name<input name="recruiter" maxlength="200" required></label>
                </div>
                <div class="outreach-template-picker"><label>Template<select name="template">${templates.map(([id, label]) => `<option value="${id}">${label}</option>`).join('')}</select></label><button type="button" data-manage-templates aria-label="Manage saved email templates" title="Manage saved email templates"><i class="fas fa-folder-open" aria-hidden="true"></i></button></div>
                <div class="outreach-template-options"><label><input type="checkbox" name="authorization"> Ask about work authorization</label><label><input type="checkbox" name="currentSalary"> Ask about current salary</label></div>
                <div class="outreach-replace" hidden><span>Replace your edited message with the selected template?</span><button type="button" data-keep>Keep editing</button><button type="button" data-replace>Use template</button></div>
                <div class="outreach-edit"><label>Subject<input name="subject" maxlength="998" required></label><label>Message<textarea name="message" maxlength="32768" rows="14" required></textarea></label></div>
                <div class="outreach-preview" hidden><button type="button" data-edit><i class="fas fa-pen" aria-hidden="true"></i> Edit message</button><iframe title="Branded email preview" sandbox="" referrerpolicy="no-referrer"></iframe></div>
                <p class="outreach-feedback" role="status" aria-live="polite"></p>
            </div>
            <footer class="outreach-footer"><button type="button" data-close>Cancel</button><button type="button" data-preview><i class="fas fa-eye" aria-hidden="true"></i> Preview email</button><button type="submit" data-send disabled><i class="fas fa-paper-plane" aria-hidden="true"></i> Send email</button></footer>
        </form>`;
        document.body.appendChild(modal);
        const form = modal.querySelector('form');
        const field = name => form.elements.namedItem(name);
        const feedback = modal.querySelector('.outreach-feedback');
        const send = modal.querySelector('[data-send]');
        const previewButton = modal.querySelector('[data-preview]');
        let edited = false, reviewed = '', busy = false, uncertain = !!saved?.uncertain, accepted = saved?.accepted || '';
        let lastTemplate = saved?.template || 'details';
        const defaults = {recipient: ctx.candidateEmail || '', position: ctx.position, company: ctx.company,
            location: ctx.location, recruiter: ctx.recruiter, template: lastTemplate};
        for (const [name, value] of Object.entries(defaults)) field(name).value = saved?.[name] ?? value;
        field('authorization').checked = !!saved?.authorization;
        field('currentSalary').checked = !!saved?.currentSalary;
        function values() {
            return {...ctx, position: field('position').value.trim(), company: field('company').value.trim(),
                location: field('location').value.trim(), recruiter: field('recruiter').value.trim()};
        }
        function payload() {
            return {candidate_name: ctx.candidateName, candidate_email: field('recipient').value.trim(),
                position: field('position').value.trim(), company: field('company').value.trim(),
                message_subject: field('subject').value, message_body: field('message').value,
                search_result_id: ctx.searchResultId || null,
                job_application_id: ctx.jobApplicationId || null,
                company_id: ctx.companyId || null,
                kind: 'custom', prefer: field('transport').value || 'auto'};
        }
        function state() { return JSON.stringify(payload()); }
        function syncSend() { send.disabled = busy || uncertain || !field('transport').value || reviewed !== state() || accepted === state(); }
        function editView() {
            modal.querySelector('.outreach-edit').hidden = false;
            modal.querySelector('.outreach-preview').hidden = true;
            reviewed = ''; syncSend();
        }
        function fillTemplate() {
            const draft = message(field('template').value, values(), {authorization: field('authorization').checked, currentSalary: field('currentSalary').checked});
            field('subject').value = draft.subject; field('message').value = draft.body;
            edited = false; lastTemplate = field('template').value; editView();
        }
        if (saved) {field('subject').value = saved.subject; field('message').value = saved.message; edited = true;}
        else fillTemplate();
        modal.querySelector('[data-manage-templates]').addEventListener('click', () => {
            const v=values();
            let subject=field('subject').value, messageText=field('message').value;
            const substitutions=[[ctx.candidateName,'candidate_name'],[v.position,'position'],[v.company,'company'],[v.recruiter,'recruiter_name'],[v.location,'job_location']].filter(([value])=>value).sort((a,b)=>b[0].length-a[0].length);
            for(const [value,key] of substitutions){subject=subject.split(value).join('{{ '+key+' }}');messageText=messageText.split(value).join('{{ '+key+' }}');}
            manageTemplates(modal,{subject,message:messageText},v,draft=>{field('subject').value=draft.subject;field('message').value=draft.message;edited=true;editView();});
        });
        function remember() {
            if (drafts.size >= 10 && !drafts.has(key)) drafts.delete(drafts.keys().next().value);
            const value = {};
            for (const name of ['recipient','position','company','location','recruiter','template','subject','message']) value[name] = field(name).value;
            drafts.set(key, {...value, authorization: field('authorization').checked, currentSalary: field('currentSalary').checked, uncertain, accepted});
        }
        const close = () => { if (busy || modal.querySelector('[data-template-manager][data-submitting="true"]')) return; remember(); modal.remove(); };
        modal.querySelectorAll('[data-close]').forEach(button => button.addEventListener('click', close));
        modal.addEventListener('keydown', event => {if (event.key === 'Escape' && busy) event.stopImmediatePropagation();});
        window.bindScheduleDialog(modal, 'Compose candidate email');
        modal.addEventListener('keydown', event => {if (event.key === 'Escape' && !busy) remember();});
        modal.querySelector('[data-edit]').addEventListener('click', editView);
        field('template').addEventListener('change', () => {
            reviewed = ''; syncSend();
            modal.querySelector('.outreach-template-options').hidden = field('template').value !== 'details';
            if (edited) modal.querySelector('.outreach-replace').hidden = false;
            else fillTemplate();
        });
        modal.querySelector('[data-keep]').addEventListener('click', () => {field('template').value = lastTemplate; modal.querySelector('.outreach-replace').hidden = true;});
        modal.querySelector('[data-replace]').addEventListener('click', () => {modal.querySelector('.outreach-replace').hidden = true; fillTemplate();});
        form.addEventListener('input', event => {
            if (['subject','message'].includes(event.target.name)) edited = true;
            if (!edited && ['position','company','location','recruiter','authorization','currentSalary'].includes(event.target.name)) fillTemplate();
            reviewed = ''; syncSend();
        });
        field('transport').addEventListener('change', () => {reviewed = ''; syncSend();});
        async function preview() {
            if (busy || !form.reportValidity()) return;
            busy = true; previewButton.disabled = true; syncSend();
            const body = payload(), fingerprint = JSON.stringify(body);
            feedback.textContent = 'Preparing your email preview...';
            try {
                const response = await fetch('/api/preview-candidate-email', {method:'POST',headers:{'Content-Type':'application/json'},body:fingerprint});
                const data = await response.json();
                if (!response.ok || data.success !== true) throw new Error(data.detail || 'Email preview is unavailable.');
                if (!modal.isConnected || fingerprint !== state()) return;
                modal.querySelector('iframe').srcdoc = data.body_html;
                modal.querySelector('.outreach-edit').hidden = true;
                modal.querySelector('.outreach-preview').hidden = false;
                reviewed = fingerprint;
                feedback.textContent = uncertain ? 'A previous send could not be confirmed. Check Sent Items before sending another message.' : 'Review the recipient and message before sending.';
            } catch (error) { feedback.textContent = humanError(error, 'Email preview is temporarily unavailable. Please try again.'); }
            finally {busy = false; previewButton.disabled = false; syncSend();}
        }
        previewButton.addEventListener('click', preview);
        form.addEventListener('submit', async event => {
            event.preventDefault();
            if (modal.querySelector('[data-template-manager]')) return;
            if (busy || send.disabled || reviewed !== state() || !form.reportValidity()) return;
            busy = true; previewButton.disabled = true; syncSend();
            const fingerprint = state();
            feedback.textContent = 'Sending your email...';
            try {
                const response = await fetch('/api/send-candidate-email', {method:'POST',headers:{'Content-Type':'application/json'},body:fingerprint});
                const data = await response.json();
                if (response.ok && data.success === true) {
                    accepted = fingerprint; feedback.textContent = 'Email accepted for sending.' + (data.audit_warning ? ' ' + data.audit_warning : '');
                    window.showNotification('Email accepted for sending.', 'success');
                } else {
                    uncertain = !!data.delivery_unknown;
                    feedback.textContent = data.error || data.detail || 'Email was not sent. Review the account and message before trying again.';
                }
            } catch (_) {uncertain = true; feedback.textContent = 'Sending could not be confirmed. Check Sent Items before trying again.';}
            finally {busy = false; previewButton.disabled = false; remember(); syncSend();}
        });
        connections().then(data => {
            if (!modal.isConnected) return;
            const select = field('transport'); select.replaceChildren();
            if (ready(data, 'microsoft', 'email')) select.add(new Option(data.microsoft.account_email + ' (Microsoft)', 'microsoft'));
            if (ready(data, 'google', 'email')) select.add(new Option(data.google.account_email + ' (Google)', 'gmail'));
            if (data.smtp?.configured) select.add(new Option('Company email (SMTP)', 'smtp'));
            if (!select.options.length) {select.add(new Option('No sending account connected', '')); feedback.textContent = 'Connect an email account in Settings before sending.';}
            else select.disabled = false;
            syncSend();
        }).catch(() => {field('transport').replaceChildren(new Option('Account check unavailable', '')); feedback.textContent = 'Connected accounts could not be checked. Try reopening this message.';});
    }

    function manageTemplates(modal, initial, ctx, apply) {
        if(modal.querySelector('[data-template-manager]'))return;
        const body=modal.querySelector('.outreach-body'),footer=modal.querySelector('.outreach-footer');
        body.hidden=true;footer.hidden=true;
        const panel=document.createElement('section');panel.className='outreach-template-editor';panel.dataset.templateManager='';
        panel.innerHTML=`<div class="outreach-body"><h3 class="text-lg font-semibold mb-4">Saved email templates</h3>
            <label>Choose template<select data-choice><option value="">New template</option></select></label>
            <label>Name<input data-name maxlength="200" required></label>
            <label>Subject<input data-subject maxlength="998" required></label>
            <label>Message<textarea data-message rows="12" maxlength="32768" required></textarea></label>
            <label>Insert field<select data-insert><option value="">Select field</option><option value="candidate_name">Candidate name</option><option value="position">Job title</option><option value="company">Company</option><option value="recruiter_name">Recruiter name</option><option value="job_location">Work location</option></select></label>
            <div data-delete-confirm hidden><p>Delete this saved template? Existing emails and candidate records will remain unchanged.</p><button type="button" data-keep-template>Keep template</button><button type="button" data-confirm-delete>Delete template</button></div>
            <p data-feedback role="status" aria-live="polite"></p></div>
            <div class="outreach-footer"><button type="button" data-back>Back to message</button><button type="button" data-discard hidden>Discard changes</button><button type="button" data-use disabled>Use template</button><button type="button" data-delete disabled aria-label="Delete saved template" title="Delete saved template"><i class="fas fa-trash" aria-hidden="true"></i></button><button type="button" data-save>Save template</button></div>`;
        body.after(panel);
        const choice=panel.querySelector('[data-choice]'),name=panel.querySelector('[data-name]'),subject=panel.querySelector('[data-subject]'),messageField=panel.querySelector('[data-message]'),feedback=panel.querySelector('[data-feedback]');
        const save=panel.querySelector('[data-save]'),use=panel.querySelector('[data-use]'),remove=panel.querySelector('[data-delete]');
        let records=[],current=null,dirty=false,busy=false,loadVersion=0;
        function setBusy(value){
            busy=value;
            if(value)panel.dataset.submitting='true';else delete panel.dataset.submitting;
            panel.setAttribute('aria-busy',String(value));
            panel.querySelectorAll('input,select,textarea,button').forEach(control=>{control.disabled=value;});
            modal.querySelector('.outreach-header [data-close]').disabled=value;
            if(!value){use.disabled=!current||dirty;remove.disabled=!current;}
        }
        const back=()=>{if(busy)return;panel.remove();body.hidden=false;footer.hidden=false;modal.querySelector('[data-manage-templates]').focus();};
        function populate(record){current=record;name.value=record?.name||'';subject.value=record?.subject??initial.subject;messageField.value=record?.message??initial.message;dirty=false;use.disabled=remove.disabled=!current;}
        async function refresh(selected,preserveDraft=false){
            const version=++loadVersion;
            const response=await fetch('/api/outreach-templates');const data=await response.json();
            if(!response.ok)throw new Error(data.detail||'Templates could not be loaded.');
            if(!panel.isConnected||version!==loadVersion)return;
            records=data.templates||[];choice.replaceChildren(new Option('New template',''));
            for(const record of records)choice.add(new Option(record.name,String(record.id)));
            choice.value=selected?String(selected):'';
            if(!preserveDraft||!dirty)populate(records.find(row=>String(row.id)===choice.value));
        }
        choice.addEventListener('change',()=>{
            if(dirty){choice.value=current?String(current.id):'';feedback.textContent='Save your changes before choosing another template.';return;}
            populate(records.find(row=>String(row.id)===choice.value));
        });
        for(const field of [name,subject,messageField])field.addEventListener('input',()=>{dirty=true;use.disabled=true;});
        panel.querySelector('[data-insert]').addEventListener('change',event=>{
            if(!event.target.value)return;
            messageField.setRangeText('{{ '+event.target.value+' }}',messageField.selectionStart,messageField.selectionEnd,'end');
            event.target.value='';dirty=true;use.disabled=true;messageField.focus();
        });
        panel.querySelector('[data-back]').addEventListener('click',()=>{
            if(dirty){feedback.textContent='Keep editing, save your template, or discard the unsaved changes.';panel.querySelector('[data-discard]').hidden=false;return;}
            back();
        });
        panel.querySelector('[data-discard]').addEventListener('click',back);
        save.addEventListener('click',async()=>{
            if(busy||![name,subject,messageField].every(field=>field.reportValidity()))return;
            setBusy(true);
            try{
                const payload={name:name.value,subject:subject.value,message:messageField.value,...(current?{version:current.version}:{})};
                const response=await fetch('/api/outreach-templates'+(current?'/'+current.id:''),{method:current?'PUT':'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
                const data=await response.json();if(!response.ok||!data.success)throw new Error(data.detail||'Template was not saved.');
                await refresh(data.template.id);feedback.textContent='Template saved.';
            }catch(error){feedback.textContent=humanError(error,'The template save could not be confirmed. Reopen saved templates before trying again.');feedback.tabIndex=-1;feedback.focus();}finally{setBusy(false);}
        });
        remove.addEventListener('click',()=>{panel.querySelector('[data-delete-confirm]').hidden=false;});
        panel.querySelector('[data-keep-template]').addEventListener('click',()=>{panel.querySelector('[data-delete-confirm]').hidden=true;});
        panel.querySelector('[data-confirm-delete]').addEventListener('click',async()=>{
            if(busy||!current)return;setBusy(true);
            try{
                const response=await fetch('/api/outreach-templates/'+current.id,{method:'DELETE',headers:{'Content-Type':'application/json'},body:JSON.stringify({version:current.version})});
                const data=await response.json();if(!response.ok||!data.success)throw new Error(data.detail||'Template was not deleted.');
                await refresh();panel.querySelector('[data-delete-confirm]').hidden=true;feedback.textContent='Template deleted.';
            }catch(error){feedback.textContent=humanError(error,'The template deletion could not be confirmed. Reopen saved templates to check.');feedback.tabIndex=-1;feedback.focus();}finally{setBusy(false);}
        });
        use.addEventListener('click',async()=>{
            if(busy||!current||dirty)return;setBusy(true);
            try{
                const response=await fetch('/api/outreach-templates/'+current.id+'/draft',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({candidate_name:ctx.candidateName,position:ctx.position,company:ctx.company,recruiter_name:ctx.recruiter,job_location:ctx.location})});
                const data=await response.json();if(!response.ok||!data.success)throw new Error(data.detail||'Template could not be applied.');
                apply(data);setBusy(false);back();
            }catch(error){feedback.textContent=humanError(error,'The template could not be loaded. Please try again.');feedback.tabIndex=-1;feedback.focus();}finally{setBusy(false);}
        });
        populate();refresh(undefined,true).catch(error=>{if(panel.isConnected)feedback.textContent=humanError(error,'Saved templates are temporarily unavailable. Please reopen this view.');});choice.focus();
    }
    window.RecruiterOutreach = {context, configureSchedule, open, message, ready};
}());
