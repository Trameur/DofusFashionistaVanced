
$.ajaxSetup({
  data: {csrfmiddlewaretoken: '{{ csrf_token }}' },
});

var itemTemplate =
'<div class="item-exchange-container"> \
    <div class="item-exchange-header"> \
    <table width="100%"><tr> \
    <td> \
        <div class="item-exchange-icon-container" style="display: inline-block"> \
        <img src="%imageSource%" class="item-exchange-icon"> \
        </div> \
    </td> \
    <td style="width: 100%"> \
    <div class="item-exchange-name">%name%</div> <br>\
    <div class="radio-buttons"> \
    <div class="item-atrib-text"><input type="radio" class="atrib"><span>%attributestitle%</span></div> \
    <div class="item-comp-text"><input type="radio" class="comp"><span>%comparisontitle%</span></div> \
    </div> \
    </td> \
    <td> \
    <div class="select-button-div" align="right"></div> \
    </td> \
    </tr></table> \
    </div> \
    <div class="item-exchange-violations">%violations%</div> \
    <div> \
    <div class="item-exchange-stats">%stats%</div> \
    <div class="item-exchange-comparison">%comparison%</div> \
    </div> \
    <br> \
</div>';

var loadUrl = "";
var popupStatFilters = [];
var popupStatOptions =
    (typeof statFilterOptions !== 'undefined' && Array.isArray(statFilterOptions) && statFilterOptions.length > 0)
        ? statFilterOptions
        : [
            {key: 'ap', label: gettext('AP')},
            {key: 'mp', label: gettext('MP')},
            {key: 'range', label: gettext('Range')},
            {key: 'summon', label: gettext('Summons')},
            {key: 'vit', label: gettext('Vitality')},
            {key: 'wis', label: gettext('Wisdom')},
            {key: 'str', label: gettext('Strength')},
            {key: 'int', label: gettext('Intelligence')},
            {key: 'cha', label: gettext('Chance')},
            {key: 'agi', label: gettext('Agility')}
        ];

function toggle_expand_header() {;
    $header = $(this);
    $violate = $header.next();
    $content = $violate.next();
    if ($content.css('display') == 'none') {
        if ($violate.text()){
            $violate.css("border-radius", "0");
        } else {
            $header.css("border-radius", "10px 10px 0px 0px");
        }
        $content.slideToggle(250);  
    } else {
        $content.slideToggle(250, function () {
            if ($violate.text()){
                $violate.css("border-radius", "0px 0px 10px 10px");
            } else {
                $violate.hide();
                $header.css("border-radius", "10px");
            
            }
        });
    }
}

function toggle_expand_violate() {;
    $violate = $(this);
    $content = $violate.next();
    if ($content.css('display') == 'none') {
        $violate.css("border-radius", "0");
        $content.slideToggle(250);
    } else {
        $content.slideToggle(250, function () {
            $violate.css("border-radius", "0px 0px 10px 10px");
        });
    }
}

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

function setPopUpDivSize(windowname, top, width) {
    var popUpDiv = document.getElementById(windowname);
    width = width / 2 - 250;
    popUpDiv.style.left = width + 'px';
    popUpDiv.style.top = top + 'px';
}

function popupSwitch(top) {
    windowname = 'popUpDiv';
    width = window_pos(top, 'blanket');
    setPopUpDivSize(windowname, top, width);
    toggleDiv(windowname);	
    blanket_size(windowname, top, 'blanket');
    toggleDiv('blanket');	
}

function clearSwitchDiv(thisItemName, imageURL) {
    loadUrl = imageURL;
    if (thisItemName != "") {
        $(".removing-div").text(gettext("Removing ") + thisItemName);
    } else {
        $(".removing-div").text(gettext("Adding Item"));
    }
    $(".search-div").empty();
    $(".weapon-order").empty();
    $(".items-to-add").empty();
    $(".items-to-add").append($('\
    <div class="loading-exchange-item-div"><br><br><br><br><br>\
    '+gettext("Loading")+'<br><br><br>\
    <img src='+imageURL+'></div>'));
    
}

