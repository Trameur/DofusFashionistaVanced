# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A hit in the caster's worst element lands its least face: Supernova adds it to its best-element hit."""

from django.test import SimpleTestCase
from django.utils import translation

from chardata.spell_buffs import get_damage_spells_for_version
from chardata.spell_combo import Castable, best_turn
from chardata.spell_reference import get_spell_reference

SUPERNOVA = 32033
BURNT_PIE = 24006
VERSIONS = ('dofus3', 'beta')
LANGUAGES = ('en', 'fr', 'es', 'pt', 'de')
WORST_LABEL = 'Hit in worst element'

SAYS_WORST = {
    SUPERNOVA: {'en': 'worst elements', 'fr': 'pires', 'es': 'peores', 'pt': 'piores',
                'de': 'schlechtesten'},
    BURNT_PIE: {'en': 'worst element', 'fr': 'pire', 'es': 'peor', 'pt': 'pior',
                'de': 'schwächsten'},
}

_STATS = {'str': 600, 'int': 400, 'cha': 200, 'agi': 100, 'pow': 0, 'dam': 0,
          'cridam': 0, 'heals': 0, 'perspedam': 0, 'perweadam': 0,
          'permedam': 0, 'perrandam': 0, 'earthdam': 0, 'firedam': 0,
          'waterdam': 0, 'airdam': 0, 'neutdam': 0, 'ch': 0, 'final': 0,
          'negfinal': 0, 'pshdam': 0, 'ap': 12}


def _in_version(test, version):
    from fashionistapulp.structure import set_current_game_version
    test.addCleanup(set_current_game_version, 'dofus3')
    set_current_game_version(version)


def _spell(version, spell_id):
    return next(spell for spells in get_damage_spells_for_version(version).values()
                for spell in spells if spell.spell_id == spell_id)


def _card(version, spell_id, language):
    for entries in get_spell_reference(version).values():
        for entry in entries:
            if entry.get('id') == spell_id:
                return ((entry.get('description') or {}).get(language) or '').lower()
    return ''


def _cast(version, spell_id):
    spell = _spell(version, spell_id)
    return Castable(spell, len(spell.level_req) - 1, crit=False)


def _turn(version, cast, **stats):
    return best_turn(dict(_STATS, **stats), [cast], cast.cost, game_version=version,
                     caster_level=200)[0]


