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

    def test_a_state_line_prints_the_state_name_then_its_level(self):
        self.assertEqual(self.texts(29420)[-1], "Pacte d'Anathar I (Niv. 1)")
        self.assertEqual(self.texts(32351)[0], 'Dofus Ébène (Niv. 1)')

    def test_a_resistance_header_precedes_the_element_lines_it_sums(self):
        lines = self.texts(29439)
        start = lines.index('17 Résistance')
        self.assertEqual(lines[start:start + 4], [
            '17 Résistance', '17 Résistance Eau', '17 Résistance Terre',
            '17 Résistance Air'])

    def test_a_mastery_header_precedes_the_element_lines_it_sums(self):
        item = self.item_with_a_merged_mastery_line()
        lines = self.texts(item)
        header = next(index for index, text in enumerate(lines)
                      if re.fullmatch(r'\d+ Maîtrise', text))
        value = lines[header].split()[0]
        self.assertTrue(lines[header + 1].startswith(value + ' Maîtrise '), lines)
        self.assertTrue(lines[header + 2].startswith(value + ' Maîtrise '), lines)

    def test_a_single_element_line_beside_a_group_gets_no_header(self):
        lines = self.texts(19892)
        self.assertIn('67 Résistance Feu', lines)
        self.assertNotIn('67 Résistance', lines)

    def item_with_a_merged_mastery_line(self):
        conn = data.connect()
        try:
            for (item,) in conn.execute(
                    "SELECT e.container FROM effects e JOIN items i ON i.id = e.container"
                    " WHERE e.container_type = 'ITEM_EQUIP' AND e.display != 0"
                    " AND i.removed = 0 AND e.action IN (122, 123, 124, 125)"
                    " GROUP BY e.container, e.params HAVING COUNT(*) > 1"):
                return item
        finally:
            conn.close()
        self.fail('no live item with two mastery lines of one value')

    def use_texts(self, item_id, language='fr'):
        return [line.text for line in data.item_detail(item_id, language).use_lines]

    def test_a_weapon_prints_its_damage_line(self):
        self.assertEqual(self.use_texts(32333), ['Dommage : 114'])

    def test_a_weapon_with_an_area_prints_its_damage_line_without_the_area(self):
        self.assertEqual(self.use_texts(32490), ['Dommage : 130'])
        self.assertEqual(self.use_texts(32491), ['Dommage : 130'])

    def test_the_critical_row_of_a_weapon_stays_hidden(self):
        conn = data.connect()
        try:
            critical = conn.execute(
                "SELECT COUNT(*) FROM effects WHERE container_type = 'ITEM_USE'"
                " AND container = 32490 AND normal_or_critical = 'CRITICAL'").fetchone()[0]
        finally:
            conn.close()
        self.assertGreater(critical, 0)
        self.assertEqual(len(self.use_texts(32490)), 1)

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
