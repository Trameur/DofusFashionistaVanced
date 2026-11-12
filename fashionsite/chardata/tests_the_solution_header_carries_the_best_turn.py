# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The build header on the solution page shows the same best turn and score as the stats panel, and holds the page's actions."""

import re

from django.test import TestCase

HEAD = re.compile(r'<header[^>]*fm-sol-head[^>]*>(.*?)</header>', re.S)
ROW = re.compile(r'<tr[^>]*solution-best-turn-row[^>]*>(.*?)</tr>', re.S)
LINK_TEXT = re.compile(r'<a[^>]*>\s*(\d+)\s*</a>')


class TheHeaderMatchesThePanelTests(TestCase):

    def setUp(self):
        from django.contrib.auth.models import User
        self.owner = User.objects.create_user('owner', 'o@x.test', 'pw')
        self.client.force_login(self.owner)

    def _page(self):
        from chardata.models import Char
        from fashionistapulp.structure import get_structure, set_current_game_version
        set_current_game_version('dofus3')
        structure = get_structure('dofus3')
        names = []
        for type_name in ('Hat', 'Cloak', 'Belt', 'Boots', 'Amulet'):
            item = next(i for i in structure.types[200][type_name] if not i.removed and i.ankama_id)
            names.append(structure.get_item_name_in_language(item, 'en'))
        self.client.post('/import/text/', {'text': '\n'.join(names), 'confirm': '1',
                                           'char_class': 'Cra', 'level': '200'})
        char = Char.objects.order_by('-id').first()
        return self.client.get('/solution/%d/' % char.id, follow=True).content.decode('utf-8')

    def test_the_header_best_turn_is_the_panel_best_turn(self):
        page = self._page()
        head = HEAD.search(page)
        row = ROW.search(page)
        self.assertIsNotNone(head)
        if row is None:
            self.assertNotIn('Best turn', head.group(1))
            return
        in_panel = LINK_TEXT.search(row.group(1))
        in_head = LINK_TEXT.search(head.group(1))
        self.assertIsNotNone(in_panel)
        self.assertIsNotNone(in_head)
        self.assertEqual(in_panel.group(1), in_head.group(1))

    def test_the_header_has_one_slot_for_each_figure_the_script_fills(self):
        head = HEAD.search(self._page()).group(1)
        for key in ('ap', 'mp', 'range', 'hp'):
            with self.subTest(key=key):
                self.assertIn('data-fm-stat="%s"' % key, head)

    def test_the_stat_cells_the_header_reads_exist_once(self):
        page = self._page()
        for key in ('ap', 'mp', 'range', 'hp'):
            with self.subTest(key=key):
                self.assertEqual(1, len(re.findall(r'name="stat_value_%s"' % key, page)))

    def test_the_page_has_one_header_and_one_doll_figure(self):
        page = self._page()
        self.assertEqual(1, len(re.findall(r'<header[^>]*fm-sol-head', page)))
        self.assertEqual(1, len(re.findall(r'class="fm-sol-figure"', page)))
        self.assertEqual(1, len(re.findall(r'id="item-container-hat"', page)))
