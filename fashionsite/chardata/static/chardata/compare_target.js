(function () {
    var root = document.getElementById('compare-target');
    if (!root) {
        return;
    }
    var TOKEN = /^(m[1-9][0-9]{0,9}\.[1-9][0-9]{0,2}|b([1-9][0-9]{0,9}|s[A-Za-z0-9._-]{1,64}))$/;
    var toggle = root.querySelector('.compare-target-button');
    var clear = root.querySelector('.compare-target-clear');
    var picker = root.querySelector('.compare-target-picker');
    var tabs = root.querySelectorAll('.compare-target-tab');
    var search = root.querySelector('#compare-target-search');
    var searchStatus = root.querySelector('.compare-target-search-status');
    var results = root.querySelector('#compare-target-results');
    var gradeBox = root.querySelector('.compare-target-grades');
    var gradeList = gradeBox.querySelector('ul');
    var buildStatus = root.querySelector('.compare-target-builds-status');
    var buildList = root.querySelector('.compare-target-builds');
    var linkField = root.querySelector('#compare-target-link');
    var linkStatus = root.querySelector('.compare-target-link-status');
    var searchTimer = null;
    var searchController = null;
    var lastQuery = '';
    var buildsLoaded = false;

    function text(name) {
        return root.getAttribute('data-' + name) || '';
    }

    function fill(template, values) {
        var out = template;
        Object.keys(values).forEach(function (key) {
            out = out.split('__' + key + '__').join(String(values[key]));
        });
        return out;
    }

    function go(token) {
        var url = new URL(window.location.href);
        if (token && TOKEN.test(token)) {
            url.searchParams.set('target', token);
        } else {
            url.searchParams.delete('target');
        }
        window.location.assign(url.toString());
    }

    function option(label, detail, onClick) {
        var item = document.createElement('li');
        var button = document.createElement('button');
        button.type = 'button';
        button.className = 'compare-target-option';
        button.textContent = label;
        if (detail) {
            var span = document.createElement('span');
            span.className = 'compare-target-detail';
            span.textContent = detail;
            button.appendChild(span);
        }
        button.addEventListener('click', onClick);
        item.appendChild(button);
        return item;
    }

    function clearList(list) {
        while (list.firstChild) {
            list.removeChild(list.firstChild);
        }
    }

    function openPicker() {
        picker.removeAttribute('hidden');
        toggle.setAttribute('aria-expanded', 'true');
        search.focus();
    }

    function closePicker(giveFocusBack) {
        picker.setAttribute('hidden', 'hidden');
        toggle.setAttribute('aria-expanded', 'false');
        if (giveFocusBack) {
            toggle.focus();
        }
    }

    function showGrades(monster) {
        clearList(gradeList);
        document.getElementById('compare-target-grades-title').textContent =
            fill(text('grades-title'), {name: monster.name});
        (monster.grades || []).forEach(function (entry) {
            var label = fill(text('grade-option'), {
                grade: entry.grade, level: entry.level,
                hp: entry.hp === null || entry.hp === undefined ? '?' : entry.hp});
            gradeList.appendChild(option(label, '', function () {
                go(entry.target);
            }));
        });
        gradeBox.removeAttribute('hidden');
        var first = gradeList.querySelector('button');
        if (first) {
            first.focus();
        }
    }

    function detailOf(monster) {
        var levels = (monster.grades || []).map(function (entry) {
            return entry.level;
        }).filter(function (level) {
            return level !== null && level !== undefined;
        });
        if (!levels.length) {
            return 'ID ' + monster.id;
        }
        var low = Math.min.apply(null, levels);
        var high = Math.max.apply(null, levels);
        return low === high
            ? fill(text('monster-level'), {level: low, id: monster.id})
            : fill(text('monster-levels'), {low: low, high: high, id: monster.id});
    }

    function showResults(monsters) {
        clearList(results);
        gradeBox.setAttribute('hidden', 'hidden');
        searchStatus.textContent = monsters.length ? '' : text('no-monster');
        monsters.forEach(function (monster) {
            results.appendChild(option(monster.name, detailOf(monster), function () {
                showGrades(monster);
            }));
        });
    }

    function runSearch() {
        searchTimer = null;
        var query = search.value.trim();
        if (query === lastQuery) {
            return;
        }
        lastQuery = query;
        if (searchController) {
            searchController.abort();
        }
        if (!query) {
            clearList(results);
            gradeBox.setAttribute('hidden', 'hidden');
            searchStatus.textContent = '';
            return;
        }
        searchStatus.textContent = text('searching');
        var controller = new AbortController();
        searchController = controller;
        fetch(text('search-url') + '?q=' + encodeURIComponent(query),
              {signal: controller.signal, credentials: 'same-origin'})
            .then(function (response) {
                return response.json();
            })
            .then(function (data) {
                if (searchController === controller) {
                    showResults((data && data.monsters) || []);
                }
            })
            .catch(function (error) {
                if (!error || error.name !== 'AbortError') {
                    searchStatus.textContent = text('load-error');
                }
            });
    }

    function loadBuilds() {
        if (buildsLoaded) {
            return;
        }
        buildsLoaded = true;
        fetch(text('builds-url'), {credentials: 'same-origin'})
            .then(function (response) {
                return response.json();
            })
            .then(function (data) {
                var builds = (data && data.builds) || [];
                clearList(buildList);
                buildStatus.textContent = builds.length ? '' : text('no-build');
                builds.forEach(function (entry) {
                    var label = fill(text('build-option'), {
                        name: entry.name, 'class': entry['class'], level: entry.level})
                        + ' #' + String(entry.target).slice(1);
                    buildList.appendChild(option(label, '', function () {
                        go(entry.target);
                    }));
                });
            })
            .catch(function () {
                buildsLoaded = false;
                buildStatus.textContent = text('build-error');
            });
    }

    function showTab(name) {
        Array.prototype.forEach.call(tabs, function (tab) {
            var on = tab.id === 'compare-target-tab-' + name;
            tab.setAttribute('aria-selected', on ? 'true' : 'false');
            if (on) {
                tab.removeAttribute('tabindex');
            } else {
                tab.setAttribute('tabindex', '-1');
            }
            var panel = document.getElementById(tab.getAttribute('aria-controls'));
            if (on) {
                panel.removeAttribute('hidden');
            } else {
                panel.setAttribute('hidden', 'hidden');
            }
        });
        if (name === 'character') {
            loadBuilds();
        }
    }

    function linkToken(value) {
        var path = value.trim().split('#')[0].split('?')[0]
            .replace(/^[A-Za-z][A-Za-z0-9+.-]*:\/\/[^\/]*/, '');
        var parts = path.split('/').filter(function (part) {
            return part !== '';
        });
        var last = parts.length ? parts[parts.length - 1] : '';
        var token = /^[1-9][0-9]{0,9}$/.test(last) ? 'b' + last : 'bs' + last;
        return parts.length >= 2 && TOKEN.test(token) ? token : '';
    }

    function useLink() {
        var token = linkToken(linkField.value);
        linkStatus.textContent = token ? '' : text('link-error');
        if (token) {
            go(token);
        }
    }

    toggle.addEventListener('click', function () {
        if (picker.hasAttribute('hidden')) {
            openPicker();
        } else {
            closePicker(false);
        }
    });
    if (clear) {
        clear.addEventListener('click', function () {
            go('');
        });
    }
    Array.prototype.forEach.call(tabs, function (tab, index) {
        tab.addEventListener('click', function () {
            showTab(tab.id.replace('compare-target-tab-', ''));
        });
        tab.addEventListener('keydown', function (event) {
            if (event.key !== 'ArrowRight' && event.key !== 'ArrowLeft') {
                return;
            }
            event.preventDefault();
            var next = tabs[(index + 1) % tabs.length];
            showTab(next.id.replace('compare-target-tab-', ''));
            next.focus();
        });
    });
    root.querySelector('.compare-target-use').addEventListener('click', useLink);
    linkField.addEventListener('keydown', function (event) {
        if (event.key === 'Enter') {
            event.preventDefault();
            useLink();
        }
    });
    search.addEventListener('input', function () {
        if (searchTimer) {
            clearTimeout(searchTimer);
        }
        searchTimer = setTimeout(runSearch, 250);
    });
    search.addEventListener('keydown', function (event) {
        if (event.key === 'Enter') {
            event.preventDefault();
            if (searchTimer) {
                clearTimeout(searchTimer);
            }
            runSearch();
        }
    });
    picker.addEventListener('keydown', function (event) {
        if (event.key === 'Escape') {
            event.preventDefault();
            closePicker(true);
        }
    });
})();
