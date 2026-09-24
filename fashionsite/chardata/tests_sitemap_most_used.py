# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The sitemap must not advertise the most-used page until its index table is built."""
from django.db import DatabaseError
from django.test import TestCase

PLAN = '/sitemap-pages.xml'
# the unprefixed address, plus one per submitted language
ADRESSES = ('/encyclopedia/most-used/', '/fr/encyclopedia/most-used/',
            '/es/encyclopedia/most-used/', '/pt/encyclopedia/most-used/')
# a page that is always submitted; a positive control against an empty sitemap
TEMOIN = '/sharedbuilds/'


class TheSitemapWaitsForTheIndexTests(TestCase):

    def _plan(self):
        reponse = self.client.get(PLAN)
        self.assertEqual(200, reponse.status_code,
                         'the pages sitemap answered %s' % reponse.status_code)
        plan = reponse.content.decode('utf-8', 'replace')
        self.assertIn(TEMOIN, plan,
                      'the sitemap carries nothing at all, so its contents '
                      'prove nothing about any one page')
        return plan

    def _un_rang(self):
        from chardata.models import ItemPopularity
        return ItemPopularity.objects.create(
            ankama_id=26066, game_version='dofus3', builds=1400,
            eligible=10000)

    def test_an_unbuilt_index_is_not_advertised(self):
        """The page ships before the index is built, so nothing should be submitted yet."""
        plan = self._plan()
        annonces = [a for a in ADRESSES if a in plan]
        self.assertEqual([], annonces,
                         'the sitemap submits %s while the index is empty'
                         % annonces)

    def test_the_page_joins_the_sitemap_by_itself_once_the_index_exists(self):
        """And it joins without anybody having to remember to add it."""
        self._un_rang()
        plan = self._plan()
        manquantes = [a for a in ADRESSES if a not in plan]
        self.assertEqual([], manquantes,
                         'the index is built and the sitemap still omits %s'
                         % manquantes)

    def test_the_four_entries_are_all_or_none(self):
        """All four entries or none: a partial submission would claim languages that are not there."""
        vide = self._plan()
        self._un_rang()
        plein = self._plan()
        self.assertEqual(0, sum(1 for a in ADRESSES if a in vide))
        self.assertEqual(len(ADRESSES), sum(1 for a in ADRESSES if a in plein))

    def test_a_missing_table_leaves_the_sitemap_standing(self):
        """Before the migration there is no table; the sitemap must skip the page, not raise."""
        from unittest import mock
        from chardata.models import ItemPopularity
        with mock.patch.object(ItemPopularity.objects, 'exists',
                               side_effect=DatabaseError('no such table')):
            plan = self._plan()
        self.assertEqual([], [a for a in ADRESSES if a in plan])
