// Server-backed candidate decisions and notes. Rendering never writes decisions.
(function () {
    'use strict';
    const states = new WeakMap();
    const statusBusy = new WeakSet();
    const notesChains = new WeakMap();
    const notesVersions = new WeakMap();
    const observed = new WeakSet();
    const statuses = new Set(['selected', 'shortlisted', 'interviewed', 'rejected']);

    function recordId(card) {
        const value = card && card.getAttribute('data-search-result-id');
        return /^[1-9]\d{0,9}$/.test(value || '') && Number(value) <= 2147483647 ? value : null;
    }

    function notify(message, kind) {
        if (typeof window.showNotification === 'function') window.showNotification(message, kind);
    }

    function checkboxes(card, activeStatus) {
        card.querySelectorAll('.hr-checkbox').forEach(input => {
            input.checked = input.dataset.status === activeStatus;
        });
    }

    function disableStatus(card, disabled) {
        card.querySelectorAll('.hr-checkbox').forEach(input => { input.disabled = disabled; });
    }

    async function request(url, options) {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), 15000);
        try {
            const response = await fetch(url, { ...options, credentials: 'same-origin', signal: controller.signal });
            if (!response.ok) throw new Error('Candidate request failed');
            const data = await response.json();
            if (data.success !== true) throw new Error('Candidate request was not accepted');
            return data;
        } finally {
            clearTimeout(timer);
        }
    }

    async function load(card) {
        if (!card) return false;
        const id = recordId(card);
        disableStatus(card, true);
        if (!id) return false;
        const textarea = card.querySelector('.hr-comments-textarea');
        const initialNoteVersion = notesVersions.get(card) || 0;
        if (textarea && !observed.has(textarea)) {
            textarea.addEventListener('input', () => { textarea.dataset.notesDirty = 'true'; });
            observed.add(textarea);
        }
        try {
            const data = await request('/api/candidate-state?ids=' + encodeURIComponent(id));
            const state = (data.candidates || []).find(row => String(row.search_result_id) === id);
            if (!state) throw new Error('Candidate record unavailable');
            if (!card.isConnected) return false;
            states.set(card, { status: state.status || null, comments: state.comments || '' });
            checkboxes(card, state.status);
            if (textarea && textarea.dataset.notesDirty !== 'true'
                    && (notesVersions.get(card) || 0) === initialNoteVersion) textarea.value = state.comments || '';
            disableStatus(card, false);
            return true;
        } catch (_) {
            notify('Could not load saved candidate actions. Refresh the candidate to retry.', 'error');
            return false;
        }
    }

    async function setStatus(card, status, checkbox) {
        const id = recordId(card);
        const saved = card && states.get(card);
        if (!id || !saved || !statuses.has(status) || !checkbox) {
            notify('The candidate record is not ready. Refresh it before changing status.', 'error');
            return false;
        }
        if (statusBusy.has(card)) {
            checkboxes(card, saved.status);
            return false;
        }
        const enabled = checkbox.checked;
        statusBusy.add(card);
        disableStatus(card, true);
        try {
            const body = new FormData();
            body.append('search_result_id', id);
            body.append('candidate_name', card.dataset.candidateName || 'Candidate');
            body.append('action_type', status);
            body.append('action_status', String(enabled));
            await request('/api/candidate-action', { method: 'POST', body });
            saved.status = enabled ? status : null;
            checkboxes(card, saved.status);
            if (enabled && typeof window.showStatusNotification === 'function') {
                window.showStatusNotification(card.dataset.candidateName || 'Candidate', status);
            } else {
                notify('Candidate status saved.', 'success');
            }
            if (typeof window.loadCandidateStatusCounts === 'function') {
                Promise.resolve().then(() => window.loadCandidateStatusCounts()).catch(() => {});
            }
            return true;
        } catch (_) {
            checkboxes(card, saved.status);
            notify('Candidate status was not confirmed saved. Refresh or retry.', 'error');
            return false;
        } finally {
            statusBusy.delete(card);
            disableStatus(card, false);
        }
    }

    function saveNotes(card, textarea) {
        const id = recordId(card);
        if (!id || !textarea) {
            notify('The candidate record is not ready. Your note has not been saved.', 'error');
            return Promise.resolve(false);
        }
        const comments = textarea.value;
        if (comments.length > 10000) {
            textarea.setAttribute('aria-invalid', 'true');
            notify('Candidate notes must be 10000 characters or fewer.', 'error');
            return Promise.resolve(false);
        }
        const version = (notesVersions.get(card) || 0) + 1;
        notesVersions.set(card, version);
        textarea.dataset.notesDirty = 'true';
        textarea.setAttribute('aria-busy', 'true');
        const operation = (notesChains.get(card) || Promise.resolve()).then(async () => {
            try {
                await request('/api/candidate-notes/' + encodeURIComponent(id), {
                    method: 'PATCH', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ comments })
                });
                const saved = states.get(card);
                if (saved) saved.comments = comments;
                if (notesVersions.get(card) === version && textarea.value === comments) {
                    textarea.removeAttribute('aria-invalid');
                    delete textarea.dataset.notesDirty;
                }
                return true;
            } catch (_) {
                textarea.setAttribute('aria-invalid', 'true');
                notify('Your note has not been confirmed saved. The text is kept here so you can retry.', 'error');
                return false;
            } finally {
                if (notesVersions.get(card) === version) textarea.removeAttribute('aria-busy');
            }
        });
        notesChains.set(card, operation);
        return operation;
    }

    window.CandidateState = { load, setStatus, saveNotes, checkboxes };
})();
