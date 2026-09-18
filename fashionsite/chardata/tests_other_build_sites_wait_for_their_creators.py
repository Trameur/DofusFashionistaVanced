# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Other build sites stay hidden in production until their creators agree."""
import sys
from unittest import mock

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase, override_settings

from chardata import build_link_import, dofusbook_export

DOFUSBOOK_LINK = dofusbook_export.build_url(
    'dofus3', 'fr', dofusbook_export.payload([[], [], [], [], [], [], [694], [], [], []], 200))
DOFUS_STUFFER_LINK = ('http://www.dofus-stuffer.is-great.net?stuff='
                      + DOFUSBOOK_LINK.split('stuff=', 1)[1])
DOFUSCREATOR_LINK = 'https://dofuscreator.com/projet/6e9f4'


class ProductionWaitsForTheCreatorsTests(TestCase):

    def test_no_creator_has_agreed_yet(self):
        """Update when a creator agrees."""
        production = sys.modules['fashionsite.settings']
        self.assertEqual((), production.BUILD_SITES_AGREED)


class _OwnedBuild(object):

    def _owned_build(self):
        from chardata.coaching_view import create_build
        owner = User.objects.create_user('waiter', 'w@test.local', 'pw-wait-42')
        request = RequestFactory().post('/')
        request.user = owner
        char = create_build(request, 'Iop', 200, {'str'}, 'dofus3')
        # Dressed, or the solution page redirects
        from chardata.dofusbook_view import _place_items
        from fashionistapulp.structure import get_structure
        _place_items(char, [get_structure('dofus3').items_dict_ankama[694].id])
        self.client.force_login(owner)
        return char


@override_settings(BUILD_SITES_ENABLED=())
class WithNoSiteEnabledTests(_OwnedBuild, TestCase):

    def test_the_import_page_speaks_of_names_and_screenshots_only(self):
        page = self.client.get('/import/text/').content.decode('utf-8')
        self.assertNotIn('import-link-note', page)
        self.assertNotIn('build link', page)
        self.assertNotIn('another build site', page)
        self.assertIn('Paste your item names or drop tooltip screenshots.', page)
        self.assertIn('placeholder="One item name per line"', page)

    def test_no_link_is_read_and_nothing_is_fetched(self):
        with mock.patch('urllib.request.urlopen',
                        side_effect=AssertionError('fetched')):
            for link in (DOFUSBOOK_LINK, DOFUS_STUFFER_LINK, DOFUSCREATOR_LINK):
                with self.subTest(link=link):
                    self.assertFalse(build_link_import.recognises(link))
                    page = self.client.post('/import/text/', {'text': link})
                    self.assertContains(page, 'We cannot read links from that '
                                              'site yet.')
        self.assertEqual([], build_link_import.readable_sites())

    def test_the_solution_page_offers_no_export(self):
        char = self._owned_build()
        page = self.client.get('/solution/%d/' % char.id)
        self.assertEqual(200, page.status_code)
        self.assertNotContains(page, 'Open on DofusBook')

    def test_the_export_page_does_not_exist(self):
        char = self._owned_build()
        self.assertEqual(404, self.client.get(
            '/export/dofusbook/%d/' % char.id).status_code)

    def test_the_changelog_and_the_privacy_page_name_none_of_them(self):
        changelog = self.client.get('/changelog-content/').content.decode('utf-8')
        self.assertNotIn('another build site', changelog)
        self.assertIn('Import a whole build: paste item names or drop one '
                      'tooltip screenshot per piece.', changelog)
        privacy = self.client.get('/privacy/').content.decode('utf-8')
        self.assertNotIn('DofusBook', privacy)
        self.assertNotIn('DofusCreator', privacy)


@override_settings(BUILD_SITES_ENABLED=('dofusbook',))
class EachSiteComesBackOnItsOwnTests(_OwnedBuild, TestCase):

    def test_the_export_comes_back_with_its_site(self):
        char = self._owned_build()
        self.assertContains(self.client.get('/solution/%d/' % char.id),
                            'Open on DofusBook')
        # No network in tests
        with mock.patch('urllib.request.urlopen',
                        side_effect=OSError('no network in tests')):
            self.assertEqual(200, self.client.get(
                '/export/dofusbook/%d/' % char.id).status_code)

    def test_only_the_agreed_site_is_read_and_named(self):
        self.assertEqual(['dofusbook.net'], build_link_import.readable_sites())
        self.assertTrue(build_link_import.recognises(DOFUSBOOK_LINK))
        self.assertFalse(build_link_import.recognises(DOFUS_STUFFER_LINK))
        self.assertFalse(build_link_import.recognises(DOFUSCREATOR_LINK))
        privacy = self.client.get('/privacy/').content.decode('utf-8')
        self.assertIn('DofusBook', privacy)
        self.assertNotIn('DofusCreator', privacy)

    def test_a_dofus_stuffer_link_does_not_ride_on_dofusbook(self):
        with self.assertRaises(Exception) as caught:
            build_link_import.read(DOFUS_STUFFER_LINK)
        self.assertEqual('not_a_link', getattr(caught.exception, 'reason', None))
