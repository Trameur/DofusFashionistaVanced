import os

from django.test import SimpleTestCase

from chardata import wakfu_encyclopedia_data as data


class WakfuItemDetailKeepsUseLinesApartFromWornLinesTests(SimpleTestCase):
    """An item's worn lines and its use lines are cached apart and never swap places."""

    def setUp(self):
        if not os.path.exists(data.database_path()):
            self.skipTest('no Wakfu database built; run update_data_wakfu.py')

    def test_the_two_line_sets_of_a_weapon_differ_and_stay_stable_when_read_again(self):
        first = data.item_detail(32490, 'fr')
        second = data.item_detail(32490, 'fr')
        self.assertTrue(first.lines)
        self.assertTrue(first.use_lines)
        self.assertNotEqual(first.lines, first.use_lines)
        self.assertEqual(first.lines, second.lines)
        self.assertEqual(first.use_lines, second.use_lines)
        self.assertTrue(first.critical_use_lines)
        self.assertNotEqual(first.use_lines, first.critical_use_lines)
        self.assertEqual(first.critical_use_lines, second.critical_use_lines)

    def test_the_use_lines_of_each_language_keep_their_own_language(self):
        texts = {language: [line.text for line in data.item_detail(32490, language).use_lines]
                 for language in ('fr', 'en')}
        self.assertEqual(texts['fr'], ['Dommage : 130'])
        self.assertEqual(texts['en'], ['Damage: 130'])

    def test_the_critical_use_lines_of_each_language_keep_their_own_language(self):
        texts = {language: [line.text for line in
                            data.item_detail(32490, language).critical_use_lines]
                 for language in ('fr', 'en')}
        self.assertEqual(texts['fr'], ['Dommage : 163'])
        self.assertEqual(texts['en'], ['Damage: 163'])

    def test_an_item_with_no_use_effect_has_no_use_line(self):
        conn = data.connect()
        try:
            item = conn.execute(
                "SELECT i.id FROM items i WHERE i.removed = 0 AND NOT EXISTS (SELECT 1 FROM"
                " effects e WHERE e.container_type = 'ITEM_USE' AND e.container = i.id)"
                " LIMIT 1").fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(data.item_detail(item, 'fr').use_lines, ())
        self.assertEqual(data.item_detail(item, 'fr').critical_use_lines, ())
