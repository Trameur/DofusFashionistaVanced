# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The import page links, as partners, the build sites whose links it reads as its version."""

import io
import os
import urllib.parse
from html.parser import HTMLParser

from django.conf import settings
from django.test import SimpleTestCase, TestCase, override_settings

from chardata import build_link_import, build_sites, dofusbook_import, dofuscreator_import
from chardata import tests_a_stuffer_link_imports as stuffer_link_tests

ALL_HOMES = [('DofusBook', 'https://www.dofusbook.net/', 'dofusbook.net'),
             ('Dofus-Stuffer', 'http://www.dofus-stuffer.is-great.net/',
              'dofus-stuffer.is-great.net'),
             ('DofusCreator', 'https://dofuscreator.com/', 'dofuscreator.com')]
OLD_NOTE = 'Build links our server can read today'


class _PartnerBlock(HTMLParser):
    """The links inside section#import-partners, with their name and host spans."""

    def __init__(self):
        super().__init__()
        self.found = False
        self.heading = ''
        self.links = []
        self._depth = 0
        self._link = None
        self._span = None
        self._in_heading = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if not self._depth:
            if tag == 'section' and attrs.get('id') == 'import-partners':
                self.found = True
                self._depth = 1
            return
        if tag == 'section':
            self._depth += 1
        elif tag == 'h2':
            self._in_heading = True
        elif tag == 'a':
            self._link = dict(attrs, name='', host='')
        elif tag == 'span' and self._link is not None:
            classes = (attrs.get('class') or '').split()
            self._span = next((c[len('import-partner-'):] for c in classes
                               if c in ('import-partner-name', 'import-partner-host')),
                              None)

    def handle_endtag(self, tag):
        if not self._depth:
            return
        if tag == 'section':
            self._depth -= 1
        elif tag == 'h2':
            self._in_heading = False
        elif tag == 'span':
            self._span = None
        elif tag == 'a' and self._link is not None:
            self.links.append(self._link)
            self._link = None

    def handle_data(self, data):
        if self._in_heading:
            self.heading += data
        if self._link is not None and self._span:
            self._link[self._span] += data.strip()


def _block(page):
    parser = _PartnerBlock()
    parser.feed(page)
    return parser


def _page(client, path='/import/text/'):
    return client.get(path, HTTP_ACCEPT_LANGUAGE='en').content.decode('utf-8')


def _triples(links):
    return [(link['name'], link['href'], link['host']) for link in links]


@override_settings(BUILD_SITES_ENABLED=build_sites.ALL)
class ThePartnerBlockListsTheEnabledSitesTests(TestCase):

    def test_every_enabled_site_is_linked_to_its_home_in_reader_order(self):
        block = _block(_page(self.client))
        self.assertTrue(block.found, 'no partner block on the import page')
        self.assertEqual('Partner sites', block.heading.strip())
        self.assertEqual(ALL_HOMES, _triples(block.links))

    def test_each_link_opens_a_new_tab_and_hands_over_only_our_origin(self):
        links = _block(_page(self.client)).links
        self.assertTrue(links)
        for link in links:
            with self.subTest(site=link['name']):
                rel = (link.get('rel') or '').split()
                self.assertEqual('_blank', link.get('target'))
                self.assertIn('noopener', rel)
                self.assertNotIn('noreferrer', rel)
                self.assertEqual('origin', link.get('referrerpolicy'))

    def test_a_retro_page_links_only_the_retro_dofusbook(self):
        links = _block(_page(self.client, '/retro/import/text/')).links
        self.assertEqual([('DofusBook', 'https://retro.dofusbook.net/', 'retro.dofusbook.net')],
                         _triples(links))

    def test_a_touch_page_links_only_the_touch_dofusbook(self):
        links = _block(_page(self.client, '/touch/import/text/')).links
        self.assertEqual([('DofusBook', 'https://touch.dofusbook.net/', 'touch.dofusbook.net')],
                         _triples(links))

    def test_a_version_no_site_reads_has_no_block_yet_still_takes_a_link(self):
        for path in ('/dofus2/import/text/', '/beta/import/text/'):
            with self.subTest(path=path):
                page = _page(self.client, path)
                self.assertFalse(_block(page).found)
                self.assertIn('a link to a public build from another build site', page)
                self.assertIn('placeholder="One item name per line, or a build link"', page)

    def test_the_old_one_line_list_is_gone(self):
        page = _page(self.client)
        self.assertNotIn(OLD_NOTE, page)
        self.assertNotIn('import-link-note', page)
        self.assertNotIn('dofusbook.net, dofus-stuffer.is-great.net', page)


