import collections
import io
import itertools
import json
import math
import os
import shutil
import sqlite3
import tempfile

from django.core.management import call_command
from django.test import SimpleTestCase

from fashionistapulp import wakfu_db, wakfu_turn, wakfu_value
from fashionistapulp.wakfu_value_rules import RULES

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CLASSES = (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 18, 19)
FIRE_AT_DISTANCE = wakfu_value.DamageDealer(('fire',), 'distance')
WATER_AT_DISTANCE = wakfu_value.DamageDealer(('water',), 'distance')


def totals(**stats):
    out = wakfu_value.bare_totals()
    for key, number in stats.items():
        out[key] = number
    return out


def rows_of(text, critical=None):
    return [dict(zip(('kind', 'value', 'critical', 'conditions', 'unless', 'mode',
                      'hits', 'reach', 'heading', 'cost'), clause))
            for clause in wakfu_turn.read_clauses(text, critical)]


def row(conditions=(), unless=()):
    return wakfu_turn.Row(0, 'fire', 100, 125, 'x1.25', frozenset(conditions),
                          frozenset(unless), 'hit', 1, None, '', collections.Counter())


class TheSpellTextSaysWhatEachRowNeedsTests(SimpleTestCase):
    """Each damage figure of the level-245 text gets its conditions, mode and hits."""

    def test_a_row_before_any_heading_lands_on_every_cast(self):
        row, = rows_of('Dommage : 80 Pousse de 1 case')
        self.assertEqual(frozenset(), row['conditions'])
        self.assertEqual('hit', row['mode'])

    def test_a_row_said_in_place_of_the_hit_replaces_it_under_its_heading(self):
        first, second = rows_of(
            'Dommage : 80 Si la cible est Trempée : - Dommage : 120 à la place')
        self.assertEqual(frozenset(), first['conditions'])
        self.assertEqual(frozenset(('if: si la cible est trempée',)), second['conditions'])
        self.assertEqual('instead', second['mode'])

    def test_a_conditional_copy_of_the_hit_replaces_it_without_saying_so(self):
        _first, second = rows_of(
            'Dommage : 100 Si la cible dort : - Pousse de 1 case - Dommage : 100')
        self.assertEqual('instead', second['mode'])

    def test_extra_damage_adds_to_the_hit(self):
        _first, second = rows_of('Dommage : 100 Si la cible dort : - Dommage : 30 '
                                 'supplémentaires')
        self.assertEqual('adds', second['mode'])

    def test_the_otherwise_row_lands_unless_its_pair_holds(self):
        first, second = rows_of('Si la cible a plus de 50 % de ses PV : - Dommage : 150 '
                                'Sinon : - Dommage : 90')
        self.assertEqual(frozenset(('if: si la cible a plus de 50 % de ses pv',)),
                         first['conditions'])
        self.assertEqual(frozenset(), second['conditions'])
        self.assertEqual(first['conditions'], second['unless'])

    def test_a_row_on_a_later_event_is_an_event_and_keeps_its_melee_mark(self):
        _first, second = rows_of(
            'Dommage : 60 Bouclier En fin de tour : - Attire les ennemis - '
            'Le lanceur leur inflige Dommage : 60 (mêlée)')
        self.assertEqual(frozenset((wakfu_turn.EVENT,)), second['conditions'])
        self.assertEqual('melee', second['reach'])

    def test_a_line_after_a_heading_list_starts_over(self):
        row, = rows_of('Mode A : - Pousse de 1 case Mode B : - Echange de position '
                       'Dommage : 90')
        self.assertEqual(frozenset(), row['conditions'])

    def test_a_heading_after_an_item_is_not_nested_in_the_list_before(self):
        row, = rows_of('Lancé sur allié : - Stabilisé (1 tour) Lancé sur ennemi : - '
                       'Dommage : 83')
        self.assertEqual(frozenset((wakfu_turn.ENEMY,)), row['conditions'])

    def test_a_nested_heading_needs_its_list_opener_too(self):
        _first, second = rows_of('Dommage : 98 Si la cible est sur un Portail : - '
                                 'Serein : Vole 10 % - Exalté : Dommage : 130 à la place')
        self.assertEqual(frozenset(('portal', 'exalte')), second['conditions'])

    def test_twice_means_two_hits_and_an_area_is_no_condition(self):
        twice, = rows_of('Deux fois : Dommage : 50')
        self.assertEqual((frozenset(), 2), (twice['conditions'], twice['hits']))
        area, = rows_of('En zone croix : - Dommage : 55 - 20 Armure')
        self.assertEqual((frozenset(), 1), (area['conditions'], area['hits']))

    def test_a_row_on_summons_needs_a_summon(self):
        _first, second = rows_of('Dommage : 60 - Dommage : 120 sur invocations')
        self.assertEqual(frozenset(('summon target',)), second['conditions'])

    def test_a_berserk_section_row_needs_berserk_and_costs_what_the_section_says(self):
        row, = rows_of('Effets normaux Attire de 3 cases Effets si Berserk Coûte 1 PW '
                       'supplémentaire Dommage : 70')
        self.assertEqual(frozenset((wakfu_turn.BERSERK,)), row['conditions'])
        self.assertEqual({'wp': 1}, dict(row['cost']))
        self.assertEqual('adds', row['mode'])

    def test_a_cost_said_under_a_condition_goes_with_that_condition(self):
        _first, second = rows_of('Dommage : 100 Si le Pandawa porte : - Le sort coûte 1 PA '
                                 'de moins - Dommage : 100')
        self.assertEqual(frozenset(('carrying',)), second['conditions'])
        self.assertEqual({'ap': -1}, dict(second['cost']))

    def test_a_pictured_target_is_the_enemy_only_when_nothing_else_deals_damage(self):
        only, = rows_of('Lancé sur : - Stabilisé Lancé sur : - Dommage : 175')
        self.assertEqual(frozenset((wakfu_turn.ENEMY,)), only['conditions'])
        _first, second = rows_of('Dommage : 121 Lancé sur : - Attire de 2 cases - '
                                 'Dommage : 121')
        self.assertEqual(frozenset((wakfu_turn.PICTURED,)), second['conditions'])

    def test_a_spell_that_must_target_a_pictured_object_needs_one(self):
        self.assertEqual(frozenset((wakfu_turn.OBJECT,)),
                         wakfu_turn.requirements('Dommage : 100 Doit cibler un'))
        self.assertEqual(frozenset((wakfu_turn.OBJECT,)),
                         wakfu_turn.requirements('Doit cibler une ou un Arbre'))
        self.assertEqual(frozenset(),
                         wakfu_turn.requirements('Doit cibler une cellule occupée'))
        self.assertEqual(frozenset(),
                         wakfu_turn.requirements('Doit cibler un combattant ou un'))

    def test_the_critical_text_gives_each_row_its_own_critical_value(self):
        first, second = rows_of('Dommage : 80 Si la cible dort : - Dommage : 30 '
                                'supplémentaires',
                                'Dommage : 101 Si la cible dort : - Dommage : 38 '
                                'supplémentaires')
        self.assertEqual((101, 38), (first['critical'], second['critical']))

    def test_a_negated_heading_holds_until_the_role_takes_its_key(self):
        first, _heal, otherwise, _other_heal = rows_of(
            'Si aucun portail à 3 cases ou moins de la cible : - Dommage : 90 - Soin : 49 '
            'Sinon : - Dommage : 60 - Soin : 33')
        self.assertEqual(frozenset(('no portal',)), first['conditions'])
        self.assertEqual(first['conditions'], otherwise['unless'])
        plain = wakfu_turn.DEFAULT_CONDITIONS
        portal = plain | {'portal'}
        self.assertEqual((True, False),
                         (wakfu_turn.lands(row(first['conditions']), plain),
                          wakfu_turn.lands(row(unless=otherwise['unless']), plain)))
        self.assertEqual((False, True),
                         (wakfu_turn.lands(row(first['conditions']), portal),
                          wakfu_turn.lands(row(unless=otherwise['unless']), portal)))
        self.assertEqual('unless a portal is involved', wakfu_turn.describe('no portal'))

    def test_a_negated_heading_with_no_named_key_needs_the_role_to_take_it(self):
        _first, second = rows_of("Dommage : 83 Si la cible n'est pas dans la ligne de vue du "
                                 'lanceur : Dommage : 111 à la place')
        self.assertEqual(
            frozenset(("if: si la cible n'est pas dans la ligne de vue du lanceur",)),
            second['conditions'])

    def test_a_timing_said_right_after_the_figure_makes_it_a_later_event(self):
        delayed, = rows_of('Dommage : 181 en fin de tour de la cible Tous les 12 PW regagnés : '
                           '- Les effets du sort sont doublés')
        self.assertEqual(frozenset((wakfu_turn.EVENT,)), delayed['conditions'])
        self.assertEqual('en fin de tour de la cible', delayed['heading'])
        self.assertFalse(wakfu_turn.lands(row(delayed['conditions']),
                                          wakfu_turn.DEFAULT_CONDITIONS))
        on_cast, = rows_of('Dommage : 140 Au début du prochain tour : - Le sort est répliqué '
                           "sur la dernière case - 75 % des dommages du sort d'origine")
        self.assertEqual(frozenset(), on_cast['conditions'])

    def test_a_row_for_a_caster_who_has_not_moved_needs_the_stood_still_key(self):
        _first, second, third = rows_of(
            "Dommage : 181 Si le Crâ n'a pas utilisé de PM pour se déplacer dans son tour : - "
            'Dommage supplémentaires : 60 Tir précis : Dommage supplémentaires : 121 - '
            'Consomme 90 de Précision')
        self.assertEqual(frozenset((wakfu_turn.STILL,)), second['conditions'])
        self.assertEqual(frozenset(('precise shot',)), third['conditions'])

    def test_what_a_text_says_about_damage_beyond_its_figures_is_read(self):
        self.assertEqual(
            (('next cast', "Le prochain sort feu subi par le porteur de l'état inflige 15 % "
                           'Dommages supplémentaires'),
             (wakfu_turn.GAUGE, 'Concentration')),
            wakfu_turn.mechanics(
                'Lancé sur ennemi : - Dommage : 30 - Jugement (Niv. 15) - Le prochain sort feu '
                "subi par le porteur de l'état inflige 15 % Dommages supplémentaires Lancé sur "
                'allié : - Préparation (+10 Niv.) Concentration (+5 Niv.)'))
        self.assertIn(('damage bonus', '1 % supplémentaire par niveau de Retour de flamme '
                                       '(max 100)'),
                      wakfu_turn.mechanics('Retour de flamme : 30 % des PV max Dommage : 151 - '
                                           '1 % supplémentaire par niveau de Retour de flamme '
                                           '(max 100)'))
        self.assertEqual((('repeat', 'Répète ses effets sur les cibles précédentes'),),
                         wakfu_turn.mechanics('Dommage : 83 -1 PA À chaque lancer du sort : - '
                                              'Répète ses effets sur les cibles précédentes'))

    def test_a_target_debuff_or_a_life_steal_is_no_damage_bonus(self):
        self.assertEqual((), wakfu_turn.mechanics('Dommage : 83 -20 % Dommages infligés '
                                                  '-20 % Coup critique'))
        self.assertEqual((), wakfu_turn.mechanics('Dommage : 90 Vole 100 % des Dommages '
                                                  'infligés'))


