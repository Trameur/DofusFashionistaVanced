# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A remove button pressed from the keyboard leaves the focus on a basket control; a pointer click does not move it."""
import json
import os
import shutil
import subprocess
import tempfile

from django.test import SimpleTestCase

_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'chardata', 'compare_tray.js')

_STUBS = r"""
var store = {}, listeners = {}, active = 'body';
var toggle = {focus: function() { active = 'toggle'; }};
var panel = {_html: '', buttons: []};
Object.defineProperty(panel, 'innerHTML', {
    set: function(html) {
        panel._html = html;
        panel.buttons = [];
        var re = /data-ct-remove="([^"]*)"/g, m;
        while ((m = re.exec(html)) !== null) {
            (function(id) {
                var button = {id: id, focus: function() { if (panel.buttons.indexOf(button) >= 0 && active !== 'body') { active = 'remove:' + id; } },
                    closest: function(sel) { return sel === '[data-ct-remove]' ? button : null; },
                    getAttribute: function() { return id; }};
                panel.buttons.push(button);
            })(m[1]);
        }
        active = 'body';
    },
    get: function() { return panel._html; }
});
var cart = {hidden: false, classList: {remove: function() {}}, querySelector: function() { return null; }};
var document = {
    readyState: 'complete',
    body: {appendChild: function() {}},
    createElement: function() { return {classList: {add: function() {}, remove: function() {}}}; },
    getElementById: function(id) { return id === 'compare-cart' ? cart : (id === 'compare-cart-panel' ? panel : null); },
    querySelector: function(sel) { return sel === '.compare-cart-toggle' ? toggle : null; },
    querySelectorAll: function(sel) { return sel === '[data-ct-remove]' ? panel.buttons.slice() : []; },
    addEventListener: function(name, fn) { listeners[name] = fn; }
};
var localStorage = {
    getItem: function(k) { return k in store ? store[k] : null; },
    setItem: function(k, v) { store[k] = String(v); }
};
var window = {COMPARE_TRAY_CONFIG: {apiBase: '', i18n: {}}, addEventListener: function() {}, location: {}};
window.localStorage = localStorage;
function press(index, detail) {
    var target = panel.buttons[index];
    listeners.click({target: target, detail: detail, preventDefault: function() {}});
}
"""


class RemovingABuildFromTheBasketByKeyboardKeepsTheFocusInTheBasketTests(SimpleTestCase):

    def run_script(self, body):
        node = shutil.which('node')
        if node is None:
            self.skipTest('node is not installed')
        with open(_SCRIPT, encoding='utf-8') as handle:
            source = handle.read()
        program = '\n'.join([
            _STUBS,
            source,
            'var ids = ["a", "b", "c"];',
            'ids.forEach(function(id) { window.FashionCompareTray.add({id: id, name: id}); });',
            'function ids_left() { return panel.buttons.map(function(b) { return b.id; }); }',
            'console.log(JSON.stringify((function() {%s})()));' % body])
        with tempfile.NamedTemporaryFile('w', suffix='.js', encoding='utf-8', delete=False) as handle:
            handle.write(program)
            name = handle.name
        try:
            done = subprocess.run([node, name], capture_output=True, text=True)
        finally:
            os.unlink(name)
        self.assertEqual(0, done.returncode, done.stderr[-800:])
        return json.loads(done.stdout)

    def test_the_next_build_takes_the_focus_after_a_keyboard_removal(self):
        self.assertEqual([['b', 'c'], 'remove:b'], self.run_script("""
            press(0, 0);
            return [ids_left(), active];"""))

    def test_the_last_row_takes_the_focus_when_the_removed_one_was_last(self):
        self.assertEqual([['a', 'b'], 'remove:b'], self.run_script("""
            press(2, 0);
            return [ids_left(), active];"""))

    def test_a_second_keyboard_removal_goes_on_from_the_same_place(self):
        self.assertEqual([['c'], 'remove:c'], self.run_script("""
            press(0, 0);
            press(0, 0);
            return [ids_left(), active];"""))

    def test_a_pointer_click_does_not_move_the_focus(self):
        self.assertEqual([['b', 'c'], 'body'], self.run_script("""
            press(0, 1);
            return [ids_left(), active];"""))

    def test_removing_the_last_build_leaves_nothing_to_focus(self):
        self.assertEqual([[], 'body'], self.run_script("""
            press(0, 0); press(0, 0); press(0, 0);
            return [ids_left(), active];"""))
