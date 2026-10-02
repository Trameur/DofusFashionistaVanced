# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Tailor saves the weights page's pending edits first; every other page keeps asking, and a failed save says so."""
import glob
import io
import json
import os
import re
import shutil
import subprocess
import tempfile

import polib
from django.test import SimpleTestCase

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATES = os.path.join(HERE, 'templates', 'chardata')
LOCALE = os.path.join(os.path.dirname(HERE), 'locale')
FAILED = 'The changes could not be saved. Try again.'

_PAGE_STUB = r"""
var calls = {confirm: 0, clicks: [], posts: [], tailored: 0, alerts: 0};
var present = {};
var handlers = {};
var pendingPost = null;
var window = {location: null};
function gettext(text) { return text; }
function confirm() { calls.confirm += 1; return true; }
function alert() { calls.alerts += 1; }
function loadingAndRunUnchecked() { calls.tailored += 1; }
function $(selector) {
    var length = present[selector] ? 1 : 0;
    return {
        length: length,
        val: function() { return this; },
        prop: function() { return this; },
        attr: function() { return '/fashion/'; },
        serialize: function() { return 'weight_vit=5'; },
        on: function() { return this; },
        click: function(handler) { handlers[selector] = handler; return this; },
        trigger: function(name) {
            calls.clicks.push(selector);
            if (handlers[selector]) { handlers[selector](); }
            return this;
        }
    };
}
$.post = function(url, data, success) {
    calls.posts.push(url);
    pendingPost = success;
    return {fail: function() { return this; }};
};
"""


def _read(*parts):
    return io.open(os.path.join(*parts), encoding='utf-8').read()


def _confirm_run():
    base = _read(TEMPLATES, 'base.html')
    return re.search(r'function confirmRun\(\) \{.*?\n    \}\n', base, re.S).group(0)


class TailorSavesThePendingEditsFirstTests(SimpleTestCase):

    def run_script(self, body):
        node = shutil.which('node')
        if node is None:
            self.skipTest('node is not installed')
        source = '\n'.join([_PAGE_STUB, _read(HERE, 'static', 'chardata', 'stateengine.js'),
                            _confirm_run(),
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

    def test_save_and_tailor_tailors_at_once_with_nothing_to_save(self):
        engine = _read(HERE, 'static', 'chardata', 'stateengine.js')
        self.assertNotRegex(engine, r'button-save-and-tailor"\)\.prop\("disabled"')
        self.assertEqual({'tailored': 1, 'posts': []}, self.run_script("""
            setupStateEngine(function() {}, '/weightsminspost/7/', {}, null, null);
            $('#button-save-and-tailor').trigger('click');
            return {tailored: calls.tailored, posts: calls.posts};"""))

    def test_save_and_tailor_tailors_only_once_the_save_is_answered(self):
        self.assertEqual([0, ['/weightsminspost/7/'], 1], self.run_script("""
            setupStateEngine(function() {}, '/weightsminspost/7/', {}, null, null);
            setChangesPendingStateEngine(true);
            $('#button-save-and-tailor').trigger('click');
            var before = calls.tailored;
            pendingPost({});
            return [before, calls.posts, calls.tailored];"""))

    def test_the_inclusions_page_tailors_at_once_with_nothing_to_save(self):
        inclusions = _read(TEMPLATES, 'inclusions.html')
        handler = inclusions[inclusions.index('$("#button-save-and-tailor").off'):]
        self.assertRegex(handler, r'^[^\n]*\n\s*if \(!changesPendingStateEngine\) \{\s*'
                                  r'tailorStateEngine\(\);\s*return;\s*\}\s*saveStateEngine\(')

    def test_the_sidebar_tailor_saves_the_weights_page_first_and_never_asks(self):
        self.assertEqual({'allowed': False, 'confirm': 0, 'posts': ['/weightsminspost/7/'],
                          'tailored': 1}, self.run_script("""
            present['#main_form[data-save-before-tailor]'] = true;
            present['#button-save-and-tailor'] = true;
            setupStateEngine(function() {}, '/weightsminspost/7/', {}, null, null);
            setChangesPendingStateEngine(true);
            var allowed = confirmRun();
            pendingPost({});
            return {allowed: allowed, confirm: calls.confirm, posts: calls.posts,
                    tailored: calls.tailored};"""))

    def test_every_other_page_still_asks_before_discarding(self):
        self.assertEqual({'allowed': True, 'confirm': 1, 'posts': []}, self.run_script("""
            present['#button-save-and-tailor'] = true;
            setupStateEngine(function() {}, '/optionspost/7/', {}, null, null);
            setChangesPendingStateEngine(true);
            var allowed = confirmRun();
            return {allowed: allowed, confirm: calls.confirm, posts: calls.posts};"""))

    def test_only_the_weights_page_saves_before_the_sidebar_tailors(self):
        carriers = []
        for path in glob.glob(os.path.join(TEMPLATES, '**', '*.html'), recursive=True):
            if re.search(r'<form[^>]*data-save-before-tailor', _read(path)):
                carriers.append(os.path.basename(path))
        self.assertEqual(['weights_minimums.html'], carriers)

    def test_a_failed_save_is_said_in_every_language(self):
        engine = _read(HERE, 'static', 'chardata', 'stateengine.js')
        self.assertIn('.fail(function() {', engine)
        self.assertIn('gettext("%s")' % FAILED, engine)
        for language in ('fr', 'es', 'pt', 'de'):
            catalogue = polib.pofile(os.path.join(LOCALE, language, 'LC_MESSAGES', 'djangojs.po'))
            entry = catalogue.find(FAILED)
            with self.subTest(language=language):
                self.assertIsNotNone(entry)
                self.assertTrue(entry.msgstr)
                self.assertNotEqual(FAILED, entry.msgstr)
                self.assertNotIn('fuzzy', entry.flags)
