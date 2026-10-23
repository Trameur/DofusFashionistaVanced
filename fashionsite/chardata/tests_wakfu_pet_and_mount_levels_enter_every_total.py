import contextlib
import io
import json
import sqlite3
import tempfile
from pathlib import Path

from chardata.tests_wakfu_solve_obeys_every_rule_on_invented_items import (
    ALPHA, BREEDS, CATALOGUE, CRIT_ITEMS, HELM_A, HELMET, LEVEL, WP_SHOULDERS, InventedItemsCase,
    builder, item)

PET_TYPE, CHARM_TYPE, MOUNT_TYPE = 9101, 9102, 9103
TYPE_POSITION = {PET_TYPE: 'PET', CHARM_TYPE: 'PET', MOUNT_TYPE: 'MOUNT'}
TYPE_NAME = {PET_TYPE: 'Pet', CHARM_TYPE: 'Lucky Charm', MOUNT_TYPE: 'Mount'}

PET_A, PET_SMALL, PET_FEROX, PET_WISP, CHARM_A = 9201, 9202, 9203, 9204, 9205
MOUNT_A, MOUNT_B = 9301, 9302
GATE_MIN, GATE_MAX = 9401, 9402
PETS = (PET_A, PET_SMALL, PET_FEROX, PET_WISP, CHARM_A)
MOUNTS = (MOUNT_A, MOUNT_B)
VERSION = '1.0'


def leveled(key, base, per_level, **extra):
    return dict({'stat': key.upper(), 'value': base, 'params': [base, per_level]}, **extra)


def fixed(key, value):
    return {'stat': key.upper(), 'value': value, 'params': [value, 0.0]}


def companion(ident, type_id, name, lines, level=0):
    return {
        'id': ident, 'name': {'en': name, 'fr': name + ' fr'}, 'level': level,
        'type_id': type_id,
        'type_name': {'en': TYPE_NAME[type_id], 'fr': TYPE_NAME[type_id] + ' fr'},
        'positions': [TYPE_POSITION[type_id]], 'disables': [], 'rarity': 3, 'set_id': None,
        'gfx_id': 5000 + ident, 'two_handed': False, 'exclusive': None, 'lines': lines,
    }


# The cap of each leveled item is the emm of its row; eop is left at 50 so a
# cap read from the wrong field shows
PET_ROWS = [{'id': 1, 'item': PET_A, 'eoq': 50, 'eop': 50, 'emm': 50},
            {'id': 2, 'item': PET_SMALL, 'eoq': 50, 'eop': 50, 'emm': 25},
            {'id': 3, 'item': PET_FEROX, 'eoq': 50, 'eop': 50, 'emm': 50},
            {'id': 4, 'item': PET_WISP, 'eoq': 50, 'eop': 50, 'emm': 50}]
MOUNT_ROWS = [{'id': 1, 'item': MOUNT_A, 'eop': 50, 'emm': 50, 'eoq': 50},
              {'id': 2, 'item': MOUNT_B, 'eop': 50, 'emm': 50, 'eoq': 50}]

COMPANIONS = [
    companion(PET_A, PET_TYPE, 'Pet Alpha',
              [leveled('hp', 15.0, 1.5), leveled('init', 10.0, 1.0)]),
    companion(PET_SMALL, PET_TYPE, 'Pet Small', [leveled('hp', 10.0, 2.2)]),
    companion(PET_FEROX, PET_TYPE, 'Pet Ferox', [leveled('ferocity', 0.0, 0.1)]),
    companion(PET_WISP, PET_TYPE, 'Pet Wisp', [leveled('wp', 0.0, 0.2)]),
    companion(CHARM_A, CHARM_TYPE, 'Charm A', [fixed('hp', 77)], level=12),
    companion(MOUNT_A, MOUNT_TYPE, 'Mount A', [leveled('dmg_in_percent', 0.0, 0.8)], level=1),
    companion(MOUNT_B, MOUNT_TYPE, 'Mount B', [leveled('dmg_in_percent', 0.0, 0.4)], level=1),
]
GATES = [
    item(GATE_MIN, HELMET, 'Gate Min', criteria='GetCharac("FEROCITY") >= 6', hp=1000),
    item(GATE_MAX, HELMET, 'Gate Max', criteria='GetCharac("FEROCITY") <= 5', hp=1000),
]


