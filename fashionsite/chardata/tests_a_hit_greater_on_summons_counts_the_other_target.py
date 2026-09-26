# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A hit with its own rows on summons lands one face; the turn counts the other targets' one."""
from django.test import SimpleTestCase

from chardata.spell_buffs import get_damage_spells_for_version
from chardata.spell_reference import get_spell_reference
from fashionistapulp.dofus_constants import STAT_NAME_TO_KEY

MODERN = ('dofus3', 'beta', 'dofus2')
CONCENTRATION = 13123
MOUND = 13335
BANKRUPTCY = 14278
OBSOLESCENCE = 13360
TOUCH_CONCENTRATION = 8121
TOUCH_UNSUMMONING = 46
RETRO_CONCENTRATION = 158

NOT_A_SUMMON = 'Target that is not a summon'
A_SUMMON = 'Target that is a summon'

SUMMON_WORD = {'en': 'summon', 'fr': 'invocation', 'es': 'invocaci',
               'pt': 'invoca', 'de': 'beschwör'}


def _generator():
    from chardata.tests import itemscraper_module
    return itemscraper_module('generate_damage_spells')


def _touch_reader():
    from chardata.tests import itemscraper_module
    return itemscraper_module('get_spells_touch')


def _convert(*rows):
    spell = {'ankama_id': 1, 'name_en': 'Probe', 'level_requirements': [1],
             'damage_templates': {'normal': [
                 {'element': 'EARTH', 'ranges': [ranges], 'situation': situation}
                 for situation, ranges in rows]}}
    return _generator().convert_spell(spell)


def _descriptions(version):
    return {entry.get('id'): entry.get('description') or {}
            for entries in get_spell_reference(version).values()
            for entry in entries if entry.get('id') is not None}


def _stats():
    return {key: 0 for key in STAT_NAME_TO_KEY.values()}


def _castable(char_class, spell_id, version):
    from chardata.spell_combo import castable_spells
    from fashionistapulp.structure import set_current_game_version
    set_current_game_version(version)
    try:
        return next(castable for castable in castable_spells(char_class, 200,
                                                             version)
                    if castable.spell_id == spell_id)
    finally:
        set_current_game_version('dofus3')


def _mean(row):
    return (row.min_dam + row.max_dam) / 2.0


class TheGeneratorSplitsAHitOnSummonsTests(SimpleTestCase):

    def test_a_summon_row_and_a_row_for_the_rest_are_two_faces(self):
        entry = _convert(('L,M,l,m,c|80,1,0', '20-24'), ('J,j|80,1,0', '30-34'))
        self.assertEqual([(NOT_A_SUMMON, [0]), (A_SUMMON, [1])],
                         entry.aggregates)

    def test_the_plain_face_comes_first_whatever_the_row_order(self):
        entry = _convert(('j,J|88,3,0', '25-27'), ('h,m,d,H,M,D|88,3,0', '20-22'))
        self.assertEqual([(NOT_A_SUMMON, [1]), (A_SUMMON, [0])],
                         entry.aggregates)

    def test_a_hit_on_everyone_gets_no_summon_face(self):
        aggregates = _convert(('a,A|80,1,0', '41-44'),
                              ('J,j|80,1,0', '10-12')).aggregates or []
        self.assertNotIn(A_SUMMON, [label for label, _indexes in aggregates])

    def test_rows_in_different_zones_are_not_faces_of_one_hit(self):
        self.assertFalse(_convert(('l,m,L,M|80,1,0', '26-30'),
                                  ('j,J|67,2,1', '34-38')).aggregates)

    def test_a_row_naming_summons_and_others_is_no_summon_face(self):
        self.assertFalse(_convert(('l,m,L,M|80,1,0', '26-30'),
                                  ('j,J,M|80,1,0', '34-38')).aggregates)

    def test_rows_gated_differently_are_not_faces_of_one_hit(self):
        self.assertFalse(_convert(('l,m,L,M,*E700|80,1,0', '26-30'),
                                  ('j,J|80,1,0', '34-38')).aggregates)


class EachModernVersionSplitsTheSpellsItsTextNamesTests(SimpleTestCase):

    def _split(self, version):
        found = {}
        for char_class, spells in get_damage_spells_for_version(version).items():
            for spell in spells:
                aggregates = spell.get_effects_digest().aggregates or []
                labels = [label for label, _indexes in aggregates]
                if A_SUMMON in labels or NOT_A_SUMMON in labels:
                    found[spell.spell_id] = (char_class, spell, aggregates)
        return found

    def test_the_split_spells_are_the_four_the_client_marks(self):
        for version in MODERN:
            with self.subTest(version=version):
                self.assertEqual(
                    {CONCENTRATION: 'Iop', MOUND: 'Enutrof',
                     BANKRUPTCY: 'Enutrof', OBSOLESCENCE: 'Enutrof'},
                    {spell_id: found[0]
                     for spell_id, found in self._split(version).items()})

    def test_each_split_spells_text_names_summons_in_five_languages(self):
        for version in MODERN:
            descriptions = _descriptions(version)
            for spell_id in self._split(version):
                for language, word in SUMMON_WORD.items():
                    with self.subTest(version=version, spell=spell_id,
                                      language=language):
                        self.assertIn(word, descriptions[spell_id][language]
                                      .lower())

    def test_the_summon_face_is_the_greater_one_at_every_rank(self):
        for version in MODERN:
            for spell_id, (_class, spell, aggregates) in self._split(version).items():
                faces = dict(aggregates)
                for rank, rows in enumerate(spell.get_effects_digest().non_crit_dams):
                    with self.subTest(version=version, spell=spell_id, rank=rank):
                        plain = [rows[index] for index in faces[NOT_A_SUMMON]]
                        summon = [rows[index] for index in faces[A_SUMMON]]
                        self.assertEqual(1, len(plain))
                        self.assertEqual(1, len(summon))
                        self.assertGreater(_mean(summon[0]), _mean(plain[0]))


