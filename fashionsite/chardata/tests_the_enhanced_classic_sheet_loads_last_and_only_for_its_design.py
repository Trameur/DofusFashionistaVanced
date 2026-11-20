# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The enhanced classic sheet is written after every other head sheet, only for a visitor on that design, and holds only rules scoped to it."""
import io
import json
import os
import re
import subprocess
import unittest

from django.test import SimpleTestCase, TestCase

from chardata.tests_the_default_theme_is_automatic_and_a_stored_choice_wins import NODE
from chardata.tests_the_setup_stylesheet_support import STATIC, read_css, stylesheet

TEMPLATES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'chardata')
LOADER = re.compile(r"<script>(if\(document\.documentElement\.classList\.contains\('fm-enhanced'\)\)document\.write\(.*?\);)</script>")

HARNESS = '''
var vm = require('vm'), src = process.argv[1], opt = JSON.parse(process.argv[2]);
var classes = new Set(opt.classes), written = [];
vm.runInNewContext(src, {document: {documentElement: {classList: {contains: function(c){ return classes.has(c); }}}, write: function(t){ written.push(t); }}});
console.log(JSON.stringify(written));
'''


def base():
    with io.open(os.path.join(TEMPLATES, 'base.html'), encoding='utf-8') as handle:
        return handle.read()


def written_for(source, classes):
    done = subprocess.run([NODE, '-e', HARNESS, LOADER.search(source).group(1), json.dumps({'classes': classes})],
                          capture_output=True, text=True, timeout=60)
    if done.returncode:
        raise AssertionError(done.stderr)
    return json.loads(done.stdout)


class TheLoaderSitsAfterTheLastHeadSheetTests(SimpleTestCase):

    def test_the_loader_follows_the_page_sheet_block_and_precedes_the_icons(self):
        text = base()
        loader = LOADER.search(text).start()
        page_block = text.index('{% block modern_page_css %}')
        self.assertLess(text.index('{% endblock %}', page_block), loader)
        self.assertLess(loader, text.index('<link rel="shortcut icon"'))
        self.assertNotIn('rel="stylesheet"', text[LOADER.search(text).end():text.index('</head>')])

    def test_the_loader_names_the_sheet_through_the_static_tag(self):
        self.assertIn('href="{% static "chardata/enhanced.css" %}"', LOADER.search(base()).group(1))


@unittest.skipUnless(NODE, 'node is not installed')
class TheLoaderWritesTheSheetOnlyForItsDesignTests(TestCase):

    def rendered(self):
        return self.client.get('/').content.decode('utf-8')

    def test_the_enhanced_design_gets_exactly_one_stylesheet_link(self):
        written = written_for(self.rendered(), ['fm-enhanced', 'fm-light'])
        self.assertEqual(1, len(written))
        self.assertRegex(written[0], r'^<link rel="stylesheet" type="text/css" href="[^"]*chardata/enhanced[.\w]*\.css">$')

    def test_the_new_and_classic_designs_get_nothing(self):
        page = self.rendered()
        for classes in (['fm-modern', 'fm-dark'], ['fm-light'], ['fm-dark'], []):
            self.assertEqual([], written_for(page, classes), classes)


class TheRenderedPageCarriesTheLoaderTests(TestCase):

    def test_the_home_page_writes_the_loader_after_its_last_stylesheet(self):
        html = self.client.get('/').content.decode('utf-8')
        head = html[:html.index('</head>')]
        loader = LOADER.search(head)
        self.assertIsNotNone(loader)
        before = [tag for tag in re.findall(r'<link[^>]*>', head[:loader.start()]) if 'rel="stylesheet"' in tag]
        after = [tag for tag in re.findall(r'<link[^>]*>', head[loader.end():]) if 'rel="stylesheet"' in tag]
        self.assertIn('modern-', before[-1])
        self.assertEqual([], after)


class TheSheetHoldsOnlyEnhancedRulesTests(SimpleTestCase):

    def test_every_selector_is_scoped_to_the_enhanced_design(self):
        rules = stylesheet('enhanced.css')
        self.assertGreater(len(rules), 300)
        stray = [selector for rule in rules for selector in rule['selectors'] if not selector.startswith('html.fm-enhanced')]
        self.assertEqual([], stray)

    def test_the_sheet_never_names_the_new_design_or_the_root_pseudo_class(self):
        with io.open(os.path.join(STATIC, 'enhanced.css'), encoding='utf-8') as handle:
            text = handle.read()
        self.assertNotIn('fm-modern', text)
        self.assertNotIn(':root', text)

    def test_every_token_the_sheet_uses_is_declared_in_it(self):
        text = read_css('enhanced.css')
        used = set(re.findall(r'var\(\s*(--[\w-]+)', text))
        declared = set(re.findall(r'(--[\w-]+)\s*:', text))
        self.assertTrue(used)
        self.assertEqual([], sorted(used - declared))
