# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The classic design keeps the encyclopedia, compare and choose pages exactly as production renders them: their dark card rules wait for a body class that only the item page sets, so no rule of these sheets or templates may be keyed on the root dark class through the classic only selector."""
import io
import os

from django.test import SimpleTestCase

CHARDATA = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(CHARDATA, 'static', 'chardata')
TEMPLATES = os.path.join(CHARDATA, 'templates', 'chardata')
SHEETS = ('encyclopedia.css', 'encyclopedia_detail.css', 'encyclopedia_missing.css', 'compare.css', 'choose_compare_sets.css')
PAGES = ('encyclopedia_monster.html', 'encyclopedia_monsters.html', 'encyclopedia_set.html', 'encyclopedia_sets.html')
CLASSIC_DARK = ':where(html:not(.fm-modern)).fm-dark'


def read(path):
    with io.open(path, encoding='utf-8') as handle:
        return handle.read()


class TheClassicDarkEncyclopediaStaysAsProductionRendersItTests(SimpleTestCase):
    def test_no_sheet_dresses_the_classic_dark_cards_from_the_root_class(self):
        for name in SHEETS:
            with self.subTest(sheet=name):
                self.assertNotIn(CLASSIC_DARK, read(os.path.join(STATIC, name)))

    def test_no_page_style_dresses_the_classic_dark_cards_from_the_root_class(self):
        for name in PAGES:
            with self.subTest(page=name):
                self.assertNotIn(CLASSIC_DARK, read(os.path.join(TEMPLATES, name)))
