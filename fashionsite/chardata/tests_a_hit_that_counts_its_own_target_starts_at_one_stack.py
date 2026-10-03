# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Tumult and Slaughtering Arrow count every target in their area before they hit: the enemy hit is always one stack."""
from django.test import SimpleTestCase

from chardata.spell_buffs import get_damage_spells_for_version
from chardata.spell_reference import get_spell_reference

TUMULT = 13144
SLAUGHTERING_ARROW = 32457
CHILD = 99001
OWNER = 99000

ONE_STACK = {
    ('dofus3', TUMULT): (39, 41),
    ('beta', TUMULT): (39, 41),
    ('dofus2', TUMULT): (39, 41),
    ('dofus3', SLAUGHTERING_ARROW): (37, 41),
    ('beta', SLAUGHTERING_ARROW): (35, 39),
}

SAYS = {
    TUMULT: {'en': 'for each enemy in the area of effect',
             'fr': "pour chaque ennemi dans la zone d'effet",
             'es': 'por cada enemigo en la zona de efecto',
             'pt': 'para cada inimigo na zona de efeito',
             'de': 'bei jedem gegner im wirkungsbereich'},
    SLAUGHTERING_ARROW: {'en': 'for each entity in the area of effect',
                         'fr': "pour chaque entité dans la zone d'effet",
                         'es': 'por cada entidad en la zona de efecto',
                         'pt': 'para cada entidade na zona de efeito',
                         'de': 'bei jeder einheit im wirkungsbereich'},
}


def _generator():
    from chardata.tests import itemscraper_module
    return itemscraper_module('generate_damage_spells')


def _in_version(test, version):
    from fashionistapulp.structure import set_current_game_version
    test.addCleanup(set_current_game_version, 'dofus3')
    set_current_game_version(version)


def _spell(version, spell_id):
    return next(spell for spells in get_damage_spells_for_version(version).values()
                for spell in spells if spell.spell_id == spell_id)


def _text(version, spell_id, language):
    for entries in get_spell_reference(version).values():
        for entry in entries:
            if entry.get('id') == spell_id:
                text = (entry.get('description') or {}).get(language) or ''
                return text.replace('’', "'").lower()
    return ''


def _zone(shape=88, size=1):
    return {'shape': shape, 'param1': size, 'param2': 0}


def _cast(mask='A', zone=None):
    return {'effect_id': 1160, 'dice': {'min': CHILD, 'max': 1}, 'value': 0,
            'target_mask': mask, 'triggers': 'I', 'delay': 0, 'random': 0, 'flags': 0,
            'zone': zone or _zone()}


def _hit(zone=None):
    return {'effect_id': 99, 'dice': {'min': 19, 'max': 21}, 'target_mask': 'g,A',
            'triggers': 'I', 'delay': 0, 'random': 0, 'flags': 15, 'effect_element': 2,
            'zone': zone or _zone(),
            'effect_metadata': {'category': 2,
                                'description': {'en': '#1{{~1~2 to }}#2 Fire damage'}}}


def _raise(flags=0):
    return {'effect_id': 293, 'dice': {'min': OWNER, 'max': 0}, 'value': 20,
            'target_mask': 'C', 'triggers': 'I', 'delay': 0, 'flags': flags,
            'zone': _zone(80)}


def _shape(effects, child_flags=0):
    owner = {'ankama_id': OWNER, 'levels': [{'grade': 1, 'effects': effects,
                                            'critical_effects': []}]}
    child = {'ankama_id': CHILD, 'levels': [{'grade': 1, 'effects': [_raise(child_flags)]}]}
    return owner, {OWNER: owner, CHILD: child}


class TheOfficialTextCountsTheAreaTests(SimpleTestCase):

    def test_ankama_says_the_damage_grows_with_each_target_in_the_area(self):
        for version, spell_id in ONE_STACK:
            for language, words in SAYS[spell_id].items():
                with self.subTest(version=version, spell=spell_id, language=language):
                    self.assertIn(words, _text(version, spell_id, language))


