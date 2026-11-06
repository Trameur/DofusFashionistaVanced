import html as html_lib
import os
import re

from django.core.cache import cache
from django.test import TestCase

from chardata import wakfu_encyclopedia_data as data
from chardata import wakfu_game_text
from chardata.official_site import _slugify_name
from chardata.wakfu_flag_for_tests import wakfu_flag

LANGUAGES = ('en', 'fr', 'es', 'pt', 'de')
SAMPLE_SIZE = 6


def slug(name):
    return _slugify_name(name, '')


class AWakfuItemShowsItsConditionsInTheGameWordingTests(TestCase):
    """The conditions of an item are the lines item_detail reads from the game's labels."""

    def setUp(self):
        cache.clear()
        if not os.path.exists(data.database_path()):
            self.skipTest('no Wakfu database built; run update_data_wakfu.py')
        self.conn = data.connect()
        self.addCleanup(self.conn.close)
        self.items = [row[0] for row in self.conn.execute(
            "SELECT c.item FROM item_criteria c JOIN items i ON i.id = c.item"
            " WHERE i.removed = 0 AND c.criteria != '' ORDER BY c.item")]

    def test_every_live_item_with_criteria_reads_a_text_without_a_token(self):
        rows = self.conn.execute(
            "SELECT c.item, c.criteria FROM item_criteria c JOIN items i ON i.id = c.item"
            " WHERE i.removed = 0 AND c.criteria != '' ORDER BY c.item").fetchall()
        self.assertTrue(rows)
        for language in LANGUAGES:
            source = wakfu_game_text.TextSource(self.conn, language)
            for item, criteria in rows:
                for condition in data._conditions(source, criteria):
                    self.assertTrue(condition.text, (language, item))
                    self.assertFalse(set('[]{}') & set(condition.text), (language, item))

    def test_a_craft_level_condition_has_a_text_in_every_language(self):
        item = self.conn.execute(
            "SELECT c.item FROM item_criteria c JOIN items i ON i.id = c.item"
            " WHERE i.removed = 0 AND c.criteria LIKE '%GetCraftLevel%' ORDER BY c.item"
        ).fetchone()[0]
        for language in LANGUAGES:
            texts = [one.text for one in data.item_detail(item, language).conditions]
            self.assertTrue(any(texts), language)

    def pages(self, language, items):
        for item in items:
            names = dict(self.conn.execute(
                'SELECT language, name FROM item_names WHERE item = ?', (item,)).fetchall())
            prefix = '' if language == 'en' else language + '/'
            path = '/%swakfu/encyclopedia/item/equipment/%d-%s/' % (
                prefix, item, slug(names['en' if language == 'de' else language]))
            with wakfu_flag(True):
                response = self.client.get(path)
            self.assertEqual(200, response.status_code, path)
            yield item, html_lib.unescape(response.content.decode('utf-8'))

    def test_a_sample_of_pages_lists_each_condition_in_the_page_language(self):
        step = max(1, len(self.items) // SAMPLE_SIZE)
        sample = self.items[::step][:SAMPLE_SIZE]
        for language in LANGUAGES:
            for item, page in self.pages(language, sample):
                found = re.search(r'class="encyclopedia-section wakfu-conditions">(.*?)</ul>',
                                  page, re.S)
                conditions = [one.text for one in data.item_detail(item, language).conditions
                              if one.text]
                if not conditions:
                    self.assertIsNone(found, (language, item))
                    continue
                self.assertIsNotNone(found, (language, item))
                for text in conditions:
                    self.assertIn(text, found.group(1), (language, item))

    def test_an_item_without_conditions_has_no_conditions_section(self):
        item = self.conn.execute(
            'SELECT i.id FROM items i WHERE i.removed = 0 AND NOT EXISTS'
            ' (SELECT 1 FROM item_criteria c WHERE c.item = i.id) ORDER BY i.id').fetchone()[0]
        for _item, page in self.pages('en', [item]):
            self.assertNotIn('wakfu-conditions', page)
