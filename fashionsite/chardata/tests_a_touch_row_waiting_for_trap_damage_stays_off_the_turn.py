# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A Touch row that lands only when the target suffers trap damage waits apart from the cast."""
from django.test import SimpleTestCase
from django.utils import translation

from chardata.spell_buffs import get_damage_spells_for_version
from chardata.spell_combo import Castable, best_turn

VERSIONS = ('touch', 'touchbeta')
PROBE = 4242
CONSPIRACY = 62
LABEL = {'en': 'only if the target suffers trap damage',
         'fr': 'seulement si la cible subit des dommages de pièges',
         'es': 'solo si el objetivo sufre daños con trampas',
         'pt': 'apenas se o alvo sofrer dano de armadilhas',
         'de': 'nur wenn das Ziel Fallenschaden erleidet'}

_STATS = {'str': 200, 'int': 200, 'cha': 200, 'agi': 200, 'pow': 0, 'dam': 0,
          'cridam': 0, 'heals': 0, 'perspedam': 0, 'perweadam': 0,
          'permedam': 0, 'perrandam': 0, 'earthdam': 0, 'firedam': 0,
          'waterdam': 0, 'airdam': 0, 'neutdam': 0, 'ch': 0, 'final': 0,
          'negfinal': 0, 'pshdam': 0, 'ap': 12}


def _reader():
    from chardata.tests import itemscraper_module
    return itemscraper_module('get_spells_touch')


def _row(effect_id, low, high, mask='a,A', **extra):
    row = {'effectId': effect_id, 'diceNum': low, 'diceSide': high, 'value': 0, 'targetMask': mask,
           'triggers': 'I', 'delay': 0, 'duration': 0, 'random': 0, 'rawZone': 'P', 'isPreview': False}
    row.update(extra)
    return row


def _decode(effects, critical=None):
    level = {'minPlayerLevel': 1, 'apCost': 2, 'maxCastPerTurn': 1, 'maxStack': 0,
             'criticalHitProbability': 0, 'effects': effects,
             'criticalEffect': effects if critical is None else critical}
    spell = {'id': PROBE, 'nameId': 'Probe', 'descriptionId': 'Vole des PV dans l\'élément Feu.',
             'spellLevels': [PROBE * 10]}
    return _reader().decode_spell(spell, {str(PROBE * 10): level}, {str(PROBE): spell})


def _spell(version, spell_id):
    return next(spell for spells in get_damage_spells_for_version(version).values()
                for spell in spells if spell.spell_id == spell_id)


def _in_version(test, version):
    from fashionistapulp.structure import set_current_game_version
    test.addCleanup(set_current_game_version, 'dofus3')
    set_current_game_version(version)


class TheTouchReaderHoldsARowWaitingForTrapDamageTests(SimpleTestCase):

    def test_a_row_on_trap_damage_waits_for_it_and_does_not_land_later(self):
        entry = _decode([_row(94, 15, 0, mask='A', triggers='DP', duration=1)])
        self.assertEqual(entry['conditional'], {0: 'trap_damage'})
        self.assertFalse(entry.get('delayed'))

    def test_a_row_on_trap_damage_beside_a_hit_of_its_element_stops_the_reader(self):
        with self.assertRaises(SystemExit):
            _decode([_row(94, 10, 14), _row(94, 15, 0, triggers='DP', duration=1)])

    def test_a_damage_row_on_a_trigger_no_rule_reads_stops_the_reader(self):
        with self.assertRaises(SystemExit):
            _decode([_row(94, 10, 14, triggers='XYZ')])

    def test_a_preview_row_on_an_unread_trigger_is_left_alone(self):
        entry = _decode([_row(94, 10, 14), _row(94, 10, 14, triggers='XYZ', isPreview=True)])
        self.assertEqual(entry['non_crit_ranges'], [['10-14']])


class TheTouchTablesHoldConspiracyApartTests(SimpleTestCase):

    def test_conspiracy_waits_for_trap_damage(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                spell = _spell(version, CONSPIRACY)
                self.assertEqual(spell.conditional, {0: 'trap_damage'})
                self.assertFalse(getattr(spell, 'delayed', None))

    def test_a_lone_conspiracy_adds_nothing_to_the_turn(self):
        for version in VERSIONS:
            _in_version(self, version)
            spell = _spell(version, CONSPIRACY)
            cast = Castable(spell, len(spell.level_req) - 1, False)
            total, order = best_turn(dict(_STATS), [cast], 12, game_version=version,
                                     caster_level=200)
            with self.subTest(version=version):
                self.assertEqual((total, order), (0.0, []))

    def test_the_spell_card_names_the_wait_in_each_language(self):
        from chardata import spells_view
        for version in VERSIONS:
            spell = _spell(version, CONSPIRACY)
            for language, text in LABEL.items():
                with translation.override(language), self.subTest(version=version,
                                                                  language=language):
                    digest = spells_view._create_spell_web_digest(spell, version, char_level=200)
                    self.assertEqual(digest['conditional'], {'0': text})
