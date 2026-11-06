import html as html_lib
import os
import re

from django.core.cache import cache
from django.test import TestCase

from chardata import wakfu_encyclopedia_data as data
from chardata.wakfu_flag_for_tests import wakfu_flag

WEAPON = 32490
AMULET = 2021
USE_LINE = 'Dommage : 130'
CRITICAL_LINE = 'Dommage : 163'


class AWakfuItemPageShowsWornAndUseLinesApartTests(TestCase):
    """A weapon's damage sits in the use section and never among the lines it wears."""

    def setUp(self):
        cache.clear()
        if not os.path.exists(data.database_path()):
            self.skipTest('no Wakfu database built; run update_data_wakfu.py')

    def page(self, path):
        with wakfu_flag(True):
            response = self.client.get(path, follow=True)
        self.assertEqual(200, response.status_code)
        return html_lib.unescape(response.content.decode('utf-8'))

    def sections(self, path):
        page = self.page(path)
        worn = re.search(r'wakfu-worn-lines">(.*?)</ul>', page, re.S)
        use = re.search(r'wakfu-use-lines">(.*?)</ul>', page, re.S)
        return worn.group(1) if worn else None, use.group(1) if use else None

    def test_the_damage_line_is_in_the_use_section_only(self):
        worn, use = self.sections('/fr/wakfu/encyclopedia/item/equipment/%d-x/' % WEAPON)
        self.assertIsNotNone(worn)
        self.assertIsNotNone(use)
        self.assertIn(USE_LINE, use)
        self.assertNotIn(USE_LINE, worn)
        self.assertNotIn('Dommage', worn)

    def test_the_worn_lines_of_a_weapon_are_the_lines_it_wears(self):
        worn, _use = self.sections('/fr/wakfu/encyclopedia/item/equipment/%d-x/' % WEAPON)
        for line in data.item_detail(WEAPON, 'fr').lines:
            self.assertIn(line.text, worn)

    def test_an_item_with_no_use_effect_has_no_use_section(self):
        worn, use = self.sections('/fr/wakfu/encyclopedia/item/equipment/%d-x/' % AMULET)
        self.assertIsNotNone(worn)
        self.assertIsNone(use)

    def test_the_critical_row_is_under_its_own_heading_after_the_normal_row(self):
        path = '/fr/wakfu/encyclopedia/item/equipment/%d-x/' % WEAPON
        page = self.page(path)
        worn, use = self.sections(path)
        self.assertNotIn(CRITICAL_LINE, worn)
        self.assertNotIn(CRITICAL_LINE, use)
        marks = ('wakfu-use-lines', USE_LINE, 'wakfu-critical-use-lines', CRITICAL_LINE,
                 'wakfu-worn-lines')
        order = [page.index(mark) for mark in marks]
        self.assertEqual(sorted(order), order)

    def test_an_item_with_no_critical_row_shows_no_critical_heading(self):
        page = self.page('/fr/wakfu/encyclopedia/item/equipment/%d-x/' % AMULET)
        self.assertNotIn('wakfu-critical-use-lines', page)
        self.assertEqual((), data.item_detail(AMULET, 'fr').critical_use_lines)
