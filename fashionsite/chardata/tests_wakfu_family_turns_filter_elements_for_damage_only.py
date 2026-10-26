import collections
import os

from django.test import SimpleTestCase

from fashionistapulp import wakfu_family, wakfu_presets, wakfu_turn, wakfu_value
from fashionistapulp.wakfu_stats import OUT_OF_COMBAT_CAPS

BASE = {'ap': (6, 6), 'mp': (3, 3), 'wp': (6, 6)}
EARTH = ('earth',)
FECA, ENIRIPSA, XELOR = 1, 7, 5
LEVEL = 245


def totals(**stats):
    out = wakfu_value.bare_totals(BASE)
    out.update(stats)
    return out


def family_spell(rows, branch):
    return wakfu_family.FamilySpell(1, 'spell', FECA, branch, 3, 0, 0, 1, 5, 1, LEVEL,
                                    tuple(rows), ())


def turn_of(family, spells, elements, stats=None):
    role = wakfu_value.Role(elements, 'distance')
    return wakfu_turn.TurnModel(spells, role, family, casts_per_spell=1).damage(
        totals(**(stats or {})))


class AFamilyTurnReadsNoElementFilterTests(SimpleTestCase):
    def test_armor_placement_and_hindrance_count_a_spell_of_another_element(self):
        rows = {'armor': wakfu_family.FamilyRow(1, 1013, 'armor', 200, None, 'client'),
                'placement': wakfu_family.FamilyRow(1, 300, 'push', 3, None, 'client'),
                'hindrance': wakfu_family.FamilyRow(1, 55, 'ap', 4, None, 'client')}
        for family, row in rows.items():
            with self.subTest(family=family):
                spell = family_spell([row], 'fire')
                self.assertGreater(turn_of(family, [spell], EARTH), 0)
                self.assertEqual(turn_of(family, [spell], ('fire',)),
                                 turn_of(family, [spell], EARTH))

    def test_a_heal_outside_the_roles_elements_counts_with_the_mastery_of_its_own_element(self):
        heal = wakfu_family.FamilyRow(1, 258, 'water', 100, 100, 'client')
        spell = family_spell([heal], 'water')
        self.assertEqual(100, turn_of('heal', [spell], EARTH))
        self.assertEqual(200, turn_of('heal', [spell], EARTH, {'dmg_water_percent': 100}))
        self.assertEqual(100, turn_of('heal', [spell], EARTH, {'dmg_earth_percent': 100}))

    def test_the_damage_family_still_drops_a_spell_of_another_branch(self):
        row = wakfu_turn.Row(0, 'fire', 100, 125, 'client', frozenset(), frozenset(), 'hit', 1,
                             None, '', collections.Counter(), 'client', False)
        spell = wakfu_turn.Spell(1, 'spell', 'fire', 3, 0, 0, 1, 5, (row,), (), True, (), 1, None)
        role = wakfu_value.Role(EARTH, 'distance')
        self.assertEqual(0, wakfu_turn.TurnModel([spell], role, casts_per_spell=1).damage(
            totals()))
        fire = wakfu_value.Role(('fire',), 'distance')
        self.assertGreater(wakfu_turn.TurnModel([spell], fire, casts_per_spell=1).damage(
            totals()), 0)


class ClassFamiliesOnTheRealTablesTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from fashionistapulp.fashionista_config import get_items_db_path
        cls.path = get_items_db_path('wakfu')

    def setUp(self):
        if not os.path.exists(self.path):
            self.skipTest('no Wakfu database built; run update_data_wakfu.py')

    def turn(self, class_id, family, elements):
        ceiling = {name.lower(): cap for name, cap in OUT_OF_COMBAT_CAPS.items()}
        book = wakfu_turn.SpellBook(self.path)
        try:
            spells = book.family_spells(class_id, LEVEL, family)
        finally:
            book.close()
        role = wakfu_value.Role(elements, 'distance')
        return wakfu_turn.TurnModel(spells, role, family).damage(ceiling)

    def test_feca_armor_on_earth_is_the_armor_of_every_element(self):
        every = self.turn(FECA, 'armor', wakfu_value.ELEMENTS)
        self.assertGreater(every, 0)
        for element in wakfu_value.ELEMENTS:
            with self.subTest(element=element):
                self.assertEqual(every, self.turn(FECA, 'armor', (element,)))

    def test_eniripsa_heal_on_earth_reads_and_the_registry_gives_the_role(self):
        self.assertGreater(self.turn(ENIRIPSA, 'heal', EARTH), 0)
        built = wakfu_presets.role(ENIRIPSA, 'heal', EARTH, LEVEL, path=self.path)
        self.assertIn('heal', built.shares)

    def test_the_feca_tank_on_earth_holds_its_self_armor(self):
        built = wakfu_presets.role(FECA, 'tank', EARTH, LEVEL, path=self.path)
        book = wakfu_turn.SpellBook(self.path)
        try:
            turns = wakfu_presets.build_turns(book, FECA, LEVEL, built, self.path)
        finally:
            book.close()
        self.assertGreater(turns.models['armor'].damage(
            {name.lower(): cap for name, cap in OUT_OF_COMBAT_CAPS.items()}), 0)
