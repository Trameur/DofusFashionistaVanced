import json
import sqlite3
from pathlib import Path
from unittest import TestCase

ROOT = Path(__file__).resolve().parents[2]
DATABASE = ROOT / 'fashionistapulp' / 'fashionistapulp' / 'items_wakfu.db'
MIRRORS = ROOT / 'itemscraper' / 'wakfu_raw'
LANGUAGES = ('en', 'fr', 'es', 'pt', 'de')

# The client's monster table has 2874 monsters and its name file 2857
MONSTERS_WITHOUT_A_NAME = (
    5324, 5325, 5371, 5372, 5405, 5419, 5515, 5517, 5523, 5588, 5590, 5596, 5598,
    5772, 5778, 5779, 5852)

# table, id column, text columns
TABLES = (
    ('state_texts', 'state', ('name', 'description')),
    ('client_spell_texts', 'spell', ('name', 'description')),
    ('client_set_names', 'item_set', ('name',)),
    ('client_monster_names', 'monster', ('name',)),
    ('monster_family_names', 'family', ('name',)),
    ('ability_names', 'ability', ('name',)),
    ('ability_category_names', 'category', ('name',)),
    ('effect_texts', 'effect', ('text',)),
    ('action_texts', 'action', ('text',)),
)

# (table, id, en, fr, es, pt) names the same thing in the four languages
SPOT_VALUES = (
    ('state_texts', 21, 'Confusion', 'Confusion', 'Confusi\u00f3n', 'Confus\u00e3o'),
    ('client_spell_texts', 548, 'Gobball Bite', 'Morsure du Bouftou',
     'Mordedura de Jalat\u00f3', 'Mordida de Papatudo'),
    ('client_set_names', 44, 'Tofu Set', 'Panoplie Tofu', 'Set de tofu', 'Conjunto de Tofu'),
    ('client_monster_names', 2, 'Black Gobbly', 'Boufton Noir', 'Jalat\u00edn negro',
     'Paparneiro Negro'),
    ('monster_family_names', 68, 'Gobballs', 'Bouftous', 'Jalat\u00f3s', 'Papatudos'),
    ('ability_names', 2, 'Action Points', "Point d'Action", 'Puntos de acci\u00f3n',
     'Ponto de a\u00e7\u00e3o'),
    ('ability_category_names', 3, 'Strength', 'Force', 'Fuerza', 'For\u00e7a'),
)


def id_column(table):
    return next(column for name, column, _texts in TABLES if name == table)