class InventedSpells:
    """A throwaway items_wakfu.db holding one invented class, 99."""

    CLASS = 99
    TEXT = {
        1: ('Dommage : 100', 'Dommage : 126'),
        2: ('Dommage : 170', 'Dommage : 213'),
        6: ('Dommage : 80 Si la cible est Trempée : - Dommage : 120 à la place',
            'Dommage : 100 Si la cible est Trempée : - Dommage : 150 à la place'),
        8: ('Serein : - Dommage : 90 Exalté : - Dommage : 130',
            'Serein : - Dommage : 112 Exalté : - Dommage : 162'),
        9: ("Dommage : 400 Si le Crâ n'a pas utilisé de PM pour se déplacer dans son tour : "
            '- Dommage supplémentaires : 40 Tir précis : - 50 % Dommages infligés par la '
            'prochaine Flèche - Consomme 45 de Précision',
            "Dommage : 500 Si le Crâ n'a pas utilisé de PM pour se déplacer dans son tour : "
            '- Dommage supplémentaires : 50 Tir précis : - 50 % Dommages infligés par la '
            'prochaine Flèche - Consomme 45 de Précision'),
        10: ('Si aucun portail à 3 cases ou moins de la cible : - Dommage : 90 - Soin : 49 '
             'Sinon : - Dommage : 60 - Soin : 33',
             'Si aucun portail à 3 cases ou moins de la cible : - Dommage : 113 - Soin : 62 '
             'Sinon : - Dommage : 75 - Soin : 41'),
    }
    # id: (branch, ap, mp, wp, range, {level: [(element, value)]})
    SPELLS = {
        1: ('FIRE', 3, None, None, '1 - 4', {200: [('FIRE', 90)], 245: [('FIRE', 100)]}),
        2: ('FIRE', 4, None, 1, '3 - 6', {200: [('FIRE', 150)], 245: [('FIRE', 170)]}),
        3: ('FIRE', 2, None, None, '1 - 1', {200: [('FIRE', 70)]}),
        4: ('WATER', 2, None, None, '1 - 5', {200: [('WATER', 200)]}),
        5: (None, 5, None, None, '2 - 5', {200: [('LIGHT', 160)]}),
        6: ('FIRE', 3, None, None, '1 - 4', {200: [('FIRE', 80), ('FIRE', 120)]}),
        7: ('FIRE', None, 2, None, '1 - 3', {200: [('FIRE', 40)]}),
        8: ('FIRE', 4, None, None, '1 - 4', {200: [('FIRE', 90), ('FIRE', 130)]}),
        9: ('WATER', 2, None, None, '5 - 8', {245: [('WATER', 400), ('WATER', 40)]}),
        10: ('WATER', 2, None, None, '1 - 4', {245: [('WATER', 90), ('WATER', 60)]}),
    }

    def __init__(self, spells=None):
        self.folder = tempfile.mkdtemp()
        self.path = os.path.join(self.folder, 'items_wakfu.db')
        conn = sqlite3.connect(self.path)
        wakfu_db.create_tables(conn)
        for spell_id, (branch, ap, mp, wp, reach, levels) in (spells or self.SPELLS).items():
            conn.execute('INSERT INTO spells VALUES (?, ?, ?, ?, ?, ?, ?)',
                         (spell_id, self.CLASS, branch, ap, mp, wp, reach))
            conn.execute("INSERT INTO spell_names VALUES (?, 'fr', ?)",
                         (spell_id, 'Sort %d' % spell_id))
            normal, critical = self.TEXT.get(spell_id, (
                ' '.join('Dommage : %d' % value for _e, value in levels[min(levels)]), ''))
            conn.execute("INSERT INTO spell_text VALUES (?, 'fr', ?, ?)",
                         (spell_id, normal, critical))
            if 245 not in levels:
                levels = dict(levels, **{'245': levels[min(levels)]})
            for level, effects in levels.items():
                for position, (element, value) in enumerate(effects):
                    conn.execute("INSERT INTO spell_effects VALUES (?, ?, ?, 'damage', ?, ?,"
                                 ' 0, ?)', (spell_id, int(level), position, element, value,
                                            int(position > 0 and spell_id in (6, 8))))
        conn.commit()
        conn.close()

    def book(self, **options):
        return wakfu_turn.SpellBook(self.path, **options)

    def remove(self):
        shutil.rmtree(self.folder, ignore_errors=True)