def write_inputs(directory, items, pets, mounts):
    """The open data dump and the one decoded client of a build; their paths."""
    dump = directory / 'transformed_wakfu.json'
    dump.write_text(json.dumps({'version': VERSION, 'equipment': items, 'breeds': BREEDS,
                                'labels': {}, 'nations': {}}), encoding='utf-8')
    client = directory / 'client' / 'x'
    client.mkdir(parents=True, exist_ok=True)
    ids = [one['id'] for one in items]
    (client / 'tables.json').write_text(json.dumps({
        'game_version': '.'.join(VERSION.split('.')[:3]), 'item_ids': ids, 'effects': [],
        'groups': [], 'states': [], 'sets': [], 'abilities': [], 'ability_categories': [],
        'pets': list(pets), 'mounts': list(mounts)}), encoding='utf-8')
    return dump, directory / 'client'


def run_builder(directory, db, items, pets=PET_ROWS, mounts=MOUNT_ROWS):
    dump, client = write_inputs(directory, items, pets, mounts)
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        builder.main(['--dump', str(dump), '--db', str(db), '--out', str(directory / 'raw'),
                      '--client', str(client)])
    return out.getvalue()


class ACompanionCase(InventedItemsCase):
    @classmethod
    def catalogue(cls):
        return CATALOGUE + COMPANIONS + GATES

    @classmethod
    def build_db(cls, directory, items):
        run_builder(directory, cls.db, items)

    def build(self, weights=None, levels=None, forbidden=(), **options):
        from fashionistapulp.wakfu_model import WakfuBuild
        return WakfuBuild(self.structure, LEVEL, weights or {'hp': 1}, forbidden,
                          levels=levels, **options)

    def levels(self, **given):
        from fashionistapulp import wakfu_companions
        return wakfu_companions.Levels(**given)

    def keys(self, lines):
        return {self.structure.get_stat_by_id(stat_id).key: value for stat_id, value in lines}

    def totals(self, worn, **given):
        return self.build(levels=self.levels(**given)).totals(worn)

    def except_for(self, *kept):
        """Every pet and charm this class adds but those kept."""
        return set(PETS) - set(kept)