function renderStatFilters() {
    var container = $(".stat-filters-div");
    container.empty();
    if (!popupStatFilters || popupStatFilters.length === 0) {
        return;
    }

    $.each(popupStatFilters, function(i, filterRow) {
        var row = $("<div class='stat-filter-row' style='margin-top: 6px;'></div>");
        var statSelect = $("<select class='filter-stat-key'></select>");
        statSelect.append($("<option value=''>" + gettext('Any stat') + "</option>"));

        $.each(popupStatOptions, function(_, statOption) {
            var option = $("<option></option>");
            option.val(statOption.key);
            option.text(statOption.label);
            if (filterRow.key === statOption.key) {
                option.prop('selected', true);
            }
            statSelect.append(option);
        });

        var minInput = $("<input type='number' class='filter-stat-min' style='width: 90px; margin-left: 6px;' />");
        minInput.attr('placeholder', gettext('Minimum'));
        if (filterRow.min !== undefined && filterRow.min !== null && filterRow.min !== '') {
            minInput.val(filterRow.min);
        }

        var removeButton = $("<button class='button-generic' style='margin-left: 6px;'>x</button>");
        statSelect.change(function() {
            popupStatFilters[i].key = $(this).val();
        });
        minInput.on('input', function() {
            popupStatFilters[i].min = $(this).val();
        });
        removeButton.click(function(e) {
            e.preventDefault();
            popupStatFilters.splice(i, 1);
            renderStatFilters();
        });

        row.append(statSelect);
        row.append(minInput);
        row.append(removeButton);
        container.append(row);
    });
}

function getStatFiltersPayload() {
    var rows = [];
    $.each(popupStatFilters, function(_, filterRow) {
        if (!filterRow.key) {
            return;
        }
        if (filterRow.min === undefined || filterRow.min === null || filterRow.min === '') {
            return;
        }
        var minValue = parseInt(filterRow.min, 10);
        if (isNaN(minValue)) {
            return;
        }
        rows.push({key: filterRow.key, min: minValue});
    });
    return rows;
}

function populateSwitchDivInitial(key, page, itemNames, char_id, thisItemName, callBack, showComparison, orderByStat = true) {
    if (thisItemName != "") {
        $(".removing-div").text(gettext("Removing ") + thisItemName);
    } else {
        $(".removing-div").text(gettext("Adding Item"));
    }
    $(".search-div").empty();
    searchString = gettext("Search");
    resetString = gettext("Reset");
    addFilterString = gettext("Add filter");
    $(".search-div").append($("\
    <div>\
        <input id='input-search-term'></input>\
        <button id='button-search' class='button-generic'>" + searchString + "</button>\
        <button id='button-reset' class='button-generic'>" + resetString + "</button>\
        <button id='button-add-stat-filter' class='button-generic' style='margin-left: 6px;'>" + addFilterString + "</button>\
    </div>\
    <div class='stat-filters-div' style='margin-top: 8px;'></div>"));
    renderStatFilters();
    $("#button-add-stat-filter").click(function(e) {
        e.preventDefault();
        popupStatFilters.push({key: '', min: ''});
        renderStatFilters();
    });
    $("#button-search").click(function() {
        populateSwitchDiv(key, page, itemNames, char_id, $('#input-search-term').val(), callBack, showComparison, orderByStat);
    });
    $("#button-reset").click(function() {
        $('#input-search-term').val('');
        populateSwitchDiv(key, page, itemNames, char_id, null, callBack, showComparison, orderByStat);
    });
    $(".weapon-order").empty();
    slot = key.toString();
    if (slot == 'weapon') {
        addWeaponRadioButtons(key, page, itemNames, char_id, thisItemName, callBack, showComparison);
        if (orderByStat) {
            $(".weap-stats").prop('checked', true);
            $(".weap-hits").prop('checked', false);
        } else {
            $(".weap-stats").prop('checked', false);
            $(".weap-hits").prop('checked', true);
        }
    }
    populateSwitchDiv(key, page, itemNames, char_id, null, callBack, showComparison, orderByStat);
    $("#input-search-term").keyup(function (e) {
        if (e.keyCode == 13) {
            $("#button-search").click();
        }
    });
}

