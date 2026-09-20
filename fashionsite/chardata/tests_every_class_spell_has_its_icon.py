# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
import json
import os
from urllib.parse import unquote

from django.conf import settings
from django.test import SimpleTestCase

from chardata.spells_view import _reference_icon_name, _spell_image_url

HERE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(HERE, 'static')


def _reference(game_version):
    path = os.path.join(HERE, 'spell_reference', '%s.json' % game_version)
    with open(path, encoding='utf-8') as handle:
        return json.load(handle)


def _icon_file(url):
    relative = unquote(url.split('?', 1)[0])
    prefix = settings.STATIC_URL
    if relative.startswith(prefix):
        relative = relative[len(prefix):]
    return os.path.join(STATIC, *relative.split('/'))


class EveryClassSpellHasItsIconTests(SimpleTestCase):

    def _missing(self, game_version):
        from chardata.spell_buffs import get_damage_spells_for_version
        missing = []
        for class_name, entries in _reference(game_version).items():
            if class_name == 'default':
                # Shown under the model's names, the client renames some
                names = [spell.name for spell in
                         get_damage_spells_for_version(game_version)['default']]
            else:
                names = [_reference_icon_name(entry, '', game_version)
                         for entry in entries]
            for name in names:
                url = _spell_image_url(name, game_version)
                if not os.path.exists(_icon_file(url)):
                    missing.append((class_name, name))
        return missing

    def test_touch(self):
        self.assertEqual([], self._missing('touch'))

    def test_beta(self):
        self.assertEqual([], self._missing('beta'))

    def test_dofus3(self):
        self.assertEqual([], self._missing('dofus3'))

    def test_dofus2(self):
        self.assertEqual([], self._missing('dofus2'))

    def test_retro(self):
        self.assertEqual([], self._missing('retro'))

    def _retro_by_french_name(self):
        by_name = {}
        for entries in _reference('retro').values():
            for entry in entries:
                by_name.setdefault(entry['name']['fr'], []).append(entry)
        return by_name

    def test_retro_spells_sharing_a_name_resolve_to_distinct_existing_icons(self):
        from chardata.spells_view import _create_reference_web_digest
        shared = {name: entries
                  for name, entries in self._retro_by_french_name().items()
                  if len(entries) > 1}
        self.assertTrue(shared)
        for name, entries in shared.items():
            files = [_icon_file(_create_reference_web_digest(entry, 'retro')
                                ['image_url'])
                     for entry in entries]
            with self.subTest(name=name):
                self.assertEqual(len(entries), len(set(files)))
                for path in files:
                    self.assertTrue(os.path.exists(path), path)

    def test_the_lowest_id_of_a_retro_homonym_keeps_the_bare_name(self):
        for name, entries in self._retro_by_french_name().items():
            keeper = min(entry['id'] for entry in entries)
            for entry in entries:
                expected = (name if entry['id'] == keeper
                            else '%s (%s)' % (name, entry['id']))
                self.assertEqual(expected,
                                 _reference_icon_name(entry, '', 'retro'))

    def _by_icon_name(self, game_version):
        from chardata.spells_view import SPELL_ICON_LANGUAGE
        language = SPELL_ICON_LANGUAGE.get(game_version, 'en')
        by_name = {}
        for entries in _reference(game_version).values():
            for entry in entries:
                by_name.setdefault(entry['name'][language], []).append(entry)
        return by_name

    def _shared_names(self, game_version):
        return {name: entries
                for name, entries in self._by_icon_name(game_version).items()
                if len({entry['id'] for entry in entries}) > 1}

    def test_spells_sharing_a_name_resolve_to_distinct_existing_icons_on_every_version(self):
        from chardata.spells_view import _create_reference_web_digest
        for game_version in ('dofus3', 'beta', 'dofus2', 'retro'):
            shared = self._shared_names(game_version)
            with self.subTest(game_version=game_version):
                self.assertTrue(shared)
            for name, entries in shared.items():
                files = [_icon_file(_create_reference_web_digest(
                    entry, game_version)['image_url']) for entry in entries]
                with self.subTest(game_version=game_version, name=name):
                    self.assertEqual(len(entries), len(set(files)))
                    for path in files:
                        self.assertTrue(os.path.exists(path), path)

    def test_the_lowest_id_of_a_homonym_keeps_the_bare_name_on_every_version(self):
        from fashionistapulp.game_versions import version_keys
        for game_version in version_keys():
            for name, entries in self._by_icon_name(game_version).items():
                keeper = min(entry['id'] for entry in entries)
                for entry in entries:
                    expected = (name if entry['id'] == keeper
                                else '%s (%s)' % (name, entry['id']))
                    with self.subTest(game_version=game_version, name=name):
                        self.assertEqual(
                            expected,
                            _reference_icon_name(entry, '', game_version))

    def test_the_english_homonyms_file_the_higher_id_under_its_id(self):
        english = {13352: 'Collapse', 23736: 'Collapse (23736)',
                   13860: 'Compass', 13877: 'Compass (13877)',
                   13356: 'Wandering', 14604: 'Wandering (14604)'}
        # Dofus 2 still names the Eliotrope spell Flexible Portal
        expected = {'dofus3': english, 'beta': english,
                    'dofus2': {spell_id: name
                               for spell_id, name in english.items()
                               if not name.startswith('Wandering')}}
        for game_version, names in expected.items():
            shared = self._shared_names(game_version)
            with self.subTest(game_version=game_version):
                self.assertEqual({name.split(' (')[0] for name in names.values()},
                                 set(shared))
            by_id = {entry['id']: entry
                     for entries in shared.values() for entry in entries}
            for spell_id, name in names.items():
                with self.subTest(game_version=game_version, spell_id=spell_id):
                    self.assertEqual(name, _reference_icon_name(
                        by_id[spell_id], '', game_version))

    def test_the_beta_borrows_a_dofus_3_icon_it_lacks(self):
        own = os.listdir(os.path.join(STATIC, 'chardata', 'spells', 'beta'))
        shared = os.listdir(os.path.join(STATIC, 'chardata', 'spells'))
        borrowed = next(name[:-4] for name in shared
                        if name.endswith('.png') and name not in own)
        self.assertIn('/chardata/spells/%s.png' % borrowed,
                      unquote(_spell_image_url(borrowed, 'beta')))