class TheGeneratorReadsTheCountFromTheClientTests(SimpleTestCase):

    def test_a_cast_that_raises_the_spell_before_its_hit_counts_the_target(self):
        spell, lookup = _shape([_cast(), _hit()])
        self.assertTrue(_generator()._counts_its_own_target(spell, lookup))

    def test_a_raise_after_the_hit_waits_for_the_next_cast(self):
        spell, lookup = _shape([_hit(), _cast()])
        self.assertFalse(_generator()._counts_its_own_target(spell, lookup))

    def test_a_cast_on_other_cells_than_the_hit_counts_nothing(self):
        spell, lookup = _shape([_cast(zone=_zone(67, 2)), _hit()])
        self.assertFalse(_generator()._counts_its_own_target(spell, lookup))

    def test_a_raise_only_the_tooltip_shows_counts_nothing(self):
        generator = _generator()
        spell, lookup = _shape([_cast(), _hit()], child_flags=generator.CLIENT_ONLY_FLAG)
        self.assertFalse(generator._counts_its_own_target(spell, lookup))

    def test_a_cast_on_allies_only_does_not_count_the_enemy(self):
        spell, lookup = _shape([_cast(mask='a'), _hit()])
        self.assertFalse(_generator()._counts_its_own_target(spell, lookup))

    def test_the_first_row_holds_one_stack_when_the_target_is_counted(self):
        generator = _generator()
        template = {'stackable_damage': {'per_stack': [20], 'max_stacks': [4]}}
        for counted, rows, labels in (
                (False, [['19-21'], ['39-41'], ['59-61'], ['79-81'], ['99-101']],
                 ['Stack 0', 'Stack 1', 'Stack 2', 'Stack 3', 'Stack 4']),
                (True, [['39-41'], ['59-61'], ['79-81'], ['99-101']],
                 ['Stack 1', 'Stack 2', 'Stack 3', 'Stack 4'])):
            non_crit, crit, elements = [['19-21']], [['23-25']], ['FIRE']
            aggregates = generator._apply_stackable_damage(
                template, [190], non_crit, crit, elements, None, None, counted)
            with self.subTest(counted=counted):
                self.assertEqual(rows, non_crit)
                self.assertEqual(len(rows), len(crit))
                self.assertEqual(len(rows), len(elements))
                self.assertEqual(labels, [label for label, _rows in aggregates])
                self.assertEqual([[index] for index in range(len(rows))],
                                 [indices for _label, indices in aggregates])

    def test_a_counted_target_without_a_cap_still_lands_one_stack(self):
        template = {'stackable_damage': {'per_stack': [20], 'max_stacks': [None]}}
        non_crit = [['19-21']]
        aggregates = _generator()._apply_stackable_damage(
            template, [190], non_crit, [['23-25']], ['FIRE'], None, None, True)
        self.assertEqual([['39-41']], non_crit)
        self.assertEqual([('Stack 1', [0])], aggregates)


class TheTurnCountsOneStackTests(SimpleTestCase):

    def test_the_spell_table_starts_at_one_stack(self):
        for version, spell_id in ONE_STACK:
            with self.subTest(version=version, spell=spell_id):
                self.assertEqual('Stack 1', _spell(version, spell_id).aggregates[0][0])

    def test_the_best_turn_counts_the_enemy_it_hits(self):
        from chardata.spell_combo import Castable
        for (version, spell_id), (low, high) in ONE_STACK.items():
            _in_version(self, version)
            spell = _spell(version, spell_id)
            cast = Castable(spell, len(spell.level_req) - 1, False)
            with self.subTest(version=version, spell=spell_id):
                self.assertEqual([[(low, high)]],
                                 [[(hit.min_dam, hit.max_dam) for hit in face]
                                  for face in cast.plain_alternatives])