function addWeaponRadioButtons(key, page, itemNames, char_id, thisItemName, callBack, showComparison)
{
    var data = {weaponstatstitle: gettext("Order by stats"), 
            weaponhitstitle: gettext("Order by hits")};
    
    var radioButtonsTemplate = "\
        <table class='radio-buttons' style='width: 100%'> \
            <tr style='width: 100%'> \
            <td class='weapon-order-hits-text' align='center'> \
                <input type='radio' class='weap-hits'><span>%weaponhitstitle%</span> \
            </td> \
            <td class='weapon-order-stats-text' align='center'> \
                <input type='radio' class='weap-stats'><span>%weaponstatstitle%</span> \
            </td> \
            </tr> \
        </table>";
        
    container = $(".weapon-order"); 
     
    var resolved = resolveAndAppend(container, radioButtonsTemplate, data);
    
    var hits = resolved.find(".weap-hits");
    var stats = resolved.find(".weap-stats");
    var hitsText = resolved.find(".weapon-order-hits-text");
    var statsText = resolved.find(".weapon-order-stats-text");
        
    hits.click(function(e){
        clearSwitchDiv(thisItemName, loadUrl);
        e.stopPropagation();
        radioWeaponHitsClick(hits, stats, key, page, itemNames, 
                             char_id, thisItemName, callBack, showComparison)
    });
    hitsText.click(function(e){
        clearSwitchDiv(thisItemName, loadUrl);
        e.stopPropagation();
        radioWeaponHitsClick(hits, stats, key, page, itemNames, char_id, 
                             thisItemName, callBack, showComparison)
    });
    stats.click(function(e){
        clearSwitchDiv(thisItemName, loadUrl);
        e.stopPropagation();
        radioWeaponStatsClick(hits, stats, key, page, itemNames, 
                              char_id, thisItemName, callBack, showComparison)
    });
    statsText.click(function(e){
        clearSwitchDiv(thisItemName, loadUrl);
        e.stopPropagation();
        radioWeaponStatsClick(hits, stats, key, page, itemNames, 
                              char_id, thisItemName, callBack, showComparison)
    });
    
}

function radioWeaponHitsClick(hits, stats, key, page, itemNames, char_id, thisItemName, callBack, showComparison){
    stats.prop('checked', false);
    hits.prop('checked', true);
    populateSwitchDivInitial(key, page, itemNames, char_id, thisItemName, callBack, showComparison, false);
}

function radioWeaponStatsClick(hits, stats, key, page, itemNames, char_id, thisItemName, callBack, showComparison){
    stats.prop('checked', true);
    hits.prop('checked', false);
    populateSwitchDivInitial(key, page, itemNames, char_id, thisItemName, callBack, showComparison, true)
}



function populateSwitchDiv(key, page, itemNames, char_id, searchTerm, callBack, showComparison, orderByStat = true) {
    var statFiltersPayload = JSON.stringify(getStatFiltersPayload());
    if (itemNames) {
        $.post("/itemexchange/" + char_id + "/",
               {slot: key.toString(), equip: itemNames[key], page: page, search_term: searchTerm, order_by_stat: orderByStat, stat_filters_json: statFiltersPayload},
               function(data) {
                   var response = data;
                   populateItems(response.items, response.violations, char_id, searchTerm, key.toString(), response.differences, callBack, showComparison, response.weapon_info);
                   setPage(response.page, response.max_page, key, itemNames, char_id, searchTerm, callBack, showComparison, orderByStat);
                   $(".item-exchange-header").click(toggle_expand_header);
                   $(".item-exchange-violations").click(toggle_expand_violate);
                   
                    var itemHeaders = $(".item-exchange-header");
                    $.each(itemHeaders, function(key, header) {
                        if (key > 2) {
                            header.click();
                        }
                    });
               });
    } else {
        $.post("/itemadd/" + char_id + "/",
               {slot: key.toString(), page: page, search_term: searchTerm, order_by_stat: orderByStat, stat_filters_json: statFiltersPayload},
               function(data) {
                   var response = data;
                   populateItems(response.items, response.violations, char_id, searchTerm, key.toString(), response.differences, callBack, showComparison, 0);
                   setPage(response.page, response.max_page, key, itemNames, char_id, searchTerm, callBack, showComparison, orderByStat);
                   $(".item-exchange-header").click(toggle_expand_header);
                   $(".item-exchange-violations").click(toggle_expand_violate);
                   
                    var itemHeaders = $(".item-exchange-header");
                    $.each(itemHeaders, function(key, header) {
                        if (key > 2) {
                            header.click();
                        }
                    });
               });
    }
}
function checkIfViolationsAreFatal(item, violations, char_id) {
    var violationsAreFatal = false;
    if (violations != null) {
        $.each(violations[item.name], function(key, violation) {
            violationsAreFatal |= violation.cant_equip;
        });
    }
    return violationsAreFatal;
}

