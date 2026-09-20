# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
from django.test import SimpleTestCase
from django.utils.translation import override

from chardata.spell_buffs import get_damage_spells_for_version
from fashionistapulp.dofus_constants import AIR, EARTH, FIRE, WATER

VERSION = 'touch'

SNEAKY_TRAP = 65
LETHAL_TRAP = 80
IMMOBILISING_TRAP = 69
AGGRESSIVE_GLYPH = 6149
BURNING_GLYPH = 4708
ESCAPE_GLYPH = 4704
RETENTION_GLYPH = 13
EXPLOBOMB = 2808
TORNABOMB = 2796
WATER_BOMB = 2797
BLINDING_ARROW = 5725


def _spells(char_class):
    return get_damage_spells_for_version(VERSION)[char_class]


def _spell(char_class, spell_id):
    return next(spell for spell in _spells(char_class)
                if spell.spell_id == spell_id)


def _rows(ranges):
    if ranges is None:
        return None
    return [[(r.min_dam, r.max_dam) for r in row] for row in ranges]


class ThePlacedThingsDamageIsReadFromItsOwnRecordTests(SimpleTestCase):

    def test_a_trap_carries_its_explosion_spells_fire_line(self):
        trap = _spell('Sram', SNEAKY_TRAP)
        self.assertEqual('Piège Sournois', trap.name)
        self.assertEqual([[(15, 17), (16, 18), (17, 19), (18, 20), (20, 22),
                           (23, 25)]], _rows(trap.effects.non_crit_ranges))
        self.assertEqual(_rows(trap.effects.non_crit_ranges),
                         _rows(trap.effects.crit_ranges))
        self.assertEqual([FIRE], trap.effects.elements)
        self.assertEqual([('Trap damage', [0])], trap.aggregates)
        self.assertEqual({0: 'trap'}, trap.conditional)
        self.assertEqual({}, trap.delayed)
        self.assertEqual({'ap': [3] * 6, 'per_turn': [1, 1, 1, 2, 2, 2]},
                         trap.casting)

    def test_a_trap_placed_at_a_lower_grade_reads_that_grade(self):
        trap = _spell('Sram', LETHAL_TRAP)
        self.assertEqual([[(14, 18), (17, 21), (20, 24), (23, 27), (27, 31),
                           (34, 38)]], _rows(trap.effects.non_crit_ranges))
        self.assertEqual([EARTH], trap.effects.elements)
        self.assertEqual({0: 'trap'}, trap.conditional)

    def test_a_bomb_carries_its_explosion_spells_line(self):
        for char_class, spell_id, element, rows in (
                ('Rogue', EXPLOBOMB, FIRE,
                 [(11, 12), (12, 13), (13, 14), (14, 15), (15, 16), (20, 22)]),
                ('Rogue', TORNABOMB, AIR,
                 [(8, 9), (9, 10), (10, 11), (11, 12), (12, 13), (17, 19)]),
                ('Rogue', WATER_BOMB, WATER,
                 [(5, 6), (6, 7), (7, 8), (8, 9), (9, 10), (14, 16)])):
            with self.subTest(spell=spell_id):
                bomb = _spell(char_class, spell_id)
                self.assertEqual([rows], _rows(bomb.effects.non_crit_ranges))
                self.assertEqual([element], bomb.effects.elements)
                self.assertEqual([('Bomb damage', [0])], bomb.aggregates)
                self.assertEqual({0: 'bomb'}, bomb.conditional)
                self.assertEqual({}, bomb.delayed)

    def test_a_start_of_turn_glyph_carries_its_glyph_spells_line(self):
        glyph = _spell('Feca', AGGRESSIVE_GLYPH)
        self.assertEqual([[(20, 22), (22, 24), (24, 26), (26, 28), (30, 32),
                           (39, 41)]], _rows(glyph.effects.non_crit_ranges))
        self.assertEqual([EARTH], glyph.effects.elements)
        self.assertEqual([('Glyph damage', [0])], glyph.aggregates)
        self.assertEqual({}, glyph.conditional)
        self.assertEqual({0: 'turn_begin'}, glyph.delayed)
        self.assertIsNone(glyph.delayed_crit)

    def test_a_glyph_whose_spell_has_a_critical_line_keeps_it(self):
        glyph = _spell('Feca', BURNING_GLYPH)
        self.assertEqual([[(29, 31), (32, 34), (33, 35), (35, 37), (38, 40),
                           (38, 40)]], _rows(glyph.effects.non_crit_ranges))
        self.assertEqual([[(35, 37), (38, 40), (41, 43), (44, 46), (48, 50),
                           (48, 50)]], _rows(glyph.effects.crit_ranges))
        self.assertEqual([FIRE], glyph.effects.elements)
        self.assertEqual([('Glyph damage', [0])], glyph.aggregates)
        self.assertEqual({0: 'turn_begin'}, glyph.delayed)

    def test_a_placed_thing_without_a_damage_line_adds_no_entry(self):
        for char_class, spell_id in (('Sram', IMMOBILISING_TRAP),
                                     ('Feca', ESCAPE_GLYPH),
                                     ('Feca', RETENTION_GLYPH)):
            with self.subTest(spell=spell_id):
                self.assertNotIn(spell_id,
                                 [spell.spell_id for spell in _spells(char_class)])

    def test_a_spell_that_was_complete_is_untouched(self):
        spell = _spell('Cra', BLINDING_ARROW)
        self.assertEqual('Flèche Aveuglante', spell.name)
        self.assertEqual([49, 49, 49, 49, 99, 149], spell.level_req)
        self.assertEqual([[(16, 18), (17, 19), (18, 20), (20, 22), (22, 24),
                           (24, 26)]], _rows(spell.effects.non_crit_ranges))
        self.assertEqual([[(18, 20), (19, 21), (20, 22), (22, 24), (24, 26),
                           (27, 29)]], _rows(spell.effects.crit_ranges))
        self.assertEqual([FIRE], spell.effects.elements)
        self.assertEqual([], spell.aggregates)
        self.assertEqual(1, spell.stacks)
        self.assertIsNone(spell.is_linked)
        self.assertEqual({'ap': [3] * 6, 'crit': [20] * 6,
                          'per_target': [1] * 6, 'per_turn': [2] * 6},
                         spell.casting)
        self.assertEqual({}, spell.conditional)
        self.assertEqual({}, spell.delayed)

    def test_the_table_grew_by_the_eleven_placing_spells(self):
        by_class = get_damage_spells_for_version(VERSION)
        placed = sorted(spell.spell_id for spells in by_class.values()
                        for spell in spells
                        if any(label in ('Trap damage', 'Glyph damage',
                                         'Bomb damage')
                               for label, _indices in spell.aggregates))
        self.assertEqual([65, 73, 80, 2796, 2797, 2808, 4706, 4708, 5537,
                          6141, 6149], placed)
        self.assertEqual(191, sum(len(spells) for spells in by_class.values()))


