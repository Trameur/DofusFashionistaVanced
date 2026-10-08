# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A DofusBook weapon code reads into the build's weapon element and is written back the same way."""
import json
from unittest import mock

from django.test import SimpleTestCase, TestCase, override_settings

from chardata import dofusbook_export, text_build_view
from chardata.dofusbook_import import (FM_CODES, WEAPON_FIELDS, read_build,
                                       read_weapon_code, read_weapon_forge, weapon_letters)
from chardata.models import Char
from chardata.solution import get_solution
from fashionistapulp import weapon_forge
from fashionistapulp.dofus_constants import AIR, EARTH, FIRE, NEUTRAL, WATER
from fashionistapulp.structure import get_structure, set_current_game_version

_VERSIONS = ('dofus3', 'beta', 'dofus2', 'touch', 'retro')
_LINK = 'https://www.dofusbook.net/fr/stuff/7894460-zobal-m-200'
_HIDSAD_BOW = 1355
_HUNTING_KNIFE = 1934


def _field(kind):
    return next(field for field_kind, field, _key, _prefix in WEAPON_FIELDS
                if field_kind == kind)


def _key(kind):
    return next(key for field_kind, _field, key, _prefix in WEAPON_FIELDS
                if field_kind == kind)


class TheirWeaponCodesReadBackTests(SimpleTestCase):

    def test_the_element_letters_come_from_their_damage_codes(self):
        letters = weapon_letters()
        self.assertEqual({'t': EARTH, 'f': FIRE, 'e': WATER, 'a': AIR}, letters)
        for letter in letters:
            self.assertIn('d%sf' % letter, FM_CODES)

    def test_every_conversion_a_version_sells_writes_a_code_that_reads_back(self):
        for version in _VERSIONS:
            for kind in weapon_forge.kinds(version):
                for element, tier in weapon_forge.offer(version, kind):
                    with self.subTest(version=version, kind=kind, element=element, tier=tier):
                        codes = dofusbook_export.weapon_codes(version, {kind: (element, tier)})
                        self.assertEqual([_field(kind)], list(codes))
                        self.assertEqual((element, tier),
                                         read_weapon_code(version, kind, codes[_field(kind)]))
                        self.assertEqual(({kind: (element, tier)}, []),
                                         read_weapon_forge({_key(kind): codes[_field(kind)]},
                                                           version))

    def test_a_full_choice_writes_one_code_per_kind(self):
        chosen = {'damage': (FIRE, 'strong'), 'steal': (WATER, 'weak'), 'heal': (AIR, 'strong')}
        self.assertEqual({'fmWeapon': 'df-100', 'fmStealWeapon': 've-10',
                          'fmHealWeapon': 'pva-100'},
                         dofusbook_export.weapon_codes('dofus3', chosen))

    def test_neutral_writes_nothing(self):
        self.assertEqual({'fmStealWeapon': 'vf-10'}, dofusbook_export.weapon_codes(
            'beta', {'damage': (NEUTRAL, 'strong'), 'steal': (FIRE, 'weak')}))
        self.assertEqual({}, dofusbook_export.weapon_codes('dofus3', {}))
        self.assertEqual({}, dofusbook_export.weapon_codes('dofus3', None))

    def test_the_codes_seen_on_their_builds_read_only_at_a_rate_the_version_sells(self):
        for version, code, expected in (('dofus3', 'de-85', None),
                                        ('dofus3', 'de-100', (WATER, 'strong')),
                                        ('dofus2', 'de-85', (WATER, 'strong')),
                                        ('dofus2', 'df-68', (FIRE, 'medium')),
                                        ('touch', 'df-68', (FIRE, 'medium')),
                                        ('retro', 'df-68', None),
                                        ('retro', 'df-85', (FIRE, 'strong'))):
            with self.subTest(version=version, code=code):
                self.assertEqual(expected, read_weapon_code(version, 'damage', code))

    def test_a_code_that_cannot_be_read_stays_left_out(self):
        build = {'fm_weapon': 'de-85', 'fm_steal_weapon': 'vf-100',
                 'fm_heal_weapon': 'pvx-100'}
        self.assertEqual(({'steal': (FIRE, 'strong')}, ['de-85', 'pvx-100']),
                         read_weapon_forge(build, 'dofus3'))
        for code in ('dn-100', 'df-0100', 'df-', 'df100', 'vf-100', ' df-100', 7):
            with self.subTest(code=code):
                self.assertIsNone(read_weapon_code('dofus3', 'damage', code))
        self.assertIsNone(read_weapon_code('touch', 'heal', 'pva-50'))
        self.assertEqual(({}, []), read_weapon_forge({'fm_weapon': None}, 'dofus3'))

    def test_their_api_hands_the_three_fields_through(self):
        payload = {'stuff': {'name': 'Forged', 'character_level': 1,
                             'stuffItem': {'ar': 1}},
                   'items': [{'id': 1, 'official': _HIDSAD_BOW, 'name': 'Hidsad'}],
                   'fmItems': {}, 'fmGlobal': {}, 'fmWeapon': 'df-100',
                   'fmStealWeapon': 've-10', 'fmHealWeapon': 'pva-100'}

        class _Answer(object):
            def read(self, *args):
                return json.dumps(payload).encode('utf-8')

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        build = read_build(_LINK, opener=lambda request, timeout=None: _Answer())
        self.assertEqual(('df-100', 've-10', 'pva-100'),
                         (build['fm_weapon'], build['fm_steal_weapon'],
                          build['fm_heal_weapon']))


