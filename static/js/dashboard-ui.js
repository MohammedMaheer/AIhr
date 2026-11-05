(function () {
    'use strict';
    let dialogState = null;
    const sidebar = document.getElementById('sidebar');
    const toggle = document.getElementById('sidebarToggle');
    const close = document.getElementById('admin-navigation-close');
    const backdrop = document.getElementById('admin-navigation-backdrop');
    const main = document.querySelector('main');
    const mobile = window.matchMedia('(max-width: 1023px)');
    let navigationOpen = false;

    function focusable(root) {
        return [...root.querySelectorAll('a[href],button,input,select,textarea,[tabindex="0"]')]
            .filter(e => !e.disabled && e.type !== 'hidden' && !e.closest('.hidden')
                && getComputedStyle(e).display !== 'none' && getComputedStyle(e).visibility !== 'hidden');
    }

    function trap(event, root) {
        if (event.key !== 'Tab') return;
        const items = focusable(root);
        const first = items[0], last = items[items.length - 1];
        if (!first) { event.preventDefault(); root.focus(); return; }
        if (event.shiftKey && (document.activeElement === first || !root.contains(document.activeElement))) {
            event.preventDefault(); last.focus();
        } else if (!event.shiftKey && (document.activeElement === last || !root.contains(document.activeElement))) {
            event.preventDefault(); first.focus();
        }
    }

    function setNavigation(opened, restore = true) {
        navigationOpen = mobile.matches && opened;
        sidebar.classList.toggle('-translate-x-full', !navigationOpen);
        sidebar.inert = mobile.matches && !navigationOpen;
        main.inert = navigationOpen;
        backdrop.hidden = !navigationOpen;
        toggle.setAttribute('aria-expanded', String(navigationOpen));
        toggle.setAttribute('aria-label', navigationOpen ? 'Close navigation' : 'Open navigation');
        if (navigationOpen) {
            sidebar.setAttribute('role', 'dialog');
            sidebar.setAttribute('aria-modal', 'true');
            close.focus();
        } else {
            sidebar.removeAttribute('role');
            sidebar.removeAttribute('aria-modal');
            if (restore && mobile.matches) toggle.focus();
        }
    }

    function closeDialog(modal) {
        if (!modal) return;
        modal.classList.add('hidden');
        if (dialogState?.modal !== modal) return;
        const previous = dialogState;
        dialogState = null;
        for (const [element, inert] of previous.inert) element.inert = inert;
        document.body.style.overflow = previous.overflow;
        setNavigation(false, false);
        if (previous.focus?.isConnected && !previous.focus.closest('[inert],.hidden')) previous.focus.focus();
        else main.focus();
    }

    function openDialog(modal) {
        if (dialogState) closeDialog(dialogState.modal);
        if (navigationOpen) setNavigation(false, false);
        dialogState = {modal, focus: document.activeElement, overflow: document.body.style.overflow,
            inert: [...document.body.children].filter(e => e !== modal && !e.contains(modal) && !e.hasAttribute('data-notifications-root')).map(e => [e, e.inert])};
        modal.classList.remove('hidden');
        modal.setAttribute('role', 'dialog');
        modal.setAttribute('aria-modal', 'true');
        modal.setAttribute('aria-label', modal.querySelector('h2,h3,h4')?.textContent.trim() || 'Dialog');
        modal.tabIndex = -1;
        for (const [element] of dialogState.inert) element.inert = true;
        document.body.style.overflow = 'hidden';
        modal.querySelectorAll('label').forEach((label, index) => {
            if (label.control) return;
            const controls = label.parentElement.querySelectorAll('input:not([type="hidden"]),select,textarea');
            if (controls.length !== 1) return;
            const field = controls[0];
            if (!field.id) field.id = `${modal.id}-field-${index}`;
            label.htmlFor = field.id;
        });
        modal.querySelectorAll('button').forEach(button => {
            if (!button.textContent.trim() && !button.hasAttribute('aria-label')) {
                button.setAttribute('aria-label', button.title || (button.querySelector('.fa-times') ? 'Close dialog' : 'Dialog action'));
            }
        });
        (focusable(modal)[0] || modal).focus();
    }

    toggle.addEventListener('click', () => setNavigation(!navigationOpen));
    close.addEventListener('click', () => setNavigation(false));
    backdrop.addEventListener('click', () => setNavigation(false));
    sidebar.addEventListener('click', event => {
        if (navigationOpen && event.target.closest('a[href]')) {
            setNavigation(false, false);
            main.focus();
        }
    });
    document.addEventListener('keydown', event => {
        const root = dialogState?.modal || (navigationOpen ? sidebar : null);
        if (!root) return;
        if (event.key === 'Escape') {
            event.preventDefault();
            if (dialogState) closeDialog(dialogState.modal);
            else setNavigation(false);
        } else trap(event, root);
    });
    mobile.addEventListener('change', () => {
        if (dialogState) return;
        const focused = document.activeElement;
        setNavigation(false, false);
        if (mobile.matches && sidebar.contains(focused)) toggle.focus();
        else if (!mobile.matches && (focused === toggle || focused === close)) focusable(sidebar)[0]?.focus();
    });
    setNavigation(false, false);
    window.AdminUI = {openDialog, closeDialog};
}());
