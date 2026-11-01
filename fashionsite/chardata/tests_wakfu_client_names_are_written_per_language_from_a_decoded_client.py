import collections
import contextlib
import io
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from unittest import TestCase

SCRAPER = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), 'itemscraper')
if SCRAPER not in sys.path:
    sys.path.insert(0, SCRAPER)

import build_wakfu_db as builder  # noqa: E402
from chardata.tests_wakfu_effect_groups_resolve_to_known_effects import (  # noqa: E402
    effect, tables)
from fashionistapulp import wakfu_db  # noqa: E402

TEXT_TABLES = (
    'state_texts', 'client_spell_texts', 'client_set_names', 'client_monster_names',
    'monster_family_names', 'ability_names', 'ability_category_names', 'effect_texts',
    'action_texts')
FAMILIES = (
    'spell_names', 'spell_descriptions', 'monster_names', 'state_names', 'state_descriptions',
    'action_texts', 'set_names', 'effect_texts', 'monster_family_names', 'ability_names',
    'ability_category_names', 'job_names', 'breed_names', 'breed_texts', 'aptitude_texts',
    'enchantment_texts', 'item_type_names')


def texts(**families):
    """A texts.json payload: {family: {language: {str id: text}}}."""
    body = {family: {} for family in FAMILIES}
    for family, by_language in families.items():
        body[family] = {language: {str(ident): text for ident, text in table.items()}
                        for language, table in by_language.items()}
    return {'client_version': '6.0_1.0.0.1.1', 'game_version': '1.0.0', 'texts': body}


