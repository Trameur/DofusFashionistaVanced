import collections
import json
import os
import sqlite3

from django.test import SimpleTestCase

from fashionistapulp import wakfu_recipient as recipient

ARMOR = 1013
GROUP = 330
STEAL = 865
BYTES = ('trigger_side', 'trigger_target', 'trigger_caster')

CASTER_ONLY = 2
TEAM_WITH_CASTER = 4
OTHER_TEAM = 8
TEAM_WITHOUT_CASTER = 128

#: Armor rows of the class spells of the item database, without and with the stored trigger bytes
DATABASE_ARMOR_ROWS = 249
UNITS_WITHOUT_BYTES = {'caster': 82, 'team': 100, 'own summon': 10, 'targeted': 3, 'unknown': 54}
OUTPUTS_WITHOUT_BYTES = {'allies': 85, 'caster': 82, 'allies+caster': 9, 'allies+enemies': 3,
                         'allies+possibly_caster': 16, 'unknown': 54}
UNITS_WITH_BYTES = {'caster': 123, 'team': 102, 'own summon': 10, 'targeted': 9, 'unknown': 5}
OUTPUTS_WITH_BYTES = {'allies': 85, 'caster': 123, 'allies+caster': 9, 'allies+enemies': 9,
                      'allies+possibly_caster': 18, 'unknown': 5}


def params(*values):
    """Group parameters, one value per slot, each as the (base, per level) pair the table stores."""
    out = []
    for value in values:
        out += [value, 0]
    return out


def effect(effect_id, action=ARMOR, mask=0, shape=1, size=(), values=(), triggers=None, bytes_=None):
    return dict(id=effect_id, action=action, mask=mask, shape=shape, size=list(size),
                params=params(*values), triggers=triggers, bytes=bytes_)


def listener_lists(index=0):
    lists = [[] for _ in range(7)]
    lists[index] = [1]
    return lists


def database(effects, groups=(), roots=(), range_min=1, range_max=4, with_bytes=False, passive=False):
    """A table of one spell, number 1, with the given effects, groups ({group: [children]}) and roots."""
    conn = sqlite3.connect(':memory:')
    extra = ', trigger_side integer, trigger_target integer, trigger_caster integer' if with_bytes else ''
    conn.execute('create table effects (id integer primary key, action integer, area_shape integer, '
                 'area_size text, params text, target_mask integer, triggers text%s)' % extra)
    conn.execute('create table effect_groups (group_id integer, position integer, effect integer)')
    conn.execute('create table client_spell_effects (spell integer, position integer, effect integer)')
    conn.execute('create table client_spells (id integer, breed integer, ap integer, mp integer, '
                 'wp integer, range_min integer, range_max integer)')
    for x in effects:
        row = [x['id'], x['action'], x['shape'], json.dumps(x['size']), json.dumps(x['params']),
               x['mask'], json.dumps(x['triggers']) if x['triggers'] else None]
        if with_bytes:
            row += list(x['bytes'] or (0, 0, 0))
        conn.execute('insert into effects values (%s)' % ', '.join('?' * len(row)), row)
    for group, kids in dict(groups).items():
        for position, kid in enumerate(kids):
            conn.execute('insert into effect_groups values (?, ?, ?)', (group, position, kid))
    for position, root in enumerate(roots):
        conn.execute('insert into client_spell_effects values (1, ?, ?)', (position, root))
    conn.execute('insert into client_spells values (1, 1, ?, 0, 0, ?, ?)',
                 (0 if passive else 3, range_min, range_max))
    return conn


