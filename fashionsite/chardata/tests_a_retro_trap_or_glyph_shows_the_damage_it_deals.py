# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
import io
import json
import os
import unittest

from django.test import SimpleTestCase
from django.utils.translation import override

from chardata.spell_buffs import get_damage_spells_for_version
from fashionistapulp.dofus_constants import EARTH, FIRE

TRICKY_TRAP = 65
LETHAL_TRAP = 80
BURNING_GLYPH = 10
SNEAKINESS = 61

# Class spell -> the spell its placing row names
PLACING = {10: 351, 12: 1505, 13: 908, 15: 907, 17: 1503,
           65: 2007, 69: 909, 71: 1495, 73: 1688, 77: 1497, 79: 1493, 80: 1499}
CHILD_WITH_DAMAGE = {351, 1503, 2007, 1495, 1493, 1499}

RAW = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), 'itemscraper', 'retro_raw')


def _spell(char_class, spell_id):
    return next(spell for spell in get_damage_spells_for_version('retro')[char_class]
                if spell.spell_id == spell_id)


def _rows(ranges):
    if ranges is None:
        return None
    return [[(r.min_dam, r.max_dam) for r in row] for row in ranges]


def _reader():
    from chardata.tests import itemscraper_module
    return itemscraper_module('get_spells_retro')


class ThePlacedThingsDamageIsReadFromItsOwnRecordTests(SimpleTestCase):

    def test_a_trap_carries_its_explosion_spells_earth_line(self):
        trap = _spell('Sram', TRICKY_TRAP)
        self.assertEqual('Piège Sournois', trap.name)
        self.assertEqual([1, 1, 1, 1, 1, 101], trap.level_req)
        self.assertEqual([[(5, 9), (6, 10), (7, 11), (8, 12), (9, 13), (13, 17)]],
                         _rows(trap.effects.non_crit_ranges))
        self.assertEqual([[(7, 11), (8, 12), (9, 13), (10, 14), (11, 15), (15, 19)]],
                         _rows(trap.effects.crit_ranges))
        self.assertEqual([EARTH], trap.effects.elements)
        self.assertEqual([('Trap damage', [0])], trap.aggregates)
        self.assertEqual({0: 'trap'}, trap.conditional)
        self.assertEqual({}, trap.delayed)
        self.assertEqual({'ap': [2, 2, 2, 2, 2, 2], 'per_target': [1, 2, 3, 4, 5, 6]},
                         trap.casting)

    def test_a_trap_whose_child_cannot_crit_repeats_its_line_as_every_retro_row_does(self):
        trap = _spell('Sram', LETHAL_TRAP)
        self.assertEqual('Piège Mortel', trap.name)
        self.assertEqual([100, 100, 100, 100, 100, 200], trap.level_req)
        line = [[(21, 40), (26, 45), (31, 50), (36, 55), (41, 60), (41, 60)]]
        self.assertEqual(line, _rows(trap.effects.non_crit_ranges))
        self.assertEqual(line, _rows(trap.effects.crit_ranges))
        self.assertEqual([EARTH], trap.effects.elements)
        self.assertEqual([('Trap damage', [0])], trap.aggregates)
        self.assertEqual({0: 'trap'}, trap.conditional)
        self.assertNotIn('crit', trap.casting)

    def test_a_glyph_carries_its_fire_spells_line_and_lands_at_the_start_of_a_turn(self):
        glyph = _spell('Feca', BURNING_GLYPH)
        self.assertEqual('Glyphe Enflammé', glyph.name)
        self.assertEqual([70, 70, 70, 70, 70, 170], glyph.level_req)
        self.assertEqual([[(19, 27), (21, 29), (23, 31), (25, 33), (27, 35), (27, 35)]],
                         _rows(glyph.effects.non_crit_ranges))
        self.assertEqual([[(24, 32), (27, 35), (30, 38), (33, 41), (36, 44), (36, 44)]],
                         _rows(glyph.effects.crit_ranges))
        self.assertEqual([FIRE], glyph.effects.elements)
        self.assertEqual([('Glyph damage', [0])], glyph.aggregates)
        self.assertEqual({}, glyph.conditional)
        self.assertEqual({0: 'turn_begin'}, glyph.delayed)

    def test_a_spell_that_was_complete_is_untouched(self):
        spell = _spell('Sram', SNEAKINESS)
        self.assertEqual('Sournoiserie', spell.name)
        self.assertEqual([1, 1, 1, 1, 1, 101], spell.level_req)
        self.assertEqual([[(2, 4), (3, 5), (4, 6), (5, 7), (6, 8), (11, 13)]],
                         _rows(spell.effects.non_crit_ranges))
        self.assertEqual([[(4, 6), (5, 7), (6, 8), (7, 9), (8, 10), (20, 20)]],
                         _rows(spell.effects.crit_ranges))
        self.assertEqual([EARTH], spell.effects.elements)
        self.assertEqual([], spell.aggregates)
        self.assertIsNone(spell.is_linked)
        self.assertEqual(1, spell.stacks)
        self.assertEqual({'ap': [4, 4, 4, 3, 3, 3],
                          'crit': [50, 50, 50, 50, 50, 30]}, spell.casting)
        self.assertEqual({}, spell.conditional)
        self.assertEqual({}, spell.delayed)

    def test_only_the_six_spells_whose_placed_thing_hurts_carry_placed_rows(self):
        placed = {}
        for char_class, spells in get_damage_spells_for_version('retro').items():
            for spell in spells:
                if spell.conditional or spell.delayed:
                    placed[(char_class, spell.spell_id)] = (
                        dict(spell.conditional), dict(spell.delayed))
        self.assertEqual({
            ('Feca', 10): ({}, {0: 'turn_begin'}),
            ('Feca', 17): ({}, {0: 'turn_begin'}),
            ('Sram', 65): ({0: 'trap'}, {}),
            ('Sram', 71): ({0: 'trap'}, {}),
            ('Sram', 79): ({0: 'trap'}, {}),
            ('Sram', 80): ({0: 'trap'}, {}),
        }, placed)
        for (char_class, spell_id) in placed:
            spell = _spell(char_class, spell_id)
            self.assertEqual(1, len(spell.aggregates), spell.name)
            self.assertEqual([0], spell.aggregates[0][1], spell.name)


