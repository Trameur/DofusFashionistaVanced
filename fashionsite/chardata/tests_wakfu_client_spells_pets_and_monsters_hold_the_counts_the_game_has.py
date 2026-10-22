import sqlite3
import sys
import zipfile
from pathlib import Path
from unittest import TestCase

from fashionistapulp import wakfu_db

ROOT = Path(__file__).resolve().parents[2]
DATABASE = ROOT / 'fashionistapulp' / 'fashionistapulp' / 'items_wakfu.db'
CLIENT_DIR = ROOT / 'itemscraper' / 'wakfu_client'
if str(ROOT / 'itemscraper') not in sys.path:
    sys.path.insert(0, str(ROOT / 'itemscraper'))

from get_wakfu_client import version_key  # noqa: E402

# The encyclopedia names these spells wrongly (its names are shifted by one
# among the Sacrier ones, and a few classes renamed theirs); the client's own
# text is right. Known difference, the harvest is not fixed here.
HARVEST_NAMES_THAT_DIFFER_FROM_THE_CLIENT = (
    4720, 5030, 5041, 5043, 5044, 5045, 5047, 6845, 6942, 7064, 7084, 7211)
# The two spells whose range the client and the encyclopedia give differently
RANGE_DIFFERS = {4716, 5047}
ELEMENT_CODES = {'FIRE': 1, 'WATER': 2, 'EARTH': 3, 'AIR': 4, None: 9}
CLASS_SPELLS_PER_BREED = {
    1: 39, 2: 38, 3: 38, 4: 36, 5: 41, 6: 41, 7: 41, 8: 41, 9: 40, 10: 41, 11: 41,
    12: 38, 13: 41, 14: 40, 15: 40, 16: 41, 18: 41, 19: 44}
SET_ASIDE_FROM_THE_HARVEST = 5150
APPLY_MASTERY = 120
PETS_WITH_FIXED_EFFECTS = {128, 262, 263, 264, 265}


def client_names():
    """{spell id: French name} from the decoded client's text jar, or None without it."""
    jars = sorted(CLIENT_DIR.glob('*/i18n_fr.jar'),
                  key=lambda path: version_key(path.parent.name))
    if not jars:
        return None
    with zipfile.ZipFile(jars[-1]) as jar:
        body = jar.read('texts_fr.properties').decode('utf-8')
    names = {}
    for line in body.splitlines():
        if line.startswith('content.3.'):
            key, _separator, text = line.partition('=')
            names[int(key[len('content.3.'):])] = text
    return names


def straight(text):
    return text.replace(chr(0x2019), "'")


