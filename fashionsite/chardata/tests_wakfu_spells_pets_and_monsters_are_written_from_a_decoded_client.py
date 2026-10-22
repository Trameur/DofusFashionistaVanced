import collections
import os
import sqlite3
import sys

from django.test import SimpleTestCase

SCRAPER = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), 'itemscraper')
if SCRAPER not in sys.path:
    sys.path.insert(0, SCRAPER)

import build_wakfu_db as builder  # noqa: E402
from chardata.tests_wakfu_effect_groups_resolve_to_known_effects import (  # noqa: E402
    effect, tables)
from fashionistapulp import wakfu_db  # noqa: E402


def spell(ident, effect_ids, breed=0):
    return {'id': ident, 'breed': breed, 'ap': 3.0, 'mp': 0.0, 'wp': 1.0, 'range_min': 1.0,
            'range_max': 5.0, 'element': 4, 'unlock_level': 12, 'max_level': 245,
            'effect_ids': effect_ids}


# Spell 40 lists effect 500 (which runs group 500) and effect 502. Effect 501 and
# effect 900 carry the container SPELL 40 and 41 but no spell lists them.
EFFECTS = [
    effect(500, 330, 'SPELL', 40), effect(501, 20, 'GROUP', 500, [4.0, 0.5]),
    effect(502, 20, 'SPELL', 40, [1.0, 0.0]), effect(503, 20, 'SPELL', 40, [9.0, 0.0]),
    effect(900, 20, 'SPELL', 41), effect(100, 120, 'ITEM_EQUIP', 7, [0.0, 0.8]),
]
GROUPS = [(500, [501])]
SPELLS = [spell(40, [500, 502], breed=3), spell(41, [])]
PETS = [{'id': 11, 'item': 7, 'eoq': 50, 'eop': 50, 'emm': 25}]
MOUNTS = [{'id': 149, 'item': 7, 'eop': 50, 'emm': 50, 'eoq': 50},
          {'id': 135, 'item': 20624, 'eop': 50, 'emm': 50, 'eoq': 50}]


def row(ident, target, is_list=False, rate=1.0, low=1, high=1):
    return {'id': ident, 'target': target, 'is_list': is_list, 'rate': rate,
            'quantity_min': low, 'quantity_max': high}


LOOT_LISTS = [
    {'id': 2789, 'rows': [row(1, 24706, rate=-1.0, low=25, high=100), row(2, 2793, True, 5.0),
                          row(3, 0, rate=80.0)]},
    {'id': 2793, 'rows': []},
]
MONSTERS = [
    {'id': 735, 'family': 147,
     'drops': [{'item': 5407, 'rate': 0.25, 'quantity_min': 1, 'quantity_max': 3},
               {'item': 18787, 'rate': 0.01, 'quantity_min': 1, 'quantity_max': 1}],
     'harvests': [{'loot_list': 2789, 'condition': 'IsDead("target")'},
                  {'loot_list': 2793, 'condition': ''}]},
    {'id': 1918, 'family': 3000, 'drops': [], 'harvests': []},
]


def client(**changes):
    payload = tables(EFFECTS, GROUPS)
    payload.update(spells=SPELLS, pets=PETS, mounts=MOUNTS, monsters=MONSTERS,
                   loot_lists=LOOT_LISTS)
    payload.update(changes)
    return payload


