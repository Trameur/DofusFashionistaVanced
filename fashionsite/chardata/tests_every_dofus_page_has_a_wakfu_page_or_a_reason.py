# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""Each named Dofus route is served on Wakfu, shared, planned for a lot, or has a reason not to."""
from django.test import SimpleTestCase

from chardata import game_urls, wakfu_urls

LOTS = {'W11', 'W12', 'W13', 'W14', 'W15', 'W16', 'W17'}


def _names(patterns):
    return {pattern.name for pattern in patterns if getattr(pattern, 'name', None)}


class EveryDofusPageHasAWakfuPageOrAReasonTests(SimpleTestCase):
    def setUp(self):
        self.dofus = _names(game_urls.urlpatterns)
        self.tables = {
            'served': _names(wakfu_urls.urlpatterns),
            'site': set(wakfu_urls.WAKFU_SITE_ROUTES),
            'planned': set(wakfu_urls.WAKFU_PLANNED),
            'not applicable': set(wakfu_urls.WAKFU_NOT_APPLICABLE),
        }

    def test_every_dofus_route_name_is_in_exactly_one_table(self):
        for name in sorted(self.dofus):
            homes = [table for table, names in self.tables.items() if name in names]
            self.assertEqual(1, len(homes), '%s is in %s' % (name, homes or 'no table'))

    def test_no_table_lists_a_name_the_dofus_routes_lack(self):
        for table, names in self.tables.items():
            self.assertEqual([], sorted(names - self.dofus), table)

    def test_every_reason_is_written_and_every_lot_is_a_known_one(self):
        for table in (wakfu_urls.WAKFU_SITE_ROUTES, wakfu_urls.WAKFU_NOT_APPLICABLE):
            for name, reason in table.items():
                self.assertTrue(reason.strip(), name)
        for name, lot in wakfu_urls.WAKFU_PLANNED.items():
            self.assertIn(lot, LOTS, name)

    def test_the_counts_are_printed(self):
        print('dofus route names %d: served %d, site %d, planned %d, not applicable %d' % (
            len(self.dofus), *(len(names) for names in self.tables.values())))
        self.assertEqual(len(self.dofus), sum(len(names) for names in self.tables.values()))
