// 文件位置：static/js/mobile.js
// 手机端抽屉侧边栏控制

(function () {
    function getSidebar() {
        return document.querySelector('.sidebar');
    }

    function getMask() {
        return document.querySelector('.mobile-mask');
    }

    window.toggleMobileSidebar = function () {
        const sidebar = getSidebar();
        const mask = getMask();
        if (sidebar) sidebar.classList.add('mobile-open');
        if (mask) mask.classList.add('active');
        document.body.classList.add('mobile-sidebar-open');
    };

    window.closeMobileSidebar = function () {
        const sidebar = getSidebar();
        const mask = getMask();
        if (sidebar) sidebar.classList.remove('mobile-open');
        if (mask) mask.classList.remove('active');
        document.body.classList.remove('mobile-sidebar-open');
    };

    document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape') {
            window.closeMobileSidebar();
        }
    });

    document.addEventListener('click', function (event) {
        const target = event.target;
        if (target && target.closest && target.closest('.sidebar .nav-item')) {
            window.closeMobileSidebar();
        }
    });
})();
