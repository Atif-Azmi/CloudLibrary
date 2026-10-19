// CloudLibrary - Neumorphic UI JavaScript Helpers

document.addEventListener('DOMContentLoaded', function () {
    // 1. Live Clock & Date for the Neumorphic Stat Widget
    function updateLiveClock() {
        const timeEl = document.getElementById('liveClockTime');
        const dateEl = document.getElementById('liveClockDate');
        if (!timeEl) return;

        const now = new Date();
        const hours = String(now.getHours()).padStart(2, '0');
        const minutes = String(now.getMinutes()).padStart(2, '0');
        const seconds = String(now.getSeconds()).padStart(2, '0');
        timeEl.textContent = `${hours}:${minutes}:${seconds}`;

        if (dateEl) {
            const options = { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' };
            dateEl.textContent = now.toLocaleDateString(undefined, options);
        }
    }

    if (document.getElementById('liveClockTime')) {
        updateLiveClock();
        setInterval(updateLiveClock, 1000);
    }

    // 2. Auto-dismiss alerts after 5 seconds
    const alerts = document.querySelectorAll('.neo-alert');
    alerts.forEach(function (alert) {
        setTimeout(function () {
            alert.style.opacity = '0';
            alert.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
            alert.style.transform = 'translateY(-10px)';
            setTimeout(function () {
                if (alert.parentNode) {
                    alert.parentNode.removeChild(alert);
                }
            }, 400);
        }, 5000);
    });

    // 3. Mobile Navigation Drawer Toggle
    const navToggleBtn = document.getElementById('navToggleBtn');
    const navMenuCollapse = document.getElementById('navMenuCollapse');
    if (navToggleBtn && navMenuCollapse) {
        navToggleBtn.addEventListener('click', function () {
            navMenuCollapse.classList.toggle('show');
            const icon = navToggleBtn.querySelector('i');
            if (icon) {
                if (navMenuCollapse.classList.contains('show')) {
                    icon.className = 'bi bi-x-lg';
                } else {
                    icon.className = 'bi bi-list';
                }
            }
        });
    }
});

/**
 * Quick-fill demo credentials on the login page
 * @param {string} role - 'admin' or 'student'
 */
function fillDemoCredentials(role) {
    const usernameInput = document.getElementById('username');
    const passwordInput = document.getElementById('password');

    if (usernameInput && passwordInput) {
        if (role === 'admin') {
            usernameInput.value = 'admin';
            passwordInput.value = 'admin123';
        } else if (role === 'student') {
            usernameInput.value = 'student1';
            passwordInput.value = 'student123';
        }
    }
}

/**
 * Toggle the demo accounts drawer on the login page
 */
function toggleDemoAccounts() {
    const drawer = document.getElementById('demoAccountsDrawer');
    const icon = document.getElementById('demoToggleIcon');
    if (!drawer) return;

    if (drawer.style.display === 'none' || drawer.style.display === '') {
        drawer.style.display = 'block';
        if (icon) icon.className = 'bi bi-chevron-up ms-1';
    } else {
        drawer.style.display = 'none';
        if (icon) icon.className = 'bi bi-chevron-down ms-1';
    }
}
