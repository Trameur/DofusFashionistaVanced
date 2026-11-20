# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The sections of the weights and minimums block take their open state while the page is parsed, so they are drawn open instead of opening afterwards."""
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
TEMPLATES = os.path.join(HERE, 'templates', 'chardata')
PAGES = ('weights_minimums.html', 'wizard.html')
LOADED = '<script src="{% static "chardata/weights_minimums.js" %}"></script>'
BLOCK = '{% include "chardata/weights_minimums_block.html" %}'
CALL = '<script>wmOpenSections(false);</script>'

PAGE_STUB = r"""
var stored = {}, wide = true, denied = false, sections = [];
var window = {
    localStorage: {getItem: function(key) {
        if (denied) { throw new Error('denied'); }
        return Object.prototype.hasOwnProperty.call(stored, key) ? stored[key] : null;
    }},
    matchMedia: function(query) { return {matches: query === '(min-width: 901px)' && wide}; }
};
var document = {querySelectorAll: function(selector) { return selector === '.wm-section' ? sections : []; }};
function page() {
    sections = [['apmprange', true], ['elements', false], ['damage', false]].map(function(pair) {
        return {open: pair[1],
                getAttribute: function(name) { return name === 'data-section' ? pair[0] : null; }};
    });
}
function drawn(previewMode) {
    page();
    wmOpenSections(previewMode);
    return sections.map(function(section) { return section.open; });
}
"""


def source():
    return io.open(SCRIPT, encoding='utf-8').read()


def _functions():
    found = []
    for name in ('wmSectionsKey', 'wmOpenSections'):
        match = re.search(r'^function %s\(.*?^\}' % name, source(), re.M | re.S)
        if match is None:
            raise AssertionError('weights_minimums.js has no top level function %s' % name)
        found.append(match.group(0))
    return '\n'.join(found)


def run_page_script(case, body):
    node = shutil.which('node')
    if node is None:
        case.skipTest('node is not installed')
    program = '\n'.join([PAGE_STUB, _functions(),
                         'console.log(JSON.stringify((function() {%s})()));' % body])
    with tempfile.NamedTemporaryFile('w', suffix='.js', encoding='utf-8',
                                     delete=False) as handle:
        handle.write(program)
        name = handle.name
    try:
        done = subprocess.run([node, name], capture_output=True, text=True)
    finally:
        os.unlink(name)
    case.assertEqual(0, done.returncode, done.stderr[-800:])
    return json.loads(done.stdout)


class TheOpenStateOfTheSectionsTests(SimpleTestCase):

    def test_a_wide_screen_with_nothing_stored_opens_every_section(self):
        self.assertEqual([True, True, True], run_page_script(self, 'return drawn(false);'))

    def test_a_phone_with_nothing_stored_keeps_what_the_server_sent(self):
        self.assertEqual([True, False, False], run_page_script(self, 'wide = false; return drawn(false);'))

    def test_the_stored_state_wins_over_the_width(self):
        stored = json.dumps(json.dumps({'apmprange': False, 'elements': True, 'damage': False}))
        for wide in ('true', 'false'):
            body = 'wide = %s; stored.fm_wm_sections = %s; return drawn(false);' % (wide, stored)
            self.assertEqual([False, True, False], run_page_script(self, body), wide)

    def test_a_section_the_stored_state_does_not_know_keeps_what_the_server_sent(self):
        stored = json.dumps(json.dumps({'elements': True}))
        body = 'stored.fm_wm_sections = %s; return drawn(false);' % stored
        self.assertEqual([True, True, False], run_page_script(self, body))

    def test_the_setup_panel_reads_its_own_key_and_never_opens_by_width(self):
        other = json.dumps(json.dumps({'damage': True}))
        self.assertEqual([True, False, False],
                         run_page_script(self, 'stored.fm_wm_sections = %s; return drawn(true);' % other))
        self.assertEqual([True, False, True],
                         run_page_script(self, 'stored.fm_setup_sections = %s; return drawn(true);' % other))

    def test_a_store_that_cannot_be_read_counts_as_nothing_stored(self):
        self.assertEqual([True, True, True], run_page_script(self, 'denied = true; return drawn(false);'))
        self.assertEqual([True, True, True],
                         run_page_script(self, 'stored.fm_wm_sections = "{not json"; return drawn(false);'))
        self.assertEqual([True, False, False],
                         run_page_script(self, 'denied = true; wide = false; return drawn(false);'))


class ThePagesSetTheStateWhileParsingTests(SimpleTestCase):

    def test_each_page_loads_the_script_before_the_block_and_calls_it_right_after(self):
        for page in PAGES:
            text = io.open(os.path.join(TEMPLATES, page), encoding='utf-8').read()
            self.assertEqual(1, text.count(LOADED), page)
            self.assertEqual(1, text.count(BLOCK), page)
            self.assertLess(text.index(LOADED), text.index(BLOCK), page)
            after = text[text.index(BLOCK) + len(BLOCK):]
            self.assertTrue(after.lstrip().startswith(CALL), page)

    def test_the_page_script_still_sets_the_state_of_a_page_that_loads_it_late(self):
        body = source()[source().index('function wmInit('):]
        self.assertEqual(1, body.count('wmOpenSections(previewMode);'))

    def test_the_stored_state_is_written_under_the_key_it_is_read_from(self):
        body = source()[source().index('function wmInit('):]
        self.assertIn('var STORE_KEY = wmSectionsKey(previewMode);', body)
        self.assertIn('window.localStorage.setItem(STORE_KEY,', body)
        self.assertNotIn("'fm_wm_sections'", body)
        self.assertNotIn("'fm_setup_sections'", body)
