
$.ajaxSetup({
  data: {csrfmiddlewaretoken: '{{ csrf_token }}' },
});

var itemTemplate =
'<div class="compare-item-container"> \
    <div class="compare-item-header"> \
    <table width="100%"><tr> \
    <td> \
        <div class="solution-item-icon-container" style="display: inline-block"> \
        <img src="%imageSource%" class="item-icon"> \
        </div> \
    </td> \
    <td style="width: 100%"> \
    <div class="compare-item-name"> <b> %name% </b><br> Lv. %level%</div> <br>\
    </td> \
    <td> \
    <input type="button" class="button-thin" id="compare-button-close" value="Close" />\
    </td> \
    </tr></table> \
    </div> \
    <div class="compare-item-stats">%stats%</div> \
</div>';

function template(t, data){
    return t.replace(/%(\w*)%/g,
        function(m, key){
            return data.hasOwnProperty(key) ? data[key] : "";
        });
}

function resolveAndAppend(section, t, data) {
    var resolved = $(template(t, data));
    section.append(resolved);
    return resolved;
}

function toggle(div_id) {
    var el = document.getElementById(div_id);
    if ( el.style.display == 'none' ) {	
        el.style.display = 'block';
    } else {
        el.style.display = 'none';
    }
}

function blanketSizeSeriously(popUpDivVar, top) {
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
    var blanket3 = document.getElementById('blanket');
    blanket3.style.height = blanket_height + 'px';
}

function windowPosSeriously(popUpDivVar, top) {
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
    var blanket3 = document.getElementById('blanket');
    blanket3.style.width = window_width + 'px';
    var popUpDiv = document.getElementById(popUpDivVar);
    window_width = window_width / 2 - 250;
    popUpDiv.style.left = window_width + 'px';
    var popUpDiv = document.getElementById(popUpDivVar);
    popUpDiv_height = top;
    popUpDiv.style.top = popUpDiv_height + 'px';
}

function popupSeriously(top) {
    windowname = 'popUpDiv';
    windowPosSeriously(windowname, top);
    toggle(windowname);	
    blanketSizeSeriously(windowname, top);
    toggle('blanket');	
}

function getItemStats(itemId) {
    $.post("/get_item_stats_compare/",
           {itemId: itemId},
           function(data) {
               populatePopUp(data);
           });
}

function populatePopUp(data) {
        var stats = "";
        if (data.type == "Weapon") {
            stats += data.damage_text;
            stats += '<hr class="solution-item-hr" />';
        }
        $.each(data.stats_lines, function(i, statLine) {
            if (statLine.formatting.indexOf("#r") != -1) {
                stats += '<span class="solution-negative-stat-text">' + statLine.text + "</span>";
            } else if (statLine.formatting.indexOf("#c") != -1) {
                stats += '<span class="solution-condition-stat-text">' + statLine.text + "</span>";
            } else {
                stats += statLine.text;
            }
            stats += "<br>";
        });
        if (data.condition_lines && data.condition_lines.length > 0) {
            stats += '<hr class="solution-item-hr" />';
            $.each(data.condition_lines, function(i, conditionLine) {
                stats += conditionLine.text;
                stats += "<br>";
            });
        }
        var dict = {name: data.or_name, stats: stats, imageSource: data.file,
                    level: data.level};
        var container = $(".item-stats");
        container.empty();
        var resolved = resolveAndAppend(container, itemTemplate, dict);
        $("#compare-button-close").click(function() {
             top = $(window).scrollTop().pageYOffset + 10;
             popupSeriously(top);
         });
        top = $(window).scrollTop();
        popupSeriously(top.pageYOffset + 150);
}