class TheWakfuClientNamesAreWrittenPerLanguageFromADecodedClientTests(TestCase):
    def conn(self):
        conn = sqlite3.connect(':memory:')
        self.addCleanup(conn.close)
        wakfu_db.create_tables(conn)
        return conn

    def parents(self, conn, states=(), spells=(), sets=(), monsters=(), abilities=(),
                categories=(), effects=()):
        for ident in states:
            conn.execute('INSERT INTO states (id, key) VALUES (?, ?)', (ident, 'k'))
        for ident in spells:
            conn.execute('INSERT INTO client_spells (id) VALUES (?)', (ident,))
        for ident in sets:
            conn.execute('INSERT INTO client_sets (id, item_count) VALUES (?, 1)', (ident,))
        for ident, family in monsters:
            conn.execute('INSERT INTO monsters (id, family) VALUES (?, ?)', (ident, family))
        for ident in categories:
            conn.execute('INSERT INTO ability_categories (id) VALUES (?)', (ident,))
        for ident, category in abilities:
            conn.execute('INSERT INTO abilities (id, category) VALUES (?, ?)',
                         (ident, category))
        for ident, action in effects:
            conn.execute('INSERT INTO effects (id, action) VALUES (?, ?)', (ident, action))

    def write(self, conn, payload):
        counts = collections.Counter()
        builder.write_client_texts(conn, payload, counts)
        return counts

    def rows(self, conn, query):
        return conn.execute(query).fetchall()

    def test_a_text_pairs_with_its_row_by_id_and_german_is_the_english_text(self):
        conn = self.conn()
        self.parents(conn, states=(1, 2, 3))
        self.write(conn, texts(
            state_names={'fr': {1: 'un', 2: 'deux'}, 'en': {2: 'two', 3: 'three'}}))
        by_language = {
            language: self.rows(conn, "SELECT state, name FROM state_texts"
                                      " WHERE language = '%s' ORDER BY state" % language)
            for language in builder.LANGUAGES}
        self.assertEqual([(1, 'un'), (2, 'deux')], by_language['fr'])
        self.assertEqual([(2, 'two'), (3, 'three')], by_language['en'])
        self.assertEqual(by_language['en'], by_language['de'])
        self.assertEqual([], by_language['es'] + by_language['pt'])

    def test_a_text_only_another_language_has_gets_no_german_row(self):
        conn = self.conn()
        self.parents(conn, states=(1,))
        self.write(conn, texts(state_names={'es': {1: 'uno'}}))
        self.assertEqual([('es',)], self.rows(conn, 'SELECT language FROM state_texts'))

    def test_german_is_never_copied_from_french(self):
        conn = self.conn()
        self.parents(conn, sets=(7,))
        self.write(conn, texts(set_names={'fr': {7: 'Panoplie'}}))
        self.assertEqual([('fr', 'Panoplie')], self.rows(
            conn, 'SELECT language, name FROM client_set_names'))

    def test_a_text_whose_id_has_no_row_is_not_written_but_is_counted(self):
        conn = self.conn()
        self.parents(conn, spells=(1,))
        counts = self.write(conn, texts(
            spell_names={'fr': {1: 'un', 9: 'neuf', 10: 'dix'}, 'en': {9: 'nine'}},
            spell_descriptions={'fr': {8: 'huit'}}))
        self.assertEqual([1], [one[0] for one in self.rows(
            conn, 'SELECT DISTINCT spell FROM client_spell_texts')])
        self.assertEqual(2, counts['texts naming no row: spell_names'])
        self.assertEqual(1, counts['texts naming no row: spell_descriptions'])
        self.assertEqual(1, counts['client spell texts'])

    def test_a_description_without_a_name_gives_a_row_with_no_name(self):
        conn = self.conn()
        self.parents(conn, states=(4, 5))
        self.write(conn, texts(
            state_names={'en': {4: 'Four'}},
            state_descriptions={'en': {4: 'about four', 5: 'about five'}}))
        self.assertEqual(
            [(4, 'Four', 'about four'), (5, None, 'about five')],
            self.rows(conn, "SELECT state, name, description FROM state_texts"
                            " WHERE language = 'en' ORDER BY state"))

    def test_a_monster_family_and_an_action_are_written_only_when_something_stored_uses_it(self):
        conn = self.conn()
        self.parents(conn, monsters=((1, 68), (2, 68)), effects=((10, 20), (11, 20), (12, 21)))
        counts = self.write(conn, texts(
            monster_family_names={'en': {68: 'Gobballs', 69: 'Bouftous'}},
            action_texts={'en': {20: 'Damage', 21: 'Heal', 22: 'Never stored'}},
            monster_names={'en': {1: 'one', 2: 'two'}}))
        self.assertEqual([(68, 'Gobballs')], self.rows(
            conn, "SELECT family, name FROM monster_family_names WHERE language = 'en'"))
        self.assertEqual([(20, 'Damage'), (21, 'Heal')], self.rows(
            conn, "SELECT action, text FROM action_texts WHERE language = 'en' ORDER BY action"))
        self.assertEqual(1, counts['texts naming no row: monster_family_names'])
        self.assertEqual(1, counts['texts naming no row: action_texts'])

    def test_an_effect_text_is_written_only_for_a_stored_effect(self):
        conn = self.conn()
        self.parents(conn, effects=((10, 20),))
        self.write(conn, texts(effect_texts={'fr': {10: 'a\nb', 11: 'lost'}}))
        self.assertEqual([('fr', 10, 'a\nb')], self.rows(
            conn, 'SELECT language, effect, text FROM effect_texts'))

    def test_the_abilities_and_their_categories_are_named_through_their_own_ids(self):
        conn = self.conn()
        self.parents(conn, categories=(2,), abilities=((1, 2),))
        self.write(conn, texts(
            ability_names={'fr': {1: 'Force', 24: 'no ability'}},
            ability_category_names={'fr': {2: 'Cat'}}))
        self.assertEqual([(1, 'Force')], self.rows(
            conn, 'SELECT ability, name FROM ability_names'))
        self.assertEqual([(2, 'Cat')], self.rows(
            conn, 'SELECT category, name FROM ability_category_names'))
        self.assertEqual([], self.rows(conn, 'PRAGMA foreign_key_check'))

    def test_no_foreign_key_is_broken_by_any_table(self):
        conn = self.conn()
        self.parents(conn, states=(1,), spells=(2,), sets=(3,), monsters=((4, 5),),
                     categories=(6,), abilities=((7, 6),), effects=((8, 9),))
        every = {family: {'en': {i: 'x' for i in range(1, 11)}} for family in FAMILIES}
        self.write(conn, texts(**every))
        for table in TEXT_TABLES:
            self.assertGreater(conn.execute('SELECT COUNT(*) FROM %s' % table).fetchone()[0],
                               0, table)
        self.assertEqual([], self.rows(conn, 'PRAGMA foreign_key_check'))

    def test_the_fallback_names_only_german(self):
        self.assertEqual({'de': 'en'}, builder.CLIENT_TEXT_FALLBACK)

    def test_an_item_type_is_written_with_german_from_english(self):
        conn = self.conn()
        self.write(conn, texts(item_type_names={'fr': {100: 'Arme'}, 'en': {100: 'Weapon'}}))
        self.assertEqual(
            [('de', 100, 'Weapon'), ('en', 100, 'Weapon'), ('fr', 100, 'Arme')],
            self.rows(conn, 'SELECT language, item_type, name FROM client_item_type_names'
                            ' ORDER BY language'))

    def test_a_job_a_class_and_a_key_are_written_with_no_parent_row_and_german_is_english(self):
        conn = self.conn()
        counts = self.write(conn, texts(
            job_names={'fr': {40: 'Boulanger', 41: 'Autre'}, 'en': {40: 'Baker'}},
            breed_names={'fr': {17: 'Inconnu'}, 'en': {17: 'Unknown'}},
            breed_texts={'en': {'breed.difficulty': 'Difficulty'}},
            aptitude_texts={'fr': {'aptitude.common.title': 'Aptitudes'}},
            enchantment_texts={'en': {'enchantment.x.y': 'Socket'}}))
        self.assertEqual(
            [('de', 40, 'Baker'), ('en', 40, 'Baker'), ('fr', 40, 'Boulanger'),
             ('fr', 41, 'Autre')],
            self.rows(conn, 'SELECT language, job, name FROM client_job_names'
                            ' ORDER BY job, language'))
        self.assertEqual(
            [('de', 17, 'Unknown'), ('en', 17, 'Unknown'), ('fr', 17, 'Inconnu')],
            self.rows(conn, 'SELECT language, breed, name FROM client_breed_names'
                            ' ORDER BY language'))
        self.assertEqual(
            [('de', 'breed.difficulty', 'Difficulty'), ('en', 'breed.difficulty', 'Difficulty')],
            self.rows(conn, 'SELECT language, key, text FROM client_breed_texts'
                            ' ORDER BY language'))
        self.assertEqual([('fr', 'aptitude.common.title', 'Aptitudes')], self.rows(
            conn, 'SELECT language, key, text FROM client_aptitude_texts'))
        self.assertEqual(['de', 'en'], [one[0] for one in self.rows(
            conn, 'SELECT language FROM client_enchantment_texts ORDER BY language')])
        self.assertEqual(4 + 3 + 2 + 1 + 2, sum(
            counts[table] for table in (
                'client job names', 'client breed names', 'client breed texts',
                'client aptitude texts', 'client enchantment texts')))

    def test_a_family_the_texts_file_lacks_is_counted_and_leaves_its_table_empty(self):
        conn = self.conn()
        payload = texts(job_names={'en': {40: 'Baker'}})
        del payload['texts']['breed_texts']
        counts = collections.Counter()
        builder.write_client_texts(conn, payload, counts)
        self.assertEqual(1, counts['texts family missing: breed_texts'])
        self.assertEqual([], self.rows(conn, 'SELECT * FROM client_breed_texts'))
        self.assertEqual(2, conn.execute('SELECT COUNT(*) FROM client_job_names').fetchone()[0])

    def test_the_labels_and_nations_get_german_from_english_and_never_from_french(self):
        conn = self.conn()
        counts = collections.Counter()
        builder.write_labels(conn, {
            'labels': {'fr': {'critere.a': 'a fr', 'critere.b': 'b fr'},
                       'en': {'critere.a': 'a en'}},
            'nations': {'fr': {'3': 'Brakmar fr'}, 'en': {'3': 'Brakmar'}}}, counts)
        self.assertEqual(
            [('critere.a', 'a en'), ('critere.a', 'a fr'), ('critere.b', 'b fr')],
            sorted((key, text) for key, language, text in self.rows(
                conn, 'SELECT key, language, text FROM criteria_labels')
                if language != 'de'))
        self.assertEqual([('critere.a', 'a en')], self.rows(
            conn, "SELECT key, text FROM criteria_labels WHERE language = 'de'"))
        self.assertEqual([(3, 'Brakmar')], self.rows(
            conn, "SELECT id, name FROM nations WHERE language = 'de'"))

    def test_the_dump_of_the_caller_is_not_changed(self):
        dump = {'labels': {'en': {'critere.a': 'a en'}}, 'nations': {'en': {'3': 'Brakmar'}}}
        builder.write_labels(self.conn(), dump, collections.Counter())
        self.assertEqual({'labels': {'en': {'critere.a': 'a en'}},
                          'nations': {'en': {'3': 'Brakmar'}}}, dump)

    def test_a_german_the_dump_already_has_is_kept(self):
        conn = self.conn()
        builder.write_labels(conn, {
            'labels': {'en': {'critere.a': 'a en'}, 'de': {'critere.a': 'a de'}}},
            collections.Counter())
        self.assertEqual([('a de',)], self.rows(
            conn, "SELECT text FROM criteria_labels WHERE language = 'de'"))