class APetOrMountLineCountsAtTheLevelItIsWornAtTests(ACompanionCase):
    def test_a_pet_line_counts_at_the_level_given(self):
        from fashionistapulp import wakfu_companions
        pet = self.by_id(PET_A)
        for level, hp, init in ((10, 30, 20), (50, 90, 60)):
            with self.subTest(level=level):
                totals = self.totals({'PET': pet}, pet=level)
                self.assertEqual((hp, init), (totals['hp'], totals['init']))
                self.assertEqual(
                    {'hp': hp, 'init': init},
                    self.keys(wakfu_companions.lines_at(pet, level)))
        self.assertEqual(90, self.totals({'PET': pet})['hp'], 'no level means the cap')

    def test_a_slot_level_above_a_cap_is_read_at_the_cap(self):
        from fashionistapulp import wakfu_companions
        small = self.by_id(PET_SMALL)
        self.assertEqual(25, small.level_cap)
        self.assertEqual(25, wakfu_companions.level_of(self.levels(pet=50), small))
        self.assertEqual(65, self.totals({'PET': small}, pet=50)['hp'])
        self.assertEqual(self.totals({'PET': small}, pet=25), self.totals({'PET': small}, pet=50))

    def test_the_refusal_names_whether_the_level_is_not_whole_or_out_of_range(self):
        from fashionistapulp import wakfu_companions
        read = wakfu_companions.read_levels
        for bad, text in ((51, 'is outside 0 to 50'), (-1, 'is outside 0 to 50'),
                          (2.5, 'is not a whole number'), (True, 'is not a whole number')):
            with self.subTest(slot_level=bad):
                with self.assertRaisesRegex(ValueError, text):
                    read(self.structure, pet=bad)

    def test_a_level_out_of_range_or_not_whole_is_refused(self):
        from fashionistapulp import wakfu_companions
        read = wakfu_companions.read_levels
        for bad in (-1, 51, 2.5, True, '10'):
            with self.subTest(slot_level=bad):
                with self.assertRaises(ValueError):
                    read(self.structure, pet=bad)
                with self.assertRaises(ValueError):
                    read(self.structure, mount=bad)
        for bad in (-1, 26, 2.5, True):
            with self.subTest(item_level=bad):
                with self.assertRaises(ValueError) as caught:
                    read(self.structure, items={PET_SMALL: bad})
                self.assertIn('Pet Small', str(caught.exception))
        with self.assertRaises(ValueError) as caught:
            read(self.structure, items={PET_SMALL: 26})
        self.assertIn('26', str(caught.exception))
        self.assertIn('25', str(caught.exception))
        self.assertEqual(wakfu_companions.Levels(0, 50, {PET_SMALL: 25}),
                         read(self.structure, 0, 50, {PET_SMALL: 25}))

    def test_a_level_for_an_item_that_does_not_level_is_refused(self):
        from fashionistapulp import wakfu_companions, wakfu_legality
        with self.assertRaises(ValueError) as caught:
            wakfu_companions.read_levels(self.structure, items={HELM_A: 3})
        self.assertIn('Helm A', str(caught.exception))
        with self.assertRaises(ValueError):
            wakfu_companions.read_levels(self.structure, items={CHARM_A: 3})
        helm = self.by_id(HELM_A)
        found = wakfu_legality.violations(self.structure, LEVEL, {'HEAD': helm},
                                          levels={HELM_A: 3})
        self.assertEqual([wakfu_legality.COMPANION_LEVEL], [rule for rule, _text in found])
        self.assertIn('Helm A', found[0][1])
        self.assertEqual([], wakfu_legality.violations(
            self.structure, LEVEL, {'HEAD': helm}, levels={PET_A: 3}), 'a level for an item '
                                                                     'not worn is ignored')

    def test_a_level_out_of_range_for_a_worn_pet_is_a_violation_read_at_the_cap(self):
        from fashionistapulp import wakfu_legality
        worn = {'SHOULDERS': self.by_id(WP_SHOULDERS), 'PET': self.by_id(PET_WISP)}
        for bad in (-1, 51, 2.5, True):
            with self.subTest(level=bad):
                found = wakfu_legality.violations(
                    self.structure, LEVEL, worn, class_id=ALPHA, levels={PET_WISP: bad})
                rules = [rule for rule, _text in found]
                self.assertIn(wakfu_legality.COMPANION_LEVEL, rules)
                self.assertIn(wakfu_legality.CAP, rules, 'wp 6 + 14 + 10 at the cap of 50')
                text = dict(found)[wakfu_legality.COMPANION_LEVEL]
                for part in ('Pet Wisp', repr(bad), '50'):
                    self.assertIn(part, text)

    def test_the_solver_wears_one_item_in_pet_and_one_in_mount(self):
        weights = {'hp': 1, 'dmg_in_percent': 1}
        build = self.build(weights)
        worn = build.build().solve()
        chosen = [name.split('_', 2)[2] for name, value in build.problem.get_result().items()
                  if (value or 0) > 0.5]
        self.assertEqual(1, chosen.count('PET'), chosen)
        self.assertEqual(1, chosen.count('MOUNT'), chosen)
        self.assertIn(worn['PET'].type, (PET_TYPE, CHARM_TYPE))
        self.assertEqual(MOUNT_TYPE, worn['MOUNT'].type)

    def test_a_pet_wp_line_counts_toward_the_wp_cap(self):
        from fashionistapulp import wakfu_legality
        wisp, shoulders = self.by_id(PET_WISP), self.by_id(WP_SHOULDERS)
        worn_pet = {'SHOULDERS': shoulders, 'PET': wisp}

        def rules(level):
            return {rule for rule, _text in wakfu_legality.violations(
                self.structure, LEVEL, worn_pet, class_id=ALPHA, levels={PET_WISP: level})}

        self.assertNotIn(wakfu_legality.CAP, rules(0), 'wp 6 + 14 + 0')
        self.assertIn(wakfu_legality.CAP, rules(5), 'wp 6 + 14 + 1 is 21')
        self.assertIn(wakfu_legality.CAP, rules(50))
        build = self.build({'wp': 1}, self.levels(pet=10), self.except_for(PET_WISP),
                           class_id=ALPHA)
        worn = build.build().solve()
        self.assertEqual(PET_WISP, worn['PET'].id)
        self.assertEqual(8, build.totals(worn)['wp'], 'base 6 plus the 2 the wisp gives at 10')

    def best_helms(self, gate, level):
        forbidden = self.except_for(PET_FEROX) | set(CRIT_ITEMS) | {
            GATE_MAX if gate == GATE_MIN else GATE_MIN}
        build = self.build({'hp': 1}, self.levels(pet=level), forbidden, class_id=ALPHA)
        worn = build.build().solve()
        return build, worn

    def test_a_pet_line_opens_a_minimum_gate_only_at_a_level_that_reaches_it(self):
        from fashionistapulp import wakfu_companions
        ferox = self.by_id(PET_FEROX)
        self.assertEqual({'ferocity': 2}, self.keys(wakfu_companions.lines_at(ferox, 29)))
        self.assertEqual({'ferocity': 3}, self.keys(wakfu_companions.lines_at(ferox, 30)))
        _build, short = self.best_helms(GATE_MIN, 29)
        self.assertNotEqual(GATE_MIN, short['HEAD'].id, 'ferocity 3 + 2 is under 6')
        build, reached = self.best_helms(GATE_MIN, 30)
        self.assertEqual(GATE_MIN, reached['HEAD'].id)
        self.assertEqual(3, build.totals(reached)['ferocity'], 'the pet; the class adds 3')

    def test_a_pet_line_closes_a_maximum_gate_at_a_level_that_passes_it(self):
        build, within = self.best_helms(GATE_MAX, 29)
        self.assertEqual(GATE_MAX, within['HEAD'].id)
        self.assertEqual(2, build.totals(within)['ferocity'], 'the pet; the class adds 3')
        _build, past = self.best_helms(GATE_MAX, 30)
        self.assertNotEqual(GATE_MAX, past['HEAD'].id, 'ferocity 3 + 3 is over 5')

    def test_legality_agrees_with_the_model_at_levels_0_1_25_and_50(self):
        from fashionistapulp import wakfu_criteria, wakfu_legality
        pet, mount = self.by_id(PET_A), self.by_id(MOUNT_A)
        worn = {'PET': pet, 'MOUNT': mount}
        base = wakfu_criteria.base_values(self.structure, None)
        for level in (0, 1, 25, 50):
            totals = self.totals(worn, pet=level, mount=level)
            given = {PET_A: level, MOUNT_A: level}
            for key in ('hp', 'init', 'dmg_in_percent'):
                with self.subTest(level=level, key=key):
                    total = totals[key] + base.get(key, (0, 0))[0]
                    self.assertEqual([], wakfu_legality.violations(
                        self.structure, LEVEL, worn, minimums={key: total}, levels=given))
                    short = wakfu_legality.violations(
                        self.structure, LEVEL, worn, minimums={key: total + 1}, levels=given)
                    self.assertEqual([wakfu_legality.MINIMUM], [rule for rule, _t in short])

    def test_the_set_reports_the_level_of_its_pet_and_mount(self):
        from fashionistapulp import wakfu_solve
        forbidden = {CHARM_A}
        build = self.build({'hp': 1, 'dmg_in_percent': 1}, self.levels(pet=10, mount=20),
                           forbidden)
        worn = build.build().solve()
        self.assertEqual({worn['PET'].id: 10, worn['MOUNT'].id: 20}, worn.levels)
        result = wakfu_solve.solve_weights(
            self.structure, level=LEVEL, weights={'hp': 1, 'dmg_in_percent': 1},
            forbidden=forbidden, aptitudes=None, seconds=30, pet_level=10, mount_level=20)
        self.assertEqual({result.worn['PET'].id: 10, result.worn['MOUNT'].id: 20},
                         dict(result.levels))
        self.assertEqual({}, dict(wakfu_solve.WakfuResult(*[None] * 16).levels))

    def test_a_class_solve_reports_the_levels_it_was_given_and_refuses_one_it_cannot_wear(self):
        from fashionistapulp import wakfu_solve
        result = wakfu_solve.solve_build(
            self.structure, level=LEVEL, elements=('fire',), reach='melee', seconds=60,
            aptitudes=None, forbidden=[CHARM_A], pet_level=10, mount_level=20)
        self.assertEqual({result.worn['PET'].id: 10, result.worn['MOUNT'].id: 20},
                         dict(result.levels))
        with self.assertRaises(ValueError):
            wakfu_solve.solve_build(self.structure, level=LEVEL, elements=('fire',),
                                    reach='melee', aptitudes=None, pet_level=51)
        with self.assertRaises(ValueError):
            wakfu_solve.solve_weights(self.structure, level=LEVEL, weights={'hp': 1},
                                      aptitudes=None, item_levels={PET_SMALL: 26})

    def test_the_command_reads_item_levels_as_whole_id_level_pairs(self):
        from chardata.management.commands.wakfu_build import Command
        from django.core.management.base import CommandError
        self.assertEqual({PET_A: 7, MOUNT_A: 0},
                         Command.read_item_levels('%d=7, %d=0' % (PET_A, MOUNT_A)))
        self.assertEqual({}, Command.read_item_levels(''))
        for bad in ('%d' % PET_A, '%d=' % PET_A, '=5', '%d=2.5' % PET_A, 'a=1',
                    '%d=1,%d=2' % (PET_A, PET_A)):
            with self.subTest(text=bad):
                with self.assertRaises(CommandError):
                    Command.read_item_levels(bad)

    def test_a_default_solve_reports_every_worn_pet_and_mount_at_its_cap(self):
        build = self.build({'hp': 1, 'dmg_in_percent': 1}, forbidden={CHARM_A})
        worn = build.build().solve()
        for position in ('PET', 'MOUNT'):
            self.assertEqual(worn[position].level_cap, worn.levels[worn[position].id])

    def test_a_charm_is_worn_without_a_level(self):
        build = self.build({'hp': 1}, self.levels(pet=0), self.except_for(CHARM_A))
        worn = build.build().solve()
        self.assertEqual(CHARM_A, worn['PET'].id)
        self.assertNotIn(CHARM_A, worn.levels)
        self.assertEqual(77, build.totals({'PET': worn['PET']})['hp'])


