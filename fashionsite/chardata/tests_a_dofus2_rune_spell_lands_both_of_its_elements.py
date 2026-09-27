# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Huppermage rune spells land both elements on Dofus 2; on Dofus 3 the copied row lands once."""
from unittest import mock

from django.test import SimpleTestCase

from chardata.spell_buffs import get_damage_spells_for_version
from chardata.spell_reference import get_spell_reference

RUNE_SPELLS = (13708, 13709, 13711, 13712)

_ONE_ELEMENT = {
    13708: {'en': 'inflicts air damage.', 'fr': 'occasionne des dommages air.',
            'es': 'ocasiona daños de aire.', 'pt': 'inflige danos de ar.',
            'de': 'verursacht luftschaden.'},
    13709: {'en': 'inflicts earth damage.', 'fr': 'occasionne des dommages terre.',
            'es': 'ocasiona daños de tierra.', 'pt': 'inflige danos de terra.',
            'de': 'verursacht erdschaden.'},
    13711: {'en': 'inflicts water damage.', 'fr': 'occasionne des dommages eau.',
            'es': 'ocasiona daños de agua.', 'pt': 'inflige danos de água.',
            'de': 'verursacht wasserschaden.'},
    13712: {'en': 'inflicts fire damage.', 'fr': 'occasionne des dommages feu.',
            'es': 'ocasiona daños de fuego.', 'pt': 'inflige danos de fogo.',
            'de': 'verursacht feuerschaden.'},
}
SAYS = {
    'dofus3': _ONE_ELEMENT,
    'beta': _ONE_ELEMENT,
    'dofus2': {
        13708: {'en': 'inflicts air and earth damage',
                'fr': 'occasionne des dommages air et terre',
                'es': 'ocasiona daños de aire y tierra',
                'pt': 'inflige danos de ar e terra',
                'de': 'verursacht luft- und erdschaden'},
        13709: {'en': 'inflicts earth and water damage',
                'fr': 'occasionne des dommages terre et eau',
                'es': 'ocasiona daños de tierra y agua',
                'pt': 'inflige danos de terra e água',
                'de': 'verursacht erd- und wasserschaden'},
        13711: {'en': 'inflicts water and fire damage',
                'fr': 'occasionne des dommages eau et feu',
                'es': 'ocasiona daños de agua y fuego',
                'pt': 'inflige danos de água e fogo',
                'de': 'verursacht wasser- und feuerschaden'},
        13712: {'en': 'inflicts fire and air damage',
                'fr': 'occasionne des dommages feu et air',
                'es': 'ocasiona daños de fuego y aire',
                'pt': 'inflige danos de fogo e ar',
                'de': 'verursacht feuer- und luftschaden'},
    },
}


def _generator():
    from chardata.tests import itemscraper_module
    return itemscraper_module('generate_damage_spells')


def _in_version(test, version):
    from fashionistapulp.structure import set_current_game_version
    test.addCleanup(set_current_game_version, 'dofus3')
    set_current_game_version(version)


def _spell(version, spell_id):
    return next(spell for spell in get_damage_spells_for_version(version)['Huppermage']
                if spell.spell_id == spell_id)


def _text(version, spell_id, language):
    for entry in get_spell_reference(version).get('Huppermage', []):
        if entry.get('id') == spell_id:
            return ((entry.get('description') or {}).get(language) or '').lower()
    return ''


def _named(version, spell_id):
    said = SAYS[version][spell_id]['en']
    said = said.replace('inflicts ', '').replace(' damage', '').rstrip('.')
    return said.split(' and ')


def _top_cast(spell):
    from chardata.spell_combo import Castable
    return Castable(spell, len(spell.level_req) - 1, False)


class AnkamasTextTests(SimpleTestCase):

    def test_names_two_elements_on_dofus2_and_one_on_dofus3_and_beta(self):
        for version, spells in SAYS.items():
            for spell_id, languages in spells.items():
                for language, said in languages.items():
                    with self.subTest(version=version, spell=spell_id, language=language):
                        self.assertIn(said, _text(version, spell_id, language))


class OneCastLandsTheElementsTheTextNamesTests(SimpleTestCase):

    def test_dofus2_scores_both_rows_in_one_cast(self):
        _in_version(self, 'dofus2')
        for spell_id in RUNE_SPELLS:
            spell = _spell('dofus2', spell_id)
            cast = _top_cast(spell)
            with self.subTest(spell=spell.name):
                self.assertFalse(spell.aggregates)
                self.assertEqual(1, len(cast.plain_alternatives))
                self.assertEqual(_named('dofus2', spell_id),
                                 [row.element for row in cast.plain_alternatives[0]])
                self.assertTrue(all(row.min_dam > 0 for row in cast.plain_alternatives[0]))

    def test_dofus3_and_beta_score_the_copied_row_once(self):
        for version in ('dofus3', 'beta'):
            _in_version(self, version)
            for spell_id in RUNE_SPELLS:
                spell = _spell(version, spell_id)
                cast = _top_cast(spell)
                with self.subTest(version=version, spell=spell.name):
                    self.assertEqual(2, len(spell.effects.elements))
                    self.assertEqual(1, len(cast.plain_alternatives))
                    self.assertEqual(_named(version, spell_id),
                                     [row.element for row in cast.plain_alternatives[0]])


class TheCopiedRowsRuleTests(SimpleTestCase):

    @staticmethod
    def _rows(*shapes):
        return [dict({'element': 'AIR', 'situation': 'a,A|80,1,0', 'triggers': 'I',
                      'ranges': ['9-11', '12-14']}, **extra) for extra in shapes]

    def _groups(self, rows):
        generator = _generator()
        with mock.patch.object(generator, '_duplicated_rows',
                               {'1': {'kept': 1, 'seen': '3.5.17.26 -> 3.6.2.1'}}):
            return generator._build_duplicated_row_aggregates(1, rows, len(rows))

    def test_a_listed_copy_is_one_hit_twice(self):
        self.assertEqual([('', [0]), ('', [1])], self._groups(self._rows({}, {})))

    def test_rows_that_are_not_copies_both_land(self):
        cases = {
            'another element': self._rows({}, {'element': 'EARTH'}),
            'other values': self._rows({}, {'ranges': ['11-13', '14-16']}),
            'another target': self._rows({}, {'situation': 'A|80,1,0'}),
        }
        for name, rows in cases.items():
            with self.subTest(case=name):
                self.assertIsNone(self._groups(rows))
