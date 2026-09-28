import io
import os
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase

from chardata.tests_wakfu_turn_counts_rows_under_the_roles_conditions import (
    InventedSpells, totals)
from fashionistapulp import wakfu_turn, wakfu_value
from fashionistapulp.wakfu_value_rules import RULES

FIRE_AT_DISTANCE = wakfu_value.DamageDealer(('fire',), 'distance')


class ClassSpells(InventedSpells):
    """The invented class plus two passives, which cost nothing and deal no damage."""

    TEXT = {
        **InventedSpells.TEXT,
        20: ("Berserk : - Ajoute la Maîtrise mêlée à l'Esquive Sinon : - Ajoute la Maîtrise "
             'mêlée au Tacle', ''),
        21: ('Tous les 50 Point Faible : - 10 % Dommages supplémentaires', ''),
    }
    SPELLS = {
        **InventedSpells.SPELLS,
        20: (None, None, None, None, None, {245: []}),
        21: (None, None, None, None, None, {245: []}),
    }


def moving(share):
    return wakfu_value.DamageDealer(('water',), 'distance', movement=share)


class TheRoleSaysHowMuchOfItsMpItSpendsMovingTests(SimpleTestCase):
    def setUp(self):
        self.spells = InventedSpells()
        self.addCleanup(self.spells.remove)
        self.book = self.spells.book()
        self.addCleanup(self.book.close)

    def turn(self, role, level=245, **stats):
        return wakfu_turn.best_turn(self.book.spells(self.spells.CLASS, level), role,
                                    totals(**stats))

    def test_the_share_moving_is_rounded_up_to_whole_mp(self):
        self.assertEqual((4, 0), wakfu_turn.movement_split(moving(None), 4))
        self.assertEqual((4, 0), wakfu_turn.movement_split(moving(0), 4))
        self.assertEqual((2, 3), wakfu_turn.movement_split(moving(0.5), 5))
        self.assertEqual((2, 1), wakfu_turn.movement_split(moving(0.1), 3))
        self.assertEqual((0, 6), wakfu_turn.movement_split(moving(1), 6))

    def test_a_share_outside_zero_to_one_is_refused(self):
        for share in (-0.1, 1.5):
            with self.subTest(share=share):
                with self.assertRaises(ValueError):
                    moving(share)

    def test_the_mp_spent_moving_leave_the_spell_budget(self):
        casts = {share: self.turn(wakfu_value.DamageDealer(('fire',), 'distance',
                                                           movement=share),
                                  level=200, ap=0, mp=4, dmg_fire_percent=400).casts
                 for share in (None, 0.5, 1)}
        self.assertEqual({None: (7, 7), 0.5: (7,), 1: ()}, casts)

    def test_the_turn_names_the_mp_on_spells_and_the_mp_moving(self):
        turn = self.turn(moving(0.5), ap=2, mp=5, dmg_water_percent=400)
        self.assertEqual((2, 3), (turn.settings['mp'], turn.settings['mp_moving']))

    def test_a_row_for_a_caster_who_has_not_moved_counts_only_when_no_mp_moves(self):
        row = (9, 1, (wakfu_turn.STILL,),
               "Si le Crâ n'a pas utilisé de PM pour se déplacer dans son tour")
        still = self.turn(moving(None), ap=2, mp=4, dmg_water_percent=400)
        self.assertIn(row, still.counted)
        moved = self.turn(moving(0.25), ap=2, mp=4, dmg_water_percent=400)
        self.assertEqual((9,), moved.casts)
        self.assertIn(row, moved.dropped)
        self.assertLess(moved.damage, still.damage)
        no_mp = self.turn(moving(0.25), ap=2, mp=0, dmg_water_percent=400)
        self.assertIn(row, no_mp.counted)

    def test_with_the_rule_off_a_role_of_no_stated_share_keeps_its_mp_but_not_the_still_rows(self):
        row = (9, 1, (wakfu_turn.STILL,),
               "Si le Crâ n'a pas utilisé de PM pour se déplacer dans son tour")
        off = RULES['caster_does_not_move']._replace(value=False)
        with mock.patch.dict(RULES, {'caster_does_not_move': off}):
            fire = self.turn(FIRE_AT_DISTANCE, level=200, ap=0, mp=4, dmg_fire_percent=400)
            unstated = self.turn(moving(None), ap=2, mp=4, dmg_water_percent=400)
            stated = self.turn(moving(0), ap=2, mp=4, dmg_water_percent=400)
        self.assertEqual((7, 7), fire.casts)
        self.assertEqual((4, 0), (fire.settings['mp'], fire.settings['mp_moving']))
        self.assertIn(row, unstated.dropped)
        self.assertIn(row, stated.counted)