class TheWakfuClientNamesHoldTheCountsTheGameHasTests(TestCase):
    """Guards on the real items_wakfu.db, skipped where it is not built."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.conn = None
        if DATABASE.exists():
            conn = sqlite3.connect('file:%s?mode=ro' % DATABASE.as_posix(), uri=True)
            try:
                filled = conn.execute('SELECT COUNT(*) FROM client_monster_names').fetchone()[0]
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
            self.skipTest('items_wakfu.db is absent or has no client texts')

    def per_language(self, table, column=None):
        where = '' if column is None else ' AND %s IS NOT NULL' % column
        return dict(self.conn.execute(
            'SELECT language, COUNT(*) FROM %s WHERE 1 = 1%s GROUP BY language'
            % (table, where)).fetchall())

    def test_the_states_hold_4704_names_everywhere_and_a_few_hundred_descriptions(self):
        self.assertEqual({language: 4704 for language in LANGUAGES},
                         self.per_language('state_texts', 'name'))
        self.assertEqual({'en': 505, 'fr': 505, 'de': 505, 'es': 507, 'pt': 507},
                         self.per_language('state_texts', 'description'))

    def test_the_client_spells_hold_4137_names_and_1734_or_1739_descriptions(self):
        self.assertEqual({language: 4137 for language in LANGUAGES},
                         self.per_language('client_spell_texts', 'name'))
        self.assertEqual({'en': 1734, 'fr': 1734, 'de': 1734, 'es': 1739, 'pt': 1739},
                         self.per_language('client_spell_texts', 'description'))

    def test_the_sets_monsters_families_abilities_and_categories_hold_their_counts(self):
        for table, count in (('client_set_names', 354), ('client_monster_names', 2857),
                             ('monster_family_names', 323), ('ability_names', 31),
                             ('ability_category_names', 5), ('action_texts', 170)):
            self.assertEqual({language: count for language in LANGUAGES},
                             self.per_language(table), table)
        self.assertEqual({'en': 9331, 'fr': 9331, 'de': 9331, 'es': 9333, 'pt': 9333},
                         self.per_language('effect_texts'))

    def test_the_sets_and_monsters_without_a_name_are_the_known_ones(self):
        self.assertEqual([(641,)], self.conn.execute(
            'SELECT id FROM client_sets WHERE id NOT IN (SELECT item_set FROM client_set_names)'
        ).fetchall())
        self.assertEqual(
            [(ident,) for ident in MONSTERS_WITHOUT_A_NAME], self.conn.execute(
                'SELECT id FROM monsters WHERE id NOT IN'
                ' (SELECT monster FROM client_monster_names) ORDER BY id').fetchall())

    def test_one_entry_of_each_family_reads_the_same_in_every_language(self):
        for table, ident, en, fr, es, pt in SPOT_VALUES:
            column = 'name'
            found = dict(self.conn.execute(
                'SELECT language, %s FROM %s WHERE %s = ?'
                % (column, table, id_column(table)), (ident,)).fetchall())
            self.assertEqual(
                {'en': en, 'fr': fr, 'es': es, 'pt': pt, 'de': en}, found, table)

    def test_german_is_the_english_row_for_row_on_every_table(self):
        for table, column, texts in TABLES:
            names = ', '.join(texts)
            sql = 'SELECT %s, %s FROM %s WHERE language = ?' % (column, names, table)
            self.assertEqual(
                sorted(self.conn.execute(sql, ('en',)).fetchall(), key=repr),
                sorted(self.conn.execute(sql, ('de',)).fetchall(), key=repr), table)

    def test_a_text_is_stored_as_the_client_shows_it(self):
        for table, column, texts in TABLES:
            for text in texts:
                self.assertEqual([], self.conn.execute(
                    "SELECT %s FROM %s WHERE %s LIKE '%%' || char(92) || 'n%%' LIMIT 1"
                    % (column, table, text)).fetchall(), table)
        self.assertEqual([('Panoplie Carnage',)], self.conn.execute(
            "SELECT name FROM client_set_names WHERE item_set = 594 AND language = 'fr'"
        ).fetchall())
        self.assertEqual([('% Points de Vie',)], self.conn.execute(
            "SELECT name FROM ability_names WHERE ability = 1 AND language = 'fr'").fetchall())

    def test_no_name_row_is_left_without_its_parent(self):
        self.assertEqual([], self.conn.execute('PRAGMA foreign_key_check').fetchall())

    def mirror(self):
        found = sorted(path for path in MIRRORS.glob('*/actions.json')) \
            if MIRRORS.exists() else []
        if not found:
            self.skipTest('no open data mirror')
        return found[-1].parent

    def test_the_action_texts_equal_the_open_data_descriptions(self):
        actions = json.loads((self.mirror() / 'actions.json').read_text(encoding='utf-8'))
        compared = 0
        for action in actions:
            for language, text in (action.get('description') or {}).items():
                stored = self.conn.execute(
                    'SELECT text FROM action_texts WHERE action = ? AND language = ?',
                    (action['definition']['id'], language)).fetchone()
                self.assertEqual((text,), stored, (action['definition']['id'], language))
                compared += 1
        self.assertEqual(272, compared)

    def test_the_effect_texts_equal_the_open_data_item_effect_descriptions(self):
        items = json.loads((self.mirror() / 'items.json').read_text(encoding='utf-8'))
        seen = {}
        for item in items:
            for kind in ('useEffects', 'useCriticalEffects', 'equipEffects'):
                for entry in item['definition'].get(kind) or ():
                    effect = entry['effect']
                    for language, text in (effect.get('description') or {}).items():
                        seen[(effect['definition']['id'], language)] = text
        for (effect, language), text in seen.items():
            stored = self.conn.execute(
                'SELECT text FROM effect_texts WHERE effect = ? AND language = ?',
                (effect, language)).fetchone()
            self.assertEqual((text.replace('\r\n', '\n'),), stored, (effect, language))
        self.assertEqual(1684, len(seen))

    def test_the_ability_categories_unlock_at_the_levels_the_client_lists(self):
        rows = {ident: (json.loads(levels), json.loads(abilities)) for ident, levels, abilities
                in self.conn.execute(
                    'SELECT id, unlock_levels, ability_ids FROM ability_categories')}
        self.assertEqual([2, 3, 4, 5, 6], sorted(rows))
        for ident, last in ((2, 243), (3, 244), (4, 245), (5, 245)):
            levels = rows[ident][0]
            self.assertEqual(62, len(levels), ident)
            self.assertIn(230, levels)
            self.assertEqual(last, levels[-1], ident)
        self.assertEqual([25, 75, 125, 175, 225], rows[6][0])
        listed = {one for _levels, abilities in rows.values() for one in abilities}
        stored = {one[0] for one in self.conn.execute('SELECT id FROM abilities')}
        self.assertEqual({24, 25, 32, 33}, listed - stored)
        self.assertEqual([], self.conn.execute(
            'SELECT ability FROM ability_names WHERE ability IN (24, 25, 32, 33)').fetchall())