class TheWakfuClientSpellsPetsAndMonstersHoldTheCountsTheGameHasTests(TestCase):
    """Guards on the real items_wakfu.db, skipped where it is not built."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.conn = None
        if DATABASE.exists():
            conn = sqlite3.connect('file:%s?mode=ro' % DATABASE.as_posix(), uri=True)
            try:
                found = conn.execute('SELECT COUNT(*) FROM sqlite_master'
                                     " WHERE name = 'client_spells'").fetchone()[0]
                filled = found and conn.execute(
                    'SELECT COUNT(*) FROM client_spells').fetchone()[0]
            except sqlite3.DatabaseError:
                filled = 0
            if filled:
                cls.conn = conn
            else:
                conn.close()

    @classmethod
    def tearDownClass(cls):
        if cls.conn is not None:
            cls.conn.close()
        super().tearDownClass()

    def setUp(self):
        if self.conn is None:
            self.skipTest('no Wakfu database with the spell, pet and monster tables; run '
                          'itemscraper/get_wakfu_client.py then build_wakfu_db.py')

    def count(self, table):
        return self.conn.execute('SELECT COUNT(*) FROM %s' % table).fetchone()[0]

    def test_the_client_holds_4143_spells_and_722_class_spells(self):
        self.assertEqual(4143, self.count('client_spells'))
        per_breed = dict(self.conn.execute(
            'SELECT breed, COUNT(*) FROM client_spells WHERE breed > 0 GROUP BY breed'))
        self.assertEqual(CLASS_SPELLS_PER_BREED, per_breed)
        self.assertEqual(722, sum(per_breed.values()))

    def test_every_listed_spell_effect_is_a_stored_effect_the_spell_owns(self):
        self.assertEqual(11853, self.count('client_spell_effects'))
        stray = self.conn.execute(
            'SELECT COUNT(*) FROM client_spell_effects s LEFT JOIN effects e'
            ' ON e.id = s.effect WHERE e.id IS NULL OR e.container_type != ?'
            ' OR e.container != s.spell', ('SPELL',)).fetchone()[0]
        self.assertEqual(0, stray)

    def test_the_stored_spell_effects_are_exactly_the_listed_ones(self):
        self.assertEqual(11853, self.conn.execute(
            "SELECT COUNT(*) FROM effects WHERE container_type = 'SPELL'").fetchone()[0])

    def test_costs_element_and_class_equal_the_encyclopedia_on_every_spell_it_has(self):
        wrong = []
        common = 0
        for ident, klass, element, ap, mp, wp, _range in self.conn.execute(
                'SELECT id, class, element, ap, mp, wp, range FROM spells'):
            row = self.conn.execute(
                'SELECT breed, ap, mp, wp, element FROM client_spells WHERE id = ?',
                (ident,)).fetchone()
            if row is None:
                self.assertEqual(SET_ASIDE_FROM_THE_HARVEST, ident)
                continue
            common += 1
            if (klass, ap or 0, mp or 0, wp or 0, ELEMENT_CODES[element]) != row:
                wrong.append(ident)
        self.assertEqual(714, common)
        self.assertEqual([], wrong)

    def test_the_range_equals_the_encyclopedia_but_for_two_spells(self):
        differ = set()
        for ident, text in self.conn.execute(
                'SELECT id, range FROM spells WHERE range IS NOT NULL'):
            row = self.conn.execute('SELECT range_min, range_max FROM client_spells'
                                    ' WHERE id = ?', (ident,)).fetchone()
            if row is not None and tuple(float(part) for part in text.split(' - ')) != row:
                differ.add(ident)
        self.assertEqual(RANGE_DIFFERS, differ)

    def test_the_8_pandawa_passives_the_encyclopedia_lacks_are_there_without_a_cost(self):
        rows = self.conn.execute(
            'SELECT breed, ap, mp, wp FROM client_spells WHERE id IN'
            ' (5152, 8595, 8596, 8597, 8598, 8599, 8600, 8601)').fetchall()
        self.assertEqual([(12, 0.0, 0.0, 0.0)] * 8, rows)
        self.assertEqual(0, self.count('client_spells WHERE id = %d'
                                       % SET_ASIDE_FROM_THE_HARVEST))

    def test_the_12_harvest_spell_names_that_differ_from_the_client_are_a_known_difference(self):
        names = client_names()
        if names is None:
            self.skipTest('no decoded client text')
        differ = []
        for ident, name in self.conn.execute(
                "SELECT spell, name FROM spell_names WHERE language = 'fr'"):
            if ident in names and straight(name) != straight(names[ident]):
                differ.append(ident)
        self.assertEqual(sorted(HARVEST_NAMES_THAT_DIFFER_FROM_THE_CLIENT), sorted(differ))

    def test_the_client_holds_126_pets_each_wearing_effects_and_all_but_five_scale_with_the_level(self):
        self.assertEqual(126, self.count('pets'))
        for pet, item in self.conn.execute('SELECT id, item FROM pets'):
            worn = wakfu_db.effects_of(self.conn, 'ITEM_EQUIP', item)
            self.assertTrue(worn, 'pet %d wears nothing' % pet)
            scales = any(one.params[1] != 0 for one in worn)
            self.assertEqual(pet not in PETS_WITH_FIXED_EFFECTS, scales, 'pet %d' % pet)
        # Krosmunster Eau: action 124, 26 + 1.6 per level, 106 at level 50
        worn = [one for one in wakfu_db.effects_of(self.conn, 'ITEM_EQUIP', 14335)]
        self.assertEqual([(112911, 124)], [(one.id, one.action) for one in worn])
        self.assertEqual(106.0, wakfu_db.effect_value(worn[0].params, 0, 50))

    def test_the_three_pet_level_fields_are_kept_as_the_client_gives_them(self):
        self.assertEqual((50, 50, 25), self.conn.execute(
            'SELECT eoq, eop, emm FROM pets WHERE id = 5').fetchone())
        self.assertEqual((50, 50, 1), self.conn.execute(
            'SELECT eoq, eop, emm FROM pets WHERE id = 262').fetchone())
        self.assertEqual((0, 1, 0), self.conn.execute(
            'SELECT eoq, eop, emm FROM pets WHERE id = 128').fetchone())

    def test_the_client_holds_40_mounts_and_37_of_them_have_an_item(self):
        self.assertEqual(40, self.count('mounts'))
        self.assertEqual(37, self.count('mounts WHERE item IS NOT NULL'))
        self.assertEqual([135, 136, 137], [one[0] for one in self.conn.execute(
            'SELECT id FROM mounts WHERE item IS NULL ORDER BY id')])

    def test_every_mount_item_gives_08_of_a_mastery_per_level_and_nothing_else(self):
        for mount, item in self.conn.execute(
                'SELECT id, item FROM mounts WHERE item IS NOT NULL'):
            worn = wakfu_db.effects_of(self.conn, 'ITEM_EQUIP', item)
            real = [one for one in worn if one.params]
            self.assertEqual([APPLY_MASTERY], [one.action for one in real], mount)
            self.assertEqual(40.0, wakfu_db.effect_value(real[0].params, 0, 50), mount)
            self.assertEqual(0.0, wakfu_db.effect_value(real[0].params, 0, 0), mount)

    def test_the_client_holds_2874_monsters_in_398_families(self):
        self.assertEqual(2874, self.count('monsters'))
        self.assertEqual(398, self.count('(SELECT DISTINCT family FROM monsters)'))

    def test_the_drops_and_harvests_of_the_client_are_all_stored(self):
        self.assertEqual(16138, self.count('monster_drops'))
        self.assertEqual(1084, self.count('(SELECT DISTINCT monster FROM monster_drops)'))
        self.assertEqual(1054, self.count('monster_harvests'))
        self.assertEqual(373, self.count('(SELECT DISTINCT monster FROM monster_harvests)'))
        self.assertEqual(1089, self.count(
            'monsters WHERE id IN (SELECT monster FROM monster_drops UNION'
            ' SELECT monster FROM monster_harvests)'))

    def test_a_drop_has_a_probability_and_a_quantity_range(self):
        low, high = self.conn.execute('SELECT MIN(rate), MAX(rate) FROM monster_drops').fetchone()
        self.assertEqual((0.000125, 1.0), (low, high))
        self.assertEqual(0, self.count('monster_drops WHERE quantity_min > quantity_max'))
        self.assertEqual([(4022, 0, 20414, 1.0), (4022, 1, 20406, 0.02),
                          (4022, 2, 20407, 0.02), (4022, 3, 25123, 0.01)],
                         [one[:4] for one in self.conn.execute(
                             'SELECT * FROM monster_drops WHERE monster = 4022'
                             ' ORDER BY position')])

    def test_the_client_gives_the_bouftou_no_drop_and_no_harvest(self):
        self.assertEqual(0, self.count('monster_drops WHERE monster = 1918'))
        self.assertEqual(0, self.count('monster_harvests WHERE monster = 1918'))

    def test_a_larva_harvest_entry_names_a_list_and_a_condition(self):
        self.assertEqual(
            [(2318, ''), (809, 'not IsDead("target")'), (2439, 'IsDead("target")')],
            self.conn.execute('SELECT loot_list, condition FROM monster_harvests'
                              ' WHERE monster = 735 ORDER BY position').fetchall())

    def test_the_client_holds_2204_loot_lists_whose_nested_lists_are_all_there(self):
        self.assertEqual(2204, self.count('loot_lists'))
        self.assertEqual(14328, self.count('loot_list_rows'))
        self.assertEqual(1654, self.count('loot_list_rows WHERE sub_list IS NOT NULL'))
        self.assertEqual(0, self.count(
            'loot_list_rows WHERE sub_list IS NOT NULL AND sub_list NOT IN'
            ' (SELECT id FROM loot_lists)'))
        self.assertEqual(0, self.count(
            'monster_harvests WHERE loot_list NOT IN (SELECT id FROM loot_lists)'))

    def test_a_row_given_always_has_the_rate_minus_one(self):
        self.assertEqual(1670, self.count('loot_list_rows WHERE rate = -1'))
        rows = self.conn.execute(
            'SELECT id, item, sub_list, rate FROM loot_list_rows WHERE loot_list = 2789'
            ' ORDER BY position').fetchall()
        self.assertEqual([(24706, -1.0), (24705, -1.0)],
                         [(one[1], one[3]) for one in rows[:2]])
        self.assertEqual([(None, 2793), (None, 2795), (None, 2794)],
                         [(one[1], one[2]) for one in rows[2:5]])
        self.assertEqual([5.0, 15.0, 80.0], [one[3] for one in rows[3:]])