@override_settings(BUILD_SITES_ENABLED=(build_sites.DOFUSCREATOR,))
class OnlyAnEnabledSiteIsListedTests(TestCase):

    def test_the_block_names_the_one_enabled_site(self):
        links = _block(_page(self.client)).links
        self.assertEqual([('DofusCreator', 'https://dofuscreator.com/')],
                         [(link['name'], link['href']) for link in links])


@override_settings(BUILD_SITES_ENABLED=())
class WithNoSiteEnabledTheBlockIsAbsentTests(TestCase):

    def test_no_partner_block_and_no_partner_link(self):
        page = _page(self.client)
        self.assertFalse(_block(page).found)
        self.assertNotIn('Partner sites', page)
        for _name, home, _host in ALL_HOMES:
            self.assertNotIn(home, page)
        self.assertEqual([], build_link_import.partner_sites('dofus3'))


class EveryPartnerHomeIsOnAHostItsReaderReadsTests(SimpleTestCase):

    READ_HOSTS = {
        build_sites.DOFUSBOOK: dofusbook_import.HOSTS,
        build_sites.DOFUS_STUFFER: dofusbook_import.STUFFER_HOSTS,
        build_sites.DOFUSCREATOR: dofuscreator_import.HOSTS,
    }

    def test_every_reader_has_a_partner_entry(self):
        self.assertEqual({site for site, _r, _l, _h in build_link_import.READERS},
                         set(build_link_import.PARTNERS))

    def test_every_home_is_on_a_host_its_reader_reads_as_that_version(self):
        for site, (_name, homes) in build_link_import.PARTNERS.items():
            for version, url in homes.items():
                with self.subTest(site=site, version=version):
                    self.assertEqual(version, self.READ_HOSTS[site].get(
                        urllib.parse.urlsplit(url).hostname))

    def test_every_version_a_reader_reads_has_a_home(self):
        for site, (_name, homes) in build_link_import.PARTNERS.items():
            with self.subTest(site=site):
                self.assertEqual(set(self.READ_HOSTS[site].values()), set(homes))

    def test_every_home_is_https_but_dofus_stuffer_on_its_share_link_scheme_and_host(self):
        share = urllib.parse.urlsplit(stuffer_link_tests.ADofusStufferLinkImportsTests.LINK)
        for site, (_name, homes) in build_link_import.PARTNERS.items():
            for version, url in homes.items():
                with self.subTest(site=site, version=version):
                    parts = urllib.parse.urlsplit(url)
                    if site == build_sites.DOFUS_STUFFER:
                        self.assertEqual((share.scheme, share.hostname),
                                         (parts.scheme, parts.hostname))
                    else:
                        self.assertEqual('https', parts.scheme)


class TheTemplateNoLongerCarriesTheOldNoteTests(SimpleTestCase):

    def test_the_old_sentence_is_not_in_the_template(self):
        path = os.path.join(settings.BASE_DIR, 'chardata', 'templates', 'chardata',
                            'text_build.html')
        with io.open(path, encoding='utf-8') as f:
            source = f.read()
        self.assertNotIn(OLD_NOTE, source)
        self.assertNotIn('link_sites', source)
