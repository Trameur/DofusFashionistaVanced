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

    def test_the_beta_borrows_a_dofus_3_icon_it_lacks(self):
        own = os.listdir(os.path.join(STATIC, 'chardata', 'spells', 'beta'))
        shared = os.listdir(os.path.join(STATIC, 'chardata', 'spells'))
        borrowed = next(name[:-4] for name in shared
                        if name.endswith('.png') and name not in own)
        self.assertIn('/chardata/spells/%s.png' % borrowed,
                      unquote(_spell_image_url(borrowed, 'beta')))
