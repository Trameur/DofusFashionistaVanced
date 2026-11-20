# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The Lock page offers Customize stats as soon as an item is picked, and always for the item shown."""
import io
import json
import os
import re
import shutil
import subprocess
import tempfile

from django.test import SimpleTestCase

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATES = os.path.join(HERE, 'templates', 'chardata')
CROWN = 20359
MASK = 19075

_PAGE_STUB = r"""
var nodes = {};
var posts = [];
var ready = [];
var rendered = [];
var document = {};
var apiBase = '';
var allItemsPerType = {hat: {20359: 'Crown', 19075: 'Mask'}};
var allItemsPerTypeAndName = {};
var slotToType = {hat: 'hat'};
var slotImages = {hat: 'hat.png'};
var inclusionsInitial = {};
function gettext(text) { return text; }
function renderStatOverrideSection(slot, itemId) { rendered.push(String(itemId)); }
function $(selector) {
    if (typeof selector !== 'string') {
        return selector && selector.val ? selector : {ready: function(run) { ready.push(run); }};
    }
    if (!nodes[selector]) {
        nodes[selector] = {value: '', text: '', visible: false, data: {}, handlers: {}};
    }
    var state = nodes[selector];
    var api = {
        length: 1,
        val: function(value) {
            if (value === undefined) { return state.value; }
            state.value = String(value);
            return api;
        },
        text: function(value) {
            if (value === undefined) { return state.text; }
            state.text = String(value);
            return api;
        },
        data: function(key, value) {
            if (value === undefined) { return state.data[key]; }
            state.data[key] = value;
            return api;
        },
        attr: function() { return api; },
        after: function() { return api; },
        show: function() { state.visible = true; return api; },
        hide: function() { state.visible = false; return api; },
        is: function() { return state.visible; },
        on: function(name, run) {
            (state.handlers[name] = state.handlers[name] || []).push(run);
            return api;
        },
        off: function(name) { state.handlers[name] = []; return api; },
        click: function(run) { return run ? api.on('click', run) : api.trigger('click'); },
        change: function() { return api.trigger('change'); },
        trigger: function(name) {
            (state.handlers[name] || []).slice().forEach(function(run) {
                run.call(api, {preventDefault: function() {}});
            });
            return api;
        }
    };
    return api;
}
$.each = function(object, run) {
    Object.keys(object).forEach(function(key) { run(key, object[key]); });
};
$.ajaxSetup = function() {};
$.post = function(url, data, done) { posts.push({url: url, data: data, done: done}); };
function answer(data) {
    var waiting = posts;
    posts = [];
    waiting.forEach(function(post) { post.done(data); });
}
function statsAskedFor() {
    return posts.filter(function(post) { return post.url.indexOf('get_item_details') !== -1; })
                .map(function(post) { return String(post.data.item); });
}
function offered() { return $('#stat-override-toggle-hat').is(':visible'); }
function open() { return $('#stat-override-section-hat').is(':visible'); }
function load(initial) {
    inclusionsInitial = initial;
    inclusionsInitStateEngine(inclusionsInitial);
    ready.forEach(function(run) { run(); });
    answer({level: 200, file: 'hat.png'});
}
function customize() {
    $('#stat-override-link-hat').trigger('click');
    var asked = statsAskedFor();
    answer({stats: [{stat_id: 1, name: 'Vitality', value: 500}]});
    return asked;
}
"""


def _read(*parts):
    return io.open(os.path.join(*parts), encoding='utf-8').read()


def _page_script():
    page = _read(TEMPLATES, 'inclusions.html')
    names = ('lockItem', 'inclusionsSlots', 'inclusionsInitStateEngine', 'setupStatOverrideForSlot')
    parts = [re.search(r'function %s\(.*?\n\}\n' % name, page, re.S).group(0) for name in names]
    wiring = page[page.rindex('$(document).ready(function() {'):]
    parts.append(wiring[:wiring.index('</script>')])
    return '\n'.join(parts)


class ALockedItemOffersItsStatCustomizationTests(SimpleTestCase):

    def run_script(self, body):
        node = shutil.which('node')
        if node is None:
            self.skipTest('node is not installed')
        source = '\n'.join([_PAGE_STUB, _read(HERE, 'static', 'chardata', 'inclusions.js'),
                            _page_script(),
                            'console.log(JSON.stringify((function() {%s})()));' % body])
        with tempfile.NamedTemporaryFile('w', suffix='.js', encoding='utf-8',
                                         delete=False) as handle:
            handle.write(source)
            name = handle.name
        try:
            done = subprocess.run([node, name], capture_output=True, text=True)
        finally:
            os.unlink(name)
        self.assertEqual(0, done.returncode, done.stderr[-800:])
        return json.loads(done.stdout)

    def test_a_picked_item_is_customizable_before_its_details_arrive(self):
        self.assertEqual({'empty': False, 'picked': True, 'asked': [str(CROWN)]},
                         self.run_script("""
            load({hat: ''});
            var empty = offered();
            lockItem(%d, 'hat', 63);
            var picked = offered();
            answer({level: 200, file: 'hat.png'});
            return {empty: empty, picked: picked, asked: customize()};""" % CROWN))

    def test_a_replaced_item_shows_its_own_stats(self):
        self.assertEqual({'first': [str(CROWN)], 'removed': [False, False],
                          'replaced': [True, False], 'second': [str(MASK)],
                          'rendered': [str(CROWN), str(MASK)], 'bound': str(MASK)},
                         self.run_script("""
            load({hat: %d});
            var first = customize();
            removeItem('hat', slotImages);
            var removed = [offered(), open()];
            lockItem(%d, 'hat', 63);
            var replaced = [offered(), open()];
            answer({level: 200, file: 'hat.png'});
            var second = customize();
            return {first: first, removed: removed, replaced: replaced, second: second,
                    rendered: rendered,
                    bound: String($('#stat-override-section-hat').data('item'))};"""
                                         % (CROWN, MASK)))

    def test_discarding_brings_back_the_customization_of_the_saved_item(self):
        self.assertEqual({'removed': False, 'restored': True, 'asked': [str(CROWN)]},
                         self.run_script("""
            load({hat: %d});
            removeItem('hat', slotImages);
            var removed = offered();
            inclusionsInitStateEngine(inclusionsInitial);
            var restored = offered();
            answer({level: 200, file: 'hat.png'});
            return {removed: removed, restored: restored, asked: customize()};""" % CROWN))

    def test_discarding_closes_the_panel_of_another_item(self):
        self.assertEqual({'before': True, 'after': [True, False], 'asked': [str(CROWN)]},
                         self.run_script("""
            load({hat: %d});
            removeItem('hat', slotImages);
            lockItem(%d, 'hat', 63);
            answer({level: 200, file: 'hat.png'});
            customize();
            var before = open();
            inclusionsInitStateEngine(inclusionsInitial);
            var after = [offered(), open()];
            answer({level: 200, file: 'hat.png'});
            return {before: before, after: after, asked: customize()};""" % (CROWN, MASK)))

    def test_saving_keeps_the_open_panel_of_the_same_item(self):
        self.assertEqual([True, True], self.run_script("""
            load({hat: %d});
            customize();
            inclusionsInitStateEngine({hat: %d});
            return [offered(), open()];""" % (CROWN, CROWN)))

    def test_an_emptied_slot_offers_nothing(self):
        self.assertEqual([True, False, False], self.run_script("""
            load({hat: %d});
            var before = offered();
            inclusionsInitStateEngine({hat: ''});
            return [before, offered(), open()];""" % CROWN))
