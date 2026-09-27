# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A third focus box is refused as it is ticked and the limit flashes; submit and server checks stay."""
import json
import os
import re
import shutil
import subprocess
import tempfile

from django.test import TestCase
from django.utils import translation

_FUNCTIONS = ('flashRed', 'highlightAspectRules', 'tooManyFocusBoxes', 'refuseExtraFocus',
              'areAspectsValid', 'checkAndSubmit')

_JQUERY_STUB = r"""
var checked = {}, flashed = [];
function $(selector) {
    var id = selector.replace('#', '');
    return {
        prop: function(name, value) {
            if (value === undefined) { return !!checked[id]; }
            checked[id] = value;
            return this;
        },
        addClass: function(name) { flashed.push([id, name]); return this; },
        removeClass: function() { return this; },
        show: function() { return this; }
    };
}
$.each = function(list, callback) {
    for (var i = 0; i < list.length; i++) { callback(i, list[i]); }
};
function setTimeout() {}
function warnOnceWithoutElement() { return false; }
function click(aspect) {
    checked['check_' + aspect] = !checked['check_' + aspect];
    var event = {prevented: false, preventDefault: function() { this.prevented = true; }};
    refuseExtraFocus(event, aspect);
    if (event.prevented) {
        checked['check_' + aspect] = !checked['check_' + aspect];
    }
    return event.prevented;
}
"""


class AThirdFocusBoxIsRefusedWhenTickedTests(TestCase):

    def page(self):
        with translation.override('en'):
            return self.client.get('/setup/').content.decode('utf-8')

    def run_page_script(self, body):
        node = shutil.which('node')
        if node is None:
            self.skipTest('node is not installed')
        page = self.page()
        parts = [_JQUERY_STUB,
                 re.search(r'var inertAspects = .*?(?=\nfunction )', page, re.S).group(0),
                 re.search(r'var exclusiveFocus = .*?;\n', page).group(0)]
        for name in _FUNCTIONS:
            parts.append(re.search(r'function %s\(.*?\n\}' % name, page, re.S).group(0))
        parts.append('console.log(JSON.stringify((function() {%s})()));' % body)
        with tempfile.NamedTemporaryFile('w', suffix='.js', encoding='utf-8',
                                         delete=False) as handle:
            handle.write('\n'.join(parts))
            name = handle.name
        try:
            done = subprocess.run([node, name], capture_output=True, text=True)
        finally:
            os.unlink(name)
        self.assertEqual(0, done.returncode, done.stderr[-800:])
        return json.loads(done.stdout)

    def test_the_third_box_does_not_stay_ticked_and_the_limit_flashes(self):
        self.assertEqual([[False, False], True, False, [['aspect_limit_text', 'red-text']]],
                         self.run_page_script("""
            var first = [click("vit"), click("res")];
            var refused = click("dam");
            return [first, refused, !!checked["check_dam"], flashed];"""))

    def test_the_other_boxes_keep_their_ticks(self):
        self.assertEqual([True, True, False], self.run_page_script("""
            click("vit"); click("pp"); click("summon");
            return [checked["check_vit"], checked["check_pp"], !!checked["check_summon"]];"""))

    def test_unticking_is_never_refused(self):
        self.assertEqual([False, False, []], self.run_page_script("""
            checked["check_vit"] = checked["check_res"] = checked["check_dam"] = true;
            var refused = click("dam");
            return [refused, !!checked["check_dam"], flashed];"""))

    def test_crit_may_take_the_place_of_the_avoid_crit_box(self):
        self.assertEqual([False, True], self.run_page_script("""
            click("vit"); click("noncrit");
            var refused = click("crit");
            return [refused, checked["check_crit"]];"""))

    def test_the_balanced_box_and_the_other_columns_do_not_count(self):
        self.assertEqual(False, self.run_page_script("""
            checked["check_balanced"] = checked["check_str"] = checked["check_int"] = true;
            checked["check_omni"] = true;
            click("vit");
            return click("res");"""))

    def test_the_submit_check_still_refuses_three_boxes(self):
        self.assertEqual([False, [['aspect_limit_text', 'red-text']]], self.run_page_script("""
            checked["check_vit"] = checked["check_res"] = checked["check_dam"] = true;
            return [checkAndSubmit(), flashed];"""))

    def test_every_focus_box_but_balanced_refuses_on_click(self):
        page = self.page()
        body = re.search(r'function setupCheckboxes\(.*?\n\}', page, re.S).group(0)
        loop = re.search(r'\$\.each\(aspectLayout\[2\]\.concat\(aspectLayout\[3\]\), '
                         r'function\(i, aspect\) \{(.*?)\n    \}\);', body, re.S).group(1)
        self.assertIn('if (aspect != "balanced")', loop)
        self.assertIn("$(\"#check_\" + aspect).on('click', function(event) {", loop)
        self.assertIn('refuseExtraFocus(event, aspect);', loop)
        self.assertIn('event.preventDefault();', re.search(
            r'function refuseExtraFocus\(.*?\n\}', page, re.S).group(0))

    def test_the_limit_flash_is_readable_on_the_classic_light_header(self):
        flash = re.search(r'html\.fm-light:not\(\.fm-modern\) \.build-boxes-title \.red-text\s*'
                          r'\{\s*color:\s*(#[0-9a-fA-F]{6})', self.page()).group(1)
        css = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'chardata',
                           'forms_lighttheme.css')
        with open(css, encoding='utf-8') as handle:
            header = re.search(r'\.build-boxes-section\s*\{[^}]*background-color:\s*'
                               r'(#[0-9a-fA-F]{6})', handle.read()).group(1)
        self.assertGreaterEqual(_contrast(flash, header), 4.5)


def _luminance(colour):
    channels = [int(colour[i:i + 2], 16) / 255.0 for i in (1, 3, 5)]
    linear = [value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4
              for value in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(foreground, background):
    lighter, darker = sorted((_luminance(foreground), _luminance(background)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)