class TheWakfuBuildReadsTheClientTextsBesideTheTablesTests(TestCase):
    def setUp(self):
        if not builder.DOFUS_DB.exists():
            self.skipTest('items.db absent, the Wakfu schema is copied from it')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.client = self.directory / 'client' / '6.0_1.0.0.1.1'
        self.client.mkdir(parents=True)
        payload = tables([], [], states=[
            {'id': 5, 'bcw': 'state5', 'effect_ids': [], 'max_level': 1,
                'cumulable': False}])
        payload['game_version'] = '1.0'
        (self.client / 'tables.json').write_text(json.dumps(payload), encoding='utf-8')
        self.db = self.directory / 'items_wakfu.db'

    def build(self):
        dump = self.directory / 'transformed_wakfu.json'
        dump.write_text(json.dumps({'version': '1.0', 'equipment': []}), encoding='utf-8')
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            builder.main(['--dump', str(dump), '--db', str(self.db),
                          '--out', str(self.directory / 'raw'),
                          '--client', str(self.directory / 'client')])
        return output.getvalue()

    def stored(self):
        conn = sqlite3.connect(self.db)
        try:
            return {table: conn.execute('SELECT COUNT(*) FROM %s' % table).fetchone()[0]
                    for table in TEXT_TABLES}
        finally:
            conn.close()

    def test_without_texts_json_the_nine_tables_stay_empty_and_the_build_says_so(self):
        output = self.build()
        self.assertIn('client texts not found for 1.0 under', output)
        self.assertIn('the name tables stay empty', output)
        self.assertEqual({table: 0 for table in TEXT_TABLES}, self.stored())

    def test_texts_of_another_game_version_are_not_paired(self):
        payload = texts(state_names={'en': {5: 'Five'}})
        payload['game_version'] = '2.0'
        (self.client / 'texts.json').write_text(json.dumps(payload), encoding='utf-8')
        output = self.build()
        self.assertIn('client texts not found', output)
        self.assertEqual(0, self.stored()['state_texts'])

    def test_texts_of_the_same_game_version_fill_the_tables(self):
        payload = texts(state_names={'en': {5: 'Five'}})
        payload['game_version'] = '1.0'
        (self.client / 'texts.json').write_text(json.dumps(payload), encoding='utf-8')
        output = self.build()
        self.assertNotIn('client texts not found', output)
        self.assertEqual(2, self.stored()['state_texts'])
        conn = sqlite3.connect(self.db)
        try:
            self.assertEqual([], conn.execute('PRAGMA foreign_key_check').fetchall())
        finally:
            conn.close()