class TheWakfuSpellsPetsAndMonstersAreWrittenFromADecodedClientTests(SimpleTestCase):
    def fill(self, payload):
        conn = sqlite3.connect(':memory:')
        self.addCleanup(conn.close)
        wakfu_db.create_tables(conn)
        counts = collections.Counter()
        builder.write_client_tables(conn, payload, counts)
        return conn, counts

    def test_a_spell_reaches_the_effects_its_own_list_names_and_their_groups(self):
        conn, counts = self.fill(client())
        stored = [one[0] for one in conn.execute('SELECT id FROM effects ORDER BY id')]
        self.assertEqual([100, 500, 501, 502], stored)
        self.assertEqual([(40, 0, 500), (40, 1, 502)], conn.execute(
            'SELECT spell, position, effect FROM client_spell_effects').fetchall())
        self.assertEqual((2, 2), (counts['client spells'], counts['client spell effects']))

    def test_an_effect_only_the_container_names_is_never_a_spell_effect(self):
        conn, _counts = self.fill(client())
        self.assertEqual([], conn.execute(
            'SELECT id FROM effects WHERE id IN (503, 900)').fetchall())

    def test_the_spell_columns_hold_the_client_values_and_the_breed_of_a_class_spell(self):
        conn, _counts = self.fill(client())
        self.assertEqual((40, 3, 3.0, 0.0, 1.0, 1.0, 5.0, 4, 12, 245), conn.execute(
            'SELECT * FROM client_spells WHERE id = 40').fetchone())

    def test_a_spell_naming_an_effect_the_table_lacks_stops_the_build(self):
        with self.assertRaisesRegex(ValueError, 'effect 77 is listed'):
            self.fill(client(spells=[spell(42, [77])]))

    def test_a_pet_has_the_effects_its_item_wears(self):
        conn, _counts = self.fill(client())
        self.assertEqual([(11, 7, 50, 50, 25)], conn.execute('SELECT * FROM pets').fetchall())
        worn = wakfu_db.effects_of(conn, 'ITEM_EQUIP', 7)
        self.assertEqual([100], [one.id for one in worn])
        self.assertEqual(40.0, wakfu_db.effect_value(worn[0].params, 0, 50))

    def test_a_mount_whose_item_the_client_lacks_has_no_item(self):
        conn, counts = self.fill(client())
        self.assertEqual([(135, None), (149, 7)], conn.execute(
            'SELECT id, item FROM mounts ORDER BY id').fetchall())
        self.assertEqual(1, counts['mounts without an item'])

    def test_a_loot_list_row_is_an_item_or_a_reference_to_another_list(self):
        conn, counts = self.fill(client())
        self.assertEqual(
            [(0, 1, 24706, None, -1.0, 25, 100), (1, 2, None, 2793, 5.0, 1, 1),
             (2, 3, 0, None, 80.0, 1, 1)],
            conn.execute('SELECT position, id, item, sub_list, rate, quantity_min,'
                         ' quantity_max FROM loot_list_rows WHERE loot_list = 2789'
                         ' ORDER BY position').fetchall())
        self.assertEqual((2, 3), (counts['loot lists'], counts['loot list rows']))

    def test_a_loot_list_naming_a_list_the_client_lacks_stops_the_build(self):
        broken = [{'id': 5, 'rows': [row(1, 6, True)]}]
        with self.assertRaisesRegex(ValueError, 'list 6'):
            self.fill(client(loot_lists=broken, monsters=[]))

    def test_a_monster_has_its_drops_and_harvest_entries_in_order(self):
        conn, counts = self.fill(client())
        self.assertEqual([(735, 147), (1918, 3000)],
                         conn.execute('SELECT id, family FROM monsters ORDER BY id').fetchall())
        self.assertEqual([(0, 5407, 0.25, 1, 3), (1, 18787, 0.01, 1, 1)], conn.execute(
            'SELECT position, item, rate, quantity_min, quantity_max FROM monster_drops'
            ' WHERE monster = 735 ORDER BY position').fetchall())
        self.assertEqual([(0, 2789, 'IsDead("target")'), (1, 2793, '')], conn.execute(
            'SELECT position, loot_list, condition FROM monster_harvests'
            ' WHERE monster = 735 ORDER BY position').fetchall())
        self.assertEqual([], conn.execute(
            'SELECT * FROM monster_drops WHERE monster = 1918').fetchall())
        self.assertEqual((2, 2, 2), (counts['monsters'], counts['monster drops'],
                                     counts['monster harvests']))

    def test_a_harvest_entry_naming_a_list_the_client_lacks_stops_the_build(self):
        broken = [{'id': 1, 'family': 1, 'drops': [],
                   'harvests': [{'loot_list': 9, 'condition': ''}]}]
        with self.assertRaisesRegex(ValueError, 'list 9'):
            self.fill(client(monsters=broken))

    def test_a_client_decoded_before_these_tables_leaves_them_empty(self):
        old = tables(EFFECTS, GROUPS)
        conn, counts = self.fill(old)
        for name in ('client_spells', 'pets', 'mounts', 'monsters', 'loot_lists'):
            self.assertEqual(0, conn.execute('SELECT COUNT(*) FROM %s' % name).fetchone()[0])
        self.assertEqual(0, counts['client spells'])
