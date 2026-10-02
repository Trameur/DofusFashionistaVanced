# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""On the weights and minimums page, moving through the boxes changes nothing a player did not type."""
import io
import json
import os
import re
import shutil
import subprocess
import tempfile

from django.test import SimpleTestCase

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, 'static', 'chardata', 'weights_minimums.js')
FUNCTIONS = ('rememberFocus', 'changedSinceFocus', 'mixedAndLeftBlank', 'clampToCap',
             'afterEdit', 'selectOnFocus', 'weightChanged', 'minimumChanged', 'onEnter')

PAGE_STUB = r"""
var changesPendingStateEngine = false;
var saves = 0, selected = [], timers = [];
var document = {activeElement: null};
var rows = {}, boxes = {}, order = {weight: [], min: []};
function setTimeout(callback) { timers.push(callback); }
function runTimers() { var due = timers; timers = []; due.forEach(function(f) { f(); }); }
function row(key, members) {
    rows[key] = {key: key, members: members || [], classes: {}};
    return rows[key];
}
function box(key, col, value, max) {
    var element = {id: col + '_' + key, key: key, col: col, value: String(value),
                   max: max, data: {}, select: function() { selected.push(this.id); }};
    boxes[col + '_' + key] = element;
    order[col].push(element);
    return element;
}
function wrapRow(r) {
    return {el: r,
            hasClass: function(name) { return name === 'wm-aggregate' ? r.members.length > 0
                                                                     : !!r.classes[name]; },
            addClass: function(name) { r.classes[name] = true; return this; },
            removeClass: function(name) { delete r.classes[name]; return this; }};
}
function $(target) {
    if (target === '#button-save') {
        return {trigger: function() { saves += 1; return this; }};
    }
    var element = target.el || target;
    return {
        el: element,
        val: function(value) {
            if (value === undefined) { return element.value; }
            element.value = String(value);
            return this;
        },
        data: function(name, value) {
            if (value === undefined) { return element.data[name]; }
            element.data[name] = value;
            return this;
        },
        attr: function(name) { return name === 'max' ? element.max : undefined; },
        trigger: function(name) {
            if (name === 'change') {
                changesPendingStateEngine = true;
                (element.col === 'min' ? minimumChanged : weightChanged).call(element);
            } else if (name === 'focus') {
                document.activeElement = element;
                selectOnFocus.call(element);
            }
            return this;
        }
    };
}
$.each = function(list, callback) { list.forEach(function(item, i) { callback(i, item); }); };
function rowOf(input) { return wrapRow(rows[(input.el || input).key]); }
function column(input) { return input.col; }
function boxOf(key, col) { return $(boxes[col + '_' + key]); }
function members($row) { return $row.el.members; }
function refreshAll() {
    Object.keys(rows).forEach(function(key) {
        var r = rows[key];
        ['weight', 'min'].forEach(function(col) {
            var own = boxes[col + '_' + key];
            if (!r.members.length || !own) { return; }
            var values = r.members.map(function(m) { return boxes[col + '_' + m].value; });
            own.value = values.every(function(v) { return v === values[0]; }) ? values[0] : '';
        });
    });
}
function visibleInputs(col) {
    var list = order[col];
    return {length: list.length,
            index: function(element) { return list.indexOf(element); },
            eq: function(i) { return $(list[i]); }};
}
function focus(element) { $(element).trigger('focus'); }
function type(element, value) { element.value = String(value); }
function press(element, modifiers) {
    var event = {key: 'Enter', ctrlKey: !!(modifiers && modifiers.ctrl), metaKey: false,
                 preventDefault: function() {}};
    onEnter.call(element, event);
}
function values(col, keys) {
    return keys.map(function(key) { return boxes[col + '_' + key].value; });
}
function resistPage(weights, minimums, cap) {
    var keys = ['neutresper', 'earthresper', 'fireresper', 'waterresper', 'airresper'];
    row('perres', keys);
    box('perres', 'weight', '');
    box('perres', 'min', '');
    keys.forEach(function(key, i) {
        row(key);
        box(key, 'weight', weights[i]);
        box(key, 'min', minimums[i], cap);
    });
    row('vit');
    box('vit', 'weight', 5);
    box('vit', 'min', '');
    refreshAll();
    return keys;
}
"""