@override_settings(BUILD_SITES_ENABLED=('dofusbook',))
class AnImportThenAnExportKeepsTheConversionTests(TestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')
        self.structure = get_structure('dofus3')
        self.hat = next(item for item in self.structure.types[200]['Hat']
                        if not item.removed and item.ankama_id)

    def _patch(self, build):
        real = text_build_view.read_build
        text_build_view.read_build = lambda url, opener=None: build
        self.addCleanup(setattr, text_build_view, 'read_build', real)

    def _build(self, weapon, level, **codes):
        build = {'game_version': 'dofus3', 'source_host': 'www.dofusbook.net',
                 'build_id': '7894460', 'name': 'Forged', 'level': level,
                 'item_ids': [self.hat.id, self.structure.get_item_by_ankama_id(weapon).id],
                 'missing': [], 'base_points': {}, 'base_scrolled': {},
                 'class_is_unknown': True}
        build.update(codes)
        return build

    def _import(self, build):
        self._patch(build)
        preview = self.client.post('/import/text/', {'text': _LINK},
                                   HTTP_ACCEPT_LANGUAGE='en').content.decode('utf-8')
        self.client.post('/import/text/', {'text': _LINK, 'confirm': '1', 'char_class': 'Iop',
                                           'level': str(build['level'])},
                         HTTP_ACCEPT_LANGUAGE='en')
        return preview, Char.objects.order_by('-id').first()

    def _export(self, char):
        ankama_ids = [self.hat.ankama_id, _HIDSAD_BOW, _HUNTING_KNIFE]
        answer = mock.MagicMock()
        answer.__enter__.return_value = answer
        answer.read.return_value = json.dumps(
            {'data': [{'official': ankama_id} for ankama_id in ankama_ids]}).encode('utf-8')
        with mock.patch('chardata.dofusbook_import._urlopen_allowlisted', return_value=answer):
            return self.client.get('/export/dofusbook/%d/' % char.id,
                                   HTTP_ACCEPT_LANGUAGE='en').content.decode('utf-8')

    def test_their_codes_become_the_build_choice_and_come_back_out(self):
        for weapon, level, codes, chosen in (
                (_HIDSAD_BOW, 200, {'fm_weapon': 'df-100', 'fm_heal_weapon': 'pve-10'},
                 {'damage': (FIRE, 'strong'), 'heal': (WATER, 'weak')}),
                (_HUNTING_KNIFE, 1, {'fm_weapon': 'da-10'}, {'damage': (AIR, 'weak')})):
            with self.subTest(weapon=weapon, level=level):
                preview, char = self._import(self._build(weapon, level, **codes))
                self.assertIn('import-link-weapon-forge', preview)
                self.assertNotIn('import-link-fm-weapon', preview)
                for kind, (element, tier) in chosen.items():
                    self.assertIn(weapon_forge.item_name('dofus3', kind, element, tier, 'en'),
                                  preview)
                self.assertEqual(level, char.level)
                self.assertEqual(weapon_forge.write_choice(chosen), char.weapon_forge)
                set_current_game_version('dofus3')
                worn = get_solution(char).items['Weapon'][0]
                self.assertEqual({_field(kind): code for kind, code in (
                    ('damage', codes.get('fm_weapon')), ('heal', codes.get('fm_heal_weapon')))
                    if code}, dofusbook_export.weapon_codes('dofus3', worn.conversions))
                page = self._export(char)
                self.assertIn('export-weapon-forge', page)
                for kind, (element, tier) in chosen.items():
                    self.assertIn(weapon_forge.item_name('dofus3', kind, element, tier, 'en'),
                                  page)

    def test_a_code_we_cannot_read_keeps_the_notice_and_the_build_stays_auto(self):
        preview, char = self._import(self._build(_HIDSAD_BOW, 200, fm_weapon='de-85'))
        self.assertIn('import-link-fm-weapon', preview)
        self.assertNotIn('import-link-weapon-forge', preview)
        self.assertEqual('', char.weapon_forge)

    def test_a_partly_read_link_names_the_code_it_left_out(self):
        preview, char = self._import(self._build(_HIDSAD_BOW, 200, fm_weapon='df-100',
                                                 fm_steal_weapon='ve-85'))
        self.assertIn('import-link-weapon-forge', preview)
        self.assertIn('import-link-fm-weapon', preview)
        self.assertIn('(ve-85)', preview)
        self.assertEqual(weapon_forge.write_choice({'damage': (FIRE, 'strong')}),
                         char.weapon_forge)

    def test_a_link_without_a_code_leaves_the_build_auto(self):
        preview, char = self._import(self._build(_HUNTING_KNIFE, 1))
        self.assertNotIn('import-link-fm-weapon', preview)
        self.assertNotIn('import-link-weapon-forge', preview)
        self.assertEqual('', char.weapon_forge)

    def test_an_auto_build_has_no_weapon_note(self):
        _preview, char = self._import(self._build(_HIDSAD_BOW, 200))
        self.assertNotIn('export-weapon-forge', self._export(char))

    def test_a_build_without_a_weapon_has_no_weapon_note(self):
        build = self._build(_HUNTING_KNIFE, 200, fm_weapon='df-100')
        build['item_ids'] = [self.hat.id]
        _preview, char = self._import(build)
        self.assertNotIn('export-weapon-forge', self._export(char))
