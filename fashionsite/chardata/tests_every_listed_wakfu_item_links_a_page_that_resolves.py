# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""Each live Wakfu item has a page address that reverses and resolves to its page."""
import os

from django.test import SimpleTestCase
from django.urls import resolve, reverse
from django.utils import translation

from chardata import wakfu_encyclopedia_data as data
from chardata.official_site import _slugify_name
from chardata.wakfu_flag_for_tests import wakfu_flag


class EveryListedWakfuItemLinksAPageThatResolvesTests(SimpleTestCase):
    def setUp(self):
        if not os.path.exists(data.database_path()):
            self.skipTest('no Wakfu database built; run update_data_wakfu.py')
        self.conn = data.connect()
        self.addCleanup(self.conn.close)

    def test_every_live_item_reverses_to_an_address_that_resolves_to_it(self):
        rows = self.conn.execute(
            "SELECT i.id, n.name FROM items i JOIN item_names n ON n.item = i.id"
            " WHERE i.removed = 0 AND n.language = 'en' ORDER BY i.id").fetchall()
        self.assertEqual(self.conn.execute(
            'SELECT COUNT(*) FROM items WHERE removed = 0').fetchone()[0], len(rows))
        wrong = []
        with wakfu_flag(True), translation.override('en'):
            for item_id, name in rows:
                path = reverse('wakfu:encyclopedia_item', kwargs={
                    'ankama_type': 'equipment', 'ankama_id': item_id,
                    'slug': _slugify_name(name, '')})
                match = resolve(path)
                if (match.view_name != 'wakfu:encyclopedia_item'
                        or int(match.kwargs['ankama_id']) != item_id):
                    wrong.append(item_id)
        self.assertEqual([], wrong)

    def test_the_list_address_reverses_and_resolves_in_each_language(self):
        with wakfu_flag(True):
            for language, prefix in (('en', ''), ('fr', '/fr'), ('es', '/es'),
                                     ('pt', '/pt'), ('de', '/de')):
                with translation.override(language):
                    path = reverse('wakfu:encyclopedia')
                    self.assertEqual(prefix + '/wakfu/encyclopedia/', path)
                    self.assertEqual('wakfu:encyclopedia', resolve(path).view_name)