class TheReaderAndTheSiteAgreeOnTheHeadsTests(SimpleTestCase):

    def test_the_retro_reader_names_the_placing_effects_as_the_dofus_3_reader_does(self):
        from chardata.tests import itemscraper_module
        retro = _reader()
        modern = itemscraper_module('get_spells')
        self.assertEqual({400, 401, 402}, set(retro.PLACED_BY_EFFECT))
        for effect, pair in retro.PLACED_BY_EFFECT.items():
            self.assertEqual(modern.PLACED_BY_EFFECT[effect], pair, effect)
        self.assertEqual(frozenset(('trap',)), retro.PLACED_WAITS)

    def test_every_retro_head_is_one_the_site_reads(self):
        from chardata.tests import itemscraper_module
        from chardata.spell_combo import PLACED_LABEL
        from chardata.spells_view import _PLACED_HEADS
        generator = itemscraper_module('generate_damage_spells')
        retro = _reader()
        self.assertEqual({'trap', 'glyph'}, set(retro.PLACED_LABELS))
        for kind, head in retro.PLACED_LABELS.items():
            self.assertEqual(generator.PLACED_LABELS[kind][0], head)
            self.assertIn(head, _PLACED_HEADS)
            self.assertTrue(PLACED_LABEL.match(head), head)


class ThePlacingRowNamesTheChildAndItsRankTests(SimpleTestCase):

    def _raw(self, name):
        path = os.path.join(RAW, name)
        if not os.path.exists(path):
            raise unittest.SkipTest('retro_raw is gitignored; run '
                                    'itemscraper/download_retro_langs.py')
        with io.open(path, encoding='utf-8') as handle:
            return json.load(handle)

    def test_every_class_placing_row_names_a_spell_the_file_holds_at_a_rank_it_has(self):
        reader = _reader()
        spells = self._raw('spells_fr.json')['S']
        classes = self._raw('classes_fr.json')['G']
        found = {}
        for class_id in reader.CLASS_ID_TO_NAME:
            for spell_id in classes[str(class_id)]['s']:
                spell = spells.get(str(spell_id))
                if not isinstance(spell, dict):
                    continue
                for rank in reader.LEVELS:
                    level = spell.get(rank)
                    if not isinstance(level, list):
                        continue
                    for effect in (level[-1] or []):
                        child = reader._placed_child(effect)
                        if child is None:
                            continue
                        _effect_id, child_id, child_rank = child
                        self.assertNotIsInstance(effect[0], str, effect)
                        self.assertIn(str(child_id), spells)
                        self.assertIn('l%d' % child_rank, spells[str(child_id)])
                        found.setdefault(spell_id, set()).add(child_id)
        self.assertEqual(PLACING, {parent: next(iter(children))
                                   for parent, children in found.items()})

    def test_six_of_the_placed_spells_carry_a_damage_row(self):
        reader = _reader()
        spells = self._raw('spells_fr.json')['S']
        hurting = set()
        for child_id in PLACING.values():
            child = spells[str(child_id)]
            for rank in reader.LEVELS:
                level = child.get(rank)
                if isinstance(level, list) and reader.decode_level(level):
                    hurting.add(child_id)
        self.assertEqual(CHILD_WITH_DAMAGE, hurting)

    def test_the_reader_rebuilds_the_trap_from_the_file(self):
        reader = _reader()
        spells = self._raw('spells_fr.json')['S']
        decoded = reader.decode_spell(spells[str(TRICKY_TRAP)], TRICKY_TRAP, spells)
        self.assertEqual(['earth'], decoded['elements'])
        self.assertEqual([['5-9', '6-10', '7-11', '8-12', '9-13', '13-17']],
                         decoded['non_crit_ranges'])
        self.assertEqual([('Trap damage', [0])], decoded['aggregates'])
        self.assertEqual({0: 'trap'}, decoded['conditional'])
        self.assertEqual([{'kind': 'trap', 'effect_id': 400, 'spell_id': 2007,
                           'ranks': [1, 2, 3, 4, 5, 6]}], decoded['placed'])
        self.assertIsNone(reader.decode_spell(spells[str(TRICKY_TRAP)], TRICKY_TRAP))


