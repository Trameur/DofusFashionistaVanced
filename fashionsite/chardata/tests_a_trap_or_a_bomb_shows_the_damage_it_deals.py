# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
import json
import re

from django.test import SimpleTestCase, TestCase
from django.utils.translation import override

from chardata.spell_buffs import get_damage_spells_for_version
from chardata.spells_view import _create_spell_web_digest
from fashionistapulp.dofus_constants import AIR, EARTH, FIRE, WATER

VERSIONS = ('dofus3', 'beta')

TRICKY_TRAP = 12906
EXPLOBOMB = 13444
SCORCHED_DIRT = 12985
DISTRUST = 12988
VENDETTA = 32473
PASTURELAND = 13013
REFUGE = 13021
BLACK_ICE = 13023
PRESSURE = 13106
SCURVION_TOXICITY = 12505
FRAGMENTATION_TRAP = 12941
PESTILENTIAL_FOG = 18898


def _spell(version, char_class, spell_id):
    return next(spell for spell in get_damage_spells_for_version(version)[char_class]
                if spell.spell_id == spell_id)


def _rows(ranges):
    if ranges is None:
        return None
    return [[(r.min_dam, r.max_dam) for r in row] for row in ranges]


class ThePlacedThingsDamageIsReadFromItsOwnRecordTests(SimpleTestCase):

    def test_a_trap_carries_the_trap_spells_fire_line(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                trap = _spell(version, 'Sram', TRICKY_TRAP)
                self.assertEqual([[(10, 12), (13, 15), (17, 19)]],
                                 _rows(trap.effects.non_crit_ranges))
                self.assertEqual([FIRE], trap.effects.elements)
                self.assertIsNone(trap.effects.crit_ranges)
                self.assertEqual([('Trap damage', [0])], trap.aggregates)
                self.assertEqual({0: 'trap'}, trap.conditional)
                self.assertEqual({}, trap.delayed)

    def test_a_bomb_carries_its_explosion_spells_line(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                bomb = _spell(version, 'Rogue', EXPLOBOMB)
                self.assertEqual([[(9, 10), (13, 14), (17, 19)]] * 2,
                                 _rows(bomb.effects.non_crit_ranges))
                self.assertEqual([FIRE, FIRE], bomb.effects.elements)
                self.assertIsNone(bomb.effects.crit_ranges)
                self.assertEqual([('Bomb damage', [0])], bomb.aggregates)
                self.assertEqual({0: 'bomb', 1: 'bomb'}, bomb.conditional)
                self.assertEqual({}, bomb.delayed)

    def test_a_start_of_turn_glyph_carries_its_glyph_spells_line(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                glyph = _spell(version, 'Feca', SCORCHED_DIRT)
                self.assertEqual([[(22, 25), (27, 30), (30, 34)]],
                                 _rows(glyph.effects.non_crit_ranges))
                self.assertEqual([FIRE], glyph.effects.elements)
                self.assertEqual([('Glyph damage', [0])], glyph.aggregates)
                self.assertEqual({}, glyph.conditional)
                self.assertEqual({0: 'turn_begin'}, glyph.delayed)

    def test_an_end_of_turn_glyph_lands_at_the_end_of_a_turn(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                glyph = _spell(version, 'Feca', DISTRUST)
                self.assertEqual([EARTH, FIRE, WATER, AIR], glyph.effects.elements)
                self.assertEqual([('Glyph damage', [0, 1, 2, 3])], glyph.aggregates)
                self.assertEqual({0: 'turn_end', 1: 'turn_end',
                                  2: 'turn_end', 3: 'turn_end'}, glyph.delayed)

    def test_a_best_element_trap_keeps_its_faces_under_the_trap_label(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                trap = _spell(version, 'Cra', VENDETTA)
                self.assertEqual([EARTH, FIRE, WATER, AIR], trap.effects.elements)
                self.assertEqual([('Trap damage - Hit in best element', [0]),
                                  ('', [1]), ('', [2]), ('', [3])],
                                 trap.aggregates)
                self.assertEqual({0: 'trap', 1: 'trap', 2: 'trap', 3: 'trap'},
                                 trap.conditional)
        trap = _spell('dofus3', 'Cra', VENDETTA)
        self.assertEqual([[(16, 18)]] * 4, _rows(trap.effects.non_crit_ranges))

    def test_a_spell_that_hits_and_places_keeps_its_own_line_first(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                spell = _spell(version, 'Feca', PASTURELAND)
                self.assertEqual([[(31, 35)], [(31, 35)]],
                                 _rows(spell.effects.non_crit_ranges))
                self.assertEqual([[(37, 42)], [(37, 42)]],
                                 _rows(spell.effects.crit_ranges))
                self.assertEqual([('', [0]), ('Glyph damage - State 5260', [1])],
                                 spell.aggregates)
                self.assertEqual({1: 'state'}, spell.conditional)

    def test_a_placement_gated_on_one_state_names_it_in_the_head(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                heads = {_spell(version, 'Feca', spell_id).aggregates[1][0]
                         for spell_id in (PASTURELAND, REFUGE, BLACK_ICE)}
                self.assertEqual({'Glyph damage - State 5260'}, heads)

    def test_a_best_element_hit_renumbered_between_grades_is_one_hit(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                spell = _spell(version, 'default', SCURVION_TOXICITY)
                self.assertEqual([[(0, 0), (8, 8), (8, 8)]] * 4,
                                 _rows(spell.effects.non_crit_ranges))
                self.assertEqual([EARTH, FIRE, WATER, AIR], spell.effects.elements)
                self.assertEqual([('Hit in best element', [0]), ('', [1]), ('', [2]),
                                  ('', [3])], spell.aggregates)

    def test_a_trap_hitting_by_distance_from_its_centre_hits_an_enemy_at_one_distance(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                trap = _spell(version, 'Sram', FRAGMENTATION_TRAP)
                self.assertEqual([[(48, 52)], [(27, 31)], [(37, 41)], [(47, 51)]],
                                 _rows(trap.effects.non_crit_ranges))
                self.assertEqual([FIRE] * 4, trap.effects.elements)
                self.assertEqual([('Trap damage', [0]), ('', [1]), ('', [2]), ('', [3])],
                                 trap.aggregates)
                self.assertEqual({0: 'trap', 1: 'trap', 2: 'trap', 3: 'trap'},
                                 trap.conditional)

    def test_the_pestilential_fog_row_comes_from_the_spell_that_deals_it(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                fogs = [spell for spell in get_damage_spells_for_version(version)['default']
                        if spell.name == 'Pestilential Fog']
                self.assertEqual([PESTILENTIAL_FOG], [spell.spell_id for spell in fogs])
                self.assertEqual([[(0, 0), (18, 18), (18, 18)]] * 4,
                                 _rows(fogs[0].effects.non_crit_ranges))
                self.assertEqual([EARTH, FIRE, WATER, AIR], fogs[0].effects.elements)
                self.assertEqual({0: 'turn_begin', 1: 'turn_begin', 2: 'turn_begin',
                                  3: 'turn_begin'}, fogs[0].delayed)

    def test_a_spell_that_was_complete_is_untouched(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                spell = _spell(version, 'Iop', PRESSURE)
                self.assertEqual('Pressure', spell.name)
                self.assertEqual([1, 66, 132], spell.level_req)
                self.assertEqual([[(16, 18), (20, 23), (26, 30)]],
                                 _rows(spell.effects.non_crit_ranges))
                self.assertEqual([[(19, 21), (24, 28), (31, 36)]],
                                 _rows(spell.effects.crit_ranges))
                self.assertEqual([EARTH], spell.effects.elements)
                self.assertEqual([], spell.aggregates)
                self.assertEqual(2, spell.stacks)
                self.assertEqual((1, 'Fracture'), spell.is_linked)
                self.assertEqual({'ap': [3, 3, 3], 'per_turn': [4, 4, 4],
                                  'per_target': [2, 2, 2], 'crit': [10, 10, 10]},
                                 spell.casting)
                self.assertEqual({}, spell.conditional)
                self.assertEqual({}, spell.delayed)


class EachDistanceFromTheCentreIsACaseTests(SimpleTestCase):

    def _aggregates(self, *situations):
        from chardata.tests import itemscraper_module
        generator = itemscraper_module('generate_damage_spells')
        rows = [{'element': 'FIRE', 'ranges': ['%d-%d' % (10 * index, 10 * index + 2)],
                 'situation': situation} for index, situation in enumerate(situations, 1)]
        return generator._build_situation_aggregates(rows, len(rows))

    def test_the_centre_and_each_ring_are_cases(self):
        self.assertEqual([('', [0]), ('', [1]), ('', [2])],
                         self._aggregates('A|80,1,0', 'a,A|79,1,0', 'a,A|79,2,0'))

    def test_a_zone_covering_several_distances_or_one_distance_twice_adds_its_hit(self):
        for situations in (('A|80,1,0', 'a,A|67,3,1'), ('a,A|79,2,1', 'a,A|79,1,0'),
                           ('a,A|79,1,0', 'A|79,1,0')):
            with self.subTest(situations=situations):
                self.assertIsNone(self._aggregates(*situations))


class TheReaderAndTheSiteAgreeOnTheHeadsTests(SimpleTestCase):

    def test_the_reader_names_the_six_placing_effects(self):
        from chardata.tests import itemscraper_module
        reader = itemscraper_module('get_spells')
        self.assertEqual({400: 'trap', 401: 'glyph', 402: 'glyph', 1165: 'glyph',
                          1091: 'glyph', 1008: 'bomb'},
                         {effect: kind for effect, (kind, _when)
                          in reader.PLACED_BY_EFFECT.items()})
        self.assertEqual(1008, reader.BOMB_EFFECT_ID)

    def test_every_generator_head_is_one_the_site_reads(self):
        from chardata.tests import itemscraper_module
        from chardata.spell_combo import PLACED_LABEL
        from chardata.spells_view import _PLACED_HEADS
        generator = itemscraper_module('generate_damage_spells')
        heads = [head for pair in generator.PLACED_LABELS.values() for head in pair]
        self.assertEqual(6, len(heads))
        for head in heads:
            self.assertTrue(PLACED_LABEL.match(head), head)
            self.assertIn(head, _PLACED_HEADS)
            match = PLACED_LABEL.match(head + ' - Hit in best element')
            self.assertEqual(('Hit in best element'), match.group(2))


class ThePageNamesThePlacedThingInEachLanguageTests(SimpleTestCase):

    EXPECTED = {
        'en': ('Trap damage', 'only when an enemy sets off the trap'),
        'fr': ('Dégâts du piège', 'seulement si un ennemi déclenche le piège'),
        'es': ('Daños de la trampa', 'solo si un enemigo activa la trampa'),
        'pt': ('Danos da armadilha', 'apenas se um inimigo acionar a armadilha'),
        'de': ('Fallenschaden', 'nur wenn ein Gegner die Falle auslöst'),
    }

    def _digest(self, spell, language, version='dofus3'):
        from chardata.spells_view import _create_spell_web_digest
        with override(language):
            return _create_spell_web_digest(spell, version)

    def test_the_trap_label_and_its_wait_speak_each_language(self):
        trap = _spell('dofus3', 'Sram', TRICKY_TRAP)
        for language, (label, wait) in self.EXPECTED.items():
            with self.subTest(language=language):
                digest = self._digest(trap, language)
                self.assertEqual([[label, [0]]], digest['aggregates'])
                self.assertEqual({'0': wait}, digest['conditional'])
                self.assertEqual({}, digest['delayed'])

    def test_vendettas_card_says_its_damage_taken_waits_for_the_trap(self):
        from chardata.spell_combo import damage_taken_for_version
        sustained = {'en': 'x110% damage sustained', 'fr': 'Dommages subis x110%',
                     'es': 'Daños sufridos x110%', 'pt': 'Danos sofridos x110%',
                     'de': 'Erlittener Schaden x110%'}
        for version in VERSIONS:
            entry = next(entry for entry in damage_taken_for_version(version)['Cra']
                         if entry['spell_id'] == VENDETTA)
            for language, (_label, wait) in self.EXPECTED.items():
                with self.subTest(version=version, language=language):
                    with override(language):
                        digest = _create_spell_web_digest(
                            _spell(version, 'Cra', VENDETTA), version, taken=entry)
                    self.assertEqual({'normal': [sustained[language]],
                                      'critical': [sustained[language]],
                                      'waits': [wait]}, digest['taken'])

    def test_a_card_without_damage_taken_carries_none(self):
        self.assertIsNone(self._digest(_spell('dofus3', 'Sram', TRICKY_TRAP), 'en')['taken'])

    def test_a_best_element_trap_shows_one_face_under_the_trap_label(self):
        digest = self._digest(_spell('dofus3', 'Cra', VENDETTA), 'fr')
        self.assertEqual(
            [['Dégâts du piège - Coup dans le meilleur élément', [0, 1, 2, 3],
              'best']],
            digest['aggregates'])

    def test_a_glyph_says_when_it_lands(self):
        digest = self._digest(_spell('dofus3', 'Feca', SCORCHED_DIRT), 'fr')
        self.assertEqual([['Dégâts du glyphe', [0]]], digest['aggregates'])
        self.assertEqual({'0': "au début d'un tour"}, digest['delayed'])
        self.assertEqual({}, digest['conditional'])

    def test_a_bomb_says_it_waits_for_the_explosion(self):
        digest = self._digest(_spell('dofus3', 'Rogue', EXPLOBOMB), 'en')
        self.assertEqual([['Bomb damage', [0]]], digest['aggregates'])
        self.assertEqual({'0': 'only when the bomb explodes',
                          '1': 'only when the bomb explodes'},
                         digest['conditional'])

    def test_the_glyph_head_names_the_state_under_its_game_name(self):
        for language, head in (
                ('en', 'Glyph damage - With Greener Pastures'),
                ('fr', 'Dégâts du glyphe - Avec Glyphes déclenchés'),
                ('de', 'Glyphenschaden - Mit Vermenschwandlung')):
            with self.subTest(language=language):
                digest = self._digest(_spell('dofus3', 'Feca', PASTURELAND),
                                      language)
                self.assertEqual([['', [0]], [head, [1]]], digest['aggregates'])
        digest = self._digest(_spell('dofus2', 'Feca', PASTURELAND), 'en',
                              version='dofus2')
        self.assertEqual([['', [0]], ['Glyph damage - With Greener Pastures', [1]]],
                         digest['aggregates'])
        self.assertEqual({'1': 'only at the state the spell needs'},
                         digest['conditional'])

    def test_a_state_the_version_cannot_name_leaves_the_head_alone(self):
        from chardata.spells_view import _localized_aggregate_label
        with override('fr'):
            self.assertEqual('Dégâts du glyphe',
                             _localized_aggregate_label(
                                 'Glyph damage - State 999999', 'dofus3'))
            self.assertEqual('Dégâts du piège',
                             _localized_aggregate_label(
                                 'Trap damage - State 5260', 'retro'))


class TheBestTurnLeavesAPlacedThingsDamageOutTests(SimpleTestCase):

    def _castables(self, char_class, version):
        from chardata.spell_combo import castable_spells
        from fashionistapulp.structure import set_current_game_version
        set_current_game_version(version)
        return {castable.name: castable
                for castable in castable_spells(char_class, 200, version)}

    def test_a_trap_and_a_bomb_are_not_offered_to_the_turn(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                self.assertNotIn('Tricky Trap', self._castables('Sram', version))
                self.assertNotIn('Explobomb', self._castables('Rogue', version))

    def test_their_rows_wait_for_what_sets_them_off(self):
        from chardata.spell_combo import Castable
        for version in VERSIONS:
            with self.subTest(version=version):
                trap = Castable(_spell(version, 'Sram', TRICKY_TRAP), 2, False)
                self.assertEqual([], trap.alternatives)
                self.assertEqual(['trap'], [when for _row, when in trap.waiting_plain])
                bomb = Castable(_spell(version, 'Rogue', EXPLOBOMB), 2, False)
                self.assertEqual([], bomb.alternatives)
                self.assertEqual({'bomb'}, {when for _row, when in bomb.waiting_plain})

    def test_a_start_of_turn_glyph_counts_as_late_damage(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                glyph = self._castables('Feca', version)['Scorched Dirt']
                self.assertEqual(1, len(glyph.hits))
                self.assertEqual(['turn_begin'],
                                 [when for _row, when in glyph.delayed_plain])

    def test_a_spell_that_hits_and_places_scores_only_its_own_hit(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                spell = self._castables('Feca', version)['Pastureland']
                self.assertEqual([(31, 35)],
                                 [(hit.min_dam, hit.max_dam) for hit in spell.hits])
                self.assertEqual(['state'],
                                 [when for _row, when in spell.waiting_plain])

    def test_a_placed_block_never_passes_for_a_face_of_the_hit_before(self):
        from types import SimpleNamespace
        from chardata.spell_combo import element_runs
        for version in VERSIONS:
            with self.subTest(version=version):
                spell = _spell(version, 'Feca', PASTURELAND)
                digest = spell.get_effects_digest()
                self.assertEqual([('', [0]), ('Glyph damage - State 5260', [1])],
                                 spell.aggregates)
                self.assertEqual([], element_runs(spell.aggregates, digest.non_crit_dams[0]))
        faces = [SimpleNamespace(element=element) for element in (AIR, FIRE)]
        self.assertEqual([], element_runs([('', [0]), ('Glyph damage', [1])], faces))
        self.assertEqual([[('', [0]), ('', [1])]],
                         element_runs([('', [0]), ('', [1])], faces))


class TheDofus2TablesReadTheTrapsAndTheGlyphsTests(SimpleTestCase):

    def test_a_sram_trap_carries_the_grade_each_level_places(self):
        trap = _spell('dofus2', 'Sram', TRICKY_TRAP)
        self.assertEqual([15, 82, 149], trap.level_req)
        self.assertEqual([[(18, 20), (22, 24), (26, 28)]],
                         _rows(trap.effects.non_crit_ranges))
        self.assertEqual([FIRE], trap.effects.elements)
        self.assertEqual([('Trap damage', [0])], trap.aggregates)
        self.assertEqual({0: 'trap'}, trap.conditional)

    def test_a_feca_glyph_carries_the_grade_each_level_places(self):
        glyph = _spell('dofus2', 'Feca', SCORCHED_DIRT)
        self.assertEqual([80, 147], glyph.level_req)
        self.assertEqual([[(24, 27), (30, 34)]],
                         _rows(glyph.effects.non_crit_ranges))
        self.assertEqual([('Glyph damage', [0])], glyph.aggregates)
        self.assertEqual({0: 'turn_begin'}, glyph.delayed)

    def test_an_end_of_turn_glyph_reads_the_placed_grade_not_the_level_index(self):
        glyph = _spell('dofus2', 'Feca', DISTRUST)
        self.assertEqual([85, 152], glyph.level_req)
        self.assertEqual([[(17, 18), (21, 22)]] * 4,
                         _rows(glyph.effects.non_crit_ranges))
        self.assertEqual([EARTH, FIRE, WATER, AIR], glyph.effects.elements)
        self.assertEqual({0: 'turn_end', 1: 'turn_end',
                          2: 'turn_end', 3: 'turn_end'}, glyph.delayed)

    def test_a_gated_glyph_keeps_the_own_hit_first_and_names_the_state(self):
        spell = _spell('dofus2', 'Feca', PASTURELAND)
        self.assertEqual([[(31, 35)], [(31, 35)]],
                         _rows(spell.effects.non_crit_ranges))
        self.assertEqual([[(37, 42)], [(37, 42)]],
                         _rows(spell.effects.crit_ranges))
        self.assertEqual([('', [0]), ('Glyph damage - State 5260', [1])],
                         spell.aggregates)
        self.assertEqual({1: 'state'}, spell.conditional)

    def test_no_glyph_of_another_class_and_no_bomb_is_read(self):
        placed = {}
        for char_class, spells in get_damage_spells_for_version('dofus2').items():
            for spell in spells:
                for label, _indices in spell.aggregates or []:
                    head = label.split(' - ')[0]
                    if head.endswith(' damage') or head.endswith(' heals'):
                        placed.setdefault(char_class, set()).add(head)
        self.assertEqual({'Sram': {'Trap damage'}, 'Feca': {'Glyph damage'},
                          'Forgelance': {'Glyph damage'}}, placed)
        self.assertNotIn('Explobomb', {spell.name for spell
                                       in get_damage_spells_for_version('dofus2')['Rogue']})


class TheSpellsPageCarriesTheLabelTests(TestCase):

    def _build(self, char_class='Sram'):
        from fashionistapulp.structure import (get_structure,
                                               set_current_game_version)
        from chardata.models import Char
        set_current_game_version('dofus3')
        structure = get_structure('dofus3')
        names = []
        for type_name in ('Hat', 'Cloak', 'Belt', 'Boots', 'Amulet'):
            item = next(i for i in structure.types[200][type_name]
                        if not i.removed and i.ankama_id)
            names.append(structure.get_item_name_in_language(item, 'en'))
        self.client.post('/import/text/', {
            'text': '\n'.join(names), 'confirm': '1',
            'char_class': char_class, 'level': '200'})
        return Char.objects.order_by('-id').first()

    def _digests(self, char, language):
        page = self.client.get('/spells/%d/' % char.id,
                               HTTP_ACCEPT_LANGUAGE=language)
        self.assertEqual(200, page.status_code)
        found = re.search(r'var spellDigests = (.*);',
                          page.content.decode('utf-8'))
        self.assertTrue(found, 'the page carries no spell digests')
        return {digest['canonical']: digest
                for digest in json.loads(found.group(1))
                if digest.get('canonical')}

    def test_the_page_names_the_trap_in_english_and_in_french(self):
        char = self._build()
        for language, label, wait in (
                ('en', 'Trap damage', 'only when an enemy sets off the trap'),
                ('fr', 'Dégâts du piège',
                 'seulement si un ennemi déclenche le piège')):
            with self.subTest(language=language):
                digest = self._digests(char, language)['Tricky Trap']
                self.assertEqual([[label, [0]]], digest['aggregates'])
                self.assertEqual({'0': wait}, digest['conditional'])

    def test_the_page_puts_vendettas_damage_taken_on_its_card(self):
        char = self._build('Cra')
        for language, line, wait in (
                ('en', 'x110% damage sustained', 'only when an enemy sets off the trap'),
                ('fr', 'Dommages subis x110%', 'seulement si un ennemi déclenche le piège')):
            with self.subTest(language=language):
                digest = self._digests(char, language)['Vendetta']
                self.assertEqual({'normal': [line], 'critical': [line], 'waits': [wait]},
                                 digest['taken'])
