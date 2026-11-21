(function () {
    'use strict';
    const allowed = user => ['super_admin', 'tenant_admin'].includes(user?.user_type);
    const esc = value => (window.escapeAttr || window.escapeHtml)(value == null ? '' : String(value));
    const roleName = role => ({super_admin:'Super Admin', tenant_admin:'Tenant Admin', tenant_user:'Recruiter'}[role] || role);
    const companyId = user => user?.company?.company_id || user?.company?.id || null;

    async function request(url, options) {
        const response = await fetch(url, options);
        const data = await response.json().catch(() => ({}));
        if (!response.ok || data.success === false) {
            throw new Error(typeof data.detail === 'string' ? data.detail : 'The request could not be completed.');
        }
        return data;
    }

    function dialog(title, content, submitText, onSubmit) {
        const modal = document.createElement('div');
        modal.className = 'workspace-overlay';
        modal.dataset.adminDialog = 'true';
        modal.innerHTML = `<section class="workspace-dialog workspace-admin-dialog"><header><h3>${esc(title)}</h3>
            <button type="button" data-close aria-label="Close dialog" title="Close dialog" class="workspace-icon-button"><i class="fas fa-times" aria-hidden="true"></i></button></header>
            <form class="workspace-form"><div class="workspace-dialog-body">${content}<p data-error role="alert" class="workspace-inline-error hidden"></p></div>
            <footer><button type="button" data-close class="workspace-button">Cancel</button>
            <button type="submit" class="workspace-button ${submitText === 'Delete user' ? 'is-danger' : 'is-primary'}"><i class="fas ${submitText === 'Delete user' ? 'fa-trash' : 'fa-check'}" aria-hidden="true"></i>${esc(submitText)}</button></footer></form></section>`;
        document.body.append(modal);
        window.bindScheduleDialog(modal, title);
        let pending = false;
        modal.querySelectorAll('[data-close]').forEach(button => button.addEventListener('click', () => { if (!pending) modal.remove(); }));
        modal.addEventListener('keydown', event => {
            if (pending && event.key === 'Escape') { event.preventDefault(); event.stopImmediatePropagation(); }
        }, true);
        const form = modal.querySelector('form');
        form.addEventListener('submit', async event => {
            event.preventDefault();
            if (pending || !form.reportValidity()) return;
            pending = true;
            modal.dataset.submitting = 'true';
            const values = new FormData(form);
            const submit = form.querySelector('[type="submit"]'), submitLabel = submit.innerHTML;
            submit.innerHTML = '<i class="fas fa-circle-notch fa-spin" aria-hidden="true"></i>Saving...';
            const controls = [...form.querySelectorAll('button'), modal.querySelector('[data-close]')];
            controls.forEach(button => { button.disabled = true; });
            modal.querySelector('[data-error]').classList.add('hidden');
            try {
                await onSubmit(values);
                modal.remove();
            } catch (error) {
                const message = modal.querySelector('[data-error]');
                message.textContent = error.message || 'The request could not be completed.';
                message.classList.remove('hidden');
                message.tabIndex = -1;
                message.focus();
            } finally {
                pending = false;
                delete modal.dataset.submitting;
                controls.forEach(button => { button.disabled = false; });
                submit.innerHTML = submitLabel;
            }
        });
        return modal;
    }

    function field(label, name, value, type = 'text', attributes = '') {
        return `<div><label for="admin-${name}" class="block text-sm font-medium mb-1">${esc(label)}</label>
            <input id="admin-${name}" name="${name}" type="${type}" value="${esc(value ?? '')}"
                class="w-full border border-gray-300 rounded-md px-3 py-2" ${attributes}></div>`;
    }

    function mount(root, initialTab) {
        const user = window.currentUser;
        if (!allowed(user)) { root.textContent = 'Administrator access required.'; return () => {}; }
        const superAdmin = user.user_type === 'super_admin';
        let active = superAdmin && initialTab !== 'users' ? 'companies' : 'users';
        let sequence = 0, disposed = false, rows = [], companies = [], query = '';
        root.classList.add('recruiter-workspace','workspace-admin-view');
        root.innerHTML = `<header class="workspace-header"><h2>Administration</h2>
            <button type="button" data-connections class="workspace-button"><i class="fas fa-plug" aria-hidden="true"></i>Connections</button></header>
            <div class="workspace-toolbar admin-toolbar"><div class="workspace-tabs" role="tablist" aria-label="Administration views">
                ${superAdmin ? '<button id="admin-tab-companies" type="button" role="tab" data-tab="companies" aria-controls="admin-list">Companies</button>' : ''}
                <button id="admin-tab-users" type="button" role="tab" data-tab="users" aria-controls="admin-list">Users</button></div>
                <div class="workspace-toolbar-actions"><button type="button" data-refresh aria-label="Refresh administration" title="Refresh administration" class="workspace-icon-button"><i class="fas fa-sync-alt" aria-hidden="true"></i></button>
                <button type="button" data-add class="workspace-button is-primary"><i class="fas fa-plus" aria-hidden="true"></i><span></span></button></div></div>
            <div class="workspace-toolbar admin-list-toolbar"><span data-count class="workspace-count" role="status"></span><label class="workspace-search"><i class="fas fa-search" aria-hidden="true"></i><input type="search" data-query aria-label="Search administration" placeholder="Search companies" maxlength="200" autocomplete="off"></label></div>
            <div id="admin-list" data-table role="tabpanel" class="workspace-table-region"></div>`;
        const table = root.querySelector('[data-table]');
        const notify = message => window.showNotification(message, 'success');
        root.querySelector('[data-connections]').addEventListener('click', () => window.loadPage('settings'));

        function render() {
            root.querySelectorAll('[data-tab]').forEach(tab => {
                tab.setAttribute('aria-selected', String(tab.dataset.tab === active));
                tab.tabIndex = tab.dataset.tab === active ? 0 : -1;
            });
            table.setAttribute('aria-labelledby','admin-tab-' + active);
            root.querySelector('[data-query]').placeholder = active === 'companies' ? 'Search companies' : 'Search users';
            root.querySelector('[data-add] span').textContent = active === 'companies' ? 'Add company' : 'Add user';
            const filtered = rows.filter(row => [row.company_name,row.company_code,row.full_name,row.email,roleName(row.user_type || '')].some(value => String(value || '').toLocaleLowerCase().includes(query.toLocaleLowerCase())));
            const noun = active === 'companies' ? (rows.length === 1 ? 'company' : 'companies') : (rows.length === 1 ? 'user' : 'users');
            root.querySelector('[data-count]').textContent = (query ? filtered.length + ' of ' : '') + rows.length.toLocaleString() + ' ' + noun;
            if (!filtered.length) { table.innerHTML = `<div class="workspace-empty"><span class="workspace-empty-icon"><i class="fas ${active === 'companies' ? 'fa-building' : 'fa-users'}" aria-hidden="true"></i></span><h3>${query ? 'No matches found' : active === 'companies' ? 'No companies found' : 'No users found'}</h3></div>`; return; }
            const headers = active === 'companies' ? ['Company', 'Plan', 'Limits', 'Status', 'Actions'] : ['User', 'Role', 'Company', 'Status', 'Actions'];
            table.innerHTML = `<table class="workspace-table admin-table"><thead><tr>${headers.map(label => `<th scope="col">${label}</th>`).join('')}</tr></thead><tbody></tbody></table>`;
            const body = table.querySelector('tbody');
            for (const row of filtered) {
                const tr = document.createElement('tr');
                const content = active === 'companies' ? [
                    `<strong>${esc(row.company_name)}</strong><div class="text-xs text-gray-500">${esc(row.company_code)}</div>`,
                    `<span class="workspace-plan">${esc(row.subscription_plan || 'basic')}</span>`,
                    `<div class="admin-limits"><span><strong>${Number(row.max_users || 0).toLocaleString()}</strong> users</span><span><strong>${Number(row.max_resumes || 0).toLocaleString()}</strong> uploads</span><span><strong>${Number(row.max_searches ?? 10000).toLocaleString()}</strong> searches</span></div>`,
                    `<span class="workspace-status ${row.is_active ? 'is-active' : ''}"><span aria-hidden="true"></span>${row.is_active ? 'Active' : 'Inactive'}</span>`] : [
                    `<strong>${esc(row.full_name)}</strong><div class="text-xs text-gray-500">${esc(row.email)}</div>`,
                    esc(roleName(row.user_type)), esc(row.company_name || (row.user_type === 'super_admin' ? 'All companies' : 'Unassigned')),
                    `<span class="workspace-status ${row.is_active ? 'is-active' : ''}"><span aria-hidden="true"></span>${row.is_active ? 'Active' : 'Inactive'}</span>`];
                tr.innerHTML = content.map((value,index) => `<td data-label="${headers[index]}">${value}</td>`).join('');
                const actions = document.createElement('td'); actions.className = 'workspace-row-actions'; actions.dataset.label = 'Actions';
                const edit = document.createElement('button'); edit.type = 'button'; edit.className = 'workspace-icon-button';
                edit.title = edit.ariaLabel = active === 'companies' ? 'Edit company' : 'Edit user';
                edit.innerHTML = '<i class="fas fa-pen" aria-hidden="true"></i>';
                edit.addEventListener('click', () => active === 'companies' ? companyForm(row) : userForm(row));
                const editable = active === 'companies' || superAdmin || row.user_type !== 'super_admin';
                if (editable) actions.append(edit);
                if (editable && active === 'users' && Number(row.id) !== Number(user.id)) {
                    const remove = document.createElement('button'); remove.type = 'button'; remove.className = 'workspace-icon-button is-danger';
                    remove.title = remove.ariaLabel = 'Delete user'; remove.innerHTML = '<i class="fas fa-trash" aria-hidden="true"></i>';
                    remove.addEventListener('click', () => dialog('Delete user', `<p class="text-sm">Delete the account for <strong>${esc(row.full_name || row.email)}</strong>? This cannot be undone.</p>`, 'Delete user', async () => {
                        await request(`/api/users/${Number(row.id)}`, {method:'DELETE'}); notify('User deleted.'); await load();
                    })); actions.append(remove);
                }
                tr.append(actions); body.append(tr);
            }
        }

        async function load() {
            if (disposed || !root.isConnected) return;
            const current = ++sequence;
            table.innerHTML = '<div class="workspace-loading" role="status"><i class="fas fa-circle-notch fa-spin" aria-hidden="true"></i>Loading...</div>'; table.setAttribute('aria-busy', 'true');
            try {
                const data = await request(active === 'companies' ? '/api/companies' : '/api/users');
                if (disposed || current !== sequence || !root.isConnected) return;
                rows = data[active] || [];
                if (!Array.isArray(rows)) throw new Error('The list could not be loaded.');
                if (active === 'companies') companies = rows;
                render();
            } catch (error) {
                if (!disposed && current === sequence && root.isConnected) {
                    root.querySelector('[data-count]').textContent = 'Count unavailable';
                    table.innerHTML = `<div class="workspace-empty is-error" role="alert"><h3>List unavailable</h3><p>${esc(error.message || 'The list could not be loaded.')}</p><button type="button" data-retry class="workspace-button"><i class="fas fa-redo" aria-hidden="true"></i>Retry</button></div>`;
                    table.querySelector('[data-retry]').onclick = load;
                }
            } finally {
                if (!disposed && current === sequence) table.setAttribute('aria-busy', 'false');
            }
        }

        function companyForm(company) {
            if (!superAdmin || disposed || !root.isConnected) return;
            const editing = !!company;
            const plans = [...new Set([company?.subscription_plan || 'basic', 'basic', 'premium', 'enterprise'])];
            dialog(editing ? 'Edit company' : 'Add company',
                field('Company name', 'company_name', company?.company_name, 'text', 'required maxlength="200"') +
                field('Company code', 'company_code', company?.company_code, 'text', editing ? 'disabled' : 'required pattern="[A-Za-z0-9_-]+" maxlength="64"') +
                `<div><label for="admin-subscription_plan" class="block text-sm font-medium mb-1">Plan</label><select id="admin-subscription_plan" name="subscription_plan" class="w-full border rounded-md px-3 py-2">${plans.map(plan => `<option value="${esc(plan)}">${esc(plan)}</option>`).join('')}</select></div>` +
                field('User limit', 'max_users', company?.max_users ?? 10, 'number', 'required min="0" step="1"') +
                field('Upload limit', 'max_resumes', company?.max_resumes ?? 1000, 'number', 'required min="0" step="1"') +
                field('Monthly search limit', 'max_searches', company?.max_searches ?? 10000, 'number', 'required min="1" max="1000000000" step="1"') +
                (editing ? `<label for="admin-company-active" class="flex items-center gap-2"><input id="admin-company-active" type="checkbox" name="is_active" ${company.is_active ? 'checked' : ''}>Active company</label>` : ''),
                editing ? 'Save changes' : 'Create company', async form => {
                    const body = new URLSearchParams(form);
                    if (editing) body.set('is_active', form.has('is_active') ? 'true' : 'false');
                    await request(editing ? `/api/companies/${Number(company.id)}` : '/api/companies', {method:editing ? 'PUT' : 'POST', body});
                    notify(editing ? 'Company updated.' : 'Company created.'); await load();
                });
        }

        async function userForm(target) {
            if (disposed || !root.isConnected) return;
            const editing = !!target, self = editing && Number(target.id) === Number(user.id);
            if (!editing && superAdmin) {
                try {
                    const data = await request('/api/companies');
                    if (disposed || !root.isConnected) return;
                    if (!Array.isArray(data.companies)) throw new Error('Company list is temporarily unavailable.');
                    companies = data.companies;
                }
                catch (error) { if (!disposed) window.showNotification(error.message, 'error'); return; }
            }
            const roles = superAdmin ? ['tenant_user', 'tenant_admin', 'super_admin'] : editing ? ['tenant_user','tenant_admin'] : ['tenant_user'];
            const modal = dialog(editing ? 'Edit user' : 'Add user',
                field('Full name', 'full_name', target?.full_name, 'text', 'required maxlength="200"') +
                field('Email address', 'email', target?.email, 'email', 'required maxlength="254"') +
                field(editing ? 'New password' : 'Password', editing ? 'new_password' : 'password', '', 'password', `${editing ? '' : 'required'} minlength="8" maxlength="128" autocomplete="new-password"`) +
                `<div><label for="admin-user_type" class="block text-sm font-medium mb-1">Role</label><select id="admin-user_type" name="user_type" class="w-full border rounded-md px-3 py-2" ${self ? 'disabled' : ''}>${roles.map(role => `<option value="${role}" ${role === target?.user_type ? 'selected' : ''}>${esc(roleName(role))}</option>`).join('')}</select></div>` +
                (!editing && superAdmin ? `<div><label for="admin-company_id" class="block text-sm font-medium mb-1">Company</label><select id="admin-company_id" name="company_id" class="w-full border rounded-md px-3 py-2"><option value="">Choose company</option>${companies.filter(company => company.is_active).map(company => `<option value="${Number(company.id)}">${esc(company.company_name)}</option>`).join('')}</select></div>` : '') +
                (editing ? `<label for="admin-user-active" class="flex items-center gap-2"><input id="admin-user-active" type="checkbox" name="is_active" ${target.is_active ? 'checked' : ''} ${self ? 'disabled' : ''}>Active user</label>` : ''),
                editing ? 'Save changes' : 'Create user', async form => {
                    const body = new URLSearchParams(form);
                    if (editing) {
                        if (!form.get('new_password')) body.delete('new_password');
                        if (!self) body.set('is_active', form.has('is_active') ? 'true' : 'false');
                    } else {
                        const chosen = superAdmin ? form.get('company_id') : companyId(user);
                        if (chosen) body.set('company_id', chosen); else body.delete('company_id');
                        if (body.get('user_type') !== 'super_admin' && !chosen) throw new Error('Choose an active company for this user.');
                    }
                    await request(editing ? `/api/users/${Number(target.id)}` : '/api/users', {method:editing ? 'PUT' : 'POST', body});
                    notify(editing ? 'User updated.' : 'User created.'); await load();
                });
            const role = modal.querySelector('[name="user_type"]'), company = modal.querySelector('[name="company_id"]');
            if (company) {
                const sync = () => { company.required = role.value !== 'super_admin'; };
                role.addEventListener('change', sync); sync();
            }
        }
        const tabs = [...root.querySelectorAll('[data-tab]')];
        tabs.forEach((tab,index) => {
            tab.addEventListener('click', () => { active = tab.dataset.tab; query = ''; rows = []; root.querySelector('[data-query]').value = ''; render(); load(); });
            tab.addEventListener('keydown', event => {
                if (!['ArrowLeft','ArrowRight','Home','End'].includes(event.key)) return;
                event.preventDefault();
                const target = event.key === 'Home' ? tabs[0] : event.key === 'End' ? tabs[tabs.length-1] : tabs[(index + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length)%tabs.length];
                target.click(); target.focus();
            });
        });
        root.querySelector('[data-query]').addEventListener('input', event => { query = event.target.value.trim(); render(); });
        root.querySelector('[data-refresh]').addEventListener('click', load);
        root.querySelector('[data-add]').addEventListener('click', async event => {
            const button = event.currentTarget;
            if (button.disabled) return;
            button.disabled = true;
            try { if (active === 'companies') companyForm(); else await userForm(); }
            finally { button.disabled = false; }
        });
        render(); load();
        return () => {
            disposed = true; sequence++;
            document.querySelectorAll('[data-admin-dialog]').forEach(modal => {
                if (modal.dataset.submitting !== 'true') modal.remove();
            });
        };
    }
    window.AdminWorkspace = {mount, allowed};
}());
