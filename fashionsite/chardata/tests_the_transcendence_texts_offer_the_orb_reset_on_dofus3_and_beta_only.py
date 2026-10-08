# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The transcendence guide and forgemagie page name the orb that resets a transcended item where the game allows it."""
import json
import os

from django.test import TestCase

LANGUAGES = ('en', 'fr', 'es', 'pt', 'de')
NEW_LEAF_ORB = 17273
RESOURCE_DIRECTORY = {'dofus3': '', 'beta': 'beta'}


def _orb_names(version):
    from fashionistapulp.fashionista_config import get_fashionista_path
    names = {}
    for language in LANGUAGES:
        path = os.path.join(get_fashionista_path(), 'itemscraper',
                            RESOURCE_DIRECTORY[version],
                            'all_resources_%s.json' % language)
        with open(path, encoding='utf-8') as handle:
            data = json.load(handle)
        items = data if isinstance(data, list) else data['items']
        names[language] = next(item['name'] for item in items
                               if isinstance(item, dict)
                               and item.get('ankama_id') == NEW_LEAF_ORB)
    return names


def _guide_text(version, language):
    from chardata.guides_content import get_guide
    guide = get_guide('transcendence-runes', language, version)
    return ' '.join(guide[field] for field in ('title', 'desc', 'lead', 'body'))


def _intro(version, language):
    from chardata.forgemagie_data import get_ruleset
    from chardata.forgemagie_view import _transcendence_text
    return _transcendence_text(language, get_ruleset(version))['intro']


class TheOrbResetTests(TestCase):

    def test_each_version_reads_one_orb_name_per_language(self):
        for version in RESOURCE_DIRECTORY:
            with self.subTest(version=version):
                names = _orb_names(version)
                self.assertEqual(sorted(LANGUAGES), sorted(names))
                self.assertTrue(all(names.values()))

    def test_the_dofus3_and_beta_guides_name_the_orb_in_every_language(self):
        for version in RESOURCE_DIRECTORY:
            names = _orb_names(version)
            for language in LANGUAGES:
                with self.subTest(version=version, language=language):
                    self.assertIn(names[language], _guide_text(version, language))

    def test_the_dofus2_guide_names_no_orb_and_reads_unlike_dofus3(self):
        names = _orb_names('dofus3')
        for language in LANGUAGES:
            with self.subTest(language=language):
                dofus2 = _guide_text('dofus2', language)
                self.assertNotIn(names[language], dofus2)
                self.assertNotEqual(_guide_text('dofus3', language), dofus2)

    def test_the_forgemagie_intro_names_the_orb_on_dofus3_and_beta_only(self):
        for version in ('dofus3', 'beta', 'dofus2'):
            names = _orb_names('beta' if version == 'beta' else 'dofus3')
            for language in LANGUAGES:
                with self.subTest(version=version, language=language):
                    if version == 'dofus2':
                        self.assertNotIn(names[language], _intro(version, language))
                    else:
                        self.assertIn(names[language], _intro(version, language))

    def test_the_served_forgemagie_page_follows_its_version(self):
        name = _orb_names('dofus3')['en']
        for prefix, offered in (('', True), ('beta/', True), ('dofus2/', False)):
            with self.subTest(prefix=prefix):
                body = self.client.get('/%sforgemagie/' % prefix,
                                       HTTP_ACCEPT_LANGUAGE='en').content.decode('utf-8')
                self.assertIn('Transcendence runes (lock smithmagic)', body)
                self.assertEqual(offered, name in body)