class TheClassMechanicsAreListedPerClassTests(SimpleTestCase):
    def setUp(self):
        self.spells = ClassSpells()
        self.addCleanup(self.spells.remove)
        self.book = self.spells.book()
        self.addCleanup(self.book.close)

    def test_the_gauges_and_states_of_every_class_text_are_listed_passives_included(self):
        self.assertEqual(
            ((wakfu_turn.GAUGE, 'Point Faible', (21,)),
             (wakfu_turn.GAUGE, 'Précision', (9,)),
             (wakfu_turn.STATE, 'Berserk', (20,))),
            self.book.class_mechanics(self.spells.CLASS))
        self.assertEqual('Sort 20', self.book.names(self.spells.CLASS)[20])

    def test_a_turn_lists_the_class_mechanics_even_when_no_usable_spell_names_them(self):
        spells = self.book.spells(self.spells.CLASS, 245)
        mechanics = self.book.class_mechanics(self.spells.CLASS)
        turn = wakfu_turn.best_turn(spells, FIRE_AT_DISTANCE, totals(ap=11, mp=4),
                                    class_mechanics=mechanics)
        self.assertNotIn(9, turn.usable)
        for key, name, ids in mechanics:
            with self.subTest(name=name):
                self.assertIn((ids, key, name), turn.unmodelled)
        plain = wakfu_turn.best_turn(spells, FIRE_AT_DISTANCE, totals(ap=11, mp=4))
        self.assertEqual([], [entry for entry in plain.unmodelled
                              if entry[1] in (wakfu_turn.GAUGE, wakfu_turn.STATE)])
        self.assertEqual('class state', wakfu_turn.describe(wakfu_turn.STATE))

    def test_the_command_prints_the_turn_budget_and_class_mechanics(self):
        from chardata.management.commands.wakfu_build import Command

        out = io.StringIO()
        command = Command(stdout=out, no_color=True)
        with mock.patch('fashionistapulp.fashionista_config.get_items_db_path',
                        return_value=self.spells.path):
            command.print_turn(moving(0.5), 245, self.spells.CLASS,
                               totals(ap=4, mp=5, wp=6, dmg_water_percent=400))
        lines = out.getvalue().splitlines()
        self.assertIn('  best turn of class 99: ', lines[1])
        self.assertEqual('  budget 4 AP, 1 WP, 2 MP on spells and 3 moving, a spell at most '
                         '3 times', lines[2])
        self.assertEqual('  critical values: the encyclopedia text at level 245', lines[3])
        for line in ('  not modelled: Sort 21, class gauge: Point Faible',
                     '  not modelled: Sort 9, class gauge: Précision',
                     '  not modelled: Sort 20, class state: Berserk'):
            with self.subTest(line=line):
                self.assertIn(line, lines)
        self.assertTrue(any(line.startswith('  not counted: Sort 9 row 1, the caster has '
                                            'not moved this turn') for line in lines),
                        out.getvalue())


class TheRealTablesListThePlansClassMechanicsTests(SimpleTestCase):
    def setUp(self):
        from fashionistapulp.fashionista_config import get_items_db_path
        path = get_items_db_path('wakfu')
        if not os.path.exists(path):
            self.skipTest('no Wakfu database built; run update_data_wakfu.py')
        self.book = wakfu_turn.SpellBook(path)
        self.addCleanup(self.book.close)
        if not self.book.conn.execute('SELECT COUNT(*) FROM spells').fetchone()[0]:
            self.skipTest('no Wakfu spells imported yet')

    def test_every_class_but_osamodas_and_zobal_lists_the_gauges_and_states_of_its_texts(self):
        gauge, state = wakfu_turn.GAUGE, wakfu_turn.STATE
        wanted = {
            1: {(state, 'Bouclier')},
            2: set(),
            3: {(state, 'Trésors')},
            4: {(gauge, 'Point Faible'), (state, 'Hémorragie')},
            5: {(gauge, 'Charge de Rouage'), (state, 'heure courante')},
            6: {(gauge, 'Veine')},
            7: {(gauge, 'Propagateur')},
            8: {(gauge, 'Concentration'), (state, 'Courroux'), (state, 'Égaré')},
            9: {(gauge, 'Précision')},
            10: {(gauge, 'Engrainé')},
            11: {(gauge, 'Retour de flamme'), (state, 'Berserk')},
            12: {(state, 'Imbibé'), (state, 'Ivre')},
            13: {(gauge, 'Pulsar'), (state, 'Dynamite'), (state, 'Retour de dague')},
            14: set(),
            15: {(gauge, 'Traqueur'), (state, 'Proie')},
            16: {(gauge, 'Surpression'), (gauge, 'PS')},
            18: {(state, 'Don Céleste')},
            19: {(gauge, 'BQ'), (gauge, 'runes'), (state, 'Cœur de Lumière')},
        }
        classes = {class_id for class_id, in self.book.conn.execute(
            'SELECT DISTINCT class FROM spells')}
        self.assertEqual(set(wanted), classes)
        for class_id, mechanics in wanted.items():
            with self.subTest(class_id=class_id):
                self.assertEqual(mechanics, {(key, name) for key, name, _ids in
                                             self.book.class_mechanics(class_id)})

    def test_berserk_is_read_from_the_sacrieur_passives_too(self):
        berserk, = [ids for key, name, ids in self.book.class_mechanics(11)
                    if name == 'Berserk']
        costs = dict((spell_id, (ap, mp, wp)) for spell_id, ap, mp, wp in self.book.conn.execute(
            'SELECT id, ap, mp, wp FROM spells WHERE class = 11'))
        self.assertTrue(any(not any(costs[spell_id]) for spell_id in berserk))

    def test_the_command_prints_sacrieur_berserk_as_not_modelled(self):
        out = io.StringIO()
        call_command('wakfu_build', '--level', '110', '--elements', 'fire', '--reach', 'melee',
                     '--rounds', '1', '--class-id', '11', '--movement', '0.5', stdout=out,
                     no_color=True)
        lines = out.getvalue().splitlines()
        self.assertTrue(any(line.startswith('  not modelled: ')
                            and line.endswith('class state: Berserk') for line in lines),
                        out.getvalue())
        budget, = [line for line in lines if line.startswith('  budget ')]
        self.assertNotIn(' and 0 moving', budget)
