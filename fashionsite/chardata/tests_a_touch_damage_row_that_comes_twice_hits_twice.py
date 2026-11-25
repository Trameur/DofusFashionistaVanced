# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A Touch damage row the game lists twice, alike in every field, lands twice."""
import copy

from django.test import SimpleTestCase

from chardata.spell_buffs import get_damage_spells_for_version
from chardata.spell_combo import Castable, best_turn
from fashionistapulp.dofus_constants import AIR

VERSIONS = ('touch', 'touchbeta')
PROBE = 4242
BOOMERANG_DAGGERS = 2802

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
           'triggers': 'I', 'delay': 0, 'duration': 0, 'random': 0, 'rawZone': 'U2', 'isPreview': False}
    row.update(extra)
    return row


def _decode(effects, critical=None):
    level = {'minPlayerLevel': 1, 'apCost': 3, 'maxCastPerTurn': 2, 'maxStack': 0,
             'criticalHitProbability': 15, 'effects': effects,
             'criticalEffect': effects if critical is None else critical}
    spell = {'id': PROBE, 'nameId': 'Probe', 'descriptionId': 'Occasionne des dommages Air.',
             'spellLevels': [PROBE * 10]}
    return _reader().decode_spell(spell, {str(PROBE * 10): level}, {str(PROBE): spell})


def _spell(version, spell_id):
    return next(spell for spells in get_damage_spells_for_version(version).values()
                for spell in spells if spell.spell_id == spell_id)


def _in_version(test, version):
    from fashionistapulp.structure import set_current_game_version
    test.addCleanup(set_current_game_version, 'dofus3')
    set_current_game_version(version)


class TheTouchReaderKeepsBothCopiesOfARowTests(SimpleTestCase):

    def test_a_row_listed_twice_is_two_hits_of_its_element(self):
        entry = _decode([_row(98, 10, 14, order=1), _row(98, 10, 14, order=2)])
        self.assertEqual(entry['non_crit_ranges'], [['10-14'], ['10-14']])
        self.assertEqual(entry['crit_ranges'], [['10-14'], ['10-14']])
        self.assertEqual([_reader().element_const(token) for token in entry['elements']],
                         ['AIR', 'AIR'])

    def test_two_lines_of_one_element_that_differ_still_keep_the_strongest(self):
        entry = _decode([_row(98, 10, 14), _row(98, 6, 8)])
        self.assertEqual(entry['non_crit_ranges'], [['10-14']])

    def test_a_row_listed_twice_beside_a_stronger_line_of_its_element_stops_the_reader(self):
        with self.assertRaises(SystemExit):
            _decode([_row(98, 10, 14), _row(98, 10, 14), _row(98, 20, 24)])

    def test_a_steal_listed_twice_stops_the_reader(self):
        with self.assertRaises(SystemExit):
            _decode([_row(93, 10, 14), _row(93, 10, 14)])

    def test_a_row_listed_twice_on_one_kind_of_hit_only_stops_the_reader(self):
        with self.assertRaises(SystemExit):
            _decode([_row(98, 10, 14), _row(98, 10, 14)], critical=[_row(98, 12, 16)])


class TheTouchTablesLandBoomerangDaggersTwiceTests(SimpleTestCase):

    def test_boomerang_daggers_carries_two_equal_air_hits_at_every_rank(self):
        for version in VERSIONS:
            spell = _spell(version, BOOMERANG_DAGGERS)
            digest = spell.get_effects_digest()
            with self.subTest(version=version):
                for ranks in (digest.non_crit_dams, digest.crit_dams):
                    self.assertEqual(len(ranks), len(spell.level_req))
                    for rank in ranks:
                        self.assertEqual([row.element for row in rank], [AIR, AIR])
                        self.assertEqual((rank[0].min_dam, rank[0].max_dam),
                                         (rank[1].min_dam, rank[1].max_dam))

    def test_one_cast_of_boomerang_daggers_deals_twice_one_of_its_hits(self):
        for version in VERSIONS:
            _in_version(self, version)
            spell = _spell(version, BOOMERANG_DAGGERS)
            cast = Castable(spell, len(spell.level_req) - 1, False)
            one = copy.copy(cast)
            one.plain_alternatives = [rows[:1] for rows in cast.plain_alternatives]
            one.crit_alternatives = [rows[:1] for rows in cast.crit_alternatives]
            one.alternatives = one.plain_alternatives
            both, _order = best_turn(dict(_STATS), [cast], cast.cost, game_version=version,
                                     caster_level=200)
            single, _order = best_turn(dict(_STATS), [one], one.cost, game_version=version,
                                       caster_level=200)
            with self.subTest(version=version):
                self.assertGreater(single, 0)
                self.assertAlmostEqual(both, 2 * single)