class TheReaderAndTheSiteAgreeOnTheHeadsTests(SimpleTestCase):

    def test_the_reader_names_the_touch_placing_effects(self):
        from chardata.tests import itemscraper_module
        reader = itemscraper_module('get_spells_touch')
        self.assertEqual({400: 'trap', 401: 'glyph', 402: 'glyph',
                          1091: 'glyph', 1008: 'bomb'},
                         {effect: kind for effect, (kind, _when)
                          in reader.PLACED_BY_EFFECT.items()})
        self.assertEqual(1008, reader.BOMB_EFFECT_ID)
        self.assertEqual('SpellBombs', reader.BOMB_TABLE)

    def test_the_touch_heads_are_the_dofus_3_damage_heads(self):
        from chardata.tests import itemscraper_module
        from chardata.spell_combo import PLACED_LABEL
        from chardata.spells_view import _PLACED_HEADS
        reader = itemscraper_module('get_spells_touch')
        generator = itemscraper_module('generate_damage_spells')
        self.assertEqual({'trap', 'glyph', 'bomb'}, set(reader.PLACED_LABELS))
        for kind, head in reader.PLACED_LABELS.items():
            self.assertEqual(generator.PLACED_LABELS[kind][0], head)
            self.assertTrue(PLACED_LABEL.match(head), head)
            self.assertIn(head, _PLACED_HEADS)


class ThePageNamesThePlacedThingInEachLanguageTests(SimpleTestCase):

    def _digest(self, spell, language):
        from chardata.spells_view import _create_spell_web_digest
        with override(language):
            return _create_spell_web_digest(spell, VERSION)

    def test_the_trap_label_and_its_wait_speak_english_and_french(self):
        trap = _spell('Sram', SNEAKY_TRAP)
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
        digest = self._digest(_spell('Feca', AGGRESSIVE_GLYPH), 'fr')
        self.assertEqual([['Dégâts du glyphe', [0]]], digest['aggregates'])
        self.assertEqual({'0': "au début d'un tour"}, digest['delayed'])
        self.assertEqual({}, digest['conditional'])

    def test_a_bomb_says_it_waits_for_the_explosion(self):
        digest = self._digest(_spell('Rogue', EXPLOBOMB), 'en')
        self.assertEqual([['Bomb damage', [0]]], digest['aggregates'])
        self.assertEqual({'0': 'only when the bomb explodes'},
                         digest['conditional'])


class TheBestTurnLeavesAPlacedThingsDamageOutTests(SimpleTestCase):

    def _castables(self, char_class):
        from chardata.spell_combo import castable_spells
        from fashionistapulp.structure import set_current_game_version
        set_current_game_version(VERSION)
        return {castable.name: castable
                for castable in castable_spells(char_class, 200, VERSION)}

    def test_a_trap_and_a_bomb_are_not_offered_to_the_turn(self):
        self.assertNotIn('Piège Sournois', self._castables('Sram'))
        self.assertNotIn('Explobombe', self._castables('Rogue'))

    def test_their_rows_wait_for_what_sets_them_off(self):
        from chardata.spell_combo import Castable
        trap = Castable(_spell('Sram', SNEAKY_TRAP), 5, False)
        self.assertEqual([], trap.alternatives)
        self.assertEqual(['trap'], [when for _row, when in trap.waiting_plain])
        bomb = Castable(_spell('Rogue', EXPLOBOMB), 5, False)
        self.assertEqual([], bomb.alternatives)
        self.assertEqual(['bomb'], [when for _row, when in bomb.waiting_plain])

    def test_a_start_of_turn_glyph_counts_as_late_damage(self):
        glyph = self._castables('Feca')['Glyphe Agressif']
        self.assertEqual(1, len(glyph.hits))
        self.assertEqual([(39, 41)],
                         [(hit.min_dam, hit.max_dam) for hit in glyph.hits])
        self.assertEqual(['turn_begin'],
                         [when for _row, when in glyph.delayed_plain])