function setItemViolations(item, violations, char_id) {
    var violationsString = "";
    var addLink = true;
    var violationsAreFatal = false;
    var removedOnly = false;
    if (violations != null) {
        $.each(violations[item.name], function(key, violation) {
            violationsAreFatal |= violation.cant_equip;
        });
        $.each(violations[item.name], function(key, violation) {
            if (violation.is_red) {
                violationsString += "<span class='item-exchange-violations-error'>";
            } else {
                violationsString += "<span class='item-exchange-violations-warning'>";
            }
            if (violation.condition_type === "removed") {
                violationsString += gettext("This item no longer exists");
                removedOnly = true;
            } else if (violation.condition_type === "min") {
                removedOnly = false;
                transViolationString = gettext("Violates %(item)s's condition:") + " %(stat)s > %(value)s";
                d = {
                    item: violation.item_name,
                    stat: violation.stat_name,
                    value: (violation.stat_value - 1)
                };
                violationsString += interpolate(transViolationString, d, true);
            } else if (violation.condition_type === "max") {
                removedOnly = false;
                transViolationString = gettext("Violates %(item)s's condition:") + " %(stat)s < %(value)s";
                d = {
                    item: violation.item_name,
                    stat: violation.stat_name,
                    value: (violation.stat_value + 1)
                };
                violationsString += interpolate(transViolationString, d, true);
            } else if (violation.condition_type === "min_eq") {
                removedOnly = false;
                transViolationString = gettext("Violates %(item)s's condition:") + " %(stat)s &ge; %(value)s";
                d = {
                    item: violation.item_name,
                    stat: violation.stat_name,
                    value: (violation.stat_value)
                };
                violationsString += interpolate(transViolationString, d, true);
            } else if (violation.condition_type === "max_eq") {
                removedOnly = false;
                transViolationString = gettext("Violates %(item)s's condition:") + " %(stat)s &le; %(value)s";
                d = {
                    item: violation.item_name,
                    stat: violation.stat_name,
                    value: (violation.stat_value)
                };
                violationsString += interpolate(transViolationString, d, true);
            } else if (violation.condition_type === "repeated") {
                removedOnly = false;
                transViolationString = gettext("%(item)s is already equipped");
                d = {
                    item: violation.item_name
                };
                violationsString += interpolate(transViolationString, d, true);
                addLink = false;
            } else if (violation.condition_type === "weird_light_set") {
                removedOnly = false;
                transViolationString = gettext("Violates %(item)s's condition:") + " %(condition_text)s";
                d = {
                    item: violation.item_name,
                    condition_text: violation.stat_name
                };
                violationsString += interpolate(transViolationString, d, true);
                addLink = false;
            } else if (violation.condition_type === "weird_prysmaradite") {
                removedOnly = false;
                transViolationString = gettext("Violates %(item)s's condition:") + " %(condition_text)s";
                d = {
                    item: violation.item_name,
                    condition_text: violation.stat_name
                };
                violationsString += interpolate(transViolationString, d, true);
                addLink = false;
            } else if (violation.condition_type === "shield") {
                removedOnly = false;
                transViolationString = gettext("Violates %(item)s's condition:") + " %(condition_text)s";
                d = {
                    item: violation.item_name,
                    condition_text: violation.stat_name
                };
                violationsString += interpolate(transViolationString, d, true);
                addLink = false;
            } else {
                console.log("Unknown violation of type " + violation.condition_type);
            }
            violationsString += "</span><br>";
        });
        if (violations[item.name].length > 0) {
            if (violationsAreFatal) {
                violationsString += "<span class='item-exchange-violations-error'>";
                violationsString += gettext("You cannot equip this item.");
                if (addLink) {
                    message = gettext(' To find a set including it, lock it <a href="/inclusions/%s/">here</a> and tailor a new set.');
                    violationsString += interpolate(message, [char_id]);
                }
                violationsString += "</span>";
            } else  if (removedOnly){
                violationsString += "</span>";
            } else {
                violationsString += "<span class='item-exchange-violations-warning'>";
                violationsString += gettext("You can equip this item, but some project minimums will not be respected.");
                if (addLink) {
                    message = gettext(' To find a set including it that fulfills these conditions, lock it <a href="/inclusions/%s/">here</a> and tailor a new set.');
                    violationsString += interpolate(message, [char_id]);
                }
                violationsString += "</span>";
            }
        }
    }
    return violationsString;
}