class ALeveledLineTheBuilderCannotReadTests(ACompanionCase):
    def build_in_a_new_folder(self, items, pets=PET_ROWS, mounts=MOUNT_ROWS):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            output = run_builder(directory, directory / 'items_wakfu.db', items, pets, mounts)
            conn = sqlite3.connect(directory / 'items_wakfu.db')
            try:
                ids = {one for (one,) in conn.execute('SELECT id FROM items')}
            finally:
                conn.close()
        return output, ids

    def test_a_leveled_line_with_elements_or_a_negative_slope_stops_the_build(self):
        spread = companion(PET_A, PET_TYPE, 'Spread', [leveled('hp', 10.0, 1.0, elements=2)])
        falling = companion(PET_A, PET_TYPE, 'Falling', [leveled('hp', 10.0, -1.0)])
        for bad, message in ((spread, 'spreads over elements'),
                             (falling, 'no non-negative slope')):
            with self.subTest(message=message):
                with self.assertRaisesRegex(ValueError, message):
                    self.build_in_a_new_folder([bad], pets=PET_ROWS[:1], mounts=[])

    def test_a_sloped_pet_without_a_cap_is_left_out_and_counted(self):
        orphan = companion(9206, PET_TYPE, 'Orphan', [leveled('hp', 10.0, 1.0)])
        fixed_pet = companion(9207, PET_TYPE, 'Steady', [fixed('hp', 5)])
        output, ids = self.build_in_a_new_folder(
            [orphan, fixed_pet,
             companion(PET_A, PET_TYPE, 'Pet Alpha', [leveled('hp', 1.0, 1.0)])],
            pets=PET_ROWS[:1], mounts=[])
        self.assertNotIn(9206, ids)
        self.assertEqual({9207, PET_A}, ids)
        self.assertIn('leveled item without a cap', output)
        self.assertIn('leveled item 9206 Orphan has no cap in the client tables, left out', output)

    def test_a_removed_pet_keeps_its_cap_and_lines(self):
        pet = companion(PET_A, PET_TYPE, 'Pet Alpha',
                        [leveled('hp', 15.0, 1.5), leveled('init', 10.0, 1.0)])
        other = companion(PET_SMALL, PET_TYPE, 'Pet Small', [leveled('hp', 10.0, 2.2)])
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            db = directory / 'items_wakfu.db'
            run_builder(directory, db, [pet, other], PET_ROWS[:2], [])
            run_builder(directory, db, [other], PET_ROWS[1:2], [])
            conn = sqlite3.connect(db)
            try:
                removed = conn.execute('SELECT removed FROM items WHERE id = ?',
                                       (PET_A,)).fetchone()
                cap = conn.execute('SELECT slot, cap FROM item_level_caps WHERE item = ?',
                                   (PET_A,)).fetchone()
                lines = conn.execute('SELECT base, per_level FROM item_level_lines '
                                     'WHERE item = ? ORDER BY line', (PET_A,)).fetchall()
            finally:
                conn.close()
        self.assertTrue(removed[0])
        self.assertEqual(('PET', 50), cap)
        self.assertEqual([(15.0, 1.5), (10.0, 1.0)], lines)
