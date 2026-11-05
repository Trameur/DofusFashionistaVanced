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

    def test_the_jobs_classes_and_keyed_texts_hold_their_counts_in_five_languages(self):
        for table, count in (('client_job_names', 15), ('client_breed_names', 19),
                             ('client_breed_texts', 111), ('client_aptitude_texts', 25),
                             ('client_enchantment_texts', 160),
                             ('client_item_type_names', 149)):
            self.assertEqual({language: count for language in LANGUAGES},
                             self.per_language(table), table)

    def test_one_job_one_class_one_aptitude_and_one_enchantment_text_read_in_every_language(self):
        for sql, parameter, expected in (
                ('SELECT language, name FROM client_job_names WHERE job = ?', 40,
                 {'en': 'Baker', 'fr': 'Boulanger', 'es': 'Panadero', 'pt': 'Padeiro',
                  'de': 'Baker'}),
                ('SELECT language, name FROM client_breed_names WHERE breed = ?', 1,
                 {'en': 'Feca', 'fr': 'F\u00e9ca', 'es': 'Feca', 'pt': 'Feca', 'de': 'Feca'}),
                ('SELECT language, text FROM client_aptitude_texts WHERE key = ?',
                 'aptitude.common.title',
                 {'en': 'Characteristics', 'fr': 'Aptitudes', 'es': 'Caracter\u00edsticas',
                  'pt': 'Habilidades', 'de': 'Characteristics'}),
                ('SELECT language, text FROM client_enchantment_texts WHERE key = ?',
                 'enchantment.action.change.colors.title',
                 {'en': 'Recolor the sockets', 'fr': 'Changer la couleur des ch\u00e2sses',
                  'es': 'Cambiar el color de los engarces',
                  'pt': 'Mudar a cor dos engastes', 'de': 'Recolor the sockets'}),
                ('SELECT language, text FROM client_aptitude_texts WHERE key = ?',
                 'aptitudes.maxLevelReached',
                 {'en': 'Max level achieved', 'fr': 'Niveau max atteint',
                  'es': 'Nivel m\u00e1ximo alcanzado', 'pt': 'N\u00edvel m\u00e1ximo atingido',
                  'de': 'Max level achieved'}),
                ('SELECT language, text FROM client_breed_texts WHERE key = ?',
                 'breedLongName.1',
                 {'en': "[#1]'s Shield", 'fr': 'Le Bouclier [#1]', 'es': 'El Escudo de [#1]',
                  'pt': 'Escudo de [#1] ', 'de': "[#1]'s Shield"}),
                ('SELECT language, name FROM client_item_type_names WHERE item_type = ?', 100,
                 {'en': 'Weapon{[~1]?s:} & Shield{[~1]?s:}',
                  'fr': 'Arme{[~1]?s:} & Bouclier{[~1]?s:}',
                  'es': 'Arma{[~1]?s:} y escudo{[~1]?s:}',
                  'pt': 'Arma{[~1]?s:} e Escudo{[~1]?s:}',
                  'de': 'Weapon{[~1]?s:} & Shield{[~1]?s:}'}),
                ('SELECT language, text FROM client_breed_texts WHERE key = ?',
                 'breed.role.name.0',
                 {'en': 'Mobility', 'fr': 'Mobilit\u00e9', 'es': 'Movilidad',
                  'pt': 'Mobilidade', 'de': 'Mobility'})):
            self.assertEqual(expected, dict(self.conn.execute(sql, (parameter,)).fetchall()),
                             parameter)

    def test_a_class_name_keeps_the_plural_template_the_client_writes(self):
        self.assertEqual([('Sacrier{[1*]?:}',)], self.conn.execute(
            "SELECT name FROM client_breed_names WHERE breed = 11 AND language = 'en'"
        ).fetchall())

    def test_german_is_the_english_row_for_row_on_the_jobs_classes_and_keyed_texts(self):
        for table, key, column in (
                ('client_job_names', 'job', 'name'), ('client_breed_names', 'breed', 'name'),
                ('client_breed_texts', 'key', 'text'), ('client_aptitude_texts', 'key', 'text'),
                ('client_enchantment_texts', 'key', 'text'),
                ('client_item_type_names', 'item_type', 'name')):
            sql = 'SELECT %s, %s FROM %s WHERE language = ? ORDER BY 1' % (key, column, table)
            self.assertEqual(self.conn.execute(sql, ('en',)).fetchall(),
                             self.conn.execute(sql, ('de',)).fetchall(), table)

    def test_the_client_names_the_19_long_class_titles_and_descriptions_and_13_aptitude_texts(self):
        for prefix, count in (('breedLongName.%', 19), ('breedLongDesc.%', 19)):
            self.assertEqual(count, self.conn.execute(
                "SELECT COUNT(*) FROM client_breed_texts WHERE language = 'en' AND key LIKE ?",
                (prefix,)).fetchone()[0], prefix)
        self.assertEqual(13, self.conn.execute(
            "SELECT COUNT(*) FROM client_aptitude_texts WHERE language = 'en'"
            " AND key LIKE 'aptitudes.%'").fetchone()[0])
        self.assertEqual(12, self.conn.execute(
            "SELECT COUNT(*) FROM client_aptitude_texts WHERE language = 'en'"
            " AND key LIKE 'aptitude.%'").fetchone()[0])

    def test_the_client_names_every_item_type_the_database_holds(self):
        self.assertEqual(27, self.conn.execute('SELECT COUNT(*) FROM item_types').fetchone()[0])
        self.assertEqual(0, self.conn.execute(
            'SELECT COUNT(*) FROM item_types WHERE id NOT IN'
            ' (SELECT item_type FROM client_item_type_names)').fetchone()[0])

    def test_the_client_names_the_14_crafting_jobs_and_one_more_and_agrees_on_their_names(self):
        crafting = {job for (job,) in self.conn.execute(
            'SELECT DISTINCT job_ankama_id FROM job_names')}
        client = {job for (job,) in self.conn.execute('SELECT DISTINCT job FROM client_job_names')}
        self.assertEqual(14, len(crafting))
        self.assertEqual({82}, client - crafting)
        self.assertEqual(set(), crafting - client)
        self.assertEqual(0, self.conn.execute(
            'SELECT COUNT(*) FROM job_names j JOIN client_job_names c'
            ' ON c.job = j.job_ankama_id AND c.language = j.language'
            ' WHERE c.name != j.name').fetchone()[0])

    def test_the_condition_labels_and_the_nations_have_a_german_row_copied_from_english(self):
        self.assertEqual({language: 130 for language in LANGUAGES}, dict(self.conn.execute(
            "SELECT language, COUNT(*) FROM criteria_labels WHERE key LIKE 'critere.%'"
            ' GROUP BY language').fetchall()))
        self.assertEqual({language: 6 for language in LANGUAGES}, self.per_language('nations'))
        for sql in ('SELECT key, text FROM criteria_labels WHERE language = ? ORDER BY 1',
                    'SELECT id, name FROM nations WHERE language = ? ORDER BY 1'):
            self.assertEqual(self.conn.execute(sql, ('en',)).fetchall(),
                             self.conn.execute(sql, ('de',)).fetchall(), sql)

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