class TheTurnSpendsItsBudgetOnTheBestCastsTests(SimpleTestCase):
    """best_turn: the best casts a sheet affords, held to the role's elements and reach."""

    def setUp(self):
        self.spells = InventedSpells()
        self.addCleanup(self.spells.remove)
        self.book = self.spells.book()
        self.addCleanup(self.book.close)

    def turn(self, role=FIRE_AT_DISTANCE, level=200, **options):
        sheet = options.pop('sheet', None) or totals(ap=11, mp=4, wp=6,
                                                     dmg_fire_percent=400)
        return wakfu_turn.best_turn(self.book.spells(self.spells.CLASS, level), role,
                                    sheet, **options)

    def test_the_rotation_is_the_best_the_budget_affords(self):
        sheet = totals(ap=11, mp=4, wp=6, dmg_fire_percent=400, ferocity=27)
        spells = [spell for spell in self.book.spells(self.spells.CLASS, 200)
                  if wakfu_turn.castable(spell, ('fire',))
                  and wakfu_turn.reaches(spell, 'distance')]
        accepted = wakfu_turn.DEFAULT_CONDITIONS | {'serein'}
        worth = {spell.id: wakfu_turn.cast_damage(spell, sheet, 'distance', 'front',
                                                  accepted)[0] for spell in spells}
        best = 0
        for counts in itertools.product(range(4), repeat=len(spells)):
            ap = sum(n * spell.ap for n, spell in zip(counts, spells))
            wp = sum(n * spell.wp for n, spell in zip(counts, spells))
            mp = sum(n * spell.mp for n, spell in zip(counts, spells))
            if ap <= 11 and wp <= RULES['wp_spent_per_turn'].value and mp <= 4:
                best = max(best, sum(n * worth[spell.id] for n, spell in zip(counts, spells)))
        turn = self.turn(sheet=sheet, conditions=('serein',))
        self.assertAlmostEqual(best, turn.damage)
        self.assertEqual(turn.damage, sum(turn.elements.values()))
        for spell_id, casts in collections.Counter(turn.casts).items():
            self.assertLessEqual(casts, RULES['casts_per_spell_per_turn'].value)

    def test_a_turn_casts_only_the_roles_elements_and_branchless_spells(self):
        usable = self.turn().usable
        self.assertNotIn(4, usable)
        self.assertIn(5, usable)

    def test_the_reach_decides_which_spells_are_in_range(self):
        self.assertNotIn(3, self.turn().usable)
        melee = self.turn(role=wakfu_value.DamageDealer(('fire',), 'melee')).usable
        self.assertIn(3, melee)
        self.assertNotIn(2, melee)

    def test_light_takes_the_highest_element_mastery(self):
        spell, = [one for one in self.book.spells(self.spells.CLASS, 200) if one.id == 5]
        sheet = totals(dmg_water_percent=700, dmg_fire_percent=100, ranged_dmg=50)
        worth = wakfu_turn.cast_damage(spell, sheet, 'distance', 'front',
                                       wakfu_turn.DEFAULT_CONDITIONS)[0]
        chance = wakfu_value.critical_chance(0)
        expected = ((1 - chance) * wakfu_value.hit_damage(160, 750)
                    + chance * wakfu_value.hit_damage(math.floor(160 * 1.25), 750))
        self.assertAlmostEqual(expected, worth)

    def test_the_critical_value_is_the_encyclopedias_at_245_and_the_rule_below(self):
        at_245 = {spell.id: spell for spell in self.book.spells(self.spells.CLASS, 245)}
        self.assertEqual((213, 'encyclopedia'), (at_245[2].rows[0].critical,
                                                 at_245[2].rows[0].critical_read))
        at_200 = {spell.id: spell for spell in self.book.spells(self.spells.CLASS, 200)}
        self.assertEqual(math.floor(150 * RULES['critical_multiplier'].value),
                         at_200[2].rows[0].critical)
        given = self.spells.book(critical={(2, 200): [190]})
        self.addCleanup(given.close)
        row = {one.id: one for one in given.spells(self.spells.CLASS, 200)}[2].rows[0]
        self.assertEqual((190, 'given'), (row.critical, row.critical_read))

    def test_an_expected_hit_weighs_the_critical_hit_by_its_chance(self):
        spell = {one.id: one for one in self.book.spells(self.spells.CLASS, 245)}[1]
        sheet = totals(dmg_fire_percent=300, dmg_in_percent=50, ranged_dmg=100,
                       critical_bonus=200, ferocity=37)
        chance = wakfu_value.critical_chance(37)
        expected = ((1 - chance) * wakfu_value.hit_damage(100, 450)
                    + chance * wakfu_value.hit_damage(126, 650))
        self.assertAlmostEqual(expected, wakfu_turn.cast_damage(
            spell, sheet, 'distance', 'front', wakfu_turn.DEFAULT_CONDITIONS)[0])

    def test_a_hit_from_behind_adds_rear_mastery_and_the_rear_multiplier(self):
        spell = {one.id: one for one in self.book.spells(self.spells.CLASS, 245)}[1]
        sheet = totals(dmg_fire_percent=300, backstab_bonus=100)
        front = wakfu_turn.cast_damage(spell, sheet, 'distance', 'front',
                                       wakfu_turn.DEFAULT_CONDITIONS)[0]
        rear = wakfu_turn.cast_damage(spell, sheet, 'distance', 'rear',
                                      wakfu_turn.DEFAULT_CONDITIONS)[0]
        self.assertAlmostEqual(front * 500 / 400 * RULES['rear_hit_multiplier'].value, rear)

    def test_a_conditional_row_counts_only_when_the_role_takes_its_condition(self):
        condition = 'if: si la cible est trempée'
        plain = self.turn()
        self.assertIn((6, 1, (condition,), 'Si la cible est Trempée'), plain.dropped)
        taken = self.turn(conditions=(condition,))
        self.assertIn((6, 1, (condition,), 'Si la cible est Trempée'), taken.counted)
        spell = {one.id: one for one in self.book.spells(self.spells.CLASS, 200)}[6]
        sheet = totals(dmg_fire_percent=400)
        accepted = wakfu_turn.DEFAULT_CONDITIONS | {condition}
        one_row = spell._replace(rows=spell.rows[1:])
        self.assertAlmostEqual(
            wakfu_turn.cast_damage(one_row, sheet, 'distance', 'front', accepted)[0],
            wakfu_turn.cast_damage(spell, sheet, 'distance', 'front', accepted)[0])

    def test_a_class_with_stances_gets_its_best_stance_named(self):
        sheet = totals(ap=4, mp=0, wp=0, dmg_fire_percent=400)
        turn = self.turn(sheet=sheet)
        self.assertEqual((8,), turn.casts)
        self.assertEqual('exalte', turn.stance)
        serein = self.turn(sheet=sheet, conditions=('serein',))
        self.assertLess(serein.damage, turn.damage)

    def test_the_wp_a_turn_may_spend_caps_the_wp_spells(self):
        sheet = totals(ap=12, wp=6, dmg_fire_percent=400)
        casts = collections.Counter(self.turn(sheet=sheet).casts)
        self.assertLessEqual(casts[2], RULES['wp_spent_per_turn'].value)
        more = collections.Counter(self.turn(sheet=sheet, wp=3).casts)
        self.assertGreater(more[2], casts[2])

    def test_an_mp_spell_spends_mp_not_ap(self):
        self.assertIn(7, self.turn(sheet=totals(ap=0, mp=4, dmg_fire_percent=400)).casts)
        self.assertNotIn(7, self.turn(sheet=totals(ap=0, mp=1, dmg_fire_percent=400)).casts)

    def test_counted_rows_belong_to_the_cast_spells_only(self):
        condition = 'if: si la cible est trempée'
        idle = self.turn(sheet=totals(ap=2, mp=0, wp=0, dmg_fire_percent=400),
                         conditions=(condition,))
        self.assertIn(6, idle.usable)
        self.assertNotIn(6, idle.casts)
        self.assertEqual([], [entry for entry in idle.counted + idle.dropped if entry[0] == 6])
        busy = self.turn(conditions=(condition,))
        self.assertTrue(busy.counted)
        self.assertLessEqual({entry[0] for entry in busy.counted}, set(busy.casts))

    def test_a_negated_heading_lands_its_row_until_the_role_takes_its_key(self):
        spell = {one.id: one for one in self.book.spells(self.spells.CLASS, 245)}[10]
        sheet = totals(dmg_water_percent=400)

        def worth(one, *extra):
            return wakfu_turn.cast_damage(one, sheet, 'distance', 'front',
                                          wakfu_turn.DEFAULT_CONDITIONS | set(extra))[0]

        def alone(position):
            plain = spell.rows[position]._replace(conditions=frozenset(), unless=frozenset())
            return worth(spell._replace(rows=(plain,)))

        self.assertGreater(alone(0), alone(1))
        self.assertAlmostEqual(alone(0), worth(spell))
        self.assertAlmostEqual(alone(1), worth(spell, 'portal'))

    def test_a_turn_that_stands_still_counts_the_row_that_needs_it(self):
        sheet = totals(ap=2, mp=0, wp=0, dmg_water_percent=400)
        turn = self.turn(role=WATER_AT_DISTANCE, level=245, sheet=sheet)
        self.assertTrue(RULES['caster_does_not_move'].value)
        self.assertEqual((9,), turn.casts)
        self.assertIn((9, 1, (wakfu_turn.STILL,),
                       "Si le Crâ n'a pas utilisé de PM pour se déplacer dans son tour"),
                      turn.counted)
        spell = {one.id: one for one in self.book.spells(self.spells.CLASS, 245)}[9]
        first = wakfu_turn.cast_damage(spell._replace(rows=spell.rows[:1]), sheet, 'distance',
                                       'front', wakfu_turn.DEFAULT_CONDITIONS)[0]
        self.assertGreater(turn.damage, first)

    def test_a_turn_lists_what_its_spells_do_to_damage_beyond_the_rows(self):
        turn = self.turn(role=WATER_AT_DISTANCE, level=245)
        self.assertIn(((9,), 'next cast', '50 % Dommages infligés par la prochaine Flèche'),
                      turn.unmodelled)
        self.assertIn(((9,), wakfu_turn.GAUGE, 'Précision'), turn.unmodelled)
        self.assertNotIn(10, {one for ids, _key, _detail in turn.unmodelled for one in ids})


