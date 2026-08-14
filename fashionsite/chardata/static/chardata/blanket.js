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

// The blanket has to cover the whole page, but a popup is centred on what the
// visitor can actually see.
function window_pos(top, blanketName) {
    var root = document.body.parentNode;
    var viewportwidth = root.clientWidth || window.innerWidth;
    var blanket = document.getElementById(blanketName);
    blanket.style.width = Math.max(viewportwidth, root.scrollWidth) + 'px';
    return viewportwidth;
}

function popup(top, window, blanket) {
    window_pos(top, blanket);
    toggleDiv(window);	
    blanket_size(window, top, blanket);
    toggleDiv(blanket);	
}