class SupernovaLandsBothHitsTests(SimpleTestCase):

    def test_each_cast_lands_one_best_and_one_worst_element_row(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                _in_version(self, version)
                cast = _cast(version, SUPERNOVA)
                self.assertEqual(4, cast.worst_faces)
                self.assertEqual(16, len(cast.plain_alternatives))
                for alternative in cast.plain_alternatives + cast.crit_alternatives:
                    self.assertEqual(2, len(alternative))

    def test_the_worst_element_row_is_the_clients_second_hit(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                spell = _spell(version, SUPERNOVA)
                digest = spell.get_effects_digest()
                top = len(spell.level_req) - 1
                rows = digest.non_crit_dams[top]
                self.assertEqual([(9, 11)] * 4, [(row.min_dam, row.max_dam) for row in rows[4:8]])
                self.assertEqual([(12, 14)] * 4,
                                 [(row.min_dam, row.max_dam) for row in digest.crit_dams[top][4:8]])
                self.assertEqual((WORST_LABEL, [4]), tuple(spell.aggregates[4]))

    def test_raising_the_weakest_element_raises_the_cast(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                _in_version(self, version)
                cast = _cast(version, SUPERNOVA)
                self.assertGreater(_turn(version, cast, agi=150), _turn(version, cast))

    def test_raising_an_element_that_stays_in_the_middle_changes_nothing(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                _in_version(self, version)
                cast = _cast(version, SUPERNOVA)
                self.assertAlmostEqual(_turn(version, cast), _turn(version, cast, cha=300))


class BurntPieHitsInOneElementTests(SimpleTestCase):

    def test_the_four_rows_are_four_faces_of_one_hit(self):
        for version in VERSIONS + ('dofus2',):
            with self.subTest(version=version):
                _in_version(self, version)
                cast = _cast(version, BURNT_PIE)
                self.assertEqual(4, cast.worst_faces)
                self.assertEqual([1, 1, 1, 1], [len(face) for face in cast.plain_alternatives])

    def test_the_strongest_element_does_not_raise_the_hit(self):
        for version in VERSIONS + ('dofus2',):
            with self.subTest(version=version):
                _in_version(self, version)
                cast = _cast(version, BURNT_PIE)
                self.assertAlmostEqual(_turn(version, cast), _turn(version, cast, str=900))
                self.assertGreater(_turn(version, cast, agi=150), _turn(version, cast))

    def test_its_lines_and_casting_are_read_from_the_client(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                spell = _spell(version, BURNT_PIE)
                digest = spell.get_effects_digest()
                top = len(spell.level_req) - 1
                self.assertEqual([(11, 13)] * 4,
                                 [(row.min_dam, row.max_dam) for row in digest.crit_dams[top]])
                self.assertEqual([2, 2, 2], spell.casting['ap'])


    def test_dofus_2_reads_its_lines_and_casting_from_the_client_too(self):
        _in_version(self, 'dofus2')
        spell = _spell('dofus2', BURNT_PIE)
        digest = spell.get_effects_digest()
        top = len(spell.level_req) - 1
        self.assertEqual([(8, 10)] * 4, [(row.min_dam, row.max_dam) for row in digest.non_crit_dams[top]])
        self.assertEqual([(10, 12)] * 4, [(row.min_dam, row.max_dam) for row in digest.crit_dams[top]])
        self.assertEqual([2, 2, 2], spell.casting['ap'])
        self.assertEqual((WORST_LABEL, [0]), tuple(spell.aggregates[0]))


class ThePageShowsTheWorstElementFaceTests(SimpleTestCase):

    def test_the_page_groups_the_worst_faces_as_one_least_hit(self):
        from chardata.spells_view import convert_aggregates
        for version in VERSIONS:
            for spell_id in SAYS_WORST:
                with self.subTest(version=version, spell=spell_id):
                    spell = _spell(version, spell_id)
                    rows = spell.get_effects_digest().non_crit_dams[0]
                    with translation.override('en'):
                        groups = convert_aggregates(spell.aggregates, version, rows)
                    self.assertEqual([WORST_LABEL, [len(rows) - 4, len(rows) - 3,
                                                    len(rows) - 2, len(rows) - 1], 'worst'],
                                     groups[-1])

    def test_the_compare_digest_carries_the_width_of_the_worst_hit(self):
        from chardata.spells_view import _scored_faces_by_rank
        for version in VERSIONS:
            with self.subTest(version=version):
                _in_version(self, version)
                spell = _spell(version, SUPERNOVA)
                scored = _scored_faces_by_rank(spell, spell.get_effects_digest())
                self.assertEqual(4, scored['worst'])
                self.assertEqual(16, len(scored['non_crit']['1']))

    def test_the_label_is_said_in_every_language_and_the_card_says_worst(self):
        from chardata.spells_view import _localized_aggregate_label
        with translation.override('en'):
            english = str(_localized_aggregate_label(WORST_LABEL))
        self.assertEqual(WORST_LABEL, english)
        for language in LANGUAGES:
            with self.subTest(language=language):
                with translation.override(language):
                    label = str(_localized_aggregate_label(WORST_LABEL))
                if language != 'en':
                    self.assertNotEqual(english, label)
                for spell_id, says in SAYS_WORST.items():
                    for version in VERSIONS:
                        self.assertIn(says[language], _card(version, spell_id, language))


class TheGeneratorReadsTheWorstElementHitTests(SimpleTestCase):

    def _generator(self):
        from chardata.tests import itemscraper_module
        return itemscraper_module('generate_damage_spells')

    def _effect(self, low, high, mask='A'):
        return {'effect_id': 2832, 'effect_element': -1, 'dice': {'min': low, 'max': high},
                'target_mask': mask, 'triggers': 'I', 'delay': 0,
                'zone': {'shape': 80, 'param1': 1, 'param2': 0},
                'effect_metadata': {'category': 2, 'description': {
                    'en': '#1{{~1~2 to }}#2 worst-element damage'}}}

    def _spell(self, mask='A'):
        return {'ankama_id': 1, 'name_en': 'Probe', 'level_requirements': [1, 100],
                'levels': [{'effects': [self._effect(5, 7, mask)],
                            'critical_effects': [self._effect(8, 10, mask)]},
                           {'effects': [self._effect(9, 11, mask)],
                            'critical_effects': [self._effect(12, 14, mask)]}]}

    def test_one_hit_per_grade_becomes_four_labelled_faces(self):
        entry = self._generator().convert_spell(self._spell())
        self.assertEqual(['EARTH', 'FIRE', 'WATER', 'AIR'], entry.elements)
        self.assertEqual([['5-7', '9-11']] * 4, entry.non_crit_ranges)
        self.assertEqual([['8-10', '12-14']] * 4, entry.crit_ranges)
        self.assertEqual([(WORST_LABEL, [0]), ('', [1]), ('', [2]), ('', [3])],
                         [tuple(group) for group in entry.aggregates])

    def test_burnt_pie_has_no_hand_written_stand_in_left_to_hide_a_regression(self):
        from chardata.tests import itemscraper_module
        specs = itemscraper_module('default_damage_spells').DEFAULT_DAMAGE_SPELL_SPECS
        pie = next(spec for spec in specs if spec.name == 'Burnt Pie')
        self.assertFalse(pie.hand_written)
        self.assertNotIn('Burnt Pie', self._generator().LEGACY_DEFAULT_SPELLS)

    def test_a_worst_element_hit_beside_plain_rows_with_no_group_is_refused(self):
        generator = self._generator()
        with self.assertRaises(SystemExit):
            generator._with_worst_element_faces(None, [1, 2, 3, 4], 5)
        faces = generator._with_worst_element_faces(None, [0, 1, 2, 3], 4)
        self.assertEqual([(WORST_LABEL, [0]), ('', [1]), ('', [2]), ('', [3])], faces)

    def test_a_hit_gated_on_a_state_is_left_out(self):
        self.assertIsNone(self._generator().convert_spell(self._spell('a,A,*E5675')))
