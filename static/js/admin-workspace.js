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
        modal.className = 'fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4';
        modal.dataset.adminDialog = 'true';
        modal.innerHTML = `<div class="bg-white rounded-lg shadow-xl w-full max-w-lg max-h-[90vh] overflow-y-auto p-6">
            <div class="flex items-center justify-between gap-4 mb-4"><h3 class="text-lg font-semibold">${esc(title)}</h3>
            <button type="button" data-close aria-label="Close dialog" title="Close dialog" class="p-2"><i class="fas fa-times" aria-hidden="true"></i></button></div>
            <form class="space-y-4">${content}<p data-error role="alert" class="text-sm text-red-700 hidden"></p>
            <div class="flex justify-end gap-3 pt-3"><button type="button" data-close class="px-4 py-2 border rounded-md">Cancel</button>
            <button type="submit" class="px-4 py-2 bg-blue-600 text-white rounded-md"><i class="fas fa-check mr-2" aria-hidden="true"></i>${esc(submitText)}</button></div></form></div>`;
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
            const controls = [...form.querySelectorAll('button'), modal.querySelector('[data-close]')];
            controls.forEach(button => { button.disabled = true; });
            modal.querySelector('[data-error]').classList.add('hidden');
            try {
                await onSubmit(new FormData(form));
                modal.remove();
            } catch (error) {
                const message = modal.querySelector('[data-error]');
                message.textContent = error.message || 'The request could not be completed.';
                message.classList.remove('hidden');
            } finally {
                pending = false;
                delete modal.dataset.submitting;
                controls.forEach(button => { button.disabled = false; });
            }
        });
        return modal;
    }

    function field(label, name, value, type = 'text', attributes = '') {
        return `<div><label class="block text-sm font-medium mb-1">${esc(label)}</label>
            <input id="admin-${name}" name="${name}" type="${type}" value="${esc(value ?? '')}"
                class="w-full border border-gray-300 rounded-md px-3 py-2" ${attributes}></div>`;
    }

    function mount(root, initialTab) {
        const user = window.currentUser;
        if (!allowed(user)) { root.textContent = 'Administrator access required.'; return () => {}; }
        const superAdmin = user.user_type === 'super_admin';
        let active = superAdmin && initialTab !== 'users' ? 'companies' : 'users';
        let sequence = 0, disposed = false, rows = [], companies = [];
        root.innerHTML = `<header class="flex flex-wrap items-center justify-between gap-3 mb-5">
            <h2 class="text-2xl font-bold text-gray-900">Administration</h2>
            <button type="button" data-connections class="px-3 py-2 border rounded-md text-sm"><i class="fas fa-plug mr-2" aria-hidden="true"></i>Connections</button></header>
            <div class="flex flex-wrap items-center justify-between gap-3 border-b border-gray-200 pb-3 mb-4">
                <div class="flex gap-2" role="tablist" aria-label="Administration views">
                ${superAdmin ? '<button type="button" role="tab" data-tab="companies" class="px-3 py-2 rounded-md text-sm">Companies</button>' : ''}
                <button type="button" role="tab" data-tab="users" class="px-3 py-2 rounded-md text-sm">Users</button></div>
                <div class="flex gap-2"><button type="button" data-refresh aria-label="Refresh administration" title="Refresh administration" class="p-2 border rounded-md"><i class="fas fa-sync-alt" aria-hidden="true"></i></button>
                <button type="button" data-add class="px-3 py-2 bg-blue-600 text-white rounded-md text-sm"><i class="fas fa-plus mr-2" aria-hidden="true"></i><span></span></button></div></div>
            <div data-table role="tabpanel" aria-live="polite" class="overflow-x-auto"></div>`;
        const table = root.querySelector('[data-table]');
        const notify = message => window.showNotification(message, 'success');
        root.querySelector('[data-connections]').addEventListener('click', () => window.loadPage('settings'));

        function render() {
            root.querySelectorAll('[data-tab]').forEach(tab => {
                tab.setAttribute('aria-selected', String(tab.dataset.tab === active));
                tab.classList.toggle('bg-blue-100', tab.dataset.tab === active);
            });
            root.querySelector('[data-add] span').textContent = active === 'companies' ? 'Add company' : 'Add user';
            if (!rows.length) { table.textContent = active === 'companies' ? 'No companies found.' : 'No users found.'; return; }
            const headers = active === 'companies' ? ['Company', 'Plan', 'Limits', 'Status', 'Actions'] : ['User', 'Role', 'Company', 'Status', 'Actions'];
            table.innerHTML = `<table class="w-full text-sm text-left"><thead><tr>${headers.map(label => `<th scope="col" class="px-3 py-3 border-b">${label}</th>`).join('')}</tr></thead><tbody></tbody></table>`;
            const body = table.querySelector('tbody');
            for (const row of rows) {
                const tr = document.createElement('tr');
                const content = active === 'companies' ? [
                    `<strong>${esc(row.company_name)}</strong><div class="text-xs text-gray-500">${esc(row.company_code)}</div>`,
                    esc(row.subscription_plan || 'basic'),
                    `${esc(row.max_users)} users / ${esc(row.max_resumes)} uploads / ${esc(row.max_searches ?? 10000)} searches`,
                    row.is_active ? 'Active' : 'Inactive'] : [
                    `<strong>${esc(row.full_name)}</strong><div class="text-xs text-gray-500">${esc(row.email)}</div>`,
                    esc(roleName(row.user_type)), esc(row.company_name || 'Unassigned'), row.is_active ? 'Active' : 'Inactive'];
                tr.innerHTML = content.map(value => `<td class="px-3 py-3 border-b align-top">${value}</td>`).join('');
                const actions = document.createElement('td'); actions.className = 'px-3 py-3 border-b whitespace-nowrap';
                const edit = document.createElement('button'); edit.type = 'button'; edit.className = 'p-2 text-blue-700';
                edit.title = edit.ariaLabel = active === 'companies' ? 'Edit company' : 'Edit user';
                edit.innerHTML = '<i class="fas fa-pen" aria-hidden="true"></i>';
                edit.addEventListener('click', () => active === 'companies' ? companyForm(row) : userForm(row));
                const editable = active === 'companies' || superAdmin || row.user_type !== 'super_admin';
                if (editable) actions.append(edit);
                if (editable && active === 'users' && Number(row.id) !== Number(user.id)) {
                    const remove = document.createElement('button'); remove.type = 'button'; remove.className = 'p-2 text-red-700';
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
            table.textContent = 'Loading...'; table.setAttribute('aria-busy', 'true');
            try {
                const data = await request(active === 'companies' ? '/api/companies' : '/api/users');
                if (disposed || current !== sequence || !root.isConnected) return;
                rows = data[active] || [];
                if (!Array.isArray(rows)) throw new Error('The list could not be loaded.');
                if (active === 'companies') companies = rows;
                render();
            } catch (error) {
                if (!disposed && current === sequence && root.isConnected) table.textContent = error.message || 'The list could not be loaded.';
            } finally {
                if (!disposed && current === sequence) table.setAttribute('aria-busy', 'false');
            }
        }

        function companyForm(company) {
            if (!superAdmin) return;
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
            const editing = !!target, self = editing && Number(target.id) === Number(user.id);
            if (!editing && superAdmin) {
                try { companies = (await request('/api/companies')).companies || []; }
                catch (error) { window.showNotification(error.message, 'error'); return; }
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
        root.querySelectorAll('[data-tab]').forEach(tab => tab.addEventListener('click', () => { active = tab.dataset.tab; render(); load(); }));
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
