# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""What the sitemap promises about a page whose table may still be empty.

The most-worn page and its four sitemap entries ship in the same deploy, but
the table behind it is filled by reindex_builds_by_item -- a quarter of an hour,
run by a person, deliberately outside the container entrypoint. Between the
deploy and that command the page answers honestly that the counts are not built
yet, and the sitemap invites Google to come and read exactly that.

Four entries, not six: `_SITEMAP_LANGUAGES` is ('fr', 'es', 'pt'). German is
served and linked by hreflang but not submitted, on measured audience -- the
reason is written where the list is, and this module does not second-guess it.
Counting six here would have made the empty case pass for the wrong reason.
"""
from django.db import DatabaseError
from django.test import TestCase

PLAN = '/sitemap-pages.xml'
#: L'adresse sans prefixe, plus une par langue soumise.
ADRESSES = ('/encyclopedia/most-used/', '/fr/encyclopedia/most-used/',
            '/es/encyclopedia/most-used/', '/pt/encyclopedia/most-used/')
#: Une page toujours soumise, quoi qu'il arrive : sans elle, un plan vide ferait
#: passer le test de l'absence sans rien prouver.
TEMOIN = '/sharedbuilds/'


class TheSitemapWaitsForTheIndexTests(TestCase):

    def _plan(self):
        reponse = self.client.get(PLAN)
        self.assertEqual(200, reponse.status_code,
                         'the pages sitemap answered %s' % reponse.status_code)
        plan = reponse.content.decode('utf-8', 'replace')
        # Controle positif : le plan doit contenir autre chose, sinon
        # « la page n'y est pas » est vrai d'un fichier vide.
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
        """Nothing to show yet, so nothing submitted.

        The window this closes is real and one-sided: the page ships with the
        deploy and the command runs afterwards, so the sitemap would always be
        wrong first and right later.
        """
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
        """A half-submitted page is worse than either state.

        Three languages present and one missing would read to Google as a page
        that exists in three languages, which is a claim nobody made.
        """
        vide = self._plan()
        self._un_rang()
        plein = self._plan()
        self.assertEqual(0, sum(1 for a in ADRESSES if a in vide))
        self.assertEqual(len(ADRESSES), sum(1 for a in ADRESSES if a in plein))

    def test_a_missing_table_leaves_the_sitemap_standing(self):
        """Before the migration there is no table, and that is not an error.

        A sitemap that raises is worse than a sitemap one page short: the first
        loses every other URL in the file, the second loses one page that has
        nothing to show anyway.
        """
        from unittest import mock
        from chardata.models import ItemPopularity
        with mock.patch.object(ItemPopularity.objects, 'exists',
                               side_effect=DatabaseError('no such table')):
            plan = self._plan()
        self.assertEqual([], [a for a in ADRESSES if a in plan])
