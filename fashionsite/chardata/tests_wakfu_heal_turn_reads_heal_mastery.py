import os
from unittest import mock

from django.test import SimpleTestCase

from fashionistapulp import wakfu_client_spells, wakfu_family, wakfu_turn, wakfu_value
from fashionistapulp.wakfu_value_rules import RULES, Rule, ASSUMPTION

BASE = {'ap': (6, 6), 'mp': (3, 3), 'wp': (6, 6)}
WATER_AT_DISTANCE = wakfu_value.DamageDealer(('water',), 'distance')
ENIRIPSA = 7
MOT_SOIGNANT = 779
LEVEL = 245


def totals(**stats):
    out = wakfu_value.bare_totals(BASE)
    out.update(stats)
    return out


def heal_row(base=100, critical=None, element='water', **extra):
    return wakfu_family.FamilyRow(
        1, 258, element, base, base if critical is None else critical, 'client', **extra)


def spell(*rows, high=5, ap=3):
    return wakfu_family.FamilySpell(1, 'heal', ENIRIPSA, None, ap, 0, 0, 1, high, 1, LEVEL,
                                    tuple(rows), ())


def heal_of(spell_, stats, role=WATER_AT_DISTANCE, **options):
    """Value of the heal turn of one spell: a single cast at 3 AP, six AP, three casts at most."""
    model = wakfu_turn.TurnModel([spell_], role, 'heal', casts_per_spell=1, **options)
    return model.damage(totals(**stats))


