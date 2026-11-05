import os

from django.test import SimpleTestCase

from chardata import wakfu_encyclopedia_data as data
from chardata import wakfu_game_text

LANGUAGES = ('fr', 'en', 'es', 'pt', 'de')
NAMELESS_FUNCTIONS = ('name:GetInstanceId', 'name:IsAchievementComplete')


class WakfuConditionsRenderInTheGamesWordsTests(SimpleTestCase):
    """Each condition of a live item has a text from the game's labels, or a named missing source."""

    def setUp(self):
        if not os.path.exists(data.database_path()):
            self.skipTest('no Wakfu database built; run update_data_wakfu.py')
        self.conn = data.connect()
        self.addCleanup(self.conn.close)
        self.rows = self.conn.execute(
            'SELECT c.item, c.criteria FROM item_criteria c JOIN items i ON i.id = c.item'
            ' WHERE i.removed = 0').fetchall()

    def test_every_live_item_condition_renders_without_a_template_token(self):
        self.assertTrue(self.rows)
        for language in LANGUAGES:
            source = wakfu_game_text.TextSource(self.conn, language)
            for item, criteria in self.rows:
                lines = wakfu_game_text.condition_lines(source, criteria)
                with self.subTest(language=language, item=item):
                    self.assertTrue(lines)
                    for line in lines:
                        self.assertTrue(line.text.strip())
                        self.assertFalse(set('[]{}') & set(line.text), line.text)

    def test_a_condition_lacks_a_label_only_for_an_id_with_no_name_source(self):
        source = wakfu_game_text.TextSource(self.conn, 'fr')
        for item, criteria in self.rows:
            for line in wakfu_game_text.condition_lines(source, criteria):
                for reason in line.missing:
                    with self.subTest(item=item):
                        self.assertIn(reason, NAMELESS_FUNCTIONS)

    def test_a_condition_with_an_id_that_has_no_name_source_shows_no_raw_id(self):
        source = wakfu_game_text.TextSource(self.conn, 'fr')
        checked = 0
        for item, criteria in self.rows:
            for line in wakfu_game_text.condition_lines(source, criteria):
                if any(reason in NAMELESS_FUNCTIONS for reason in line.missing):
                    checked += 1
                    with self.subTest(item=item):
                        self.assertFalse(any(ch.isdigit() for ch in line.text), line.text)
        self.assertTrue(checked)

    def test_a_condition_renders_without_a_language_fallback(self):
        for language in LANGUAGES:
            source = wakfu_game_text.TextSource(self.conn, language)
            for _item, criteria in self.rows:
                wakfu_game_text.condition_lines(source, criteria)
            self.assertEqual(source.fallbacks, set(), language)

    def test_an_item_detail_carries_the_conditions_of_its_criterion(self):
        for item, criteria in self.rows:
            source = wakfu_game_text.TextSource(self.conn, 'fr')
            expected = tuple(wakfu_game_text.condition_lines(source, criteria))
            self.assertEqual(data.item_detail(item, 'fr').conditions, expected)

    def test_an_empty_criterion_has_no_condition(self):
        source = wakfu_game_text.TextSource(self.conn, 'fr')
        self.assertEqual(wakfu_game_text.condition_lines(source, ''), [])
        self.assertEqual(wakfu_game_text.condition_lines(source, None), [])
