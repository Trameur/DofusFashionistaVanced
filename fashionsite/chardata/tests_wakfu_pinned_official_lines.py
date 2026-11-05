import os
import re

from django.test import SimpleTestCase

from chardata import wakfu_encyclopedia_data as data


class WakfuPinnedOfficialLinesTests(SimpleTestCase):
    """Lines the official site prints for a few items are what the renderer prints."""

    def setUp(self):
        if not os.path.exists(data.database_path()):
            self.skipTest('no Wakfu database built; run update_data_wakfu.py')

    def texts(self, item_id, language='fr'):
        return [line.text for line in data.item_detail(item_id, language).lines]

    def test_the_amulet_with_four_plain_stats_prints_them_in_the_games_order(self):
        self.assertEqual(self.texts(2021),
                         ['1 PA', '6 PV', '2 % Coup critique', '9 Maîtrise Élémentaire'])

    def test_a_mastery_line_on_two_random_elements_names_the_count(self):
        self.assertIn('263 Maîtrise sur 2 éléments', self.texts(32478))

    def test_a_mastery_line_on_three_random_elements_names_the_count(self):
        self.assertIn('200 Maîtrise sur 3 éléments', self.texts(32490))
        self.assertIn('200 Maîtrise sur 3 éléments', self.texts(32617))
        self.assertIn('200 Maîtrise sur 3 éléments', self.texts(32618))

    def test_a_negative_mastery_keeps_its_sign(self):
        self.assertIn('-400 Maîtrise Berserk', self.texts(32490))

    def test_a_health_loss_effect_prints_a_negative_amount_with_the_plural_label(self):
        self.assertEqual(self.texts(6583)[-1], '-15 Points de Vie')
        self.assertEqual(self.texts(6583, 'en')[-1], '-15 Health Points')
        self.assertEqual(self.texts(6583, 'es')[-1], '-15 puntos de vida')
        self.assertEqual(self.texts(6583, 'pt')[-1], '-15 Pontos de Vida')

    def test_every_health_loss_line_follows_the_same_shape(self):
        conn = data.connect()
        try:
            rows = conn.execute(
                "SELECT DISTINCT e.container FROM effects e JOIN items i ON i.id = e.container"
                " WHERE e.action = 21 AND e.container_type = 'ITEM_EQUIP' AND e.display != 0"
                " AND i.removed = 0").fetchall()
        finally:
            conn.close()
        self.assertTrue(rows)
        shape = re.compile(r'^-\d+ Points de Vie$')
        for (item_id,) in rows:
            self.assertTrue(any(shape.match(text) for text in self.texts(item_id)), item_id)
