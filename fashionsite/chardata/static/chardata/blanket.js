function toggleDiv(div_id) {
    var el = document.getElementById(div_id);
    if ( el.style.display == 'none' ) {	
        el.style.display = 'block';
    } else {
        el.style.display = 'none';
    }
}

function blanket_size(popUpDivVar, top, blanketName) {
    if (typeof window.innerWidth != 'undefined') {
        viewportheight = window.innerHeight;
    } else {
        viewportheight = document.documentElement.clientHeight;
    }
    if ((viewportheight > document.body.parentNode.scrollHeight) && (viewportheight > document.body.parentNode.clientHeight)) {
        blanket_height = viewportheight;
    } else {
        if (document.body.parentNode.clientHeight > document.body.parentNode.scrollHeight) {
            blanket_height = document.body.parentNode.clientHeight;
        } else {
            blanket_height = document.body.parentNode.scrollHeight;
        }
    }
    var popUpDiv = document.getElementById(popUpDivVar);
    if (950 + top > blanket_height) { //size of popup
        blanket_height = 950 + top;
    }
    var blanket = document.getElementById(blanketName);
    blanket.style.height = blanket_height + 'px';
}

function window_pos(top, blanketName) {
    if (typeof window.innerWidth != 'undefined') {
        viewportwidth = window.innerHeight;
    } else {
        viewportwidth = document.documentElement.clientHeight;
    }
    if ((viewportwidth > document.body.parentNode.scrollWidth) && (viewportwidth > document.body.parentNode.clientWidth)) {
        window_width = viewportwidth;
    } else {
        if (document.body.parentNode.clientWidth > document.body.parentNode.scrollWidth) {
            window_width = document.body.parentNode.clientWidth;
        } else {
            window_width = document.body.parentNode.scrollWidth;
        }
    }
    var blanket = document.getElementById(blanketName);
    blanket.style.width = window_width + 'px';
    return window_width;
}

function popup(top, window, blanket) {
    window_pos(top, blanket);
    toggleDiv(window);	
    blanket_size(window, top, blanket);
    toggleDiv(blanket);	
}

function setupMobileMenuToggle() {
    var sidebar = document.querySelector('.sidebar');
    if (!sidebar || document.getElementById('mobile-menu-toggle')) {
        return;
    }

    var button = document.createElement('button');
    button.id = 'mobile-menu-toggle';
    button.className = 'mobile-menu-toggle';
    button.type = 'button';
    button.setAttribute('aria-expanded', 'true');
    button.textContent = 'Hide menu';

    sidebar.parentNode.insertBefore(button, sidebar);

    var mobileQuery = window.matchMedia('(max-width: 1100px)');
    var storageKey = 'fashionista-mobile-menu-collapsed';
    var showText = 'Show menu';
    var hideText = 'Hide menu';

    function readCollapsedState() {
        try {
            var stored = sessionStorage.getItem(storageKey);
            if (stored === null) {
                return true;
            }
            return stored === '1';
        } catch (error) {
            return true;
        }
    }

    function writeCollapsedState(isCollapsed) {
        try {
            sessionStorage.setItem(storageKey, isCollapsed ? '1' : '0');
        } catch (error) {
            return;
        }
    }

    function applyCollapsedState(isCollapsed) {
        document.body.classList.toggle('mobile-menu-collapsed', isCollapsed);
        var maincolumn = document.querySelector('.maincolumn');
        var secondcolumn = document.querySelector('.secondcolumn');
        if (maincolumn) {
            maincolumn.style.marginLeft = isCollapsed ? '0px' : '';
        }
        if (secondcolumn) {
            secondcolumn.style.marginLeft = isCollapsed ? '0px' : '';
        }
        button.textContent = isCollapsed ? showText : hideText;
        button.setAttribute('aria-expanded', isCollapsed ? 'false' : 'true');
    }

    function syncWithViewport() {
        if (mobileQuery.matches) {
            button.style.display = 'block';
            applyCollapsedState(readCollapsedState());
        } else {
            button.style.display = 'none';
            document.body.classList.remove('mobile-menu-collapsed');
            var maincolumn = document.querySelector('.maincolumn');
            var secondcolumn = document.querySelector('.secondcolumn');
            if (maincolumn) {
                maincolumn.style.marginLeft = '';
            }
            if (secondcolumn) {
                secondcolumn.style.marginLeft = '';
            }
            button.textContent = hideText;
            button.setAttribute('aria-expanded', 'true');
        }
    }

    button.addEventListener('click', function() {
        var isCollapsed = !document.body.classList.contains('mobile-menu-collapsed');
        applyCollapsedState(isCollapsed);
        writeCollapsedState(isCollapsed);
    });

    if (typeof mobileQuery.addEventListener === 'function') {
        mobileQuery.addEventListener('change', syncWithViewport);
    } else if (typeof mobileQuery.addListener === 'function') {
        mobileQuery.addListener(syncWithViewport);
    }

    syncWithViewport();
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setupMobileMenuToggle);
} else {
    setupMobileMenuToggle();
}
