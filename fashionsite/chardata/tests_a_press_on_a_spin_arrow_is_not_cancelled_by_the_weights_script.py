# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The weights and minimums script leaves the mouseup of an input alone, so a spin arrow stops repeating on release."""
import io
import json
import os
import shutil
import subprocess
import tempfile

from django.test import SimpleTestCase

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, 'static', 'chardata', 'weights_minimums.js')

HARNESS = r"""
var handlers = {};
var store = new Map();
var pending = [];
function chain(selector) {
    var proxy = new Proxy(function() {}, {
        get: function(target, name) {
            if (name === 'on') {
                return function(events, handler) {
                    if (typeof events === 'string' && typeof handler === 'function') {
                        handlers[selector + ' ' + events] = handler;
                    }
                    return proxy;
                };
            }
            if (name === 'length') { return 0; }
            if (/^\d+$/.test(String(name))) { return undefined; }
            if (name === 'attr') { return function() { return ''; }; }
            return function() { return proxy; };
        }
    });
    return proxy;
}
function $(arg) {
    if (!arg || !arg.select) { return chain(String(arg)); }
    return {
        data: function(key, value) {
            if (arguments.length === 1) { return store.get(key); }
            store.set(key, value);
        },
        val: function() { return '5'; }
    };
}
$.grep = function() { return []; };
var document = {
    activeElement: null,
    getElementById: function() { return {textContent: '{}'}; }
};
var window = {location: {hash: ''}};
setTimeout = function(fn) { pending.push(fn); };
"""


def run_script(case, body):
    node = shutil.which('node')
    if node is None:
        case.skipTest('node is not installed')
    source = io.open(SCRIPT, encoding='utf-8').read()
    program = '\n'.join([HARNESS, source, """
wmInit('/save/', {mode: 'form'});
var input = {selected: 0, select: function() { this.selected += 1; }};
var prevented = 0;
var event = {preventDefault: function() { prevented += 1; }};
function release() {
    var run = pending.splice(0);
    run.forEach(function(fn) { fn(); });
}
%s
""" % body])
    with tempfile.NamedTemporaryFile('w', suffix='.js', encoding='utf-8', delete=False) as handle:
        handle.write(program)
        name = handle.name
    try:
        done = subprocess.run([node, name], capture_output=True, text=True, encoding='utf-8')
    finally:
        os.unlink(name)
    case.assertEqual(0, done.returncode, done.stderr[-800:])
    return json.loads(done.stdout)


class APressOnASpinArrowIsNotCancelledTests(SimpleTestCase):

    def test_the_first_mouseup_after_a_focus_is_not_prevented(self):
        result = run_script(self, """
document.activeElement = input;
handlers['.wm-input focus'].call(input);
release();
handlers['.wm-input mouseup'].call(input, event);
console.log(JSON.stringify({prevented: prevented}));
""")
        self.assertEqual(0, result['prevented'])

    def test_the_value_is_selected_again_after_the_mouseup(self):
        result = run_script(self, """
document.activeElement = input;
handlers['.wm-input focus'].call(input);
release();
var afterFocus = input.selected;
handlers['.wm-input mouseup'].call(input, event);
var beforeTimer = input.selected;
release();
console.log(JSON.stringify({afterFocus: afterFocus, beforeTimer: beforeTimer, final: input.selected}));
""")
        self.assertEqual(1, result['afterFocus'])
        self.assertEqual(1, result['beforeTimer'])
        self.assertEqual(2, result['final'])

    def test_a_later_mouseup_neither_prevents_nor_selects(self):
        result = run_script(self, """
document.activeElement = input;
handlers['.wm-input focus'].call(input);
release();
handlers['.wm-input mouseup'].call(input, event);
release();
handlers['.wm-input mouseup'].call(input, event);
release();
console.log(JSON.stringify({prevented: prevented, selected: input.selected}));
""")
        self.assertEqual(0, result['prevented'])
        self.assertEqual(2, result['selected'])
