# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Every chardata template string marked for translation has a real
translation in the French, Spanish, Portuguese and German catalogues."""

import ast
import glob
import io
import os
import re
import unittest

from django.test import SimpleTestCase
from django.utils.translation.template import templatize

ROOT = os.path.join(os.path.dirname(__file__), '..')
LOCALE_DIR = os.path.join(ROOT, 'locale')
TEMPLATES_DIR = os.path.join(ROOT, 'chardata', 'templates')

LANGUAGES = ['fr', 'es', 'pt', 'de']

CALL_RE = re.compile(
    r"(?<![\w.])(?:gettext|_)\(u?"
    r"((?:'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"))\)")
NGETTEXT_RE = re.compile(
    r"ngettext\(u?((?:'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"))\s*,\s*u?"
    r"((?:'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"))")


def _msgids_of(template_path):
    src = io.open(template_path, encoding='utf-8').read()
    code = templatize(src, origin=template_path)
    found = set()
    for match in CALL_RE.finditer(code):
        try:
            found.add(ast.literal_eval(match.group(1)))
        except (ValueError, SyntaxError):
            pass
    for match in NGETTEXT_RE.finditer(code):
        for group in (1, 2):
            try:
                found.add(ast.literal_eval(match.group(group)))
            except (ValueError, SyntaxError):
                pass
    return found


def _wanted_msgids():
    templates = glob.glob(
        os.path.join(TEMPLATES_DIR, '**', '*.html'), recursive=True)
    wanted = {}
    for template_path in templates:
        rel = os.path.relpath(template_path, ROOT)
        for msgid in _msgids_of(template_path):
            wanted.setdefault(msgid, set()).add(rel)
    return wanted


class EveryTemplateStringIsTranslatedTests(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        try:
            import polib
        except ImportError:
            raise unittest.SkipTest('polib not installed')
        cls.wanted = _wanted_msgids()
        cls.catalogues = {}
        cls.plural_keys = set()
        for lang in LANGUAGES:
            po = polib.pofile(
                os.path.join(LOCALE_DIR, lang, 'LC_MESSAGES', 'django.po'),
                encoding='utf-8')
            cls.catalogues[lang] = {e.msgid: e for e in po if not e.obsolete}
            cls.plural_keys |= {
                e.msgid_plural for e in po if e.msgid_plural}

    def test_every_template_string_has_a_translation_in_each_language(self):
        offenders = []
        for msgid, templates in sorted(self.wanted.items()):
            if msgid in self.plural_keys:
                continue
            for lang in LANGUAGES:
                entry = self.catalogues[lang].get(msgid)
                if entry is None:
                    reason = 'absent'
                elif 'fuzzy' in entry.flags:
                    reason = 'fuzzy'
                elif not entry.msgstr and not entry.msgstr_plural:
                    reason = 'empty'
                else:
                    continue
                offenders.append('%s [%s: %s] in %s' % (
                    msgid[:120].replace('\n', ' '), lang, reason,
                    ', '.join(sorted(templates))))
        self.assertEqual(offenders, [], (
            'these template strings lack a real fr/es/pt/de translation:\n'
            + '\n'.join(offenders)))
