# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Every catalogue string for the player's saved build says build, not project, outside the listed exceptions."""

import glob
import os
import re

from django.test import SimpleTestCase

from chardata.guides_content import GUIDES

LOCALE_DIR = os.path.join(os.path.dirname(__file__), '..', 'locale')

WHOLE_WORD_PROJECT = re.compile(r'\bproject', re.IGNORECASE)

# language code -> pattern matching that language's word for "project"
LOCALIZED_PROJECT_WORD = {
    'fr': re.compile(r'\bprojets?\b', re.IGNORECASE),
    'es': re.compile(r'\bproyectos?\b', re.IGNORECASE),
    'pt': re.compile(r'\bprojetos?\b', re.IGNORECASE),
    'de': re.compile(r'\bProjekt\w*', re.IGNORECASE),
}

GUIDE_CONTENT_FIELDS = ('title', 'desc', 'lead', 'body')
LANGUAGE_CODES = ('en', 'fr', 'es', 'pt', 'de')

# msgid (English source) or guide string -> why it is allowed to still say project
ALLOWED = {
    'Support the project':
        'the website itself, not the player\'s build',
    'Some data has no first-hand source; it comes from these community '
    'projects, with our thanks:':
        'external community software/data projects, not the player\'s build',
    '<b>DofusCreator.</b> When you paste a link to a public DofusCreator '
    'project, our server fetches that page from dofuscreator.com. The call '
    'leaves from our address and not from yours, carries nothing that names '
    'you, and only reads.':
        'a public DofusCreator project is another site\'s own object',
    'Project':
        'dead catalogue entry, not referenced by any template or view',
    'project':
        'dead catalogue entry, not referenced by any template or view',
}


def _guide_strings(node, lang=None):
    """Yield (lang, text) for every string under i18n or i18n_by_group."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key in LANGUAGE_CODES and isinstance(value, dict):
                yield from _guide_strings(value, lang=key)
            elif key in GUIDE_CONTENT_FIELDS and isinstance(value, str) \
                    and lang:
                yield (lang, value)
            else:
                yield from _guide_strings(value, lang=lang)
    elif isinstance(node, (list, tuple)):
        for item in node:
            yield from _guide_strings(item, lang=lang)


def _all_guide_entries():
    for slug, guide in GUIDES.items():
        for lang, text in _guide_strings(guide):
            yield slug, lang, text


class ThePlayersObjectIsCalledABuildTests(SimpleTestCase):

    def _po_files(self):
        try:
            import polib
        except ImportError:
            self.skipTest('polib not installed')
        for po_path in sorted(glob.glob(
                os.path.join(LOCALE_DIR, '*', 'LC_MESSAGES', '*.po'))):
            yield po_path, polib.pofile(po_path, encoding='utf-8')

    def test_no_unlisted_catalogue_string_says_project(self):
        offenders = []
        for po_path, po in self._po_files():
            for entry in po:
                if entry.obsolete:
                    continue
                if WHOLE_WORD_PROJECT.search(entry.msgid) and \
                        entry.msgid not in ALLOWED:
                    offenders.append((os.path.relpath(po_path, LOCALE_DIR),
                                       entry.msgid[:80]))
        self.assertEqual(offenders, [], (
            'these catalogue strings say project without a listed reason: '
            '%s' % offenders))

    def test_no_unlisted_catalogue_translation_says_project(self):
        offenders = []
        for po_path, po in self._po_files():
            lang = os.path.relpath(po_path, LOCALE_DIR).split(os.sep)[0]
            pattern = LOCALIZED_PROJECT_WORD.get(lang)
            if pattern is None:
                continue
            for entry in po:
                if entry.obsolete or entry.msgid in ALLOWED:
                    continue
                texts = [entry.msgstr] + list(entry.msgstr_plural.values())
                for text in texts:
                    if text and pattern.search(text):
                        offenders.append((
                            os.path.relpath(po_path, LOCALE_DIR),
                            entry.msgid[:80], text[:80]))
                        break
        self.assertEqual(offenders, [], (
            'these translations say project even though their English '
            'source does not, or is not a listed exception: %s' % offenders))

    def test_every_allowed_entry_still_exists(self):
        seen = set()
        for _, po in self._po_files():
            for entry in po:
                if not entry.obsolete:
                    seen.add(entry.msgid)
        missing = [msgid for msgid in ALLOWED if msgid not in seen]
        self.assertEqual(missing, [], (
            'these allowed exceptions are no longer in any catalogue and '
            'can be dropped from ALLOWED: %s' % missing))

    def test_no_unlisted_guide_string_says_project(self):
        offenders = []
        for slug, lang, text in _all_guide_entries():
            if lang == 'en' and WHOLE_WORD_PROJECT.search(text) and \
                    text not in ALLOWED:
                offenders.append((slug, text[:80]))
        self.assertEqual(offenders, [], (
            'these guide strings say project without a listed reason: '
            '%s' % offenders))

    def test_no_unlisted_guide_translation_says_project(self):
        offenders = []
        for slug, lang, text in _all_guide_entries():
            pattern = LOCALIZED_PROJECT_WORD.get(lang)
            if pattern is None or text in ALLOWED:
                continue
            if pattern.search(text):
                offenders.append((slug, lang, text[:80]))
        self.assertEqual(offenders, [], (
            'these guide translations say project without a listed reason: '
            '%s' % offenders))