class ThePageNamesThePlacedThingTests(SimpleTestCase):

    def _digest(self, spell, language):
        from chardata.spells_view import _create_spell_web_digest
        with override(language):
            return _create_spell_web_digest(spell, 'retro')

    def test_the_trap_label_and_its_wait_speak_english_and_french(self):
        trap = _spell('Sram', TRICKY_TRAP)
        for language, label, wait in (
                ('en', 'Trap damage', 'only when an enemy sets off the trap'),
                ('fr', 'Dégâts du piège',
                 'seulement si un ennemi déclenche le piège')):
            with self.subTest(language=language):
                digest = self._digest(trap, language)
                self.assertEqual([[label, [0]]], digest['aggregates'])
                self.assertEqual({'0': wait}, digest['conditional'])
                self.assertEqual({}, digest['delayed'])

    def test_a_glyph_says_when_it_lands(self):
        digest = self._digest(_spell('Feca', BURNING_GLYPH), 'fr')
        self.assertEqual([['Dégâts du glyphe', [0]]], digest['aggregates'])
        self.assertEqual({'0': "au début d'un tour"}, digest['delayed'])
        self.assertEqual({}, digest['conditional'])


class TheBestTurnLeavesATrapOutTests(SimpleTestCase):

    def _castables(self, char_class, level):
        from chardata.spell_combo import castable_spells
        from fashionistapulp.structure import set_current_game_version
        set_current_game_version('retro')
        return {castable.name: castable
                for castable in castable_spells(char_class, level, 'retro')}

    def test_a_trap_is_not_offered_to_the_turn(self):
        for level in (1, 100, 200):
            with self.subTest(level=level):
                castables = self._castables('Sram', level)
                self.assertNotIn('Piège Sournois', castables)
                self.assertNotIn('Piège Mortel', castables)
                self.assertIn('Sournoiserie', castables)

    def test_its_rows_wait_for_what_sets_them_off(self):
        from chardata.spell_combo import Castable
        trap = Castable(_spell('Sram', TRICKY_TRAP), 0, False)
        self.assertEqual([], trap.alternatives)
        self.assertEqual(['trap'], [when for _row, when in trap.waiting_plain])
        self.assertEqual([(5, 9)], [(row.min_dam, row.max_dam)
                                    for row, _when in trap.waiting_plain])
        trap = Castable(_spell('Sram', TRICKY_TRAP), 5, True)
        self.assertEqual([], trap.alternatives)
        self.assertEqual([(15, 19)], [(row.min_dam, row.max_dam)
                                      for row, _when in trap.waiting_crit])

    def test_a_glyph_counts_as_late_damage(self):
        from chardata.spell_combo import Castable
        glyph = self._castables('Feca', 70)['Glyphe Enflammé']
        self.assertEqual(1, len(glyph.hits))
        self.assertEqual(['turn_begin'],
                         [when for _row, when in glyph.delayed_plain])
        glyph = Castable(_spell('Feca', BURNING_GLYPH), 0, False)
        self.assertEqual([(19, 27)],
                         [(hit.min_dam, hit.max_dam) for hit in glyph.hits])
        self.assertNotIn('Glyphe Enflammé', self._castables('Feca', 69))
