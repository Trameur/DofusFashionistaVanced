
$.ajaxSetup({
  data: {csrfmiddlewaretoken: '{{ csrf_token }}' },
});

var itemTemplate =
'<div class="compare-item-container"> \
    <div class="compare-item-header"> \
    <table width="100%"><tr> \
    <td> \
        <div class="solution-item-icon-container" style="display: inline-block"> \
        <img src="%imageSource%" alt="%name%" class="item-icon"> \
        </div> \
    </td> \
    <td style="width: 100%"> \
    <div class="compare-item-name"> <b> %name% </b><br> '+gettext("Lvl.")+' %level%%extra%</div> <br>\
    </td> \
    <td> \
    <input type="button" class="button-thin" id="compare-button-close" value="'+gettext("Close")+'" />\
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

// Same box as the solution page, and the same rule: centred on the width it
// really has, which on a phone is the screen less a margin.
function windowPosSeriously(popUpDivVar, top) {
    var root = document.body.parentNode;
    var viewportwidth = root.clientWidth || window.innerWidth;
    var blanket3 = document.getElementById('blanket');
    blanket3.style.width = Math.max(viewportwidth, root.scrollWidth) + 'px';
    var popUpDiv = document.getElementById(popUpDivVar);
    // popupSeriously is also how the popup closes, and a hidden box measures
    // zero.
    if (!popUpDiv.getBoundingClientRect().width) {
        return;
    }
    popUpDiv.style.top = top + 'px';
    popUpDiv.style.left = '0px';
    var box = popUpDiv.getBoundingClientRect();
    var wanted = Math.max(10, Math.round((viewportwidth - box.width) / 2));
    popUpDiv.style.left = Math.round(wanted - box.left) + 'px';
}

function popupSeriously(top) {
    windowname = 'popUpDiv';
    toggle(windowname);
    windowPosSeriously(windowname, top);
    blanketSizeSeriously(windowname, top);
    toggle('blanket');
}

function getItemStats(itemId) {
    $.post(window.compareItemStatsUrl || "/get_item_stats_compare/",
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
            if (statLine.range_text) {
                stats += ' <span class="solution-stat-range">('
                    + statLine.range_text + ')</span>';
            }
            stats += (window.spellTipHtml ? window.spellTipHtml(statLine) : '');
            stats += "<br>";
        });
        if (data.condition_lines && data.condition_lines.length > 0) {
            stats += '<hr class="solution-item-hr" />';
            $.each(data.condition_lines, function(i, conditionLine) {
                stats += conditionLine.text;
                stats += "<br>";
            });
        }
        // Same secondary lines as the switch popup: the set tells same-named
        // pieces apart, the source says whether you can craft or must farm it.
        var extra = '';
        if (data.localized_set_name) {
            extra += '<br><span class="compare-item-meta">' + gettext('Set') + ': '
                + data.localized_set_name + '</span>';
        }
        if (data.acquisition_text) {
            extra += '<br><span class="compare-item-meta">' + data.acquisition_text
                + '</span>';
        }
        var dict = {name: data.localized_name || data.or_name, stats: stats,
                    imageSource: data.file, level: data.level, extra: extra};
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
