# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The shared page template tells every same-origin ajax call which language the page is in."""

import os
import re
import unittest

BASE = os.path.join(os.path.dirname(__file__), 'templates', 'chardata', 'base.html')


class EveryPageScriptSendsItsLanguageWithEachRequestTests(unittest.TestCase):

    def setUp(self):
        with open(BASE, encoding='utf-8') as handle:
            self.source = handle.read()

    def test_the_global_ajax_setup_sets_the_language_header(self):
        self.assertRegex(self.source, r"setRequestHeader\('X-Page-Language', '\{\{ LANGUAGE_CODE\|escapejs \}\}'\)")

    def test_the_header_is_not_sent_to_another_origin(self):
        self.assertRegex(self.source, r'if \(!settings\.crossDomain\)[^}]*X-Page-Language')

    def test_no_page_script_replaces_the_global_before_send(self):
        folder = os.path.dirname(BASE)
        static = os.path.join(os.path.dirname(__file__), 'static', 'chardata')
        for root in (folder, static):
            for name in os.listdir(root):
                if not name.endswith(('.html', '.js')):
                    continue
                with open(os.path.join(root, name), encoding='utf-8', errors='ignore') as handle:
                    text = handle.read()
                if name == 'base.html':
                    continue
                with self.subTest(file=name):
                    self.assertFalse(re.search(r'ajaxSetup\([^)]*beforeSend', text, re.S))
