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
                    (Number(page.indexing_pending) ? '<div class="workspace-muted">' + Number(page.indexing_pending).toLocaleString() + ' CVs processing</div>' : '') + '</td>' +
                    '<td data-label="Applications"><button type="button" data-applicants="' + Number(page.id) + '" class="job-page-count">' + Number(page.applicant_count || 0).toLocaleString() + '</button></td>' +
                    '<td data-label="Actions" class="workspace-row-actions"><button type="button" data-edit="' + Number(page.id) + '" class="workspace-icon-button" aria-label="Edit ' + esc(page.title) + '" title="Edit job page"><i class="fas fa-pen" aria-hidden="true"></i></button>' +
                    (page.status === 'published' ? '<button type="button" data-copy="' + Number(page.id) + '" class="workspace-icon-button" aria-label="Copy application link" title="Copy application link"><i class="fas fa-link" aria-hidden="true"></i></button>' : '') +
                    '<a class="workspace-icon-button" href="' + esc(pageAddress('/job-application-pages/' + Number(page.id) + '/preview')) + '" target="_blank" rel="noopener noreferrer" aria-label="Preview ' + esc(page.title) + ' as a candidate" title="Preview candidate page"><i class="fas fa-external-link-alt" aria-hidden="true"></i></a>' +
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
            const settings = page?.application_settings || {};
            const banner = settings.banner || {};
            const pay = settings.pay || {};
            const fields = settings.fields || {};
            const modal = document.createElement('div');
            modal.className = 'workspace-overlay'; modal.dataset.jobPageDialog = 'true';
            modal.innerHTML = '<section class="workspace-dialog job-page-dialog"><header><h3>' + (editing ? 'Edit job page' : 'Create job page') + '</h3><button type="button" data-close class="workspace-icon-button" aria-label="Close dialog" title="Close dialog"><i class="fas fa-times" aria-hidden="true"></i></button></header>' +
                '<form><div class="workspace-dialog-body job-page-form"><label>Job title<input name="title" maxlength="180" required value="' + esc(page?.title || '') + '"></label>' +
                '<div class="job-page-form-grid"><label>Location<input name="location" maxlength="180" placeholder="e.g. Abu Dhabi" value="' + esc(page?.location || '') + '"></label><label>Employment type<input name="employment_type" list="employment-type-options" maxlength="80" value="' + esc(page?.employment_type || 'Full-time') + '"><datalist id="employment-type-options"><option>Full-time</option><option>Part-time</option><option>Contract</option><option>Temporary</option><option>Internship</option><option>Freelance</option><option>Fixed-term</option></datalist></label></div>' +
                '<label>Role description<textarea name="description" rows="8" minlength="20" maxlength="12000" required placeholder="Describe the role, responsibilities and essential qualifications.">' + esc(page?.description || '') + '</textarea></label>' +
                '<section class="job-page-settings"><h4>Job details candidates will see</h4><div class="job-page-form-grid"><label>Work arrangement<select name="work_arrangement"><option value="unspecified">Not specified</option><option value="onsite">On-site</option><option value="hybrid">Hybrid</option><option value="remote">Remote</option></select></label>' +
                '<label>Resume requirement<select name="resume_policy"><option value="either">Upload a CV or provide a link</option><option value="upload">CV upload required</option><option value="link">Resume link required</option></select></label></div>' +
                '<label class="job-page-check"><input name="show_pay" type="checkbox" ' + (pay.show ? 'checked' : '') + '> Show compensation on the job page</label><div data-pay-fields class="job-page-form-grid"><label>Minimum pay<input name="pay_minimum" type="number" min="0" max="999999999.99" step="0.01" value="' + esc(pay.minimum || '') + '"></label><label>Maximum pay<input name="pay_maximum" type="number" min="0" max="999999999.99" step="0.01" value="' + esc(pay.maximum || '') + '"></label><label>Currency<input name="pay_currency" list="pay-currency-options" placeholder="AED" maxlength="3" pattern="[A-Za-z]{3}" value="' + esc(pay.currency || 'AED') + '" required><datalist id="pay-currency-options"><option>AED</option><option>SAR</option><option>USD</option><option>INR</option><option>GBP</option><option>EUR</option></datalist></label><label>Pay period<select name="pay_period"><option value="hour">Per hour</option><option value="day">Per day</option><option value="month">Per month</option><option value="year">Per year</option></select></label></div>' +
                '<label>Compensation note (optional)<input name="pay_note" maxlength="160" placeholder="e.g. Depending on experience" value="' + esc(pay.note || '') + '"></label></section>' +
                '<section class="job-page-settings"><h4>Brand the application page</h4><div class="job-page-form-grid"><label>Banner headline<input name="banner_headline" maxlength="160" placeholder="e.g. Build what’s next with us" value="' + esc(banner.headline || '') + '"></label><label>Banner color<input name="banner_color" type="color" value="' + esc(banner.color || '#173b47') + '"></label></div><label>Banner image link (optional)<input name="banner_image_url" type="url" pattern="https://.+" maxlength="2048" placeholder="https://…" value="' + esc(banner.image_url || '') + '"></label><p class="workspace-muted">Use a publicly accessible HTTPS image link.</p></section>' +
                '<fieldset class="job-page-settings job-page-field-options"><legend>Candidate information to collect</legend><div class="job-page-option-grid">' +
                '<label class="job-page-check"><input name="field_phone" type="checkbox" ' + (fields.phone !== false ? 'checked' : '') + '> Phone</label><label class="job-page-check"><input name="field_location" type="checkbox" ' + (fields.location !== false ? 'checked' : '') + '> Current location</label><label class="job-page-check"><input name="field_experience" type="checkbox" ' + (fields.experience !== false ? 'checked' : '') + '> Years of experience</label><label class="job-page-check"><input name="field_linkedin" type="checkbox" ' + (fields.linkedin !== false ? 'checked' : '') + '> LinkedIn profile</label><label class="job-page-check"><input name="field_portfolio" type="checkbox" ' + (fields.portfolio === true ? 'checked' : '') + '> Portfolio link</label></div></fieldset>' +
                '<section class="job-question-editor" aria-describedby="job-question-help"><div class="job-question-toolbar"><div><strong>Application questions</strong><span class="workspace-muted">Optional · up to six</span></div><button type="button" data-generate-questions class="workspace-button"><i class="fas fa-wand-magic-sparkles" aria-hidden="true"></i>Draft with AI</button></div>' +
                '<p id="job-question-help" class="workspace-muted">Questions stay optional for candidates. AI drafts use this role and your company’s other job pages; review them before use.</p><div data-question-list class="job-question-list"></div>' +
                '<div class="job-question-footer"><button type="button" data-add-question class="workspace-button"><i class="fas fa-plus" aria-hidden="true"></i>Add question</button><span data-question-count class="workspace-muted" aria-live="polite">0 of 6</span></div></section>' +
                '<p class="workspace-muted">Applicants provide their contact details and CV. Applications are not automatically scored.</p><p data-error role="alert" class="workspace-inline-error hidden"></p></div>' +
                '<footer><button type="button" data-close class="workspace-button">Cancel</button><button type="submit" class="workspace-button is-primary"><i class="fas fa-check" aria-hidden="true"></i>' + (editing ? 'Save changes' : 'Save draft') + '</button></footer></form></section>';
            document.body.append(modal);
            window.bindScheduleDialog?.(modal, editing ? 'Edit job page' : 'Create job page');
            const form = modal.querySelector('form');
            form.elements.work_arrangement.value = settings.work_arrangement || 'unspecified';
            form.elements.resume_policy.value = settings.resume_policy || 'either';
            form.elements.pay_period.value = pay.period || 'month';
            form.elements.pay_note.addEventListener('input', () => form.elements.pay_note.setCustomValidity(''));
            form.elements.pay_maximum.addEventListener('input', () => form.elements.pay_maximum.setCustomValidity(''));
            form.elements.show_pay.addEventListener('change', () => {
                modal.querySelector('[data-pay-fields]').hidden = !form.elements.show_pay.checked;
            });
            modal.querySelector('[data-pay-fields]').hidden = !form.elements.show_pay.checked;
            const questionList = modal.querySelector('[data-question-list]');
            const addQuestion = modal.querySelector('[data-add-question]');
            const questionCount = modal.querySelector('[data-question-count]');
            let questionValues = Array.isArray(page?.custom_questions) ? page.custom_questions.slice() : [];
            form.elements.title.addEventListener('input', () => form.elements.title.setCustomValidity(''));
            form.elements.description.addEventListener('input', () => form.elements.description.setCustomValidity(''));

            function renderQuestionFields(focusIndex = null) {
                questionList.innerHTML = questionValues.map((question, index) => '<div class="job-question-row"><label for="job-question-' + index + '"><span>Question ' + (index + 1) + '</span><input id="job-question-' + index + '" type="text" maxlength="180" required value="' + esc(question) + '" data-question-index="' + index + '"><span class="job-question-length" data-question-length="' + index + '">' + esc(String(question).length) + '/180</span></label><button type="button" data-remove-question="' + index + '" class="workspace-icon-button is-danger" aria-label="Remove question ' + (index + 1) + '" title="Remove question"><i class="fas fa-trash" aria-hidden="true"></i></button></div>').join('');
                questionCount.textContent = questionValues.length + ' of 6';
                addQuestion.disabled = questionValues.length >= 6;
                if (focusIndex !== null) questionList.querySelector('[data-question-index="' + focusIndex + '"]')?.focus();
            }

            function validateQuestionFields() {
                const inputs = [...questionList.querySelectorAll('[data-question-index]')];
                const seen = new Set();
                let valid = true;
                inputs.forEach(input => {
                    input.setCustomValidity('');
                    const normalized = input.value.trim().replace(/\s+/g, ' ').toLowerCase();
                    if (!normalized) input.setCustomValidity('Enter a question or remove this row.');
                    else if (seen.has(normalized)) input.setCustomValidity('Remove this duplicate question.');
                    else seen.add(normalized);
                    if (!input.checkValidity()) valid = false;
                });
                return valid;
            }

            function closeForm() {
                document.querySelectorAll('[data-question-preview]').forEach(preview => preview.remove());
                modal.remove();
            }

            modal.querySelectorAll('[data-close]').forEach(button => button.onclick = closeForm);
            questionList.addEventListener('input', event => {
                const input = event.target.closest('[data-question-index]');
                if (!input) return;
                const index = Number(input.dataset.questionIndex);
                questionValues[index] = input.value;
                const length = questionList.querySelector('[data-question-length="' + index + '"]');
                if (length) length.textContent = input.value.length + '/180';
                input.setCustomValidity('');
            });
            questionList.addEventListener('click', event => {
                const button = event.target.closest('[data-remove-question]');
                if (!button) return;
                questionValues.splice(Number(button.dataset.removeQuestion), 1);
                renderQuestionFields(Math.min(Number(button.dataset.removeQuestion), questionValues.length - 1));
            });
            addQuestion.addEventListener('click', () => {
                if (questionValues.length >= 6) return;
                questionValues.push('');
                renderQuestionFields(questionValues.length - 1);
            });
            renderQuestionFields();

            async function openQuestionPreview() {
                const title = form.elements.title.value.trim();
                const description = form.elements.description.value.trim();
                if (title.length < 2 || description.length < 20) {
                    form.elements.title.setCustomValidity(title.length < 2 ? 'Enter a job title before drafting questions.' : '');
                    form.elements.description.setCustomValidity(description.length < 20 ? 'Add at least 20 characters of role detail before drafting questions.' : '');
                    form.reportValidity();
                    return;
                }
                form.elements.title.setCustomValidity('');
                form.elements.description.setCustomValidity('');
                const preview = document.createElement('div');
                preview.className = 'workspace-overlay'; preview.dataset.questionPreview = 'true';
                preview.innerHTML = '<section class="workspace-dialog job-question-preview"><header><h3>Review AI question suggestions</h3><button type="button" data-preview-close class="workspace-icon-button" aria-label="Close suggestions" title="Close"><i class="fas fa-times" aria-hidden="true"></i></button></header>' +
                    '<div class="workspace-dialog-body"><p class="job-question-preview-note">Suggestions for <strong data-preview-company>your company</strong>. Review and edit each question before using it. Nothing is saved until you save the job page.</p><div data-preview-state class="job-question-preview-state" role="status" aria-live="polite"><i class="fas fa-circle-notch fa-spin" aria-hidden="true"></i>Preparing role-specific suggestions…</div><div data-preview-questions class="job-question-preview-list"></div><p data-preview-error class="workspace-inline-error hidden" role="alert"></p></div>' +
                    '<footer><span data-preview-count class="workspace-muted">0 of 6 selected</span><button type="button" data-preview-close class="workspace-button">Cancel</button><button type="button" data-replace-questions class="workspace-button" hidden>Replace current</button><button type="button" data-use-questions class="workspace-button is-primary" disabled>Use selected questions</button></footer></section>';
                document.body.append(preview);
                window.bindScheduleDialog?.(preview, 'Review AI question suggestions');
                preview.querySelectorAll('[data-preview-close]').forEach(button => button.onclick = () => preview.remove());
                const state = preview.querySelector('[data-preview-state]');
                const suggestionsHost = preview.querySelector('[data-preview-questions]');
                const apply = preview.querySelector('[data-use-questions]');
                const replace = preview.querySelector('[data-replace-questions]');
                const selectedCount = preview.querySelector('[data-preview-count]');
                let suggestions = [];
                replace.hidden = questionValues.length === 0;
                if (questionValues.length) apply.textContent = 'Add to current';
                function updateDraftCount() {
                    const selected = suggestions.filter(item => item.selected).length;
                    selectedCount.textContent = selected + ' of 6 selected';
                    apply.disabled = selected < 1 || selected > 6;
                }
                function renderSuggestions(focusIndex = null) {
                    suggestionsHost.replaceChildren();
                    suggestions.forEach((item, index) => {
                        const row = document.createElement('div'); row.className = 'job-question-preview-row';
                        const label = document.createElement('label'); label.className = 'job-question-preview-select';
                        const checkbox = document.createElement('input'); checkbox.type = 'checkbox'; checkbox.checked = item.selected;
                        checkbox.setAttribute('aria-label', 'Include question ' + (index + 1));
                        checkbox.addEventListener('change', () => { item.selected = checkbox.checked; updateDraftCount(); });
                        label.append(checkbox, document.createTextNode('Use'));
                        const editor = document.createElement('div'); editor.className = 'job-question-preview-edit';
                        const caption = document.createElement('label'); caption.textContent = 'Question ' + (index + 1);
                        const textarea = document.createElement('textarea'); textarea.maxLength = 180; textarea.rows = 2;
                        textarea.value = item.question; textarea.setAttribute('aria-label', 'Edit question ' + (index + 1));
                        textarea.addEventListener('input', () => { item.question = textarea.value; });
                        const length = document.createElement('span'); length.className = 'job-question-length'; length.textContent = item.question.length + '/180';
                        textarea.addEventListener('input', () => { length.textContent = textarea.value.length + '/180'; });
                        editor.append(caption, textarea, length);
                        const remove = document.createElement('button'); remove.type = 'button'; remove.className = 'workspace-icon-button is-danger';
                        remove.setAttribute('aria-label', 'Remove suggestion ' + (index + 1)); remove.title = 'Remove suggestion';
                        remove.innerHTML = '<i class="fas fa-trash" aria-hidden="true"></i>';
                        remove.addEventListener('click', () => { suggestions.splice(index, 1); renderSuggestions(); });
                        row.append(label, editor, remove); suggestionsHost.append(row);
                    });
                    let add = preview.querySelector('[data-add-draft-question]');
                    if (!add) {
                        add = document.createElement('button'); add.type = 'button'; add.dataset.addDraftQuestion = 'true';
                        add.className = 'workspace-button'; add.innerHTML = '<i class="fas fa-plus" aria-hidden="true"></i>Add a question';
                        suggestionsHost.after(add);
                        add.addEventListener('click', () => {
                            if (suggestions.length >= 6) return;
                            suggestions.push({question:'', selected:true});
                            renderSuggestions(suggestions.length - 1);
                        });
                    }
                    add.disabled = suggestions.length >= 6;
                    if (focusIndex !== null) suggestionsHost.querySelectorAll('textarea')[focusIndex]?.focus();
                    updateDraftCount();
                }
                function applyDraft(replaceCurrent) {
                    const chosen = suggestions.filter(item => item.selected).map(item => item.question.trim().replace(/\s+/g, ' '));
                    const combined = replaceCurrent ? chosen : [...questionValues, ...chosen];
                    const seen = new Set();
                    const problem = combined.find(question => {
                        const key = question.toLowerCase();
                        if (!question || question.length > 180 || seen.has(key)) return true;
                        seen.add(key); return false;
                    });
                    if (!chosen.length || problem !== undefined) {
                        const box = preview.querySelector('[data-preview-error]');
                        box.textContent = !chosen.length ? 'Select at least one question to continue.' : 'Fix blank or duplicate questions before continuing.';
                        box.classList.remove('hidden');
                        return;
                    }
                    if (combined.length > 6) {
                        const box = preview.querySelector('[data-preview-error]');
                        box.textContent = 'There is room for ' + (replaceCurrent ? 6 : Math.max(0, 6 - questionValues.length)) + ' more question(s). Remove or unselect suggestions, or replace the current questions.';
                        box.classList.remove('hidden');
                        return;
                    }
                    questionValues = combined;
                    renderQuestionFields();
                    preview.remove();
                }
                apply.addEventListener('click', () => applyDraft(false));
                replace.addEventListener('click', () => applyDraft(true));
                const body = {title, description, location:form.elements.location.value,
                    employment_type:form.elements.employment_type.value,
                    ...(editing ? {page_id:Number(page.id)} : {}),
                    ...(isSuperAdmin ? {company_id:Number(selectedCompanyId)} : {})};
                try {
                    const data = await scopedRequest('/api/job-application-pages/generate-questions', {
                        method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)
                    });
                    if (!preview.isConnected) return;
                    if (!Array.isArray(data.questions) || !data.questions.length) throw new Error('No question suggestions were returned.');
                    preview.querySelector('[data-preview-company]').textContent = data.company_name || 'your company';
                    suggestions = data.questions.slice(0, 6).map(question => ({question:String(question), selected:true}));
                    state.textContent = 'Review the suggestions. You can edit, remove, or add questions.';
                    renderSuggestions();
                } catch (error) {
                    if (!preview.isConnected) return;
                    state.textContent = 'Suggestions could not be prepared.';
                    const box = preview.querySelector('[data-preview-error]');
                    box.textContent = error.message; box.classList.remove('hidden');
                }
            }
            modal.querySelector('[data-generate-questions]').addEventListener('click', openQuestionPreview);
            form.addEventListener('submit', async event => {
                event.preventDefault();
                form.elements.pay_note.setCustomValidity('');
                form.elements.pay_maximum.setCustomValidity('');
                if (!validateQuestionFields()) {
                    questionList.querySelector(':invalid')?.reportValidity();
                    return;
                }
                if (!form.reportValidity()) return;
                const submit = form.querySelector('[type="submit"]');
                submit.disabled = true; submit.innerHTML = '<i class="fas fa-circle-notch fa-spin" aria-hidden="true"></i>Saving...';
                const questions = questionValues.map(value => value.trim().replace(/\s+/g, ' '));
                const minimum = form.elements.pay_minimum.value.trim();
                const maximum = form.elements.pay_maximum.value.trim();
                if (form.elements.show_pay.checked && !minimum && !maximum && !form.elements.pay_note.value.trim()) {
                    form.elements.pay_note.setCustomValidity('Enter a pay range or compensation note to show pay.');
                    form.reportValidity(); submit.disabled = false;
                    submit.innerHTML = '<i class="fas fa-check" aria-hidden="true"></i>' + (editing ? 'Save changes' : 'Save draft');
                    return;
                }
                form.elements.pay_note.setCustomValidity('');
                if (minimum && maximum && Number(minimum) > Number(maximum)) {
                    form.elements.pay_maximum.setCustomValidity('Maximum pay must be at least the minimum pay.');
                    form.reportValidity(); submit.disabled = false;
                    submit.innerHTML = '<i class="fas fa-check" aria-hidden="true"></i>' + (editing ? 'Save changes' : 'Save draft');
                    return;
                }
                form.elements.pay_maximum.setCustomValidity('');
                const applicationSettings = {
                    banner:{headline:form.elements.banner_headline.value,image_url:form.elements.banner_image_url.value,color:form.elements.banner_color.value},
                    work_arrangement:form.elements.work_arrangement.value,
                    resume_policy:form.elements.resume_policy.value,
                    pay:{show:form.elements.show_pay.checked,minimum,maximum,currency:form.elements.pay_currency.value,
                        period:form.elements.pay_period.value,note:form.elements.pay_note.value},
                    fields:{phone:form.elements.field_phone.checked,location:form.elements.field_location.checked,
                        experience:form.elements.field_experience.checked,linkedin:form.elements.field_linkedin.checked,
                        portfolio:form.elements.field_portfolio.checked}
                };
                const payload = {title:form.elements.title.value, location:form.elements.location.value,
                    employment_type:form.elements.employment_type.value, description:form.elements.description.value,
                    custom_questions:questions, application_settings:applicationSettings,
                    ...(isSuperAdmin ? {company_id:Number(selectedCompanyId)} : {}),
                    ...(editing ? {version:page.version} : {status:'draft'})};
                try {
                    await scopedRequest(editing ? '/api/job-application-pages/' + Number(page.id) : '/api/job-application-pages',
                        {method:editing ? 'PUT' : 'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
                    closeForm(); notify(editing ? 'Job page updated.' : 'Draft saved. Publish it when it is ready.'); await loadPages();
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
                    const cvMarkup = row.resume_upload_id
                        ? '<a class="workspace-icon-button" href="/api/resume-library/' + Number(row.resume_upload_id) + '/document" target="_blank" rel="noopener noreferrer" aria-label="Open uploaded CV for ' + esc(row.candidate_name) + '" title="Open uploaded CV"><i class="fas fa-file-alt" aria-hidden="true"></i></a><div class="workspace-muted">' + (row.vector_indexed ? 'Uploaded and searchable' : 'Uploaded; processing') + '</div>'
                        : row.resume_url ? '<span class="workspace-muted">External resume link · file not uploaded</span>' : '<span class="workspace-muted">No resume provided</span>';
                    const resumeLink = row.resume_url ? '<div><a href="' + esc(row.resume_url) + '" target="_blank" rel="noopener noreferrer">Open resume link</a></div>' : '';
                    const portfolioLink = row.portfolio_url ? '<div><a href="' + esc(row.portfolio_url) + '" target="_blank" rel="noopener noreferrer">Portfolio</a></div>' : '';
                    return '<tr><td data-label="Candidate"><strong>' + esc(row.candidate_name) + '</strong><div><a href="mailto:' + esc(row.normalized_email) + '">' + esc(row.normalized_email) + '</a></div>' +
                        (row.phone ? '<div class="workspace-muted">' + esc(row.phone) + '</div>' : '') + (row.location ? '<div class="workspace-muted">' + esc(row.location) + '</div>' : '') +
                        (row.linkedin_url ? '<a href="' + esc(row.linkedin_url) + '" target="_blank" rel="noopener noreferrer">LinkedIn</a>' : '') + resumeLink + portfolioLink + (answerRows ? '<details class="job-answers"><summary>Application answers</summary>' + answerRows + '</details>' : '') + '</td>' +
                        '<td data-label="Experience">' + (row.years_experience == null ? 'Not provided' : esc(row.years_experience) + ' years') + '</td>' +
                        '<td data-label="CV">' + cvMarkup + '</td>' +
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
        return () => { disposed = true; sequence++; window.removeEventListener('job-application-interview-scheduled', onInterviewScheduled); document.querySelectorAll('[data-job-page-dialog],[data-question-preview]').forEach(modal => modal.remove()); };
    }

    async function initPublicApplicationPage(root) {
        const token = root.dataset.publicToken || '';
        const previewPageId = root.dataset.previewPageId || '';
        const previewMode = Boolean(previewPageId);
        const alert = document.createElement('div');
        alert.className = 'application-alert'; alert.hidden = true; alert.setAttribute('role','alert');
        try {
            const previewQuery = root.dataset.previewCompanyId
                ? '?company_id=' + encodeURIComponent(root.dataset.previewCompanyId) : '';
            const data = await request(previewMode
                ? '/api/job-application-pages/' + encodeURIComponent(previewPageId) + '/preview-data' + previewQuery
                : '/api/public/application-pages/' + encodeURIComponent(token),
                {credentials:previewMode ? 'same-origin' : 'omit', cache:'no-store'});
            const page = data.page;
            const settings = page.application_settings || {};
            const banner = settings.banner || {};
            const fields = settings.fields || {};
            const pay = settings.pay || {};
            const resumePolicy = settings.resume_policy || 'either';
            root.innerHTML = (previewMode ? '<aside class="application-preview-note" role="status"><span><strong>Preview only</strong> · This page is not accepting applications.</span><a href="/#/jobApplications">Back to job pages</a></aside>' : '') +
                '<section class="application-banner" data-banner hidden><img data-banner-image alt="" referrerpolicy="no-referrer" hidden><div class="application-banner-content"><p data-banner-headline></p></div></section>' +
                '<section class="application-heading"><p class="application-eyebrow" data-company></p><h1 data-title></h1><p class="application-meta" data-meta></p><p class="application-pay" data-pay hidden></p></section>' +
                '<section class="application-description" data-description></section><section class="application-form"><h2>Apply for this role</h2><div data-alert class="application-alert" role="alert" hidden></div>' +
                '<form data-form enctype="multipart/form-data"><div class="application-grid"><div class="application-field"><label for="candidate-name">Full name <span aria-hidden="true">*</span></label><input id="candidate-name" name="candidate_name" autocomplete="name" maxlength="160" required></div>' +
                '<div class="application-field"><label for="candidate-email">Email address <span aria-hidden="true">*</span></label><input id="candidate-email" name="email" type="email" autocomplete="email" maxlength="254" required></div>' +
                '<div class="application-field" data-field="phone"><label for="candidate-phone">Phone</label><input id="candidate-phone" name="phone" type="tel" autocomplete="tel" maxlength="40"></div>' +
                '<div class="application-field" data-field="location"><label for="candidate-location">Current location</label><input id="candidate-location" name="location" autocomplete="address-level2" maxlength="180"></div>' +
                '<div class="application-field" data-field="experience"><label for="candidate-experience">Years of experience</label><input id="candidate-experience" name="years_experience" type="number" min="0" max="80" step="0.5" inputmode="decimal"></div>' +
                '<div class="application-field" data-field="linkedin"><label for="candidate-linkedin">LinkedIn profile</label><input id="candidate-linkedin" name="linkedin_url" type="url" placeholder="https://www.linkedin.com/in/…" maxlength="500" pattern="https://.+"></div>' +
                '<div class="application-field" data-field="portfolio"><label for="candidate-portfolio">Portfolio or work samples</label><input id="candidate-portfolio" name="portfolio_url" type="url" placeholder="https://…" maxlength="2048" pattern="https://.+"></div></div>' +
                '<div data-questions></div><section class="application-resume"><h3>Resume</h3><p class="application-help" data-resume-help></p><div class="application-field" data-resume-upload><label for="candidate-cv">Upload your CV or resume</label><input id="candidate-cv" name="file" type="file" accept=".pdf,.doc,.docx,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document"><p class="application-help">PDF or Word document, up to 10 MB.</p></div><div class="application-field" data-resume-link><label for="candidate-resume-url">Resume link</label><input id="candidate-resume-url" name="resume_url" type="url" pattern="https://.+" maxlength="2048" placeholder="https://…"><p class="application-help">Use a public HTTPS link and allow the hiring team to view it.</p></div></section>' +
                '<label class="application-consent"><input name="consent" type="checkbox" required><span>I agree that Efforts Solutions may use my details and the resume I provide for recruitment. Uploaded CVs may be reviewed with AI-assisted tools, but hiring decisions are made by people.</span></label>' +
                '<label class="application-honeypot" aria-hidden="true">Company website<input name="company_website" tabindex="-1" autocomplete="off"></label><button class="application-submit" type="submit">Submit application</button></form></section>';
            root.querySelector('[data-company]').textContent = page.company_name || 'Efforts Solutions';
            root.querySelector('[data-title]').textContent = page.title;
            document.title = (previewMode ? 'Preview: ' : '') + page.title + ' | Efforts Solutions';
            const arrangementLabels = {onsite:'On-site',hybrid:'Hybrid',remote:'Remote'};
            root.querySelector('[data-meta]').textContent = [page.location, page.employment_type,
                arrangementLabels[settings.work_arrangement]].filter(Boolean).join(' · ');
            root.querySelector('[data-description]').textContent = page.description;
            const bannerHost = root.querySelector('[data-banner]');
            const bannerHeadline = root.querySelector('[data-banner-headline]');
            const bannerImage = root.querySelector('[data-banner-image]');
            if (banner.headline || banner.image_url) {
                bannerHost.hidden = false;
                bannerHost.style.backgroundColor = /^#[0-9a-f]{6}$/i.test(banner.color || '') ? banner.color : '#173b47';
                if (banner.headline) bannerHeadline.textContent = banner.headline;
                else bannerHeadline.hidden = true;
                if (banner.image_url) { bannerImage.src = banner.image_url; bannerImage.hidden = false; }
            }
            const payBox = root.querySelector('[data-pay]');
            if (pay.show) {
                const formatPay = amount => {
                    try { return new Intl.NumberFormat(undefined,{style:'currency',currency:pay.currency,maximumFractionDigits:2}).format(Number(amount)); }
                    catch (_) { return String(amount) + ' ' + String(pay.currency || ''); }
                };
                const range = pay.minimum && pay.maximum ? formatPay(pay.minimum) + ' – ' + formatPay(pay.maximum)
                    : pay.minimum ? 'From ' + formatPay(pay.minimum) : pay.maximum ? 'Up to ' + formatPay(pay.maximum) : '';
                const period = {hour:'hour',day:'day',month:'month',year:'year'}[pay.period] || 'month';
                payBox.textContent = [range ? range + ' per ' + period : '', pay.note || ''].filter(Boolean).join(' · ');
                payBox.hidden = !payBox.textContent;
            }
            for (const [key, enabled] of Object.entries({phone:fields.phone !== false,location:fields.location !== false,
                experience:fields.experience !== false,linkedin:fields.linkedin !== false,portfolio:fields.portfolio === true})) {
                const field = root.querySelector('[data-field="' + key + '"]');
                if (field) field.hidden = !enabled;
            }
            const uploadField = root.querySelector('[data-resume-upload]');
            const linkField = root.querySelector('[data-resume-link]');
            const uploadInput = root.querySelector('[name="file"]');
            const linkInput = root.querySelector('[name="resume_url"]');
            uploadField.hidden = resumePolicy === 'link';
            linkField.hidden = resumePolicy === 'upload';
            uploadInput.required = resumePolicy === 'upload';
            linkInput.required = resumePolicy === 'link';
            root.querySelector('[data-resume-help]').textContent = resumePolicy === 'upload'
                ? 'A CV or resume file is required for this role.' : resumePolicy === 'link'
                    ? 'Provide a public HTTPS link to your CV or resume.' : 'Upload a CV or provide a link. You may provide both.';
            const questions = Array.isArray(page.custom_questions) ? page.custom_questions : [];
            const questionHost = root.querySelector('[data-questions]');
            questions.forEach((question, index) => {
                const wrapper = document.createElement('div'); wrapper.className = 'application-field application-question';
                const label = document.createElement('label'); label.htmlFor = 'application-question-' + index; label.textContent = question + ' (optional)';
                const input = document.createElement('input'); input.id = label.htmlFor; input.dataset.question = String(index); input.maxLength = 1000; input.autocomplete = 'off';
                wrapper.append(label, input); questionHost.append(wrapper);
            });
            const form = root.querySelector('[data-form]'), errorBox = root.querySelector('[data-alert]');
            if (previewMode) {
                form.querySelectorAll('input,textarea,select,button').forEach(control => { control.disabled = true; });
                form.querySelector('[type="submit"]').textContent = 'Preview only';
            }
            form.addEventListener('submit', async event => {
                event.preventDefault(); errorBox.hidden = true;
                if (previewMode) return;
                uploadInput.setCustomValidity('');
                if (resumePolicy === 'either' && !uploadInput.files?.length && !linkInput.value.trim()) {
                    uploadInput.setCustomValidity('Upload a CV or provide a resume link.');
                }
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
                    const message = document.createElement('p'); message.textContent = 'Thank you for applying. Your details and resume information have been shared with the hiring team.';
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
