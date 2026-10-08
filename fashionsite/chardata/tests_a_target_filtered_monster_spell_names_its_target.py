# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A monster spell row the client limits to one monster (F<id>) or keeps off one
(f<id>) names that monster."""
import html
import sqlite3

from django.test import SimpleTestCase, TestCase

from chardata.tests import itemscraper_module
from fashionistapulp.fashionista_config import get_items_db_path

VERSIONS = ('dofus3', 'beta')
LANGUAGES = ('en', 'fr', 'es', 'pt', 'de')
MURDEROUS_BEAR = 5271
ARTAND = 5272
SPLIT_BLOW = 10291
DAMAGE = 98
PUSH = 5
NAMES = {ARTAND: 'Artand', 31: 'Blue Larva'}
TEXTS = {'4': '#1{{~1~2 to }}#2 Neutral damage', '5': 'Pushes back #1 cells'}
EFFECTS = {DAMAGE: {'descriptionId': 4}, PUSH: {'descriptionId': 5}}


def _storer():
    return itemscraper_module('store_monster_spells')


def _row(effect_id, low, high, mask):
    return {'actionId': effect_id, 'diceNum': low, 'diceSide': high, 'targetMask': mask}


def _rows(version, sql, params=()):
    conn = sqlite3.connect(get_items_db_path(version))
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


class TargetMaskTests(SimpleTestCase):

    def test_an_upper_f_names_the_only_target(self):
        target_monsters = _storer().target_monsters
        self.assertEqual('Artand', target_monsters('F%d' % ARTAND, NAMES, 'en'))
        self.assertEqual('Artand, Blue Larva',
                         target_monsters('a,F%d,F31,F%d' % (ARTAND, ARTAND), NAMES, 'en'))

    def test_a_lower_f_names_the_monster_left_out_in_each_language(self):
        target_monsters = _storer().target_monsters
        for language, word in (('en', 'except'), ('fr', 'sauf'), ('es', 'excepto'),
                               ('pt', 'exceto'), ('de', 'außer')):
            with self.subTest(language=language):
                self.assertEqual('%s Artand' % word,
                                 target_monsters('A,f%d' % ARTAND, NAMES, language))

    def test_a_mask_without_a_named_monster_names_nothing(self):
        target_monsters = _storer().target_monsters
        for mask in ('a,A', '', None, 'F99999', '*F%d' % ARTAND):
            with self.subTest(mask=mask):
                self.assertIsNone(target_monsters(mask, NAMES, 'en'))

    def test_rows_are_grouped_under_the_monsters_they_target(self):
        storer = _storer()
        level = {'grade': 1, 'effects': {'Array': [
            _row(DAMAGE, 81, 110, 'F%d' % ARTAND), _row(PUSH, 1, 0, 'a,A'),
            _row(DAMAGE, 11, 20, 'A,f%d' % ARTAND), _row(PUSH, 2, 0, 'F%d' % ARTAND)]}}
        self.assertEqual('Artand: 81 to 110 Neutral damage, Pushes back 2 cells; '
                         'Pushes back 1 cells; except Artand: 11 to 20 Neutral damage',
                         storer.grade_description(level, EFFECTS, TEXTS, NAMES, 'en'))
        self.assertEqual('Artand : 81 to 110 Neutral damage, Pushes back 2 cells ; '
                         'Pushes back 1 cells ; sauf Artand : 11 to 20 Neutral damage',
                         storer.grade_description(level, EFFECTS, TEXTS, NAMES, 'fr'))

    def test_a_description_opening_on_a_spared_monster_starts_with_a_capital(self):
        level = {'grade': 1, 'effects': {'Array': [_row(DAMAGE, 11, 20, 'A,f%d' % ARTAND)]}}
        self.assertEqual('Except Artand: 11 to 20 Neutral damage',
                         _storer().grade_description(level, EFFECTS, TEXTS, NAMES, 'en'))

    def test_a_row_limited_to_monsters_the_client_lacks_is_left_out(self):
        storer = _storer()
        level = {'grade': 1, 'effects': {'Array': [
            _row(DAMAGE, 81, 110, 'A,F99999'), _row(PUSH, 1, 0, 'a,A'),
            _row(DAMAGE, 11, 20, 'A,F99999,F%d' % ARTAND)]}}
        self.assertEqual('Pushes back 1 cells; Artand: 11 to 20 Neutral damage',
                         storer.grade_description(level, EFFECTS, TEXTS, NAMES, 'en'))


class StoredTargetTests(SimpleTestCase):

    def test_a_target_filtered_monster_spell_names_its_target(self):
        storer = _storer()
        for version in VERSIONS:
            names = dict(_rows(version, 'SELECT language, name FROM monster_names '
                                        'WHERE monster_ankama_id = ?', (ARTAND,)))
            stored = dict(_rows(version, 'SELECT language, description FROM monster_spell_names '
                                         'WHERE spell_ankama_id = ?', (SPLIT_BLOW,)))
            for language in LANGUAGES:
                colon, semicolon = storer._SEPARATORS.get(language, storer._DEFAULT_SEPARATORS)
                with self.subTest(version=version, language=language):
                    self.assertTrue(stored[language].startswith(names[language] + colon),
                                    stored[language])
                    self.assertIn('%s%s %s%s' % (semicolon, storer._EXCEPT[language],
                                                 names[language], colon), stored[language])


class TargetPageTests(TestCase):

    def test_the_monster_page_names_the_target(self):
        from chardata.official_site import get_monster_link
        for version in VERSIONS:
            name = _rows(version, "SELECT name FROM monster_names WHERE monster_ankama_id = ? "
                                  "AND language = 'en'", (MURDEROUS_BEAR,))[0][0]
            response = self.client.get(get_monster_link(MURDEROUS_BEAR, name, version))
            page = html.unescape(response.content.decode('utf-8'))
            with self.subTest(version=version):
                self.assertEqual(200, response.status_code)
                self.assertIn('Artand: 81 to 110 Neutral damage; except Artand: ', page)