def _functions():
    source = io.open(SCRIPT, encoding='utf-8').read()
    found = []
    for name in FUNCTIONS:
        match = re.search(r'\n    function %s\(.*?\n    \}\n' % name, source, re.S)
        if match is None:
            raise AssertionError('weights_minimums.js has no function %s' % name)
        found.append(match.group(0))
    return '\n'.join(found)


def run_page_script(case, body):
    node = shutil.which('node')
    if node is None:
        case.skipTest('node is not installed')
    source = '\n'.join([PAGE_STUB, _functions(),
                        'console.log(JSON.stringify((function() {%s})()));' % body])
    with tempfile.NamedTemporaryFile('w', suffix='.js', encoding='utf-8',
                                     delete=False) as handle:
        handle.write(source)
        name = handle.name
    try:
        done = subprocess.run([node, name], capture_output=True, text=True)
    finally:
        os.unlink(name)
    case.assertEqual(0, done.returncode, done.stderr[-800:])
    return json.loads(done.stdout)


class MovingThroughTheBoxesChangesNothingTests(SimpleTestCase):

    def test_enter_in_an_untouched_box_moves_on_without_a_pending_change(self):
        self.assertEqual({'pending': False, 'at': 'weight_earthresper', 'saves': 0},
                         run_page_script(self, """
            resistPage([0, 240, 240, 240, 240], ['', '', '', '', ''], '53');
            focus(boxes.weight_neutresper);
            press(boxes.weight_neutresper);
            press(document.activeElement, {ctrl: true});
            return {pending: changesPendingStateEngine, at: document.activeElement.id,
                    saves: saves};"""))

    def test_enter_on_a_mixed_resist_minimum_keeps_every_resist_minimum(self):
        self.assertEqual({'minimums': ['', '', '30', '', ''], 'pending': False, 'saves': 0},
                         run_page_script(self, """
            var keys = resistPage([240, 240, 240, 240, 240], ['', '', '30', '', ''], '53');
            focus(boxes.min_perres);
            press(boxes.min_perres);
            focus(boxes.min_perres);
            press(boxes.min_perres, {ctrl: true});
            return {minimums: values('min', keys), pending: changesPendingStateEngine,
                    saves: saves};"""))

    def test_enter_on_a_mixed_resist_weight_keeps_every_resist_weight(self):
        self.assertEqual(['0', '240', '240', '240', '240'], run_page_script(self, """
            var keys = resistPage([0, 240, 240, 240, 240], ['', '', '', '', ''], '53');
            focus(boxes.weight_perres);
            press(boxes.weight_perres);
            focus(boxes.weight_perres);
            $(boxes.weight_perres).trigger('change');
            return values('weight', keys);"""))

    def test_a_shared_weight_cleared_on_the_group_sets_each_member_to_zero(self):
        self.assertEqual({'weights': ['0', '0', '0', '0', '0'], 'pending': True},
                         run_page_script(self, """
            var keys = resistPage([240, 240, 240, 240, 240], ['', '', '', '', ''], '53');
            focus(boxes.weight_perres);
            type(boxes.weight_perres, '');
            press(boxes.weight_perres);
            return {weights: values('weight', keys), pending: changesPendingStateEngine};"""))

    def test_a_typed_member_weight_saves_with_ctrl_enter(self):
        self.assertEqual({'vit': '9', 'saves': 1, 'pending': True}, run_page_script(self, """
            resistPage([240, 240, 240, 240, 240], ['', '', '', '', ''], '53');
            focus(boxes.weight_vit);
            type(boxes.weight_vit, '9');
            press(boxes.weight_vit, {ctrl: true});
            return {vit: boxes.weight_vit.value, saves: saves,
                    pending: changesPendingStateEngine};"""))

    def test_only_the_box_still_focused_selects_its_text(self):
        self.assertEqual(['min_vit'], run_page_script(self, """
            resistPage([240, 240, 240, 240, 240], ['', '', '', '', ''], '53');
            focus(boxes.min_fireresper);
            focus(boxes.min_vit);
            runTimers();
            runTimers();
            return selected;"""))
