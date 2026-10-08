# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A capped trophy's page prints its version's set bonus cap, and a Prysmaradite piece its own rule."""

import html

from django.test import TestCase

MINOR_OBSTRUCTOR = 16182
MINOR_LOCKER = 12622
TOUCH_MINOR_BLOODTHIRST = 19317
PRYTEKT_O_MAT = 21451


class TheItemPagePrintsTheSetBonusCapTests(TestCase):

    def _page(self, url):
        page = self.client.get(url, follow=True)
        self.assertEqual(200, page.status_code)
        return html.unescape(page.content.decode('utf-8'))

    def test_each_version_prints_its_own_cap(self):
        pages = (
            ('/encyclopedia/item/equipment/%d-x/' % MINOR_OBSTRUCTOR,
             'Number of sets equipped < 2'),
            ('/beta/encyclopedia/item/equipment/%d-x/' % MINOR_OBSTRUCTOR,
             'Number of sets equipped < 2'),
            ('/dofus2/encyclopedia/item/equipment/%d-x/' % MINOR_OBSTRUCTOR,
             'Set bonus < 2'),
            ('/touch/encyclopedia/item/equipment/%d-x/' % TOUCH_MINOR_BLOODTHIRST,
             'Set bonus < 2'),
        )
        for url, line in pages:
            with self.subTest(url=url):
                self.assertIn(line, self._page(url))

    def test_an_uncapped_trophy_prints_no_cap(self):
        page = self._page('/beta/encyclopedia/item/equipment/%d-x/' % MINOR_LOCKER)
        self.assertNotIn('Set bonus <', page)

    def test_a_prysmaradite_piece_prints_its_rule(self):
        page = self._page('/encyclopedia/item/equipment/%d-x/' % PRYTEKT_O_MAT)
        self.assertIn('Prysmaradite < 1', page)
