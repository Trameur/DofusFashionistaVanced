import html as html_lib
import os
import re

from django.core.cache import cache
from django.test import TestCase

from chardata import wakfu_encyclopedia_data as data
from chardata.official_site import _slugify_name
from chardata.wakfu_flag_for_tests import wakfu_flag

LANGUAGES = ('en', 'fr', 'es', 'pt', 'de')


def slug(name):
    return _slugify_name(name, '')


class AWakfuRecipeListsItsIngredientsAndJobTests(TestCase):
    """The recipe of a crafted item shows its job, each ingredient and each quantity."""

    def setUp(self):
        cache.clear()
        if not os.path.exists(data.database_path()):
            self.skipTest('no Wakfu database built; run update_data_wakfu.py')
        self.conn = data.connect()
        self.addCleanup(self.conn.close)
        self.item = self.conn.execute(
            "SELECT r.item FROM item_recipes r JOIN items i ON i.id = r.item AND i.removed = 0"
            " GROUP BY r.item HAVING SUM(r.ingredient_subtype = 'equipment') > 0"
            " AND COUNT(*) > 3 AND COUNT(*) = COUNT(DISTINCT r.ingredient_ankama_id)"
            " ORDER BY COUNT(*) DESC, r.item LIMIT 1").fetchone()[0]

    def by_language(self, sql, *args):
        return dict(self.conn.execute(sql, args).fetchall())

    def page(self, language):
        names = self.by_language('SELECT language, name FROM item_names WHERE item = ?',
                                 self.item)
        prefix = '' if language == 'en' else language + '/'
        path = '/%swakfu/encyclopedia/item/equipment/%d-%s/' % (
            prefix, self.item, slug(names['en' if language == 'de' else language]))
        with wakfu_flag(True):
            response = self.client.get(path)
        self.assertEqual(200, response.status_code, path)
        return html_lib.unescape(response.content.decode('utf-8'))

    def section(self, page):
        found = re.search(r'class="encyclopedia-section wakfu-recipe">(.*?)</ul>', page, re.S)
        self.assertIsNotNone(found)
        return found.group(1)

    def test_the_recipe_lists_every_ingredient_row_with_its_quantity(self):
        rows = self.conn.execute(
            'SELECT ingredient_ankama_id, ingredient_subtype, quantity FROM item_recipes'
            ' WHERE item = ? ORDER BY position', (self.item,)).fetchall()
        for language in LANGUAGES:
            section = self.section(self.page(language))
            self.assertEqual(len(rows), section.count('<li'), language)
            quantities = [int(one) for one in re.findall(r'<span>\s*(\d+) x\s', section)]
            self.assertEqual([quantity for _id, _subtype, quantity in rows], quantities,
                             language)

    def test_each_ingredient_is_named_in_the_page_language(self):
        rows = self.conn.execute(
            'SELECT ingredient_ankama_id, ingredient_subtype FROM item_recipes WHERE item = ?',
            (self.item,)).fetchall()
        for language in LANGUAGES:
            section = self.section(self.page(language))
            for ingredient, subtype in rows:
                names = self.by_language(
                    'SELECT language, name FROM item_recipe_ingredient_names'
                    ' WHERE ingredient_ankama_id = ? AND ingredient_subtype = ?',
                    ingredient, subtype)
                self.assertIn(names[language], section, (language, ingredient))

    def test_the_job_line_names_the_job_and_its_level(self):
        job, level = self.conn.execute(
            'SELECT job_ankama_id, level FROM item_craft_jobs WHERE item = ?',
            (self.item,)).fetchone()
        names = self.by_language('SELECT language, name FROM client_job_names WHERE job = ?',
                                 job)
        for language in LANGUAGES:
            section = self.section(self.page(language))
            self.assertIn(names[language], section, language)
            self.assertIn(str(level), section, language)

    def test_a_live_equipment_ingredient_links_its_page_and_shows_its_picture(self):
        live = self.conn.execute(
            "SELECT r.ingredient_ankama_id FROM item_recipes r JOIN items i"
            " ON i.id = r.ingredient_ankama_id AND i.removed = 0"
            " WHERE r.item = ? AND r.ingredient_subtype = 'equipment'", (self.item,)).fetchall()
        self.assertTrue(live)
        section = self.section(self.page('en'))
        for (ingredient,) in live:
            self.assertIn('/wakfu/encyclopedia/item/equipment/%d-' % ingredient, section)
        self.assertEqual(len(live), section.count('class="craft-item"'))
        self.assertEqual(len(live), section.count('<a href='))