class TheEncyclopediaTablesReadIntoTurnsTests(SimpleTestCase):
    """The real spell tables: every castable damage spell reads, and hits match the pages."""

    def setUp(self):
        from fashionistapulp.fashionista_config import get_items_db_path
        path = get_items_db_path('wakfu')
        if not os.path.exists(path):
            self.skipTest('no Wakfu database built; run update_data_wakfu.py')
        self.book_path = path
        self.book = wakfu_turn.SpellBook(path)
        self.addCleanup(self.book.close)
        if not self.book.conn.execute('SELECT COUNT(*) FROM spells').fetchone()[0]:
            self.skipTest('no Wakfu spells imported yet')

    def harvest_path(self):
        dump = os.path.join(REPO, 'itemscraper', 'transformed_wakfu.json')
        if not os.path.exists(dump):
            self.skipTest('no decoded Wakfu dump')
        with io.open(dump, encoding='utf-8') as handle:
            build = json.load(handle).get('version') or ''
        path = os.path.join(REPO, 'itemscraper', 'wakfu_raw', build, 'spells_fr.json')
        if not os.path.exists(path):
            self.skipTest('no French spell harvest for %s' % build)
        return path

    def harvest(self):
        with io.open(self.harvest_path(), encoding='utf-8') as handle:
            return json.load(handle)

    def test_every_castable_damage_spell_text_lines_up_with_its_rows(self):
        spells = [spell for class_id in CLASSES for spell in self.book.spells(class_id, 245)]
        self.assertGreater(len(spells), 250)
        self.assertEqual([], [spell.id for spell in spells if not spell.read])

    def test_at_mastery_zero_a_hit_is_the_encyclopedias_base_or_critical_damage(self):
        pages = self.harvest()
        compared = 0
        for class_id in CLASSES:
            for spell in self.book.spells(class_id, 245):
                page = pages[str(spell.id)]['levels']['245']
                normal = [value for _element, value in page['damage']]
                critical = [value for _element, value in page['critical_damage']]
                if len(critical) != len(normal):
                    continue
                plain = [position for position, is_percent in self.book.conn.execute(
                    "SELECT position, is_percent FROM spell_effects WHERE spell = ?"
                    " AND level = 245 AND kind = 'damage' ORDER BY position",
                    (spell.id,)) if not is_percent]
                for row in spell.rows:
                    at = plain.index(row.position)
                    with self.subTest(spell=spell.id, row=row.position):
                        solo = spell._replace(rows=(row._replace(conditions=frozenset(),
                                                                 unless=frozenset(),
                                                                 hits=1),))
                        for ferocity, wanted in ((-100, normal[at]), (100, critical[at])):
                            self.assertAlmostEqual(wanted, wakfu_turn.cast_damage(
                                solo, totals(ferocity=ferocity), 'distance', 'front',
                                wakfu_turn.DEFAULT_CONDITIONS)[0])
                    compared += 1
        self.assertGreater(compared, 300)

    def test_a_carried_copy_of_a_hit_is_never_a_second_hit(self):
        lucha = [spell for spell in self.book.spells(12, 245) if spell.id == 4715]
        if not lucha:
            self.skipTest("no Lucha L'ambrée in the tables")
        spell, = lucha
        sheet = totals(dmg_earth_percent=500)
        one, _parts, _cost = wakfu_turn.cast_damage(
            spell._replace(rows=spell.rows[:1]), sheet, 'melee', 'front',
            wakfu_turn.DEFAULT_CONDITIONS)
        for extra in ((), ('carrying',)):
            with self.subTest(conditions=extra):
                worth, _parts, change = wakfu_turn.cast_damage(
                    spell, sheet, 'melee', 'front',
                    wakfu_turn.DEFAULT_CONDITIONS | set(extra))
                self.assertAlmostEqual(one, worth)
        self.assertEqual(-1, change['ap'])

    def test_below_245_each_row_takes_the_harvests_critical_value(self):
        pages = self.harvest()
        level = 110
        book = wakfu_turn.SpellBook(self.book_path, critical=wakfu_turn.harvest_criticals(
            self.harvest_path(), [level]))
        self.addCleanup(book.close)
        compared = 0
        for class_id in CLASSES:
            for spell in book.spells(class_id, level):
                page = pages[str(spell.id)]['levels'][str(level)]
                critical = [value for _element, value in page['critical_damage']]
                if len(critical) != len(page['damage']):
                    continue
                plain = [position for position, is_percent in book.conn.execute(
                    "SELECT position, is_percent FROM spell_effects WHERE spell = ?"
                    " AND level = ? AND kind = 'damage' ORDER BY position",
                    (spell.id, level)) if not is_percent]
                for one in spell.rows:
                    with self.subTest(spell=spell.id, row=one.position):
                        self.assertEqual((critical[plain.index(one.position)], 'given'),
                                         (one.critical, one.critical_read))
                    compared += 1
        self.assertGreater(compared, 300)

    def test_a_spell_that_hits_harder_away_from_portals_lands_that_hit_by_default(self):
        pulsation = [spell for spell in self.book.spells(18, 245) if spell.id == 4692]
        if not pulsation:
            self.skipTest('no Pulsation in the tables')
        spell, = pulsation
        away, near = spell.rows
        self.assertGreater(away.base, near.base)
        sheet = totals(dmg_water_percent=500)
        for extra, landed in (((), away), (('portal',), near)):
            with self.subTest(conditions=extra):
                plain = landed._replace(conditions=frozenset(), unless=frozenset())
                self.assertAlmostEqual(
                    wakfu_turn.cast_damage(spell._replace(rows=(plain,)), sheet, 'distance',
                                           'front', wakfu_turn.DEFAULT_CONDITIONS)[0],
                    wakfu_turn.cast_damage(spell, sheet, 'distance', 'front',
                                           wakfu_turn.DEFAULT_CONDITIONS | set(extra))[0])


class TheWakfuBuildCommandPrintsTheTurnTests(SimpleTestCase):
    """wakfu_build --class-id: the best turn, its budget and what it leaves out."""

    def setUp(self):
        from fashionistapulp.fashionista_config import get_items_db_path
        if not os.path.exists(get_items_db_path('wakfu')):
            self.skipTest('no Wakfu database built; run update_data_wakfu.py')

    def test_the_class_option_prints_the_turn_and_what_it_does_not_count(self):
        out = io.StringIO()
        call_command('wakfu_build', '--level', '110', '--elements', 'fire', '--reach', 'melee',
                     '--rounds', '1', '--class-id', '8', stdout=out, no_color=True)
        lines = out.getvalue().splitlines()
        for start in ('  best turn of class 8: ', '  budget ', '  critical values: ',
                      '  not counted: ', '  not modelled: '):
            with self.subTest(line=start):
                self.assertTrue(any(line.startswith(start) for line in lines), out.getvalue())
        self.assertTrue(any(line.startswith('  not modelled: ')
                            and line.endswith('class gauge: Concentration') for line in lines),
                        out.getvalue())
