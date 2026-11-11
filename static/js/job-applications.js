(function () {
    'use strict';
    const esc = value => (window.escapeAttr || window.escapeHtml)(String(value ?? ''));
    const statuses = ['received', 'reviewing', 'shortlisted', 'rejected', 'hired', 'withdrawn'];

    async function request(url, options = {}) {
        let response;
        try { response = await fetch(url, {credentials: 'same-origin', ...options}); }
        catch (_) { throw new Error('The application workspace could not be reached. Please try again.'); }
        const data = response.headers.get('content-type')?.includes('application/json')
            ? await response.json().catch(() => ({})) : {};
        if (!response.ok || data.success === false) {
            throw new Error(typeof data.detail === 'string' ? data.detail : 'The request could not be completed.');
        }
        return data;
    }

    function mount(root) {
        let disposed = false, sequence = 0, pages = [], selectedPage = null, selectedOffset = 0, noticeTimer = null;
        const isSuperAdmin = window.currentUser?.user_type === 'super_admin';
        let selectedCompanyId = window.currentUser?.company?.company_id || window.currentUser?.company?.id || '';
        root.classList.add('recruiter-workspace', 'job-applications-view');
        root.innerHTML = '<header class="workspace-header"><div><h2>Job Applications</h2><p class="workspace-muted">Create a role page and review applications in one place.</p></div><button type="button" data-create class="workspace-button is-primary"><i class="fas fa-plus" aria-hidden="true"></i>Create job page</button></header><div data-notice role="status" aria-live="polite"></div><div data-content class="workspace-table-region"></div>';
        const content = root.querySelector('[data-content]');
        const alive = id => !disposed && root.isConnected && id === sequence;
        const pageAddress = url => !isSuperAdmin || !selectedCompanyId || url === '/api/companies' ? url
            : url + (url.includes('?') ? '&' : '?') + 'company_id=' + encodeURIComponent(selectedCompanyId);
        const scopedRequest = (url, options) => request(pageAddress(url), options);
        const createButton = root.querySelector('[data-create]');

        if (isSuperAdmin) {
            const label = document.createElement('label');
            label.className = 'job-company-picker';
            label.innerHTML = '<span>Company workspace</span>';
            const picker = document.createElement('select');
            picker.setAttribute('aria-label', 'Company workspace for job applications');
            picker.append(new Option('Loading companies…', ''));
            label.append(picker);
            root.querySelector('.workspace-header').insertBefore(label, createButton);
            createButton.disabled = true;
            picker.addEventListener('change', () => {
                selectedCompanyId = picker.value;
                createButton.disabled = !selectedCompanyId;
                selectedPage = null;
                pages = [];
                if (selectedCompanyId) loadPages();
                else showCompanyPrompt();
            });
            loadCompanies(picker);
        }

        async function loadCompanies(picker) {
            try {
                const data = await request('/api/companies');
                if (disposed || !root.isConnected) return;
                if (!Array.isArray(data.companies)) throw new Error('The company list is temporarily unavailable.');
                picker.replaceChildren(new Option('Choose a company', ''));
                data.companies.forEach(company => picker.add(new Option(
                    company.company_name + (company.is_active ? '' : ' (inactive)'), String(company.id))));
                const available = new Set(data.companies.map(company => String(company.id)));
                if (!available.has(String(selectedCompanyId))) selectedCompanyId = data.companies.length === 1 ? String(data.companies[0].id) : '';
                picker.value = String(selectedCompanyId || '');
                createButton.disabled = !selectedCompanyId;
                if (selectedCompanyId) loadPages();
                else showCompanyPrompt();
            } catch (error) {
                if (!disposed) {
                    picker.replaceChildren(new Option('Companies unavailable', ''));
                    content.innerHTML = '<div class="workspace-empty is-error" role="alert"><h3>Company list unavailable</h3><p>' + esc(error.message) + '</p></div>';
                }
            }
        }

        function showCompanyPrompt() {
            content.innerHTML = '<div class="workspace-empty"><span class="workspace-empty-icon"><i class="fas fa-building" aria-hidden="true"></i></span><h3>Choose a company</h3><p>Select a company workspace above to manage its job pages and applicants.</p></div>';
        }

        function notify(message, kind = 'success') {
            const notice = root.querySelector('[data-notice]');
            window.clearTimeout(noticeTimer);
            notice.className = 'job-application-notice ' + (kind === 'error' ? 'is-error' : 'is-success');
            notice.textContent = message;
            noticeTimer = window.setTimeout(() => { if (notice.isConnected) { notice.className = 'job-application-notice'; notice.textContent = ''; } }, 5000);
        }

        async function loadPages() {
            const id = ++sequence;
            content.setAttribute('aria-busy', 'true');
            content.innerHTML = '<div class="workspace-loading" role="status"><i class="fas fa-circle-notch fa-spin" aria-hidden="true"></i>Loading job pages...</div>';
            try {
                const data = await scopedRequest('/api/job-application-pages');
                if (!alive(id)) return;
                if (!Array.isArray(data.pages)) throw new Error('Job pages are temporarily unavailable.');
                pages = data.pages;
                renderPages();
            } catch (error) {
                if (!alive(id)) return;
                content.innerHTML = '<div class="workspace-empty is-error" role="alert"><h3>Job pages unavailable</h3><p>' + esc(error.message) + '</p><button type="button" data-retry class="workspace-button"><i class="fas fa-redo" aria-hidden="true"></i>Retry</button></div>';
                content.querySelector('[data-retry]').onclick = loadPages;
            } finally { if (alive(id)) content.setAttribute('aria-busy', 'false'); }
        }

        function renderPages() {
            selectedPage = null;
            if (!pages.length) {
                content.innerHTML = '<div class="workspace-empty"><span class="workspace-empty-icon"><i class="fas fa-briefcase" aria-hidden="true"></i></span><h3>No job pages yet</h3><p>Create a role page and share its private link with candidates.</p><button type="button" data-empty-create class="workspace-button is-primary"><i class="fas fa-plus" aria-hidden="true"></i>Create job page</button></div>';
                content.querySelector('[data-empty-create]').onclick = () => pageForm();
                return;
            }
            content.innerHTML = '<table class="workspace-table job-pages-table"><thead><tr><th scope="col">Role</th><th scope="col">Status</th><th scope="col">Applications</th><th scope="col">Actions</th></tr></thead><tbody>' +
                pages.map(page => '<tr><td data-label="Role"><strong>' + esc(page.title) + '</strong><div class="workspace-muted">' + esc([page.location, page.employment_type].filter(Boolean).join(' | ') || 'Location not specified') + '</div></td>' +
                    '<td data-label="Status"><span class="workspace-status ' + (page.status === 'published' ? 'is-active' : '') + '"><span aria-hidden="true"></span>' + esc(page.status) + '</span>' +
                    (Number(page.indexing_pending) ? '<div class="workspace-muted">' + Number(page.indexing_pending).toLocaleString() + ' CVs awaiting index</div>' : '') + '</td>' +
                    '<td data-label="Applications"><button type="button" data-applicants="' + Number(page.id) + '" class="job-page-count">' + Number(page.applicant_count || 0).toLocaleString() + '</button></td>' +
                    '<td data-label="Actions" class="workspace-row-actions"><button type="button" data-edit="' + Number(page.id) + '" class="workspace-icon-button" aria-label="Edit ' + esc(page.title) + '" title="Edit job page"><i class="fas fa-pen" aria-hidden="true"></i></button>' +
                    (page.status === 'published' ? '<button type="button" data-copy="' + Number(page.id) + '" class="workspace-icon-button" aria-label="Copy application link" title="Copy application link"><i class="fas fa-link" aria-hidden="true"></i></button><a class="workspace-icon-button" href="' + esc(location.origin + page.public_url) + '" target="_blank" rel="noopener noreferrer" aria-label="Preview candidate page" title="Preview candidate page"><i class="fas fa-external-link-alt" aria-hidden="true"></i></a>' : '') +
                    '<button type="button" data-status="' + Number(page.id) + '" class="workspace-icon-button" aria-label="Change page status" title="' + (page.status === 'published' ? 'Pause applications' : page.status === 'closed' ? 'Reopen as draft' : 'Publish page') + '"><i class="fas ' + (page.status === 'published' ? 'fa-pause' : page.status === 'closed' ? 'fa-rotate-left' : 'fa-globe') + '" aria-hidden="true"></i></button>' +
                    (page.status !== 'published' && !Number(page.applicant_count) ? '<button type="button" data-delete-page="' + Number(page.id) + '" class="workspace-icon-button is-danger" aria-label="Delete empty ' + esc(page.title) + ' page" title="Delete empty page"><i class="fas fa-trash" aria-hidden="true"></i></button>' : '') + '</td></tr>').join('') + '</tbody></table>';
            content.querySelectorAll('[data-edit]').forEach(button => button.onclick = () => pageForm(pages.find(page => Number(page.id) === Number(button.dataset.edit))));
            content.querySelectorAll('[data-applicants]').forEach(button => button.onclick = () => loadApplications(pages.find(page => Number(page.id) === Number(button.dataset.applicants))));
            content.querySelectorAll('[data-status]').forEach(button => button.onclick = () => changePageStatus(pages.find(page => Number(page.id) === Number(button.dataset.status))));
            content.querySelectorAll('[data-copy]').forEach(button => button.onclick = () => copyLink(pages.find(page => Number(page.id) === Number(button.dataset.copy))));
            content.querySelectorAll('[data-delete-page]').forEach(button => button.onclick = () => deletePage(pages.find(page => Number(page.id) === Number(button.dataset.deletePage))));
            content.querySelectorAll('[data-status]').forEach(button => {
                const page = pages.find(item => Number(item.id) === Number(button.dataset.status));
                if (!page || page.status === 'closed') return;
                const close = document.createElement('button'); close.type = 'button'; close.className = 'workspace-icon-button';
                close.title = 'Close applications and retain applicant records'; close.setAttribute('aria-label', close.title);
                close.innerHTML = '<i class="fas fa-archive" aria-hidden="true"></i>';
                close.onclick = async () => {
                    if (!window.confirm('Close this job page? Existing applications and CVs will be retained.')) return;
                    await changePageStatus(page, 'closed');
                };
                button.parentElement.append(close);
            });
        }

        function pageForm(page = null) {
            const editing = !!page;
            const modal = document.createElement('div');
            modal.className = 'workspace-overlay'; modal.dataset.jobPageDialog = 'true';
            modal.innerHTML = '<section class="workspace-dialog job-page-dialog"><header><h3>' + (editing ? 'Edit job page' : 'Create job page') + '</h3><button type="button" data-close class="workspace-icon-button" aria-label="Close dialog" title="Close dialog"><i class="fas fa-times" aria-hidden="true"></i></button></header>' +
                '<form><div class="workspace-dialog-body job-page-form"><label>Job title<input name="title" maxlength="180" required value="' + esc(page?.title || '') + '"></label>' +
                '<div class="job-page-form-grid"><label>Location<input name="location" maxlength="180" placeholder="e.g. Abu Dhabi or Remote" value="' + esc(page?.location || '') + '"></label><label>Employment type<input name="employment_type" maxlength="80" value="' + esc(page?.employment_type || 'Full-time') + '"></label></div>' +
                '<label>Role description<textarea name="description" rows="8" minlength="20" maxlength="12000" required placeholder="Describe the role, responsibilities and essential qualifications.">' + esc(page?.description || '') + '</textarea></label>' +
                '<label>Optional application questions <span class="workspace-muted">One question per line, up to six</span><textarea name="questions" rows="4" maxlength="1100" placeholder="What is your notice period?\nWhat salary range are you seeking?">' + esc((page?.custom_questions || []).join('\n')) + '</textarea></label>' +
                '<p class="workspace-muted">Applicants provide their contact details and CV. Applications are not automatically scored.</p><p data-error role="alert" class="workspace-inline-error hidden"></p></div>' +
                '<footer><button type="button" data-close class="workspace-button">Cancel</button><button type="submit" class="workspace-button is-primary"><i class="fas fa-check" aria-hidden="true"></i>' + (editing ? 'Save changes' : 'Save draft') + '</button></footer></form></section>';
            document.body.append(modal);
            window.bindScheduleDialog?.(modal, editing ? 'Edit job page' : 'Create job page');
            modal.querySelectorAll('[data-close]').forEach(button => button.onclick = () => modal.remove());
            const form = modal.querySelector('form');
            form.addEventListener('submit', async event => {
                event.preventDefault();
                if (!form.reportValidity()) return;
                const submit = form.querySelector('[type="submit"]');
                submit.disabled = true; submit.innerHTML = '<i class="fas fa-circle-notch fa-spin" aria-hidden="true"></i>Saving...';
                const questions = form.elements.questions.value.split(/\r?\n/).map(value => value.trim()).filter(Boolean);
                const payload = {title:form.elements.title.value, location:form.elements.location.value,
                    employment_type:form.elements.employment_type.value, description:form.elements.description.value,
                    custom_questions:questions, ...(isSuperAdmin ? {company_id:Number(selectedCompanyId)} : {}),
                    ...(editing ? {version:page.version} : {status:'draft'})};
                try {
                    await scopedRequest(editing ? '/api/job-application-pages/' + Number(page.id) : '/api/job-application-pages',
                        {method:editing ? 'PUT' : 'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
                    modal.remove(); notify(editing ? 'Job page updated.' : 'Draft saved. Publish it when it is ready.'); await loadPages();
                } catch (error) {
                    const message = modal.querySelector('[data-error]'); message.textContent = error.message; message.classList.remove('hidden');
                    submit.disabled = false; submit.innerHTML = '<i class="fas fa-check" aria-hidden="true"></i>' + (editing ? 'Save changes' : 'Save draft');
                }
            });
        }

        async function changePageStatus(page, explicitStatus) {
            if (!page) return;
            const status = explicitStatus || (page.status === 'published' ? 'paused' : page.status === 'closed' ? 'draft' : 'published');
            try {
                const data = await scopedRequest('/api/job-application-pages/' + Number(page.id) + '/status',
                    {method:'PATCH', headers:{'Content-Type':'application/json'}, body:JSON.stringify({status,version:page.version})});
                notify(status === 'published' ? 'Application page published.' : status === 'paused' ? 'Applications paused; existing records are retained.' : 'Page reopened as a draft.');
                await loadPages();
                if (data.page?.public_url) await copyLink(pages.find(item => Number(item.id) === Number(page.id)), false);
            } catch (error) { notify(error.message, 'error'); }
        }

        async function deletePage(page) {
            if (!page || !window.confirm('Delete this empty job page? A page with candidate applications cannot be deleted.')) return;
            try {
                await scopedRequest('/api/job-application-pages/' + Number(page.id), {method:'DELETE',
                    headers:{'Content-Type':'application/json'}, body:JSON.stringify({version:page.version})});
                notify('Empty job page deleted. The audit record is retained.'); await loadPages();
            } catch (error) { notify(error.message, 'error'); }
        }

        async function copyLink(page, showNotice = true) {
            if (!page?.public_url) return;
            const link = location.origin + page.public_url;
            try { await navigator.clipboard.writeText(link); if (showNotice) notify('Application link copied.'); }
            catch (_) {
                const input = document.createElement('input'); input.value = link; input.setAttribute('readonly','');
                input.className = 'job-copy-fallback'; document.body.append(input); input.select();
                const copied = document.execCommand('copy'); input.remove();
                if (showNotice) notify(copied ? 'Application link copied.' : 'Open the page preview and copy its address.', copied ? 'success' : 'error');
            }
        }

        async function loadApplications(page, offset = 0) {
            if (!page) return;
            selectedPage = page;
            const pageOffset = Math.max(0, Number(offset) || 0);
            const id = ++sequence;
            content.setAttribute('aria-busy','true');
            content.innerHTML = '<div class="workspace-loading" role="status"><i class="fas fa-circle-notch fa-spin" aria-hidden="true"></i>Loading applications...</div>';
            try {
                const data = await scopedRequest('/api/job-application-pages/' + Number(page.id) + '/applications?limit=50&offset=' + pageOffset);
                if (!alive(id) || selectedPage !== page) return;
                renderApplications(page, data.applications, data.total, pageOffset);
            } catch (error) {
                if (alive(id)) content.innerHTML = '<div class="workspace-empty is-error" role="alert"><h3>Applications unavailable</h3><p>' + esc(error.message) + '</p><button type="button" data-back class="workspace-button">Back to job pages</button></div>';
            } finally { if (alive(id)) content.setAttribute('aria-busy','false'); }
        }

        function renderApplications(page, applications, total, offset) {
            selectedOffset = offset;
            content.innerHTML = '<div class="job-applications-heading"><button type="button" data-back class="workspace-button"><i class="fas fa-arrow-left" aria-hidden="true"></i>Job pages</button><div><h3>' + esc(page.title) + '</h3><p class="workspace-muted">' + Number(total).toLocaleString() + ' applications</p></div><a class="workspace-button" href="' + esc(pageAddress('/api/job-application-pages/' + Number(page.id) + '/applications.csv')) + '"><i class="fas fa-download" aria-hidden="true"></i>Export CSV</a></div>' +
                (applications.length ? '<table class="workspace-table job-candidates-table"><thead><tr><th scope="col">Candidate</th><th scope="col">Experience</th><th scope="col">CV</th><th scope="col">Interview</th><th scope="col">Status</th><th scope="col">Received</th><th scope="col">Actions</th></tr></thead><tbody>' + applications.map(row => {
                    const answerRows = Object.entries(row.answers || {}).map(([key, answer]) => '<div><strong>Question ' + (Number(key) + 1) + ':</strong> ' + esc(answer) + '</div>').join('');
                    const received = row.created_at ? new Date(row.created_at).toLocaleDateString() : 'Unavailable';
                    return '<tr><td data-label="Candidate"><strong>' + esc(row.candidate_name) + '</strong><div><a href="mailto:' + esc(row.normalized_email) + '">' + esc(row.normalized_email) + '</a></div>' +
                        (row.phone ? '<div class="workspace-muted">' + esc(row.phone) + '</div>' : '') + (row.location ? '<div class="workspace-muted">' + esc(row.location) + '</div>' : '') +
                        (row.linkedin_url ? '<a href="' + esc(row.linkedin_url) + '" target="_blank" rel="noopener noreferrer">LinkedIn</a>' : '') + (answerRows ? '<details class="job-answers"><summary>Application answers</summary>' + answerRows + '</details>' : '') + '</td>' +
                        '<td data-label="Experience">' + (row.years_experience == null ? 'Not provided' : esc(row.years_experience) + ' years') + '</td>' +
                        '<td data-label="CV">' + (row.resume_upload_id ? '<a class="workspace-icon-button" href="/api/resume-library/' + Number(row.resume_upload_id) + '/document" target="_blank" rel="noopener noreferrer" aria-label="Open CV for ' + esc(row.candidate_name) + '" title="Open CV"><i class="fas fa-file-alt" aria-hidden="true"></i></a>' +
                            '<div class="workspace-muted">' + (row.vector_indexed ? 'Indexed' : 'Received; indexing pending') + '</div>' : 'Unavailable') + '</td>' +
                        '<td data-label="Interview">' + (row.interview_id ? '<span class="workspace-status ' + (row.interview_status === 'scheduled' ? 'is-active' : '') + '">' + esc(row.interview_status) + '</span><div class="workspace-muted">' + esc(row.interview_date || '') + (row.interview_time ? ' · ' + esc(String(row.interview_time).slice(0,5)) : '') + '</div>' : '<span class="workspace-muted">Not scheduled</span>') + '</td>' +
                        '<td data-label="Status"><select data-application-status="' + Number(row.id) + '" data-version="' + Number(row.version) + '" aria-label="Status for ' + esc(row.candidate_name) + '">' + statuses.map(status => '<option value="' + status + '" ' + (row.status === status ? 'selected' : '') + '>' + status.replace(/^./, value => value.toUpperCase()) + '</option>').join('') + '</select></td>' +
                        '<td data-label="Received"><time datetime="' + esc(row.created_at) + '">' + esc(received) + '</time></td>' +
                        '<td data-label="Actions" class="workspace-row-actions"><button type="button" data-email-applicant="' + Number(row.id) + '" class="workspace-icon-button" aria-label="Compose email to ' + esc(row.candidate_name) + '" title="Compose email"><i class="fas fa-envelope" aria-hidden="true"></i></button>' +
                        '<button type="button" data-schedule-applicant="' + Number(row.id) + '" class="workspace-icon-button" aria-label="Schedule interview with ' + esc(row.candidate_name) + '" title="Schedule interview"><i class="fas fa-calendar-plus" aria-hidden="true"></i></button></td></tr>';
                }).join('') + '</tbody></table>' : '<div class="workspace-empty"><span class="workspace-empty-icon"><i class="fas fa-inbox" aria-hidden="true"></i></span><h3>No applications yet</h3><p>Share the published application link to receive candidates for this role.</p></div>');
            if (applications.length) {
                const footer = document.createElement('footer'); footer.className = 'workspace-pagination';
                footer.innerHTML = '<span class="workspace-muted">Showing ' + (offset + 1).toLocaleString() + '–' + Math.min(total, offset + applications.length).toLocaleString() + ' of ' + Number(total).toLocaleString() + '</span><div class="workspace-page-controls"><button type="button" data-prev class="workspace-icon-button" aria-label="Previous applications" title="Previous page"><i class="fas fa-chevron-left" aria-hidden="true"></i></button><button type="button" data-next class="workspace-icon-button" aria-label="Next applications" title="Next page"><i class="fas fa-chevron-right" aria-hidden="true"></i></button></div>';
                footer.querySelector('[data-prev]').disabled = offset === 0;
                footer.querySelector('[data-next]').disabled = offset + applications.length >= total;
                footer.querySelector('[data-prev]').onclick = () => loadApplications(page, Math.max(0, offset - 50));
                footer.querySelector('[data-next]').onclick = () => loadApplications(page, offset + applications.length);
                content.append(footer);
            }
            content.querySelector('[data-back]').onclick = loadPages;
            content.querySelectorAll('[data-email-applicant]').forEach(button => button.addEventListener('click', () => {
                const row = applications.find(item => Number(item.id) === Number(button.dataset.emailApplicant));
                if (!row?.normalized_email) { notify('No valid applicant email is available.', 'error'); return; }
                window.RecruiterOutreach?.open({useSearch:false,candidateName:row.candidate_name,candidateEmail:row.normalized_email,
                    position:page.title,location:page.location || '',jobApplicationId:String(row.id),companyId:String(selectedCompanyId || window.currentUser?.company?.company_id || window.currentUser?.company?.id || '')});
            }));
            content.querySelectorAll('[data-schedule-applicant]').forEach(button => button.addEventListener('click', () => {
                const row = applications.find(item => Number(item.id) === Number(button.dataset.scheduleApplicant));
                if (!row) return;
                window.scheduleInterview?.(row.candidate_name,row.normalized_email || '',
                    {position:page.title,jobApplicationId:String(row.id),jobApplicationPageId:String(page.id),
                        companyId:String(selectedCompanyId || window.currentUser?.company?.company_id || window.currentUser?.company?.id || '')});
            }));
            content.querySelectorAll('[data-application-status]').forEach(select => select.addEventListener('change', async () => {
                const previous = select.querySelector('option[selected]')?.value || 'received'; select.disabled = true;
                try {
                    const data = await scopedRequest('/api/job-applications/' + Number(select.dataset.applicationStatus) + '/status',
                        {method:'PATCH', headers:{'Content-Type':'application/json'}, body:JSON.stringify({status:select.value,version:Number(select.dataset.version)})});
                    select.dataset.version = data.application.version;
                    [...select.options].forEach(option => option.defaultSelected = option.value === select.value);
                    notify('Application status updated.');
                } catch (error) { select.value = previous; notify(error.message, 'error'); }
                finally { select.disabled = false; }
            }));
        }

        root.querySelector('[data-create]').onclick = () => {
            if (isSuperAdmin && !selectedCompanyId) { notify('Choose a company workspace first.', 'error'); return; }
            pageForm();
        };
        const onInterviewScheduled = event => {
            if (selectedPage && Number(event.detail?.pageId) === Number(selectedPage.id) && root.isConnected) {
                loadApplications(selectedPage, selectedOffset);
            }
        };
        window.addEventListener('job-application-interview-scheduled', onInterviewScheduled);
        if (!isSuperAdmin) loadPages();
        return () => { disposed = true; sequence++; window.removeEventListener('job-application-interview-scheduled', onInterviewScheduled); document.querySelectorAll('[data-job-page-dialog]').forEach(modal => modal.remove()); };
    }

    async function initPublicApplicationPage(root) {
        const token = root.dataset.publicToken || '';
        const alert = document.createElement('div');
        alert.className = 'application-alert'; alert.hidden = true; alert.setAttribute('role','alert');
        try {
            const data = await request('/api/public/application-pages/' + encodeURIComponent(token), {credentials:'omit', cache:'no-store'});
            const page = data.page;
            root.innerHTML = '<section class="application-heading"><p class="application-eyebrow" data-company></p><h1 data-title></h1><p class="application-meta" data-meta></p></section>' +
                '<section class="application-description" data-description></section><section class="application-form"><h2>Apply for this role</h2><div data-alert class="application-alert" role="alert" hidden></div>' +
                '<form data-form enctype="multipart/form-data"><div class="application-grid"><div class="application-field"><label for="candidate-name">Full name <span aria-hidden="true">*</span></label><input id="candidate-name" name="candidate_name" autocomplete="name" maxlength="160" required></div>' +
                '<div class="application-field"><label for="candidate-email">Email address <span aria-hidden="true">*</span></label><input id="candidate-email" name="email" type="email" autocomplete="email" maxlength="254" required></div>' +
                '<div class="application-field"><label for="candidate-phone">Phone</label><input id="candidate-phone" name="phone" type="tel" autocomplete="tel" maxlength="40"></div>' +
                '<div class="application-field"><label for="candidate-location">Current location</label><input id="candidate-location" name="location" autocomplete="address-level2" maxlength="180"></div>' +
                '<div class="application-field"><label for="candidate-experience">Years of experience</label><input id="candidate-experience" name="years_experience" type="number" min="0" max="80" step="0.5" inputmode="decimal"></div>' +
                '<div class="application-field"><label for="candidate-linkedin">LinkedIn profile</label><input id="candidate-linkedin" name="linkedin_url" type="url" placeholder="https://www.linkedin.com/in/…" maxlength="500"></div></div>' +
                '<div data-questions></div><div class="application-field"><label for="candidate-cv">CV or resume <span aria-hidden="true">*</span></label><input id="candidate-cv" name="file" type="file" accept=".pdf,.doc,.docx,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document" required><p class="application-help">PDF or Word document, up to 10 MB.</p></div>' +
                '<label class="application-consent"><input name="consent" type="checkbox" required><span>I agree that Efforts Solutions may use my details and CV for recruitment. My CV may be reviewed with AI-assisted tools, but hiring decisions are made by people.</span></label>' +
                '<label class="application-honeypot" aria-hidden="true">Company website<input name="company_website" tabindex="-1" autocomplete="off"></label><button class="application-submit" type="submit">Submit application</button></form></section>';
            root.querySelector('[data-company]').textContent = page.company_name || 'Efforts Solutions';
            root.querySelector('[data-title]').textContent = page.title;
            root.querySelector('[data-meta]').textContent = [page.location, page.employment_type].filter(Boolean).join(' | ');
            root.querySelector('[data-description]').textContent = page.description;
            const questions = Array.isArray(page.custom_questions) ? page.custom_questions : [];
            const questionHost = root.querySelector('[data-questions]');
            questions.forEach((question, index) => {
                const wrapper = document.createElement('div'); wrapper.className = 'application-field application-question';
                const label = document.createElement('label'); label.htmlFor = 'application-question-' + index; label.textContent = question;
                const input = document.createElement('input'); input.id = label.htmlFor; input.dataset.question = String(index); input.maxLength = 1000; input.autocomplete = 'off';
                wrapper.append(label, input); questionHost.append(wrapper);
            });
            const form = root.querySelector('[data-form]'), errorBox = root.querySelector('[data-alert]');
            form.addEventListener('submit', async event => {
                event.preventDefault(); errorBox.hidden = true;
                if (!form.reportValidity()) return;
                const submit = form.querySelector('[type=submit]');
                submit.disabled = true; submit.textContent = 'Submitting…';
                const formData = new FormData(form);
                const candidateAnswers = {};
                form.querySelectorAll('[data-question]').forEach(input => {
                    if (input.value.trim()) candidateAnswers[input.dataset.question] = input.value.trim();
                });
                formData.set('answers', JSON.stringify(candidateAnswers));
                try {
                    await request('/api/public/application-pages/' + encodeURIComponent(token) + '/applications',
                        {method:'POST', body:formData, credentials:'omit'});
                    const done = document.createElement('div'); done.className = 'application-alert is-success';
                    done.setAttribute('role','status'); done.setAttribute('aria-live','polite');
                    const heading = document.createElement('strong'); heading.textContent = 'Application received';
                    const message = document.createElement('p'); message.textContent = 'Thank you for applying. Your details and CV have been shared with the hiring team.';
                    done.append(heading,message); done.tabIndex = -1; form.replaceWith(done); done.focus();
                } catch (failure) {
                    errorBox.textContent = failure.message || 'Your application could not be sent. Please try again.';
                    errorBox.className = 'application-alert is-error'; errorBox.hidden = false;
                    submit.disabled = false; submit.textContent = 'Submit application';
                }
            });
        } catch (error) {
            root.innerHTML = '<section class="application-unavailable"><h1>This application page is unavailable</h1><p>This job may have closed or the link may no longer be active.</p></section>';
        }
    }

    window.JobApplications = {mount};
    const publicRoot = document.getElementById('candidate-application');
    if (publicRoot) initPublicApplicationPage(publicRoot);
})();