class TheTurnCountsTheFaceOtherTargetsTakeTests(SimpleTestCase):

    def test_concentration_lands_one_row_in_each_modern_version(self):
        from chardata.spell_combo import best_turn, crit_chance
        for version in MODERN:
            with self.subTest(version=version):
                castable = _castable('Iop', CONCENTRATION, version)
                rows = castable.effects
                self.assertEqual(2, len(rows))
                self.assertEqual(1, len(castable.hits))
                self.assertIs(rows[0], castable.plain_alternatives[0][0])
                self.assertEqual(NOT_A_SUMMON, castable.scored_group)
                stats = _stats()
                chance = crit_chance(castable.crit_rate, stats, version)
                by_hand = ((1 - chance) * _mean(castable.plain_alternatives[0][0])
                           + chance * _mean(castable.crit_alternatives[0][0]))
                total, order = best_turn(stats, [castable], castable.cost,
                                         game_version=version,
                                         caster_level=200)
                self.assertEqual(1, len(order))
                self.assertAlmostEqual(by_hand, total)

    def test_the_enutrof_spells_land_one_row_too(self):
        for version in MODERN:
            for spell_id in (MOUND, BANKRUPTCY, OBSOLESCENCE):
                with self.subTest(version=version, spell=spell_id):
                    castable = _castable('Enutrof', spell_id, version)
                    self.assertEqual(1, len(castable.hits))
                    self.assertEqual(NOT_A_SUMMON, castable.scored_group)


class TouchKeepsTheLineOtherTargetsTakeTests(SimpleTestCase):

    def _rows(self, *effects):
        return _touch_reader().collect_damage([
            {'effectId': effect_id, 'diceNum': low, 'diceSide': high,
             'targetMask': mask, 'rawZone': zone, 'triggers': 'I'}
            for effect_id, low, high, mask, zone in effects])

    def test_a_summon_only_line_gives_way_to_the_line_for_the_rest(self):
        self.assertEqual({'earth': (20, 24, None)},
                         self._rows((97, 20, 24, 'H,M', 'P'),
                                    (97, 30, 34, 'I,S', 'P')))

    def test_faces_behind_the_same_state_still_give_way(self):
        self.assertEqual({'earth': (20, 24, None)},
                         self._rows((97, 20, 24, 'H,M,*e809', 'P'),
                                    (97, 30, 34, '*e809,I,S', 'P')))

    def test_a_summon_line_in_another_zone_is_still_read(self):
        self.assertEqual({'earth': (30, 34, None)},
                         self._rows((97, 20, 24, 'H,M', 'P'),
                                    (97, 30, 34, 'I,S', 'C2')))

    def test_a_summon_line_behind_another_state_is_still_read(self):
        self.assertEqual({'earth': (30, 34, None)},
                         self._rows((97, 20, 24, 'H,M', 'P'),
                                    (97, 30, 34, 'I,S,*e809', 'P')))

    def test_touch_concentration_shows_what_a_player_or_monster_takes(self):
        spell = next(spell for spell in get_damage_spells_for_version('touch')['Iop']
                     if spell.spell_id == TOUCH_CONCENTRATION)
        rows = spell.get_effects_digest().non_crit_dams
        self.assertEqual([(12, 16), (13, 17), (14, 18), (15, 19), (16, 20),
                          (20, 24)],
                         [(rank[0].min_dam, rank[0].max_dam) for rank in rows])
        castable = _castable('Iop', TOUCH_CONCENTRATION, 'touch')
        self.assertEqual([(20, 24)],
                         [(row.min_dam, row.max_dam) for row in castable.hits])

    def test_touch_concentrations_text_names_summons(self):
        description = _descriptions('touch')[TOUCH_CONCENTRATION]
        for language in ('en', 'fr', 'es', 'pt'):
            with self.subTest(language=language):
                self.assertIn(SUMMON_WORD[language],
                              description[language].lower())

    def test_touch_unsummoning_keeps_its_line(self):
        spell = next(spell for spell in get_damage_spells_for_version('touch')['Enutrof']
                     if spell.spell_id == TOUCH_UNSUMMONING)
        last = spell.get_effects_digest().non_crit_dams[-1]
        self.assertEqual([(31, 34)], [(row.min_dam, row.max_dam) for row in last])


class RetroConcentrationHasNoSummonRuleTests(SimpleTestCase):

    def test_retro_concentrations_text_names_no_summon_and_keeps_one_row(self):
        description = _descriptions('retro')[RETRO_CONCENTRATION]
        for language, word in SUMMON_WORD.items():
            with self.subTest(language=language):
                self.assertNotIn(word, description[language].lower())
        spell = next(spell for spell in get_damage_spells_for_version('retro')['Iop']
                     if spell.spell_id == RETRO_CONCENTRATION)
        digest = spell.get_effects_digest()
        self.assertFalse(digest.aggregates)
        self.assertEqual(1, len(digest.non_crit_dams[-1]))
