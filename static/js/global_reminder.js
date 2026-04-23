const GLOBAL_TOAST_ID = 'globalToastContainer';

function ensureToastContainer() {
    let container = document.getElementById(GLOBAL_TOAST_ID);
    if (!container) {
        container = document.createElement('div');
        container.id = GLOBAL_TOAST_ID;
        container.style.position = 'fixed';
        container.style.top = '20px';
        container.style.right = '24px';
        container.style.zIndex = '9999';
        container.style.display = 'flex';
        container.style.flexDirection = 'column';
        container.style.gap = '12px';
        document.body.appendChild(container);
    }
    return container;
}

function showGlobalToast(title, message) {
    const container = ensureToastContainer();

    const toast = document.createElement('div');
    toast.style.background = '#ffffff';
    toast.style.borderLeft = '4px solid #3b82f6';
    toast.style.boxShadow = '0 10px 25px rgba(0,0,0,0.1)';
    toast.style.padding = '16px 24px';
    toast.style.borderRadius = '8px';
    toast.style.display = 'flex';
    toast.style.alignItems = 'flex-start';
    toast.style.gap = '16px';
    toast.style.width = '320px';
    toast.style.transform = 'translateX(120%)';
    toast.style.transition = 'transform 0.4s ease';

    toast.innerHTML = `
        <div style="font-size:24px;line-height:1;">🔔</div>
        <div>
            <h4 style="font-size:15px;font-weight:600;color:#1e293b;margin:0 0 4px 0;">${title}</h4>
            <p style="font-size:13px;color:#64748b;margin:0;line-height:1.4;">${message}</p>
        </div>
    `;

    container.appendChild(toast);

    setTimeout(() => {
        toast.style.transform = 'translateX(0)';
    }, 50);

    setTimeout(() => {
        toast.style.transform = 'translateX(120%)';
        setTimeout(() => toast.remove(), 400);
    }, 5000);
}

function getCurrentReminderUser() {
    return localStorage.getItem('currentUser') || 'guest';
}

function loadGlobalReminders() {
    const currentUser = getCurrentReminderUser();
    const stored = localStorage.getItem(`reminders_${currentUser}`);
    if (!stored) return [];

    try {
        const reminders = JSON.parse(stored);
        return Array.isArray(reminders) ? reminders : [];
    } catch (e) {
        return [];
    }
}

function saveGlobalReminders(reminders) {
    const currentUser = getCurrentReminderUser();
    localStorage.setItem(`reminders_${currentUser}`, JSON.stringify(reminders));
}

function startGlobalReminderScheduler() {
    setInterval(() => {
        const currentUser = localStorage.getItem('currentUser');
        if (!currentUser) return;

        const reminders = loadGlobalReminders();
        if (!reminders.length) return;

        const now = new Date();
        const hours = String(now.getHours()).padStart(2, '0');
        const minutes = String(now.getMinutes()).padStart(2, '0');
        const seconds = now.getSeconds();
        const currentTime = `${hours}:${minutes}`;

        let changed = false;

        reminders.forEach(rm => {
            if (rm.time === currentTime && seconds === 0 && !rm.triggered) {
                showGlobalToast('健康日程提醒', rm.text);
                rm.triggered = true;
                changed = true;
            }

            if (currentTime < rm.time && rm.triggered) {
                rm.triggered = false;
                changed = true;
            }
        });

        if (changed) {
            saveGlobalReminders(reminders);
        }
    }, 1000);
}

document.addEventListener('DOMContentLoaded', () => {
    startGlobalReminderScheduler();
});
