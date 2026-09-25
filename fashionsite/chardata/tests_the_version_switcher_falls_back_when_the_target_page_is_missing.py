# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The header version switcher must never send a reader to a 404, falling back to a version that is routed."""
import re

from django.test import TestCase


def _switcher_hrefs(html):
    """{href for every <a class="version-link" ...> in the header}."""
    hrefs = []
    for tag in re.findall(r'<a [^>]*>', html):
        if 'version-link' in tag:
            match = re.search(r'href="([^"]+)"', tag)
            if match:
                hrefs.append(match.group(1))
    return hrefs


class TheGuideSwitcherNeverLinksToADeadDofus3Page(TestCase):

    def test_a_localized_retro_guide_links_dofus3_without_the_prefix(self):
        page = self.client.get('/fr/retro/guides/choisir-sa-classe/')
        self.assertEqual(200, page.status_code)
        hrefs = _switcher_hrefs(page.content.decode('utf-8'))
        self.assertIn('/guides/choisir-sa-classe/', hrefs)
        self.assertNotIn('/fr/guides/choisir-sa-classe/', hrefs)

    def test_that_dofus3_link_is_not_itself_a_404(self):
        page = self.client.get('/guides/choisir-sa-classe/')
        self.assertEqual(200, page.status_code)


class TheMostUsedSwitcherFallsBackToTheEncyclopediaHub(TestCase):

    def test_other_versions_link_to_their_encyclopedia_hub(self):
        page = self.client.get('/encyclopedia/most-used/')
        self.assertEqual(200, page.status_code)
        hrefs = _switcher_hrefs(page.content.decode('utf-8'))
        for version in ('beta', 'dofus2', 'retro', 'touch'):
            hub = '/%s/encyclopedia/' % version
            self.assertIn(hub, hrefs, version)
            self.assertNotIn('%s/encyclopedia/most-used/' % ('/' + version),
                             hrefs, version)

    def test_those_hub_links_are_not_themselves_dead(self):
        for version in ('beta', 'dofus2', 'retro', 'touch'):
            with self.subTest(version=version):
                page = self.client.get('/%s/encyclopedia/' % version)
                self.assertEqual(200, page.status_code)


class TheLoginSwitcherFallsBackToHome(TestCase):

    def test_other_versions_link_to_their_home_not_a_missing_login(self):
        page = self.client.get('/login/')
        self.assertEqual(200, page.status_code)
        hrefs = _switcher_hrefs(page.content.decode('utf-8'))
        for version in ('beta', 'dofus2', 'retro', 'touch'):
            self.assertIn('/%s/' % version, hrefs, version)
            self.assertNotIn('/%s/login/' % version, hrefs, version)
