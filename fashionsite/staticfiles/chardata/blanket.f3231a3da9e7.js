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
