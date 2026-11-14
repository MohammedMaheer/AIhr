(function () {
    'use strict';
    const identity = () => JSON.stringify([window.currentUser?.id, window.currentUser?.user_type, window.currentUser?.company]);
    const esc = value => {
        const node = document.createElement('span');
        node.textContent = String(value ?? '');
        return node.innerHTML.replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    };
    function offer(root, data) {
        if (!root || root.querySelector('[data-find-similar]') || !Array.isArray(data.results) || data.results.length ||
            typeof data.query !== 'string' || !data.query.trim() || !Array.isArray(data.folder_filters) ||
            !data.resume_filters || typeof data.resume_filters !== 'object' || Array.isArray(data.resume_filters)) return;
        const scope = JSON.parse(JSON.stringify({query:data.query, folders:data.folder_filters,
            filters:data.resume_filters, count:data.requested_result_count || 10}));
        const owner = identity();
        const button = document.createElement('button');
        button.type = 'button';
        button.dataset.findSimilar = '';
        button.className = 'workspace-button is-primary similar-candidates-action';
        button.innerHTML = '<i class="fas fa-search" aria-hidden="true"></i>Search for similar candidates';
        root.firstElementChild?.append(button);
        button.addEventListener('click', () => {
            if (document.querySelector('[data-similar-dialog]') || owner !== identity()) return;
            const modal = document.createElement('div');
            modal.dataset.similarDialog = '';
            modal.className = 'workspace-overlay';
            modal.innerHTML = '<section class="workspace-dialog similar-candidates-dialog"><header><h3>Closest available profiles</h3>' +
                '<button type="button" data-close class="workspace-icon-button" aria-label="Close similar candidates" title="Close"><i class="fas fa-times" aria-hidden="true"></i></button></header>' +
                '<div class="workspace-dialog-body"><p class="similar-candidates-note">Similar profiles, not verified exact matches. Original folders, tags and dates are retained.</p>' +
                '<p class="workspace-muted similar-candidates-query"></p><div data-suggestions role="status" aria-live="polite"></div></div>' +
                '<footer><span class="workspace-muted">Indexed details may be incomplete. Check the original CV.</span><button type="button" data-close class="workspace-button">Close</button></footer></section>';
            modal.querySelector('.similar-candidates-query').textContent = scope.query;
            document.body.append(modal);
            window.bindScheduleDialog?.(modal, 'Similar candidates', button);
            let controller, timer;
            const alive = () => modal.isConnected && button.isConnected && root.isConnected && owner === identity();
            const close = () => {controller?.abort(); clearTimeout(timer); modal.remove();};
            modal.querySelectorAll('[data-close]').forEach(node => node.addEventListener('click', close));
            modal.addEventListener('click', event => {if (event.target === modal) close();});
            const cleanup = new MutationObserver(() => {
                if (!alive()) {cleanup.disconnect(); close();}
            });
            cleanup.observe(document.body, {childList:true, subtree:true});
            const output = modal.querySelector('[data-suggestions]');
            async function load() {
                if (!alive() || button.disabled) return;
                button.disabled = true;
                output.textContent = 'Finding the closest profiles...';
                controller = new AbortController();
                timer = setTimeout(() => controller.abort(), 20000);
                const form = new FormData();
                form.set('query', scope.query);
                form.set('result_count', String(scope.count));
                if (scope.folders.length) form.set('folders', JSON.stringify(scope.folders));
                form.set('filters', JSON.stringify(scope.filters));
                try {
                    const response = await fetch('/api/similar-candidates', {method:'POST', body:form,
                        credentials:'same-origin', signal:controller.signal});
                    const value = await response.json();
                    if (!response.ok || value.success !== true || !Array.isArray(value.results)) throw new Error('Unavailable');
                    if (!alive()) return;
                    if (!value.results.length) {
                        output.textContent = 'No profiles are available within the selected folders, tags and dates.';
                        return;
                    }
                    output.innerHTML = '<p class="workspace-count">'+value.results.length+' similar profile'+(value.results.length === 1 ? '' : 's')+'</p><ol class="similar-candidates-list">' +
                        value.results.map(row => {
                            const years = Number.isFinite(row.experience_years) ? row.experience_years+' years' : 'Experience not recorded';
                            const misses = Array.isArray(row.unmet_criteria) ? row.unmet_criteria : [];
                            const labels = {skill:'Skill', location:'Location', experience_years:'Experience', language:'Language'};
                            const download = typeof row.file_path === 'string' && row.file_path.startsWith('gs://')
                                ? '<a class="workspace-icon-button" href="/api/download-resume?file_path='+encodeURIComponent(row.file_path)+'" aria-label="Download '+esc(row.file_name)+'" title="Download CV"><i class="fas fa-download" aria-hidden="true"></i></a>' : '';
                            return '<li><div class="similar-candidates-row"><strong>'+esc(row.file_name || 'CV')+'</strong>'+download+'</div>' +
                                '<p class="workspace-muted">'+esc(years)+' &middot; '+esc(row.location || 'Location not recorded')+'</p>' +
                                '<p class="similar-candidates-gap">'+(misses.length ? 'Not matched or not confirmed:' : 'Requirements need CV review.')+'</p>' +
                                (misses.length ? '<ul>'+misses.slice(0,12).map(m=>'<li>'+esc(labels[m.criterion] || 'Requirement')+': '+esc(String(m.required ?? '').slice(0,200))+'</li>').join('')+'</ul>' : '')+'</li>';
                        }).join('')+'</ol>';
                } catch (_) {
                    if (!alive()) return;
                    output.innerHTML = '<p role="alert">Similar candidates could not be loaded. Please try again.</p><button type="button" data-retry class="workspace-button"><i class="fas fa-redo" aria-hidden="true"></i>Try again</button>';
                    output.querySelector('[data-retry]').addEventListener('click', load);
                } finally {clearTimeout(timer); button.disabled = false;}
            }
            load();
        });
    }
    window.SimilarCandidates = {offer};
})();