function setStats(item, weaponInfo) {
    var stats = "";
    if (item.type == "Weapon") {
        if (weaponInfo != 0) {
            stats += createWeaponHitDescription(weaponInfo, item);
            stats += '<hr class="solution-item-hr" />';
        }
        stats += item.damage_text;
        stats += '<hr class="solution-item-hr" />';
    }
    $.each(item.stats_lines, function(i, statLine) {
        var statText = normalizeStatLineText(statLine.text);
        if (statLine.formatting.indexOf("#r") != -1) {
            stats += '<span class="solution-negative-stat-text">' + statText + "</span>";
        } else if (statLine.formatting.indexOf("#c") != -1) {
            stats += '<span class="solution-condition-stat-text">' + statText + "</span>";
        } else {
            stats += statText;
        }
        stats += "<br>";
    });
    return stats;
}

function normalizeStatLineText(text) {
    if (!text) {
        return text;
    }
    // Ensure there is a space between a leading icon glyph and numeric value.
    return text.replace(/^([^\w\s<])(\d)/u, '$1 $2');
}

function setConditionLines(item) {
    conds = "";
    if (item.condition_lines && item.condition_lines.length > 0) {
        conds += '<hr class="solution-item-hr" />';
        $.each(item.condition_lines, function(i, conditionLine) {
            conds += normalizeStatLineText(conditionLine.text);
            conds += "<br>";
        });
    }
    return conds;
}

function createComparison(differences, item){
    var comparison = "";
    if (differences != null) {
        $.each(differences[item.name], function(i, statLine) {
            if (statLine.formatting.indexOf("#r") != -1) {
                comparison += '<span class="solution-negative-stat-text">' + statLine.text + "</span>";
            } else {
                comparison += "+" + statLine.text;
            }
            comparison += "<br>";
        });
        if (comparison === "") {
            comparison = gettext("There are no differences.");
        }
    }
    return comparison;
}

function populateItems(items, violations, char_id, searchTerm, slot, differences, callBack, showComparison, weaponInfo) {
    var container = $(".items-to-add");
    container.empty();
    container.scrollTop();
    if (items.length == 0) {
        container.append(document.createTextNode(gettext('No items found containing') + ' "' + searchTerm + '".'));
        return;
    }
    
    $.each(items, function(key, item) {
        var headerString = item.localized_name + '<br>' + gettext('Lvl.')+ ' ' + item.level;
        var violationsString = setItemViolations(item, violations, char_id);
        var violationsAreFatal = checkIfViolationsAreFatal(item, violations, char_id);
        var stats = setStats(item, weaponInfo);
        stats += setConditionLines(item);
        var comparison = createComparison(differences, item);
        var data = {name: headerString, violations: violationsString, stats: stats,
            imageSource: item.file, comparison: comparison, comparisontitle: gettext("Comparison"), 
            attributestitle: gettext("Attributes")};
        var resolved = resolveAndAppend(container, itemTemplate, data);
        
        if (showComparison == false) {
            resolved.find(".item-comp-text").remove();
        }
        var button = $("<button class='button-generic'>" + gettext("Select") + "</button>");
        button.click(function () {
            callBack(item.id, slot, char_id);
        });
        if (violationsAreFatal) {
            button.attr('disabled', 'disabled');
        }
        resolved.find(".select-button-div").append(button);
        
        var attributes = resolved.find(".atrib");
        var comparison = resolved.find(".comp");
        var attributesText = resolved.find(".item-atrib-text");
        var comparisonText = resolved.find(".item-comp-text");
        var attrDiv = resolved.find(".item-exchange-stats");
        var compDiv = resolved.find(".item-exchange-comparison");
        
        attributes.click(function(e){
            e.stopPropagation();
            radioAttributesClick(attributes, comparison, attrDiv, compDiv);
        });
        attributesText.click(function(e){
            e.stopPropagation();
            radioAttributesClick(attributes, comparison, attrDiv, compDiv);
        });
        comparison.click(function(e){
            e.stopPropagation();
            radioComparisonsClick(attributes, comparison, attrDiv, compDiv);
        });
        comparisonText.click(function(e){
            e.stopPropagation();
            radioComparisonsClick(attributes, comparison, attrDiv, compDiv);
        });
        
        resolved.find(".select-button-div").append(button);
        radioAttributesClick(attributes, comparison, attrDiv, compDiv);
        
    });
}

