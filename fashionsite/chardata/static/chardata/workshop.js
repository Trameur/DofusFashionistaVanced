(function () {
    'use strict';

    var MAX_OWNED_DEFAULT = 9999999;
    var MAX_QUANTITY = 999;
    var SAVE_DEBOUNCE_MS = 400;
    var MAX_KEYS_PER_REQUEST_DEFAULT = 300;
    var MAX_SUBRECIPE_DEPTH = 8;

    function clampOwned(raw, max) {
        var limit = max || MAX_OWNED_DEFAULT;
        var n = parseInt(raw, 10);
        if (!isFinite(n) || isNaN(n) || n < 0) {
            return 0;
        }
        return Math.min(n, limit);
    }

    function clampQuantity(raw) {
        var n = parseInt(raw, 10);
        if (!isFinite(n) || isNaN(n) || n < 1) {
            return 1;
        }
        return Math.min(n, MAX_QUANTITY);
    }

    function rowState(owned, need) {
        owned = owned || 0;
        need = need || 0;
        if (need <= 0) {
            return 'done';
        }
        if (owned <= 0) {
            return 'none';
        }
        if (owned >= need) {
            return 'done';
        }
        return 'part';
    }

    function cardState(rows) {
        if (!rows || !rows.length) {
            return 'norecipe';
        }
        var doneCount = 0;
        var anyOwned = false;
        for (var i = 0; i < rows.length; i++) {
            var owned = rows[i].owned || 0;
            if (rowState(owned, rows[i].need) === 'done') {
                doneCount++;
            }
            if (owned > 0) {
                anyOwned = true;
            }
        }
        if (doneCount === rows.length) {
            return 'done';
        }
        if (!anyOwned) {
            return 'none';
        }
        return 'part';
    }

    function stillMissing(total, owned) {
        return Math.max(0, (total || 0) - (owned || 0));
    }

    function subrecipeChildNeed(childQuantity, intermediateNeed, intermediateOwned) {
        return (childQuantity || 0) * stillMissing(intermediateNeed, intermediateOwned);
    }

    function cardMatchesFilter(state, filter) {
        if (filter === 'ready') {
            return state === 'done';
        }
        if (filter === 'progress') {
            return state === 'part';
        }
        if (filter === 'notstarted') {
            return state === 'none' || state === 'norecipe';
        }
        return true;
    }

    function filterCounts(states) {
        var counts = {all: 0, ready: 0, progress: 0, notstarted: 0};
        (states || []).forEach(function (state) {
            counts.all++;
            if (state === 'done') {
                counts.ready++;
            } else if (state === 'part') {
                counts.progress++;
            } else {
                counts.notstarted++;
            }
        });
        return counts;
    }

    var CARD_SORT_RANK = {none: 0, part: 1, done: 2, norecipe: 3};

    function sortCards(cards, sortKey) {
        var indexed = (cards || []).map(function (card, i) {
            return {card: card, i: i};
        });
        indexed.sort(function (a, b) {
            var diff = 0;
            if (sortKey === 'level') {
                diff = (b.card.level || 0) - (a.card.level || 0);
            } else if (sortKey === 'name') {
                diff = String(a.card.name || '').localeCompare(String(b.card.name || ''));
            } else if (sortKey === 'state') {
                var rankA = CARD_SORT_RANK[a.card.state];
                var rankB = CARD_SORT_RANK[b.card.state];
                diff = (rankA === undefined ? 3 : rankA) - (rankB === undefined ? 3 : rankB);
            } else {
                diff = (a.card.order || 0) - (b.card.order || 0);
            }
            return diff !== 0 ? diff : a.i - b.i;
        });
        return indexed.map(function (entry) { return entry.card; });
    }

    function keyOf(ankamaId, subtype) {
        return String(ankamaId) + ':' + String(subtype);
    }

    function format(template, vars) {
        return String(template == null ? '' : template).replace(/\{(\w+)\}/g, function (whole, name) {
            return Object.prototype.hasOwnProperty.call(vars, name) ? String(vars[name]) : whole;
        });
    }

    function chunkKeys(keys, size) {
        var limit = size > 0 ? size : keys.length;
        var chunks = [];
        for (var offset = 0; offset < keys.length; offset += limit) {
            chunks.push(keys.slice(offset, offset + limit));
        }
        return chunks;
    }

    function sourceKind(info) {
        if (info && info.monsters && info.monsters.length) {
            return 'drops';
        }
        if (info && info.crafted) {
            return 'crafted';
        }
        return 'none';
    }

    function formatDropRate(rate) {
        if (!rate || rate <= 0) {
            return '0%';
        }
        if (rate < 0.01) {
            return '< 0.01%';
        }
        return (Math.round(rate * 100) / 100) + '%';
    }

    function csvField(value, separator) {
        var s = value === null || value === undefined ? '' : String(value);
        var sep = separator || ',';
        if (/["\r\n]/.test(s) || s.indexOf(sep) !== -1) {
            s = '"' + s.replace(/"/g, '""') + '"';
        }
        return s;
    }

    function buildCsv(headers, rows, separator) {
        var sep = separator || ',';
        var field = function (value) { return csvField(value, sep); };
        var lines = [(headers || []).map(field).join(sep)];
        (rows || []).forEach(function (row) {
            lines.push((row || []).map(field).join(sep));
        });
        return lines.join('\r\n');
    }

    function buildMissingListText(items) {
        return (items || [])
            .filter(function (item) { return (item.missing || 0) > 0; })
            .map(function (item) { return item.name + ': ' + item.missing; })
            .join('\n');
    }

    function csvSeparatorFor(language) {
        return String(language || 'en').slice(0, 2).toLowerCase() === 'en' ? ',' : ';';
    }

    function buildMissingListCsv(items, headers, separator) {
        headers = headers || {};
        var rows = (items || []).map(function (item) {
            return [item.name, item.needed || 0, item.owned || 0, item.missing || 0];
        });
        var csv = buildCsv(
            [headers.name, headers.needed, headers.owned, headers.missing], rows, separator);
        return String.fromCharCode(0xFEFF) + csv;
    }

    function hideGatheredFromStored(stored) {
        return stored !== '0';
    }

    function shoppingRowHidden(hideGathered, gathered, focused) {
        return !!(hideGathered && gathered && !focused);
    }

    var pure = {
        clampOwned: clampOwned,
        clampQuantity: clampQuantity,
        rowState: rowState,
        cardState: cardState,
        stillMissing: stillMissing,
        keyOf: keyOf,
        format: format,
        chunkKeys: chunkKeys,
        cardMatchesFilter: cardMatchesFilter,
        filterCounts: filterCounts,
        sortCards: sortCards,
        sourceKind: sourceKind,
        formatDropRate: formatDropRate,
        csvField: csvField,
        buildCsv: buildCsv,
        buildMissingListText: buildMissingListText,
        buildMissingListCsv: buildMissingListCsv,
        csvSeparatorFor: csvSeparatorFor,
        subrecipeChildNeed: subrecipeChildNeed,
        hideGatheredFromStored: hideGatheredFromStored,
        shoppingRowHidden: shoppingRowHidden
    };

    if (typeof window === 'undefined' || !document.getElementById('ws-list')) {
        if (typeof window !== 'undefined') {
            window.FashionWorkshop = pure;
        }
        return;
    }

    var cfg = window.WORKSHOP_CONFIG || {};
    var i18n = cfg.i18n || {};

    function jsonData(id) {
        var el = document.getElementById(id);
        if (!el) {
            return null;
        }
        try {
            return JSON.parse(el.textContent);
        } catch (e) {
            return null;
        }
    }

    var cardRows = jsonData('ws-card-rows-data') || {};
    var resourceTotals = jsonData('ws-resource-totals-data') || [];
    var resourceTotalsByKey = {};
    resourceTotals.forEach(function (item) {
        resourceTotalsByKey[keyOf(item.ankama_id, item.subtype)] = item;
    });
    var stock = jsonData('ws-stock-data') || {};
    var hideGathered = loadHideGathered();
    var stockLimits = jsonData('ws-stock-limits-data') || {};
    var maxOwned = stockLimits.max_owned || MAX_OWNED_DEFAULT;
    var maxKeysPerRequest = stockLimits.max_keys_per_request || MAX_KEYS_PER_REQUEST_DEFAULT;

    var csrfInput = document.querySelector('#ws-csrf input[name=csrfmiddlewaretoken]');
    var csrf = csrfInput ? csrfInput.value : '';

    var cardsById = {};
    var multipliers = {};
    var rowElsByKey = {};
    var resourceIndex = {};
    var pendingKeys = {};
    var editSeq = 0;
    var failedSaves = 0;
    var MAX_SAVE_RETRIES = 3;
    var saveTimer = null;
    var qtyTimers = {};
    var saving = false;
    var removedIds = {};
    var currentFilter = 'all';
    var currentSort = 'added';
    var undoClearTimer = null;
    var SORT_STORAGE_KEY = 'wsSort';
    var sourceCache = {};
    var subrecipeCache = {};
    var subrecipeDependents = {};

    function postJson(url, payload) {
        return fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrf,
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify(payload)
        }).then(function (response) {
            return response.json().catch(function () {
                return {};
            }).then(function (data) {
                return {ok: response.ok, status: response.status, data: data};
            });
        });
    }

    function postForm(url, data) {
        var body = new URLSearchParams(data || {});
        body.append('csrfmiddlewaretoken', csrf);
        return fetch(url, {
            method: 'POST',
            headers: {'X-Requested-With': 'XMLHttpRequest'},
            body: body
        }).then(function (response) {
            return response.json().catch(function () {
                return {};
            });
        });
    }

    function announce(text) {
        var el = document.getElementById('ws-save-status');
        if (el) {
            el.textContent = text || '';
        }
    }

    function announceUndo(text, onUndo) {
        clearTimeout(undoClearTimer);
        var el = document.getElementById('ws-undo-status');
        if (!el) {
            return;
        }
        el.textContent = '';
        el.appendChild(document.createTextNode((text || '') + ' '));
        var btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'ws-undo-inline';
        btn.textContent = i18n.undoButton || '';
        btn.addEventListener('click', function () {
            clearTimeout(undoClearTimer);
            el.textContent = '';
            onUndo();
        });
        el.appendChild(btn);
        undoClearTimer = setTimeout(function () {
            if (el.contains(btn)) {
                el.textContent = '';
            }
        }, 10000);
    }

    function buildResourceIndex() {
        Object.keys(cardRows).forEach(function (itemId) {
            (cardRows[itemId] || []).forEach(function (row) {
                var key = keyOf(row.ankama_id, row.subtype);
                var entry = resourceIndex[key];
                if (!entry) {
                    entry = resourceIndex[key] = {meta: row, items: {}};
                }
                entry.items[itemId] = (entry.items[itemId] || 0) + (row.quantity || 0);
            });
        });
    }

    function liveTotalNeed(key) {
        var entry = resourceIndex[key];
        if (!entry) {
            return 0;
        }
        var total = 0;
        Object.keys(entry.items).forEach(function (itemId) {
            total += entry.items[itemId] * (multipliers[itemId] || 1);
        });
        return total;
    }

    function cardRowsWithState(itemId) {
        return (cardRows[itemId] || []).map(function (row) {
            var key = keyOf(row.ankama_id, row.subtype);
            return {
                owned: stock[key] || 0,
                need: (row.quantity || 0) * (multipliers[itemId] || 1)
            };
        });
    }

    function registerRow(key, entry) {
        (rowElsByKey[key] = rowElsByKey[key] || []).push(entry);
    }

    function iconEl(cls) {
        var span = document.createElement('span');
        span.className = 'fm-ico ' + cls;
        span.setAttribute('aria-hidden', 'true');
        return span;
    }

    function renderSourcePanel(panel, info) {
        panel.innerHTML = '';
        var kind = sourceKind(info);
        if (kind === 'crafted') {
            var craftedLine = document.createElement('p');
            craftedLine.className = 'ws-source-line';
            craftedLine.textContent = i18n.craftableLabel || '';
            panel.appendChild(craftedLine);
            return;
        }
        if (kind === 'none') {
            var emptyLine = document.createElement('p');
            emptyLine.className = 'ws-source-line';
            emptyLine.textContent = i18n.noKnownDrop || '';
            panel.appendChild(emptyLine);
            return;
        }
        var list = document.createElement('ul');
        list.className = 'ws-source-list';
        (info.monsters || []).forEach(function (monster) {
            var item = document.createElement('li');
            item.className = 'ws-source-monster';

            var nameEl = document.createElement('span');
            nameEl.className = 'ws-source-name';
            if (monster.url) {
                var link = document.createElement('a');
                link.href = monster.url;
                link.textContent = monster.name;
                nameEl.appendChild(link);
            } else {
                nameEl.textContent = monster.name;
            }
            item.appendChild(nameEl);

            if (monster.level) {
                var levelEl = document.createElement('span');
                levelEl.className = 'ws-source-level';
                levelEl.textContent = monster.level;
                item.appendChild(levelEl);
            }

            var rateEl = document.createElement('span');
            rateEl.className = 'ws-source-rate';
            rateEl.textContent = formatDropRate(monster.rate);
            item.appendChild(rateEl);

            if (monster.has_conditions && monster.conditions_text) {
                var condEl = document.createElement('span');
                condEl.className = 'ws-source-conditions';
                condEl.textContent = monster.conditions_text;
                item.appendChild(condEl);
            }

            list.appendChild(item);
        });
        panel.appendChild(list);
    }

    function fetchSource(key, panel) {
        panel.textContent = i18n.loading || '';
        fetch(cfg.sourcesUrl + '?keys=' + encodeURIComponent(key), {
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        }).then(function (response) {
            return response.json();
        }).then(function (data) {
            var info = (data && data.sources && data.sources[key])
                || {monsters: [], crafted: false};
            sourceCache[key] = info;
            renderSourcePanel(panel, info);
        }).catch(function () {
            panel.textContent = i18n.saveError || '';
        });
    }

    function buildSourceDisclosure(key) {
        var wrap = document.createElement('div');
        wrap.className = 'ws-source-wrap';

        var toggle = document.createElement('button');
        toggle.type = 'button';
        toggle.className = 'ws-source-toggle';
        toggle.setAttribute('aria-expanded', 'false');
        toggle.textContent = i18n.whereToGetIt || '';

        var panel = document.createElement('div');
        panel.className = 'ws-source-panel';
        panel.setAttribute('aria-live', 'polite');
        panel.hidden = true;

        toggle.addEventListener('click', function () {
            var expanded = toggle.getAttribute('aria-expanded') === 'true';
            if (expanded) {
                toggle.setAttribute('aria-expanded', 'false');
                panel.hidden = true;
                return;
            }
            toggle.setAttribute('aria-expanded', 'true');
            panel.hidden = false;
            if (sourceCache[key] !== undefined) {
                renderSourcePanel(panel, sourceCache[key]);
            } else {
                fetchSource(key, panel);
            }
        });

        wrap.appendChild(toggle);
        wrap.appendChild(panel);
        return wrap;
    }

    function registerSubrecipeDependent(parentKey, entry) {
        (subrecipeDependents[parentKey] = subrecipeDependents[parentKey] || []).push(entry);
    }

    function cascadeSubrecipe(key) {
        (subrecipeDependents[key] || []).forEach(function (entry) {
            updateRow(entry);
            cascadeSubrecipe(entry.el.getAttribute('data-res-key'));
        });
    }

    function fetchSubrecipe(key, depth, ancestorPath, callback) {
        if (subrecipeCache[key] !== undefined) {
            callback(subrecipeCache[key]);
            return;
        }
        var url = cfg.subrecipeUrl + '?keys=' + encodeURIComponent(key) + '&depth=' + depth;
        if (ancestorPath.length) {
            url += '&path=' + encodeURIComponent(ancestorPath.join(','));
        }
        fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}}).then(function (response) {
            if (!response.ok) {
                throw new Error('subrecipe request failed');
            }
            return response.json();
        }).then(function (data) {
            var info = (data && data.subrecipes && data.subrecipes[key])
                || {found: false, children: []};
            subrecipeCache[key] = info;
            callback(info);
        }).catch(function () {
            callback(null);
        });
    }

    function renderSubrecipePanel(panel, key, meta, getNeed, depth, ancestorPath, onDone) {
        panel.innerHTML = '';

        if (meta.craftable_item_id) {
            var addBtn = document.createElement('button');
            addBtn.type = 'button';
            addBtn.className = 'ws-mini-btn ws-subrecipe-add';
            addBtn.textContent = i18n.addAsOwnCard || '';
            addBtn.addEventListener('click', function () {
                postForm(cfg.addUrl, {item_id: meta.craftable_item_id, quantity: 1})
                    .then(function (resp) {
                        if (resp && resp.success) {
                            announce(format(i18n.addedAsCard || '', {name: meta.name}));
                        } else {
                            announce((resp && resp.error) || i18n.saveError || '');
                        }
                    }).catch(function () {
                        announce(i18n.saveError || '');
                    });
            });
            panel.appendChild(addBtn);
        }

        var body = document.createElement('div');
        body.className = 'ws-subrecipe-body';
        body.textContent = i18n.loading || '';
        panel.appendChild(body);

        fetchSubrecipe(key, depth, ancestorPath, function (info) {
            body.innerHTML = '';
            if (!info) {
                var errMsg = document.createElement('p');
                errMsg.className = 'ws-source-line';
                errMsg.textContent = i18n.saveError || '';
                body.appendChild(errMsg);
                if (onDone) {
                    onDone(false);
                }
                return;
            }
            var children = (info.found && !info.cycle) ? info.children : [];
            if (!children.length) {
                var msg = document.createElement('p');
                msg.className = 'ws-source-line';
                msg.textContent = i18n.noSubrecipe || '';
                body.appendChild(msg);
                if (onDone) {
                    onDone(true);
                }
                return;
            }
            var list = document.createElement('ul');
            list.className = 'ws-subrecipe-list';
            var selfPath = ancestorPath.concat([key]);
            children.forEach(function (child) {
                var childKey = keyOf(child.ankama_id, child.subtype);
                var childGetNeed = function () {
                    return subrecipeChildNeed(child.quantity, getNeed(), stock[key] || 0);
                };
                var entry = buildRowElement(childKey, child, childGetNeed, 'subrecipe', null);
                registerSubrecipeDependent(key, entry);
                list.appendChild(entry.el);
                updateRow(entry);

                if (child.craftable && depth < MAX_SUBRECIPE_DEPTH
                    && selfPath.indexOf(childKey) === -1) {
                    entry.el.appendChild(buildSubrecipeDisclosure(
                        childKey, child, childGetNeed, depth + 1, selfPath));
                }
            });
            body.appendChild(list);
            if (onDone) {
                onDone(true);
            }
        });
    }

    function buildSubrecipeDisclosure(key, meta, getNeed, depth, ancestorPath) {
        var wrap = document.createElement('div');
        wrap.className = 'ws-subrecipe-wrap';

        var toggle = document.createElement('button');
        toggle.type = 'button';
        toggle.className = 'ws-subrecipe-toggle';
        toggle.setAttribute('aria-expanded', 'false');
        toggle.setAttribute('aria-label', format(i18n.showSubrecipe, {name: meta.name}));
        toggle.textContent = i18n.craftableLabel || '';

        var panel = document.createElement('div');
        panel.className = 'ws-subrecipe-panel';
        panel.setAttribute('aria-live', 'polite');
        panel.hidden = true;

        var loaded = false;

        toggle.addEventListener('click', function () {
            var expanded = toggle.getAttribute('aria-expanded') === 'true';
            if (expanded) {
                toggle.setAttribute('aria-expanded', 'false');
                panel.hidden = true;
                return;
            }
            toggle.setAttribute('aria-expanded', 'true');
            panel.hidden = false;
            if (!loaded) {
                renderSubrecipePanel(panel, key, meta, getNeed, depth, ancestorPath,
                    function (ok) {
                        loaded = ok;
                    });
            }
        });

        wrap.appendChild(toggle);
        wrap.appendChild(panel);
        return wrap;
    }

    function buildRowElement(key, meta, getNeed, context, itemId) {
        var owned = stock[key] || 0;

        var li = document.createElement('li');
        li.className = 'ws-row';
        li.setAttribute('data-res-key', key);

        if (meta.image_url) {
            var img = document.createElement('img');
            img.className = 'ws-row-img';
            img.src = meta.image_url;
            img.alt = '';
            li.appendChild(img);
        } else {
            var placeholder = document.createElement('span');
            placeholder.className = 'ws-row-img';
            li.appendChild(placeholder);
        }

        var nameEl = document.createElement('span');
        nameEl.className = 'ws-row-name';
        var link = meta.local_item_url || meta.resource_url;
        if (link) {
            var a = document.createElement('a');
            a.href = link;
            a.textContent = meta.name;
            nameEl.appendChild(a);
        } else {
            nameEl.textContent = meta.name;
        }
        li.appendChild(nameEl);

        var needEl = document.createElement('span');
        needEl.className = 'ws-row-need';
        var needIcon = iconEl('');
        var needText = document.createElement('span');
        needText.className = 'ws-row-need-text';
        needEl.appendChild(needIcon);
        needEl.appendChild(needText);
        li.appendChild(needEl);

        var ctl = document.createElement('div');
        ctl.className = 'ws-row-ctl';

        var zeroBtn = document.createElement('button');
        zeroBtn.type = 'button';
        zeroBtn.className = 'ws-step ws-step-zero';
        zeroBtn.textContent = '0';
        zeroBtn.setAttribute('aria-label', format(i18n.setZeroLabel, {name: meta.name}));
        zeroBtn.addEventListener('click', function () {
            setStockValue(key, 0);
        });
        ctl.appendChild(zeroBtn);

        var input = document.createElement('input');
        input.type = 'text';
        input.inputMode = 'numeric';
        input.pattern = '[0-9]*';
        input.className = 'ws-num pretty-input ws-owned-input';
        input.setAttribute('data-res-key', key);
        input.setAttribute('aria-label', format(i18n.ownedLabel, {name: meta.name}));
        input.value = String(owned);
        input.addEventListener('input', function () {
            setStockValue(key, input.value);
        });
        input.addEventListener('change', function () {
            input.value = String(stock[key] || 0);
        });
        ctl.appendChild(input);

        var maxBtn = document.createElement('button');
        maxBtn.type = 'button';
        maxBtn.className = 'ws-step ws-step-max';
        maxBtn.textContent = i18n.maxButton || 'Max';
        maxBtn.setAttribute('aria-label', format(i18n.setMaxLabel, {name: meta.name}));
        maxBtn.addEventListener('click', function () {
            var target;
            if (context === 'card') {
                var row = (cardRows[itemId] || []).filter(function (r) {
                    return keyOf(r.ankama_id, r.subtype) === key;
                })[0];
                var perUnit = row ? row.quantity : 0;
                target = Math.max(stock[key] || 0, perUnit * (multipliers[itemId] || 1));
            } else if (context === 'subrecipe') {
                target = Math.max(stock[key] || 0, getNeed());
            } else {
                target = liveTotalNeed(key);
            }
            setStockValue(key, target);
        });
        ctl.appendChild(maxBtn);

        li.appendChild(ctl);

        var extra = null;
        var sharedNote = null;
        if (context === 'card') {
            sharedNote = document.createElement('div');
            sharedNote.className = 'ws-row-shared';
            sharedNote.hidden = true;
            li.appendChild(sharedNote);
        } else if (context === 'list') {
            extra = document.createElement('div');
            extra.className = 'ws-row-extra';
            var missingSpan = document.createElement('span');
            missingSpan.className = 'ws-row-missing';
            var usedBySpan = document.createElement('span');
            usedBySpan.className = 'ws-row-usedby';
            extra.appendChild(missingSpan);
            extra.appendChild(usedBySpan);
            li.appendChild(extra);
            li.appendChild(buildSourceDisclosure(key));
        }

        var entry = {
            el: li,
            input: input,
            needIcon: needIcon,
            needText: needText,
            nameEl: nameEl,
            sharedNote: sharedNote,
            extra: extra,
            meta: meta,
            getNeed: getNeed,
            context: context,
            usedBy: meta.used_by
        };
        registerRow(key, entry);
        return entry;
    }

    var STATE_ICON = {done: 'fm-ico-check', part: 'fm-ico-warn', none: 'fm-ico-close'};

    function updateRow(entry) {
        var key = entry.el.getAttribute('data-res-key');
        var owned = stock[key] || 0;
        var need = entry.getNeed();
        var state = rowState(owned, need);

        entry.el.setAttribute('data-state', state);
        entry.needIcon.className = 'fm-ico ' + (STATE_ICON[state] || '');
        entry.needText.textContent = owned + ' / ' + need;
        entry.nameEl.classList.toggle('ws-row-name-done', state === 'done');

        if (document.activeElement !== entry.input) {
            entry.input.value = String(owned);
        }

        if (entry.context === 'card' && entry.sharedNote) {
            var total = liveTotalNeed(key);
            if (state === 'done' && total > owned) {
                entry.sharedNote.hidden = false;
                entry.sharedNote.textContent = format(i18n.sharedNote, {
                    total: total,
                    missing: stillMissing(total, owned)
                });
            } else {
                entry.sharedNote.hidden = true;
                entry.sharedNote.textContent = '';
            }
        }

        if (entry.context === 'list' && entry.extra) {
            var missing = stillMissing(need, owned);
            entry.extra.querySelector('.ws-row-missing').textContent =
                format(i18n.stillMissingLabel, {count: missing});
            entry.extra.querySelector('.ws-row-usedby').textContent =
                format(i18n.usedByLabel, {count: entry.usedBy || 0});
        }
    }

    function refreshCardFooter(itemId) {
        var card = cardsById[itemId];
        if (!card || removedIds[itemId] || card.dataset.missing === '1') {
            return;
        }
        var rows = cardRowsWithState(itemId);
        var state = cardState(rows);
        var progress = card.querySelector('.ws-progress');
        var progressBar = progress ? progress.querySelector('span') : null;
        var status = card.querySelector('.ws-status');
        var statusIcon = status ? status.querySelector('.fm-ico') : null;
        var statusText = status ? status.querySelector('.ws-status-text') : null;
        var craftBtn = card.querySelector('.ws-craft-btn');
        if (craftBtn) {
            craftBtn.hidden = state !== 'done';
        }

        if (state === 'norecipe') {
            card.removeAttribute('data-state');
            if (progress) {
                progress.hidden = true;
            }
            if (statusIcon) {
                statusIcon.className = 'fm-ico';
                statusIcon.hidden = true;
            }
            if (statusText) {
                statusText.textContent = i18n.noRecipe || '';
            }
            return;
        }

        card.setAttribute('data-state', state);

        var doneCount = rows.filter(function (r) {
            return rowState(r.owned, r.need) === 'done';
        }).length;
        var pct = rows.length ? Math.round((doneCount / rows.length) * 100) : 0;

        if (progress) {
            progress.hidden = false;
            progress.setAttribute('aria-valuenow', String(pct));
            var name = card.querySelector('.ws-name');
            if (name) {
                progress.setAttribute('aria-label', name.textContent.trim());
            }
            progress.setAttribute('aria-valuetext', doneCount + ' / ' + rows.length);
            if (progressBar) {
                progressBar.style.width = pct + '%';
            }
        }

        if (statusIcon) {
            statusIcon.hidden = false;
        }
        if (state === 'done') {
            if (statusIcon) {
                statusIcon.className = 'fm-ico fm-ico-check';
            }
            if (statusText) {
                statusText.textContent = i18n.ready || '';
            }
        } else if (state === 'none') {
            if (statusIcon) {
                statusIcon.className = 'fm-ico fm-ico-close';
            }
            if (statusText) {
                statusText.textContent = i18n.notStarted || '';
            }
        } else {
            if (statusIcon) {
                statusIcon.className = 'fm-ico fm-ico-warn';
            }
            if (statusText) {
                statusText.textContent = format(i18n.progress, {done: doneCount, total: rows.length});
            }
        }
    }

    function cardStateForFilter(itemId) {
        var card = cardsById[itemId];
        if (!card || removedIds[itemId]) {
            return 'norecipe';
        }
        if (card.dataset.missing === '1') {
            return 'norecipe';
        }
        return cardState(cardRowsWithState(itemId));
    }

    function updateFilterChipCounts(counts) {
        var spans = {
            all: document.getElementById('ws-chip-all'),
            ready: document.getElementById('ws-chip-ready'),
            progress: document.getElementById('ws-chip-progress'),
            notstarted: document.getElementById('ws-chip-notstarted')
        };
        Object.keys(spans).forEach(function (key) {
            if (spans[key]) {
                spans[key].textContent = String(counts[key] || 0);
            }
        });
    }

    function refreshSummary() {
        var el = document.getElementById('ws-summary');
        var totalCards = 0;
        var readyCards = 0;
        var filterStates = [];
        Object.keys(cardsById).forEach(function (itemId) {
            var card = cardsById[itemId];
            if (removedIds[itemId]) {
                card.hidden = true;
                return;
            }
            totalCards++;
            var state = cardStateForFilter(itemId);
            filterStates.push(state);
            if (state === 'done') {
                readyCards++;
            }
            card.hidden = !cardMatchesFilter(state, currentFilter);
        });

        var missingResources = 0;
        Object.keys(resourceIndex).forEach(function (key) {
            if (stillMissing(liveTotalNeed(key), stock[key] || 0) > 0) {
                missingResources++;
            }
        });

        if (el) {
            var readyText = format(i18n.summaryReady, {ready: readyCards, total: totalCards});
            var missingText = format(i18n.summaryMissing, {count: missingResources});
            el.textContent = totalCards ? (readyText + '  ·  ' + missingText) : '';
        }

        updateFilterChipCounts(filterCounts(filterStates));
    }

    function refreshKey(key) {
        (rowElsByKey[key] || []).forEach(updateRow);
        cascadeSubrecipe(key);
        var entry = resourceIndex[key];
        if (entry) {
            Object.keys(entry.items).forEach(refreshCardFooter);
        }
        refreshSummary();
        applyHideGathered(hideGathered);
    }

    function setStockValue(key, raw) {
        stock[key] = clampOwned(raw, maxOwned);
        editSeq++;
        pendingKeys[key] = editSeq;
        refreshKey(key);
        scheduleSave();
    }

    function scheduleSave() {
        clearTimeout(saveTimer);
        saveTimer = setTimeout(flushSave, SAVE_DEBOUNCE_MS);
    }

    function stockUpdatesFor(keys) {
        return keys.map(function (key) {
            var sep = key.lastIndexOf(':');
            return {
                ingredient_ankama_id: parseInt(key.slice(0, sep), 10),
                subtype: key.slice(sep + 1),
                owned: stock[key] || 0
            };
        });
    }

    function flushSave() {
        var allKeys = Object.keys(pendingKeys);
        if (!allKeys.length || saving) {
            return;
        }
        var firstChunk = chunkKeys(allKeys, maxKeysPerRequest)[0];
        var sentSeq = {};
        firstChunk.forEach(function (key) {
            sentSeq[key] = pendingKeys[key];
        });
        saving = true;
        postJson(cfg.stockUrl, {updates: stockUpdatesFor(firstChunk)}).then(function (result) {
            saving = false;
            if (result.ok && result.data && result.data.success) {
                failedSaves = 0;
                firstChunk.forEach(function (key) {
                    if (pendingKeys[key] === sentSeq[key]) {
                        delete pendingKeys[key];
                    }
                });
                announce(i18n.saved || '');
                if (Object.keys(pendingKeys).length) {
                    scheduleSave();
                }
            } else {
                saveFailed(result.status >= 500);
            }
        }).catch(function () {
            saving = false;
            saveFailed(true);
        });
    }

    function saveFailed(retryable) {
        announce(i18n.saveError || '');
        if (retryable && failedSaves < MAX_SAVE_RETRIES) {
            failedSaves++;
            clearTimeout(saveTimer);
            saveTimer = setTimeout(flushSave, 3000 * failedSaves);
        }
    }

    function flushPendingOnUnload() {
        var keys = Object.keys(pendingKeys);
        chunkKeys(keys, maxKeysPerRequest).forEach(function (chunk) {
            try {
                fetch(cfg.stockUrl, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrf,
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    body: JSON.stringify({updates: stockUpdatesFor(chunk)}),
                    keepalive: true
                });
            } catch (e) {}
        });
    }

    function sortedResourceTotals() {
        return resourceTotals.slice().sort(function (a, b) {
            var aKey = keyOf(a.ankama_id, a.subtype);
            var bKey = keyOf(b.ankama_id, b.subtype);
            var aMissing = stillMissing(a.quantity, stock[aKey] || 0) > 0 ? 0 : 1;
            var bMissing = stillMissing(b.quantity, stock[bKey] || 0) > 0 ? 0 : 1;
            if (aMissing !== bMissing) {
                return aMissing - bMissing;
            }
            return String(a.name || '').localeCompare(String(b.name || ''));
        });
    }

    function buildCards() {
        document.querySelectorAll('.ws-card').forEach(function (card) {
            var itemId = card.dataset.itemId;
            cardsById[itemId] = card;
            var qtyInput = card.querySelector('.ws-qty-input');
            multipliers[itemId] = clampQuantity(qtyInput ? qtyInput.value : 1);
            if (qtyInput) {
                qtyInput.value = String(multipliers[itemId]);
                qtyInput.addEventListener('input', function () {
                    onQuantityChange(card, qtyInput);
                });
                qtyInput.addEventListener('change', function () {
                    qtyInput.value = String(multipliers[itemId]);
                });
            }

            var removeBtn = card.querySelector('.ws-remove');
            if (removeBtn) {
                removeBtn.addEventListener('click', function () {
                    var workshopId = removeBtn.getAttribute('data-workshop-id');
                    postForm(cfg.removeUrlBase + workshopId + '/').then(function (resp) {
                        if (resp && resp.success) {
                            window.location.reload();
                        } else {
                            announce(i18n.saveError || '');
                        }
                    }).catch(function () {
                        announce(i18n.saveError || '');
                    });
                });
            }

            var resList = card.querySelector('.ws-res');
            if (!resList) {
                return;
            }
            (cardRows[itemId] || []).forEach(function (row) {
                var key = keyOf(row.ankama_id, row.subtype);
                var getNeed = (function (rowQuantity) {
                    return function () {
                        return rowQuantity * (multipliers[itemId] || 1);
                    };
                })(row.quantity || 0);
                var entry = buildRowElement(key, row, getNeed, 'card', itemId);
                resList.appendChild(entry.el);
                if (row.craftable) {
                    entry.el.appendChild(buildSubrecipeDisclosure(key, row, getNeed, 1, []));
                }
            });
        });
    }

    function onQuantityChange(card, qtyInput) {
        var itemId = card.dataset.itemId;
        var workshopId = qtyInput.getAttribute('data-workshop-id');
        multipliers[itemId] = clampQuantity(qtyInput.value);

        var keys = {};
        (cardRows[itemId] || []).forEach(function (row) {
            keys[keyOf(row.ankama_id, row.subtype)] = true;
        });
        Object.keys(keys).forEach(refreshKey);

        clearTimeout(qtyTimers[workshopId]);
        qtyTimers[workshopId] = setTimeout(function () {
            postForm(cfg.setQtyUrlBase + workshopId + '/', {quantity: multipliers[itemId]})
                .then(function (resp) {
                    if (!resp || !resp.success) {
                        announce(i18n.saveError || '');
                    }
                })
                .catch(function () {
                    announce(i18n.saveError || '');
                });
        }, SAVE_DEBOUNCE_MS);
    }

    function buildShoppingList() {
        var list = document.getElementById('ws-shopping-list');
        if (!list) {
            return;
        }
        sortedResourceTotals().forEach(function (item) {
            var key = keyOf(item.ankama_id, item.subtype);
            var entry = buildRowElement(key, item, function () {
                return liveTotalNeed(key);
            }, 'list', null);
            list.appendChild(entry.el);
        });
    }

    function shoppingListSnapshot() {
        var list = document.getElementById('ws-shopping-list');
        var rows = list ? list.querySelectorAll('.ws-row') : [];
        return Array.prototype.map.call(rows, function (row) {
            var key = row.getAttribute('data-res-key');
            var item = resourceTotalsByKey[key] || {};
            var needed = liveTotalNeed(key);
            var owned = stock[key] || 0;
            return {
                name: item.name || '',
                needed: needed,
                owned: owned,
                missing: stillMissing(needed, owned)
            };
        });
    }

    function copyTextToClipboardFallback(text) {
        return new Promise(function (resolve, reject) {
            try {
                var textarea = document.createElement('textarea');
                textarea.value = text;
                textarea.setAttribute('readonly', '');
                textarea.style.position = 'fixed';
                textarea.style.left = '-9999px';
                document.body.appendChild(textarea);
                textarea.select();
                textarea.setSelectionRange(0, textarea.value.length);
                var ok = document.execCommand('copy');
                document.body.removeChild(textarea);
                if (ok) {
                    resolve();
                } else {
                    reject(new Error('copy command failed'));
                }
            } catch (e) {
                reject(e);
            }
        });
    }

    function copyTextToClipboard(text) {
        try {
            if (navigator.clipboard && navigator.clipboard.writeText) {
                return navigator.clipboard.writeText(text).catch(function () {
                    return copyTextToClipboardFallback(text);
                });
            }
        } catch (e) {
            // fall through to the textarea fallback below
        }
        return copyTextToClipboardFallback(text);
    }

    function downloadCsv(csvText, filename) {
        try {
            var blob = new Blob([csvText], {type: 'text/csv;charset=utf-8;'});
            var url = URL.createObjectURL(blob);
            var link = document.createElement('a');
            link.href = url;
            link.download = filename;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            setTimeout(function () {
                URL.revokeObjectURL(url);
            }, 1000);
        } catch (e) {
            announceExport(i18n.saveError || '');
        }
    }

    function announceExport(text) {
        var el = document.getElementById('ws-export-status');
        if (el) {
            el.textContent = text || '';
        }
    }

    function wireExportButtons() {
        var copyBtn = document.getElementById('ws-copy-missing');
        var csvBtn = document.getElementById('ws-download-csv');

        if (copyBtn) {
            copyBtn.addEventListener('click', function () {
                var text = buildMissingListText(shoppingListSnapshot());
                if (!text) {
                    announceExport(i18n.copyNothing || '');
                    return;
                }
                copyTextToClipboard(text).then(function () {
                    announceExport(i18n.copySuccess || '');
                }).catch(function () {
                    announceExport(i18n.copyError || '');
                });
            });
        }

        if (csvBtn) {
            csvBtn.addEventListener('click', function () {
                var csv = buildMissingListCsv(shoppingListSnapshot(), {
                    name: i18n.csvHeaderName || '',
                    needed: i18n.csvHeaderNeeded || '',
                    owned: i18n.csvHeaderOwned || '',
                    missing: i18n.csvHeaderMissing || ''
                }, csvSeparatorFor(document.documentElement.lang));
                downloadCsv(csv, 'workshop-shopping-list.csv');
            });
        }
    }

    function loadHideGathered() {
        try {
            return hideGatheredFromStored(localStorage.getItem('wsHideGathered'));
        } catch (e) {
            return true;
        }
    }

    function saveHideGathered(value) {
        try {
            localStorage.setItem('wsHideGathered', value ? '1' : '0');
        } catch (e) {}
    }

    function applyHideGathered(hidden) {
        hideGathered = hidden;
        var list = document.getElementById('ws-shopping-list');
        var emptyMsg = document.getElementById('ws-shopping-empty');
        if (!list) {
            return;
        }
        var visibleCount = 0;
        var active = document.activeElement;
        Array.prototype.forEach.call(list.querySelectorAll('.ws-row'), function (row) {
            var key = row.getAttribute('data-res-key');
            var gathered = stillMissing(liveTotalNeed(key), stock[key] || 0) === 0;
            var hide = shoppingRowHidden(hidden, gathered, !!active && row.contains(active));
            row.hidden = hide;
            if (!hide) {
                visibleCount++;
            }
        });
        if (emptyMsg) {
            if (!resourceTotals.length) {
                emptyMsg.hidden = false;
                emptyMsg.textContent = i18n.noRecipeData || '';
            } else if (!visibleCount) {
                emptyMsg.hidden = false;
                emptyMsg.textContent = i18n.nothingMissing || '';
            } else {
                emptyMsg.hidden = true;
            }
        }
    }

    function cardSortRecord(itemId) {
        var card = cardsById[itemId];
        var nameEl = card.querySelector('.ws-name');
        return {
            itemId: itemId,
            order: parseInt(card.getAttribute('data-order'), 10) || 0,
            level: parseInt(card.getAttribute('data-level'), 10) || 0,
            name: nameEl ? nameEl.textContent.trim() : '',
            state: cardStateForFilter(itemId)
        };
    }

    function applySort() {
        var list = document.getElementById('ws-list');
        if (!list) {
            return;
        }
        var records = Object.keys(cardsById).map(cardSortRecord);
        sortCards(records, currentSort).forEach(function (record) {
            list.appendChild(cardsById[record.itemId]);
        });
    }

    function loadSort() {
        try {
            var value = localStorage.getItem(SORT_STORAGE_KEY);
            return (value === 'level' || value === 'name' || value === 'state')
                ? value : 'added';
        } catch (e) {
            return 'added';
        }
    }

    function saveSort(value) {
        try {
            localStorage.setItem(SORT_STORAGE_KEY, value);
        } catch (e) {}
    }

    function wireSortSelect() {
        var select = document.getElementById('ws-sort-select');
        if (!select) {
            return;
        }
        select.value = currentSort;
        select.addEventListener('change', function () {
            currentSort = select.value;
            saveSort(currentSort);
            applySort();
        });
    }

    function wireFilterChips() {
        var chips = document.querySelectorAll('.ws-chip');
        chips.forEach(function (chip) {
            chip.addEventListener('click', function () {
                currentFilter = chip.getAttribute('data-filter');
                chips.forEach(function (c) {
                    c.setAttribute('aria-pressed', c === chip ? 'true' : 'false');
                });
                refreshSummary();
            });
        });
    }

    function wireCardBulkButtons() {
        document.querySelectorAll('.ws-all-zero').forEach(function (btn) {
            btn.addEventListener('click', function () {
                var itemId = btn.getAttribute('data-item-id');
                (cardRows[itemId] || []).forEach(function (row) {
                    setStockValue(keyOf(row.ankama_id, row.subtype), 0);
                });
            });
        });
        document.querySelectorAll('.ws-all-max').forEach(function (btn) {
            btn.addEventListener('click', function () {
                var itemId = btn.getAttribute('data-item-id');
                (cardRows[itemId] || []).forEach(function (row) {
                    var key = keyOf(row.ankama_id, row.subtype);
                    var need = (row.quantity || 0) * (multipliers[itemId] || 1);
                    setStockValue(key, Math.max(stock[key] || 0, need));
                });
            });
        });
    }

    function mergeStockResult(stockResult) {
        Object.keys(stockResult || {}).forEach(function (key) {
            stock[key] = stockResult[key];
        });
    }

    function refreshItemKeys(itemId) {
        (cardRows[itemId] || []).forEach(function (row) {
            refreshKey(keyOf(row.ankama_id, row.subtype));
        });
    }

    function undoCraft(itemId, workshopId) {
        postForm(cfg.uncraftUrlBase + workshopId + '/').then(function (resp) {
            if (resp && resp.success) {
                delete removedIds[itemId];
                multipliers[itemId] = resp.quantity;
                mergeStockResult(resp.stock);
                var card = cardsById[itemId];
                // A craft that emptied the card deletes it server-side, so
                // undo recreates it under a new id: repoint every control
                // still carrying the old one, or they 404 on the next action.
                var newId = resp.workshop_item_id != null
                    ? String(resp.workshop_item_id) : workshopId;
                if (card) {
                    card.setAttribute('data-workshop-id', newId);
                    var qtyInput = card.querySelector('.ws-qty-input');
                    if (qtyInput) {
                        qtyInput.value = String(resp.quantity);
                        qtyInput.setAttribute('data-workshop-id', newId);
                    }
                    var removeBtn = card.querySelector('.ws-remove');
                    if (removeBtn) {
                        removeBtn.setAttribute('data-workshop-id', newId);
                    }
                    var craftBtn = card.querySelector('.ws-craft-btn');
                    if (craftBtn) {
                        craftBtn.setAttribute('data-workshop-id', newId);
                    }
                }
                if (newId !== workshopId && qtyTimers[workshopId] !== undefined) {
                    qtyTimers[newId] = qtyTimers[workshopId];
                    delete qtyTimers[workshopId];
                }
                refreshItemKeys(itemId);
                applySort();
                announce(i18n.restored || '');
            } else {
                announce((resp && resp.error) || i18n.saveError || '');
            }
        }).catch(function () {
            announce(i18n.saveError || '');
        });
    }

    function wireCraftButtons() {
        document.querySelectorAll('.ws-craft-btn').forEach(function (btn) {
            btn.addEventListener('click', function () {
                var workshopId = btn.getAttribute('data-workshop-id');
                var itemId = btn.getAttribute('data-item-id');
                btn.disabled = true;
                postForm(cfg.craftUrlBase + workshopId + '/').then(function (resp) {
                    btn.disabled = false;
                    if (resp && resp.success) {
                        mergeStockResult(resp.stock);
                        var card = cardsById[itemId];
                        if (resp.removed) {
                            removedIds[itemId] = true;
                            multipliers[itemId] = 0;
                        } else {
                            multipliers[itemId] = resp.quantity;
                            var qtyInput = card ? card.querySelector('.ws-qty-input') : null;
                            if (qtyInput) {
                                qtyInput.value = String(resp.quantity);
                            }
                        }
                        refreshItemKeys(itemId);
                        applySort();
                        announceUndo(i18n.crafted || '', function () {
                            undoCraft(itemId, workshopId);
                        });
                    } else {
                        announce((resp && resp.error) || i18n.saveError || '');
                    }
                }).catch(function () {
                    btn.disabled = false;
                    announce(i18n.saveError || '');
                });
            });
        });
    }

    function wireResetStock() {
        var btn = document.getElementById('ws-reset-stock');
        if (!btn) {
            return;
        }
        btn.addEventListener('click', function () {
            if (!window.confirm(i18n.resetConfirm || '')) {
                return;
            }
            postForm(cfg.resetStockUrl).then(function (resp) {
                if (resp && resp.success) {
                    window.location.reload();
                } else {
                    announce((resp && resp.error) || i18n.saveError || '');
                }
            }).catch(function () {
                announce(i18n.saveError || '');
            });
        });
    }

    function wireSearch() {
        var input = document.getElementById('ws-search-input');
        var results = document.getElementById('ws-search-results');
        if (!input || !results) {
            return;
        }
        var timer = null;

        function hideResults() {
            results.hidden = true;
            results.innerHTML = '';
        }

        function addSearchResult(item) {
            postForm(cfg.addUrl, {item_id: item.id, quantity: 1}).then(function (resp) {
                if (resp && resp.success) {
                    window.location.reload();
                } else {
                    announce((resp && resp.error) || i18n.saveError || '');
                }
            }).catch(function () {
                announce(i18n.saveError || '');
            });
        }

        function renderResults(items) {
            results.innerHTML = '';
            if (!items.length) {
                var empty = document.createElement('div');
                empty.className = 'ws-search-result';
                empty.textContent = i18n.noItemFound || '';
                results.appendChild(empty);
            }
            items.forEach(function (item) {
                var row = document.createElement('div');
                row.className = 'ws-search-result';
                row.setAttribute('role', 'button');
                row.setAttribute('tabindex', '0');
                if (item.image_url) {
                    var img = document.createElement('img');
                    img.src = item.image_url;
                    img.alt = '';
                    row.appendChild(img);
                }
                var label = document.createElement('span');
                label.textContent = item.level
                    ? item.name + ' (' + item.level + ')' : item.name;
                row.appendChild(label);
                row.addEventListener('click', function () {
                    addSearchResult(item);
                });
                row.addEventListener('keydown', function (e) {
                    if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        addSearchResult(item);
                    }
                });
                results.appendChild(row);
            });
            results.hidden = false;
        }

        input.addEventListener('input', function () {
            var query = input.value.trim();
            clearTimeout(timer);
            if (query.length < 2) {
                hideResults();
                return;
            }
            timer = setTimeout(function () {
                fetch(cfg.searchUrl + '?q=' + encodeURIComponent(query) + '&all_types=1&with_recipe=1', {
                    headers: {'X-Requested-With': 'XMLHttpRequest'}
                }).then(function (response) {
                    return response.json();
                }).then(function (data) {
                    renderResults(data.items || []);
                }).catch(hideResults);
            }, 250);
        });

        document.addEventListener('click', function (e) {
            if (!results.contains(e.target) && e.target !== input) {
                hideResults();
            }
        });
    }

    function wireEvents() {
        var clearLink = document.getElementById('workshop_clear');
        if (clearLink) {
            clearLink.addEventListener('click', function (e) {
                e.preventDefault();
                if (!window.confirm(i18n.clearConfirm || '')) {
                    return;
                }
                postForm(cfg.clearUrl).then(function (resp) {
                    if (resp && resp.success) {
                        window.location.reload();
                    } else {
                        announce(i18n.saveError || '');
                    }
                }).catch(function () {
                    announce(i18n.saveError || '');
                });
            });
        }

        var toggle = document.getElementById('ws-hide-gathered-toggle');
        if (toggle) {
            toggle.checked = loadHideGathered();
            toggle.addEventListener('change', function () {
                saveHideGathered(toggle.checked);
                applyHideGathered(toggle.checked);
            });
        }
        var shoppingList = document.getElementById('ws-shopping-list');
        if (shoppingList) {
            shoppingList.addEventListener('focusout', function () {
                setTimeout(function () {
                    applyHideGathered(hideGathered);
                }, 0);
            });
        }

        wireResetStock();
        wireCardBulkButtons();
        wireCraftButtons();
        wireFilterChips();
        wireSortSelect();
        wireSearch();
        wireExportButtons();

        window.addEventListener('beforeunload', flushPendingOnUnload);
    }

    function refreshEverything() {
        Object.keys(rowElsByKey).forEach(function (key) {
            rowElsByKey[key].forEach(updateRow);
        });
        Object.keys(cardsById).forEach(refreshCardFooter);
        refreshSummary();
    }

    function init() {
        currentSort = loadSort();
        buildResourceIndex();
        buildCards();
        buildShoppingList();
        refreshEverything();
        applySort();
        wireEvents();
        applyHideGathered(hideGathered);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    window.FashionWorkshop = pure;
})();