class HealMasteryTests(SimpleTestCase):
    def test_a_heal_with_no_mastery_is_its_base(self):
        self.assertEqual(100, heal_of(spell(heal_row()), {}))

    def test_a_hundred_heal_mastery_doubles_a_non_critical_heal(self):
        plain = heal_of(spell(heal_row()), {})
        self.assertEqual(2 * plain, heal_of(spell(heal_row()), {'heal_in_percent': 100}))

    def test_the_element_the_heal_names_adds_its_mastery_and_the_others_do_not(self):
        wanted = heal_of(spell(heal_row()), {'dmg_water_percent': 100})
        other = heal_of(spell(heal_row()), {'dmg_fire_percent': 100})
        self.assertEqual(200, wanted)
        self.assertEqual(100, other)

    def test_elemental_mastery_of_every_element_adds_to_a_heal(self):
        self.assertEqual(150, heal_of(spell(heal_row()), {wakfu_value.ELEMENTAL_MASTERY: 50}))

    def test_a_heal_cast_at_distance_takes_the_distance_mastery(self):
        found = heal_of(spell(heal_row()), {'ranged_dmg': 100, 'melee_dmg': 300})
        self.assertEqual(200, found)

    def test_a_heal_the_spell_can_aim_only_at_its_caster_takes_the_melee_mastery(self):
        stats = {'ranged_dmg': 100, 'melee_dmg': 300}
        self.assertEqual(400, heal_of(spell(heal_row(), high=0), stats))

    def test_without_the_rule_a_self_heal_takes_the_reach_of_the_role(self):
        patched = dict(RULES, self_heal_uses_melee_mastery=Rule(False, ASSUMPTION, 'test'))
        stats = {'ranged_dmg': 100, 'melee_dmg': 300}
        with mock.patch.dict(RULES, patched):
            self.assertEqual(200, heal_of(spell(heal_row(), high=0), stats))

    def test_resistances_and_rear_mastery_do_not_touch_a_heal(self):
        stats = {'res_water_percent': 400, wakfu_defense_key(): 300, 'backstab_bonus': 500}
        self.assertEqual(100, heal_of(spell(heal_row()), stats))

    def test_a_critical_heal_adds_the_critical_mastery_by_the_rule(self):
        stats = {'critical_bonus': 100, 'ferocity': 1000}
        sure = heal_of(spell(heal_row(base=100, critical=125)), stats)
        self.assertEqual(125 * 2, sure)
        patched = dict(RULES, critical_mastery_heals=Rule(False, ASSUMPTION, 'test'))
        with mock.patch.dict(RULES, patched):
            self.assertEqual(125, heal_of(spell(heal_row(base=100, critical=125)), stats))

    def test_berserk_mastery_does_not_add_to_a_heal_by_the_rule(self):
        stats = {'berserk_dmg': 200}
        found = heal_of(spell(heal_row()), stats, conditions=(wakfu_turn.BERSERK,))
        self.assertEqual(100, found)
        patched = dict(RULES, berserk_mastery_heals=Rule(True, ASSUMPTION, 'test'))
        with mock.patch.dict(RULES, patched):
            found = heal_of(spell(heal_row()), stats, conditions=(wakfu_turn.BERSERK,))
        self.assertEqual(300, found)

    def test_a_heal_that_is_a_share_of_life_is_read_with_the_life_of_the_build(self):
        from fashionistapulp import wakfu_defense
        found = heal_of(spell(heal_row(base=10, percent=True)), {'hp': 400})
        self.assertEqual(wakfu_defense.life(LEVEL, totals(hp=400)) * 10 // 100, found)

    def test_a_share_of_life_heal_takes_the_heal_mastery_by_the_assumed_rule(self):
        rule = RULES['percent_heals_use_heal_mastery']
        self.assertEqual(ASSUMPTION, rule.status)
        self.assertTrue(rule.value)
        stats = {'hp': 400, 'heal_in_percent': 100, 'dmg_water_percent': 100}
        from fashionistapulp import wakfu_defense
        life = wakfu_defense.life(LEVEL, totals(**stats)) * 10 // 100
        self.assertAlmostEqual(life * 3, heal_of(spell(heal_row(base=10, percent=True)), stats), 9)

    def test_the_rule_set_to_false_leaves_a_share_of_life_heal_at_the_life_share(self):
        from fashionistapulp import wakfu_defense
        patched = dict(RULES, percent_heals_use_heal_mastery=Rule(False, ASSUMPTION, 'test'))
        stats = {'hp': 400, 'heal_in_percent': 100, 'ferocity': 600, 'critical_bonus': 80}
        life = wakfu_defense.life(LEVEL, totals(**stats)) * 10 // 100
        with mock.patch.dict(RULES, patched):
            found = heal_of(spell(heal_row(base=10, percent=True)), stats)
            plain = heal_of(spell(heal_row(base=100)), stats)
        self.assertEqual(life, found)
        self.assertGreater(plain, 100)

    def test_health_steal_is_a_heal_action(self):
        self.assertIn(24, wakfu_client_spells.FAMILIES['heal'])
        self.assertEqual('heal', wakfu_client_spells.FAMILY_OF[24])


def wakfu_defense_key():
    from fashionistapulp import wakfu_defense
    return wakfu_defense.ELEMENTAL_RESISTANCE


class EniripsaHealsTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from fashionistapulp.fashionista_config import get_items_db_path
        path = get_items_db_path('wakfu')
        cls.book = None
        if os.path.exists(path):
            book = wakfu_turn.SpellBook(path)
            if book.client() is None:
                book.close()
            else:
                cls.book = book

    @classmethod
    def tearDownClass(cls):
        if cls.book is not None:
            cls.book.close()
        super().tearDownClass()

    def setUp(self):
        if self.book is None:
            self.skipTest('no Wakfu database with the client spell table')

    def test_at_mastery_zero_every_heal_row_holds_the_client_value_and_critical(self):
        client = self.book.client()
        compared = 0
        for breed in client.breeds():
            for found in self.book.family_spells(breed, LEVEL, 'heal'):
                own = client.spell(found.id)
                values = {row.effect: row for row in own.rows_of('heal')}
                for row in found.rows:
                    mine = values[row.id]
                    self.assertEqual(mine.value(LEVEL), row.base, found.id)
                    if row.critical_read == wakfu_turn.CLIENT:
                        self.assertIn(row.critical, {
                            other.value(LEVEL) for other in own.rows_of(
                                'heal', wakfu_client_spells.CRITICAL)}, found.id)
                    compared += 1
        self.assertGreater(compared, 40)

    def test_mot_soignant_heals_the_figures_the_game_shows(self):
        found = {spell_.id: spell_ for spell_ in self.book.family_spells(ENIRIPSA, LEVEL, 'heal')}
        row, = found[MOT_SOIGNANT].rows
        self.assertEqual((49, 62), (row.base, row.critical))

    def test_an_eniripsa_heals_for_more_with_mastery_than_without(self):
        spells = self.book.family_spells(ENIRIPSA, LEVEL, 'heal')
        model = wakfu_turn.TurnModel(spells, WATER_AT_DISTANCE, 'heal')
        bare = model.damage(totals())
        masterful = model.damage(totals(dmg_water_percent=500, heal_in_percent=200))
        self.assertGreater(bare, 0)
        self.assertGreater(masterful, 5 * bare)

    def test_a_heal_row_the_text_explains_keeps_the_text_conditions(self):
        kept = [row for breed in self.book.client().breeds()
                for found in self.book.family_spells(breed, LEVEL, 'heal')
                for row in found.rows if row.mode != 'hit' or row.conditions]
        self.assertGreater(len(kept), 0)