class FilterAndGroupChainTests(SimpleTestCase):
    def test_a_caster_only_filter_lands_on_the_caster_when_a_group_hands_the_target(self):
        conn = database([effect(1, GROUP), effect(2, mask=CASTER_ONLY)], {1: [2]}, [1])
        found = recipient.recipients_of(conn, 1)
        self.assertEqual(recipient.TARGETED, found[1].unit)
        self.assertEqual(recipient.CASTER, found[2].unit)
        self.assertEqual(frozenset({'caster'}), found[2].outputs)
        self.assertIsNone(found[2].reason)

    def test_a_caster_only_filter_handed_a_team_unit_takes_that_unit(self):
        for group_mask, unit in ((TEAM_WITH_CASTER, recipient.TEAM),
                                 (TEAM_WITHOUT_CASTER, recipient.ALLY)):
            with self.subTest(unit=unit):
                conn = database([effect(1, GROUP, mask=group_mask), effect(2, mask=CASTER_ONLY)],
                                {1: [2]}, [1])
                found = recipient.recipients_of(conn, 1)
                self.assertEqual(unit, found[2].unit)
                self.assertEqual(frozenset({'allies'}), found[2].outputs)

    def test_a_filter_of_zero_takes_the_unit_its_group_hands_down(self):
        conn = database([effect(1, GROUP, mask=TEAM_WITHOUT_CASTER), effect(2, mask=0)], {1: [2]}, [1])
        found = recipient.recipients_of(conn, 1)
        self.assertEqual(recipient.ALLY, found[1].unit)
        self.assertEqual(recipient.ALLY, found[2].unit)

    def test_a_team_filter_reaches_the_caster_when_its_area_holds_a_cell_the_caster_can_cast_from(self):
        conn = database([effect(1, mask=TEAM_WITH_CASTER, shape=2, size=[2])], roots=[1],
                        range_min=1, range_max=4)
        found = recipient.recipients_of(conn, 1)[1]
        self.assertEqual(recipient.TEAM, found.unit)
        self.assertEqual(frozenset({'allies', 'caster'}), found.outputs)

    def test_a_team_filter_on_a_single_cell_reaches_the_caster_only_with_a_range_min_of_zero(self):
        for range_min, outputs in ((0, {'allies', 'caster'}), (1, {'allies'})):
            with self.subTest(range_min=range_min):
                conn = database([effect(1, mask=TEAM_WITH_CASTER)], roots=[1], range_min=range_min,
                                range_max=3)
                self.assertEqual(frozenset(outputs), recipient.recipients_of(conn, 1)[1].outputs)

    def test_an_area_turned_behind_the_target_reaches_the_caster_only_possibly(self):
        conn = database([effect(1, mask=TEAM_WITH_CASTER, shape=8, size=[-2, 0])], roots=[1],
                        range_min=1, range_max=4)
        self.assertEqual(frozenset({'allies', 'possibly_caster'}),
                         recipient.recipients_of(conn, 1)[1].outputs)

    def test_an_area_turned_in_front_of_the_target_never_reaches_the_caster(self):
        conn = database([effect(1, mask=TEAM_WITH_CASTER, shape=8, size=[2, 0])], roots=[1],
                        range_min=1, range_max=4)
        self.assertEqual(frozenset({'allies'}), recipient.recipients_of(conn, 1)[1].outputs)

    def test_a_team_filter_without_the_caster_never_reaches_the_caster(self):
        conn = database([effect(1, mask=TEAM_WITHOUT_CASTER, shape=2, size=[3])], roots=[1],
                        range_min=0, range_max=4)
        found = recipient.recipients_of(conn, 1)[1]
        self.assertEqual(recipient.ALLY, found.unit)
        self.assertEqual(frozenset({'allies'}), found.outputs)

    def test_a_fired_listener_lands_where_its_bytes_point_and_ignores_its_filter(self):
        listener = effect(1, mask=OTHER_TEAM, triggers=listener_lists(), bytes_=(1, 3, 1))
        conn = database([listener], roots=[1], with_bytes=True)
        found = recipient.recipients_of(conn, 1)[1]
        self.assertEqual(recipient.CASTER, found.unit)
        self.assertEqual(frozenset({'caster'}), found.outputs)
        plain = database([effect(1, mask=OTHER_TEAM)], roots=[1], with_bytes=True)
        self.assertEqual(recipient.ENEMY, recipient.recipients_of(plain, 1)[1].unit)

    def test_a_listener_without_its_bytes_leaves_its_rows_unknown(self):
        listener = effect(1, GROUP, triggers=listener_lists(), bytes_=(0, 0, 0))
        for with_bytes in (False, True):
            with self.subTest(with_bytes=with_bytes):
                conn = database([listener, effect(2, mask=CASTER_ONLY)], {1: [2]}, [1],
                                with_bytes=with_bytes)
                found = recipient.recipients_of(conn, 1)
                for effect_id in (1, 2):
                    self.assertEqual(recipient.UNKNOWN, found[effect_id].unit)
                    self.assertEqual(frozenset({'unknown'}), found[effect_id].outputs)
                    self.assertEqual(recipient.REASON_BYTES, found[effect_id].reason)
                    self.assertEqual('a listener without its trigger bytes', found[effect_id].reason)

    def test_a_row_without_a_target_filter_column_is_unknown_with_its_reason(self):
        conn = sqlite3.connect(':memory:')
        conn.execute('create table effects (id integer primary key, action integer, area_shape integer, '
                     'area_size text, params text)')
        conn.execute('create table effect_groups (group_id integer, position integer, effect integer)')
        conn.execute('create table client_spell_effects (spell integer, position integer, effect integer)')
        conn.execute('create table client_spells (id integer, breed integer, ap integer, mp integer, '
                     'wp integer, range_min integer, range_max integer)')
        conn.execute("insert into effects values (1, %d, 1, '[]', '[]')" % ARMOR)
        conn.execute('insert into client_spell_effects values (1, 0, 1)')
        conn.execute('insert into client_spells values (1, 1, 3, 0, 0, 1, 4)')
        found = recipient.recipients_of(conn, 1)[1]
        self.assertEqual(recipient.UNKNOWN, found.unit)
        self.assertEqual('the database holds no target filter', found.reason)

    def test_a_caster_change_aims_the_subtree_at_the_target_the_group_received(self):
        outer = effect(1, GROUP)
        change = effect(2, GROUP, mask=TEAM_WITHOUT_CASTER, values=(0, 0, 1, 0, 1, 1))
        plain = effect(3, mask=0)
        caster_only = effect(4, mask=CASTER_ONLY)
        conn = database([outer, change, plain, caster_only], {1: [2], 2: [3, 4]}, [1])
        found = recipient.recipients_of(conn, 1)
        self.assertEqual(recipient.ALLY, found[2].unit)
        self.assertEqual(recipient.TARGETED, found[3].unit)
        self.assertEqual(recipient.ALLY, found[4].unit)

    def test_the_second_child_of_a_steal_runs_on_the_caster_unless_its_parameter_says_target(self):
        for second, unit in ((0, recipient.CASTER), (1, recipient.TARGETED)):
            with self.subTest(second=second):
                conn = database([effect(1, STEAL, values=(0, 0, second)), effect(2), effect(3)],
                                {1: [2, 3]}, [1])
                found = recipient.recipients_of(conn, 1)
                self.assertEqual(recipient.TARGETED, found[2].unit)
                self.assertEqual(unit, found[3].unit)

    def test_a_group_run_on_each_cell_hands_no_unit(self):
        for on_target, unit in ((1, recipient.ALLY), (0, recipient.TARGETED)):
            with self.subTest(on_target=on_target):
                group = effect(1, GROUP, mask=TEAM_WITHOUT_CASTER, values=(0, 0, on_target))
                conn = database([group, effect(2)], {1: [2]}, [1])
                found = recipient.recipients_of(conn, 1)
                self.assertEqual(recipient.ALLY, found[1].unit)
                self.assertEqual(unit, found[2].unit)


class ClassArmorRowsOnTheDatabaseTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from fashionistapulp.fashionista_config import get_items_db_path
        cls.path = get_items_db_path('wakfu')

    def setUp(self):
        if not os.path.exists(self.path):
            self.skipTest('no Wakfu database built; run update_data_wakfu.py')

    def test_every_class_armor_row_has_a_recipient_and_each_unknown_one_a_reason(self):
        conn = sqlite3.connect('file:%s?mode=ro' % self.path.replace(os.sep, '/'), uri=True)
        try:
            columns = {row[1] for row in conn.execute('pragma table_info(effects)')}
            if 'target_mask' not in columns:
                self.skipTest('no Wakfu database with the target filter')
            stored = all(name in columns for name in BYTES)
            actions = dict(conn.execute('select id, action from effects where action in (1013, 1010)'))
            spells = [row[0] for row in conn.execute('select id from client_spells where breed > 0')]
            units = collections.Counter()
            outputs = collections.Counter()
            reasons = collections.Counter()
            rows = 0
            for spell in spells:
                for effect_id, found in recipient.recipients_of(conn, spell).items():
                    if effect_id not in actions:
                        continue
                    rows += 1
                    units[found.unit] += 1
                    outputs['+'.join(sorted(found.outputs))] += 1
                    if found.unit == recipient.UNKNOWN:
                        reasons[found.reason] += 1
                    else:
                        self.assertIsNone(found.reason)
        finally:
            conn.close()
        self.assertEqual(DATABASE_ARMOR_ROWS, rows)
        self.assertEqual(units[recipient.UNKNOWN], sum(reasons.values()))
        self.assertNotIn(None, reasons)
        self.assertEqual(UNITS_WITH_BYTES if stored else UNITS_WITHOUT_BYTES, dict(units))
        self.assertEqual(OUTPUTS_WITH_BYTES if stored else OUTPUTS_WITHOUT_BYTES, dict(outputs))
        if not stored:
            self.assertEqual({recipient.REASON_BYTES: 54}, dict(reasons))
