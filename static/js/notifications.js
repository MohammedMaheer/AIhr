(function () {
    'use strict';
    const timers = new WeakMap();
    function show(message, type = 'info') {
        type = ['success', 'error', 'warning', 'info'].includes(type) ? type : 'info';
        let root = document.getElementById('app-notifications');
        if (!root) {
            root = document.createElement('section');
            root.id = 'app-notifications';
            root.className = 'app-notifications';
            root.setAttribute('aria-label', 'Notifications');
            root.setAttribute('data-notifications-root', '');
            document.body.appendChild(root);
        }
        const text = String(message ?? '');
        const duplicate = [...root.children].find(e => e.dataset.type === type && e.querySelector('.app-notification-message').textContent === text);
        if (duplicate) return duplicate;
        while (root.children.length >= 4) {
            const oldest = root.firstElementChild;
            clearTimeout(timers.get(oldest)); oldest.remove();
        }
        const toast = document.createElement('div');
        toast.className = 'app-notification app-notification-' + type;
        toast.dataset.type = type;
        toast.setAttribute('role', type === 'error' ? 'alert' : 'status');
        toast.setAttribute('aria-atomic', 'true');
        const icon = document.createElement('i');
        icon.className = 'fas fa-' + {success:'check-circle',error:'exclamation-circle',warning:'exclamation-triangle',info:'info-circle'}[type];
        icon.setAttribute('aria-hidden','true');
        const body = document.createElement('div');
        body.className = 'app-notification-message'; body.textContent = text;
        const close = document.createElement('button');
        close.type = 'button'; close.setAttribute('aria-label','Dismiss notification'); close.title = 'Dismiss notification';
        const closeIcon = document.createElement('i');
        closeIcon.className = 'fas fa-times'; closeIcon.setAttribute('aria-hidden','true'); close.appendChild(closeIcon);
        const dismiss = () => { clearTimeout(timers.get(toast)); toast.remove(); };
        close.addEventListener('click',dismiss);
        toast.append(icon,body,close); root.appendChild(toast);
        const delay = {success:6000,info:8000,warning:12000,error:0}[type];
        if (delay) {
            const start = () => { clearTimeout(timers.get(toast)); timers.set(toast,setTimeout(dismiss,delay)); };
            toast.addEventListener('mouseenter',() => clearTimeout(timers.get(toast)));
            toast.addEventListener('mouseleave',start);
            toast.addEventListener('focusin',() => clearTimeout(timers.get(toast)));
            toast.addEventListener('focusout',start);
            start();
        }
        return toast;
    }
    window.AppNotifications = {show};
}());
