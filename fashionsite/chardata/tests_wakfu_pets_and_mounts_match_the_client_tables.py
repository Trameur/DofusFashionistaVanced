import collections
import json
import sqlite3
from unittest import TestCase

from fashionistapulp.wakfu_db import effects_of, level_value

from .tests_wakfu_open_data_and_client_differ_only_by_the_ids_pinned_here import (
    DATABASE, PETS_THE_OPEN_DATA_LACKS, ROOT)

DUMP = ROOT / 'itemscraper' / 'transformed_wakfu.json'

PET_TYPE = 582
CHARM_TYPE = 849
MOUNT_TYPE = 611
COSTUME_TYPE = 647
JOB_ACTION = 2001
NO_PARAMETER_ACTION = 400
STATE_ACTION = 304
PETS_WITH_A_JOB_LINE = (15098, 22551, 23881, 27310, 27311, 27540, 27541)
MOUNT_ROWS_WITHOUT_AN_ITEM = (135, 136, 137)


class TheWakfuPetsAndMountsMatchTheClientTablesTests(TestCase):
    """Guards on the shipped db and the open data dump, skipped when either is absent."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.conn = None
        if not DATABASE.exists() or not DUMP.exists():
            return
        conn = sqlite3.connect('file:%s?mode=ro' % DATABASE.as_posix(), uri=True)
        if conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'item_level_caps'"
                        ).fetchone() is None:
            conn.close()
            return
        cls.conn = conn
        with DUMP.open(encoding='utf-8') as handle:
            cls.equipment = json.load(handle)['equipment']
        cls.by_type = collections.defaultdict(list)
        for item in cls.equipment:
            cls.by_type[item['type_id']].append(item)
        cls.caps = {item: (slot, cap) for item, slot, cap in conn.execute(
            'SELECT item, slot, cap FROM item_level_caps')}

    @classmethod
    def tearDownClass(cls):
        if cls.conn is not None:
            cls.conn.close()
        super().tearDownClass()

    def setUp(self):
        if self.conn is None:
            self.skipTest('no Wakfu database with the level tables, or no open data dump')

    def ids(self, type_id):
        return {item['id'] for item in self.by_type[type_id]}

    def client_stat_effects(self, item, actions):
        return sorted((effect.action, tuple(effect.params))
                      for effect in effects_of(self.conn, 'ITEM_EQUIP', item['id'])
                      if effect.action in actions)

    @staticmethod
    def stat_actions(items):
        return {line['action'] for item in items for line in item['lines'] if line.get('stat')}

    def item_rows(self):
        return {item for (item,) in self.conn.execute('SELECT id FROM items')}

    def test_the_117_open_data_pets_are_table_117_rows_and_the_9_others_are_pinned(self):
        pets = self.ids(PET_TYPE)
        self.assertEqual(117, len(pets))
        rows = self.conn.execute('SELECT id, item FROM pets').fetchall()
        self.assertEqual(126, len(rows))
        pinned = set(PETS_THE_OPEN_DATA_LACKS)
        self.assertEqual(9, len(pinned))
        self.assertEqual(pets | pinned, {item for _row, item in rows})
        self.assertEqual(set(), pinned & {item['id'] for item in self.equipment})
        self.assertEqual(set(), pinned & self.item_rows())

    def test_the_37_open_data_mounts_are_table_144_rows_and_rows_135_to_137_name_no_item(self):
        mounts = self.ids(MOUNT_TYPE)
        self.assertEqual(37, len(mounts))
        rows = self.conn.execute('SELECT id, item FROM mounts').fetchall()
        self.assertEqual(40, len(rows))
        self.assertEqual(mounts, {item for _row, item in rows if item is not None})
        self.assertEqual(list(MOUNT_ROWS_WITHOUT_AN_ITEM),
                         sorted(row for row, item in rows if item is None))

    def test_no_lucky_charm_is_a_pet_or_mount_row(self):
        charms = self.ids(CHARM_TYPE)
        self.assertEqual(42, len(charms))
        rows = {item for table in ('pets', 'mounts') for (item,) in self.conn.execute(
            'SELECT item FROM %s WHERE item IS NOT NULL' % table)}
        self.assertEqual(set(), charms & rows)
        self.assertEqual(set(), charms & set(self.caps))

    def test_every_cap_is_emm(self):
        emm = {item: cap for table in ('pets', 'mounts') for item, cap in self.conn.execute(
            'SELECT item, emm FROM %s WHERE item IS NOT NULL' % table)}
        self.assertEqual(set(emm) - set(PETS_THE_OPEN_DATA_LACKS), set(self.caps))
        for item, (_slot, cap) in self.caps.items():
            with self.subTest(item=item):
                self.assertEqual(emm[item], cap)
        pets = collections.Counter(cap for slot, cap in self.caps.values() if slot == 'PET')
        mounts = collections.Counter(cap for slot, cap in self.caps.values() if slot == 'MOUNT')
        self.assertEqual({50: 110, 25: 6, 0: 1}, dict(pets))
        self.assertEqual({50: 37}, dict(mounts))

    def test_every_leveled_line_equals_the_client_effect_at_every_level(self):
        leveled = [item for type_id in (PET_TYPE, MOUNT_TYPE) for item in self.by_type[type_id]]
        actions = self.stat_actions(leveled)
        compared = mismatches = 0
        for item in leveled:
            cap = self.caps[item['id']][1]
            mine = sorted(
                (item['lines'][line]['action'], base, per_level)
                for line, base, per_level in self.conn.execute(
                    'SELECT line, base, per_level FROM item_level_lines WHERE item = ?',
                    (item['id'],)))
            client = sorted((action, params[0], params[1]) for action, params
                            in self.client_stat_effects(item, actions))
            self.assertEqual(len(client), len(mine), item['id'])
            for (action, base, per_level), (mine_action, mine_base, mine_slope) in zip(
                    client, mine):
                self.assertEqual(action, mine_action)
                for level in range(cap + 1):
                    compared += 1
                    if (level_value(base, per_level, level)
                            != level_value(mine_base, mine_slope, level)):
                        mismatches += 1
        self.assertEqual(0, mismatches)
        self.assertEqual(13473, compared)

    def test_the_charm_lines_are_fixed_and_equal_the_client_effects(self):
        charms = self.by_type[CHARM_TYPE]
        actions = self.stat_actions(charms)
        lines = 0
        for item in charms:
            mine = sorted((line['action'], tuple(line['params']))
                          for line in item['lines'] if line.get('stat'))
            self.assertEqual(mine, self.client_stat_effects(item, actions), item['id'])
            for line in item['lines']:
                if not line.get('stat'):
                    continue
                lines += 1
                params = line['params']
                self.assertEqual(0, params[1] if len(params) > 1 else 0, item['id'])
                self.assertEqual(int(line['value']), level_value(params[0], 0, item['level']))
        self.assertEqual(237, lines)
        self.assertEqual(0, self.conn.execute(
            'SELECT COUNT(*) FROM item_level_lines WHERE item IN (%s)'
            % ','.join(str(item['id']) for item in charms)).fetchone()[0])

    def test_the_lines_left_out_are_12_job_lines_on_7_pets_and_37_movement_lines(self):
        left_out = collections.defaultdict(list)
        for type_id in (PET_TYPE, MOUNT_TYPE, CHARM_TYPE):
            for item in self.by_type[type_id]:
                for line in item['lines']:
                    if not line.get('stat'):
                        left_out[line['action']].append(item['id'])
        self.assertEqual({JOB_ACTION, NO_PARAMETER_ACTION}, set(left_out))
        self.assertEqual(12, len(left_out[JOB_ACTION]))
        self.assertEqual(sorted(PETS_WITH_A_JOB_LINE), sorted(set(left_out[JOB_ACTION])))
        self.assertEqual(self.ids(MOUNT_TYPE), set(left_out[NO_PARAMETER_ACTION]))
        self.assertEqual(37, len(left_out[NO_PARAMETER_ACTION]))
        for item in self.equipment:
            if item['id'] not in self.caps:
                continue
            kept = {line for (line,) in self.conn.execute(
                'SELECT line FROM item_level_lines WHERE item = ?', (item['id'],))}
            left = {number for number, line in enumerate(item['lines']) if not line.get('stat')}
            self.assertEqual(set(), kept & left, item['id'])

    def test_no_leveled_item_was_left_without_a_cap(self):
        missing = []
        for type_id in (PET_TYPE, MOUNT_TYPE, CHARM_TYPE):
            for item in self.by_type[type_id]:
                sloped = any(line.get('stat') and len(line['params']) > 1 and line['params'][1]
                             for line in item['lines'])
                if sloped and item['id'] not in self.caps:
                    missing.append(item['id'])
        self.assertEqual([], missing)
        every = self.ids(PET_TYPE) | self.ids(MOUNT_TYPE) | self.ids(CHARM_TYPE)
        self.assertEqual(set(), every - self.item_rows())

    def test_the_44_legacy_pets_and_20_legacy_mounts_are_default_exclusions(self):
        from fashionistapulp.structure import get_structure
        from fashionistapulp.wakfu_exclusions import default_exclusions
        excluded = set(default_exclusions(get_structure('wakfu')))
        rarity = {item: value for item, value in self.conn.execute(
            'SELECT item, rarity FROM item_rarity')}
        legacy_pets = {item for item in self.ids(PET_TYPE) if rarity.get(item) == 0}
        legacy_mounts = {item for item in self.ids(MOUNT_TYPE) if rarity.get(item) == 0}
        self.assertEqual(44, len(legacy_pets))
        self.assertEqual(20, len(legacy_mounts))
        self.assertEqual(set(), (legacy_pets | legacy_mounts) - excluded)
        companions = self.ids(PET_TYPE) | self.ids(MOUNT_TYPE)
        self.assertEqual(legacy_pets | legacy_mounts, excluded & companions)

    def test_the_7_costumes_stay_out_and_give_no_characteristic(self):
        costumes = self.by_type[COSTUME_TYPE]
        self.assertEqual(7, len(costumes))
        self.assertEqual(0, self.conn.execute(
            'SELECT COUNT(*) FROM items WHERE type = ?', (COSTUME_TYPE,)).fetchone()[0])
        for item in costumes:
            self.assertEqual([STATE_ACTION], [line['action'] for line in item['lines']])
            state = int(item['lines'][0]['params'][0])
            actions = [effect.action for effect in effects_of(self.conn, 'STATE', state)]
            self.assertTrue(actions, item['id'])
            self.assertEqual({NO_PARAMETER_ACTION}, set(actions), item['id'])