function createWeaponHitDescription(weaponInfo, item){
    string = '';
    if (weaponInfo[item.name].is_mageable && weaponInfo[item.name].element != 'neut'){
        var ele = weaponInfo[item.name].element;
        transRatingString = gettext("The average damage/AP of this weapon while %(element)s maged would be");
        d = {
            element: ele
        };
        string += interpolate(transRatingString, d, true);
    } else {
        string = gettext("The average damage/AP of this weapon would be");
    }
    var rating = weaponInfo[item.name].rating.toFixed(1);
    if (rating < 0) {
        rating = 0 - rating;
    }
    string += ' <b>' + rating + '</b>.';
    string += '<br>';
    if (weaponInfo[item.name].min_noncrit_dam > 0) {
        string += gettext('With the current set this weapon would hit ');
    } else {
        string += gettext('With the current set this weapon would <font color="#CC0000">heal</font> ');
    }
    
    var minNoncritDam = weaponInfo[item.name].min_noncrit_dam;
    var maxNoncritDam = weaponInfo[item.name].max_noncrit_dam;
    var minCritDam = weaponInfo[item.name].min_crit_dam;
    var maxCritDam = weaponInfo[item.name].max_crit_dam;
    if (minNoncritDam < 0) {
        minNoncritDam = 0 - minNoncritDam;
    }
    if (maxNoncritDam < 0) {
        maxNoncritDam = 0 - maxNoncritDam;
    }
    if (minCritDam < 0) {
        minCritDam = 0 - minCritDam;
    }
    if (maxCritDam < 0) {
        maxCritDam = 0 - maxCritDam;
    }
    
    if (minCritDam) {
        transDamString = gettext("from <b> %(minNonCrit)s </b> to <b> %(maxNoncritDam)s </b> on a normal hit, and from <b> %(minCritDam)s </b> to <b> %(maxCritDam)s </b> on a critical hit.");
        d = {
            minNonCrit: minNoncritDam,
            maxNoncritDam: maxNoncritDam,
            minCritDam: minCritDam,
            maxCritDam: maxCritDam
        };
        string += interpolate(transDamString, d, true);
    } else {
    
        transDamString = gettext("from <b> %(minNonCrit)s </b> to <b> %(maxNoncritDam)s </b> on a normal hit.");
        d = {
            minNonCrit: minNoncritDam,
            maxNoncritDam: maxNoncritDam
        };
        string += interpolate(transDamString, d, true);
    }
    return string;
}

function radioAttributesClick(attributes, comparison, attrDiv, compDiv){
    comparison.prop('checked', false);
    attributes.prop('checked', true);
    attrDiv.show();
    compDiv.hide();
}

function radioComparisonsClick(attributes, comparison, attrDiv, compDiv){
    comparison.prop('checked', true);
    attributes.prop('checked', false);
    attrDiv.hide();
    compDiv.show();
}

function setPage(page, maxPages, key, itemNames, char_id, searchTerm, callBack, showComparison, orderByStat) {
    var pages = [];
    page = parseInt(page);
    maxPages = parseInt(maxPages);
    if (page < 4){
        for (var i = 1; i <= page-1; i++)
        {
            pages.push(i);
        }
    } else {
        pages.push(1);
        
        for (var i = page-2; i <= page-1; i++)
        {
            pages.push(i);
        }
    }
    
    if (page + 2 >= maxPages){
        for (var i = page; i <= maxPages; i++)
        {
            pages.push(i);
        }
    } else {
        for (var i = page; i <= page + 2; i++)
        {
            pages.push(i);
        }
        pages.push(maxPages);
    }
    var div = $("#pages");
    div.empty();
    for (var i = 0; i < pages.length; i++) {
        if (pages[i] === page){
                div.append($("<label class='pages-current'> "+ page +" </label>"));
        } else {
            if (i === 0){
                var label = createPageLabel(pages[i], key, itemNames, char_id, searchTerm, callBack, showComparison, orderByStat);
                div.append(label);
            } else {
                    div.append($("<label class='pages-not-link'> </label>"));
                if (pages[i] > pages[i-1] + 1){
                    div.append($("<label class='pages-not-link'>... </label>"));
                }
                var label = createPageLabel(pages[i], key, itemNames, char_id, searchTerm, callBack, showComparison, orderByStat);
                div.append(label);
            }
        }
    }
}

function createPageLabel(page, key, itemNames, char_id, searchTerm, callBack, showComparison, orderByStat) {
    var label = $("<label class='pages-link'>" + page + "</label>");
    label.click(function() {
        populateSwitchDiv(key, page, itemNames, char_id, searchTerm, callBack, showComparison, orderByStat);
    });
    return label;
}

