# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A guide page whose numbers or sentences differ from an earlier version's is its own canonical."""

import re
from html.parser import HTMLParser

from django.test import SimpleTestCase, TestCase

LANGUAGES = ('en', 'fr', 'es', 'pt', 'de')


def _version_names():
    from chardata.guides_content import _version_name
    from fashionistapulp.game_versions import version_keys
    return sorted({_version_name(version, language)
                   for version in version_keys() for language in LANGUAGES},
                  key=len, reverse=True)


def _reading(slug, version, language, names):
    """What a reader sees, without tags or any version's name."""
    from chardata.guides_content import get_guide
    guide = get_guide(slug, language, version)
    text = re.sub(r'<[^>]+>', ' ', ' '.join(guide[field] for field in
                                            ('title', 'desc', 'lead', 'body')))
    for name in names:
        text = text.replace(name, ' ')
    return re.sub(r'\s+', ' ', text).strip()


class TheCanonicalFollowsWhatThePageSaysTests(SimpleTestCase):

    def test_no_page_points_at_a_page_with_other_numbers_or_sentences(self):
        from chardata.guides_content import guide_canonical_version, ordered_slugs
        from fashionistapulp.game_versions import version_keys
        names = _version_names()
        pointing = 0
        for slug in ordered_slugs():
            for version in version_keys():
                canonical = guide_canonical_version(slug, version)
                if canonical == version:
                    continue
                pointing += 1
                for language in LANGUAGES:
                    own = _reading(slug, version, language, names)
                    target = _reading(slug, canonical, language, names)
                    with self.subTest(slug=slug, version=version, language=language):
                        self.assertEqual(re.findall(r'\d+', target), re.findall(r'\d+', own))
                        self.assertEqual(target, own)
        self.assertGreater(pointing, 0)

    def test_a_self_canonical_page_reads_unlike_every_version_before_it(self):
        from chardata.guides_content import guide_canonical_version, ordered_slugs
        from fashionistapulp.game_versions import version_keys
        names = _version_names()
        versions = list(version_keys())
        for slug in ordered_slugs():
            for position, version in enumerate(versions[1:], 1):
                if guide_canonical_version(slug, version) != version:
                    continue
                own = [_reading(slug, version, language, names) for language in LANGUAGES]
                for earlier in versions[:position]:
                    with self.subTest(slug=slug, version=version, earlier=earlier):
                        self.assertNotEqual(
                            own, [_reading(slug, earlier, language, names)
                                  for language in LANGUAGES])

    def test_the_lock_and_dodge_and_trophy_pages(self):
        from chardata.guides_content import canonical_versions, guide_canonical_version
        self.assertEqual(['dofus3', 'dofus2', 'touch', 'retro'],
                         canonical_versions('lock-and-dodge'))
        self.assertEqual('dofus3', guide_canonical_version('lock-and-dodge', 'beta'))
        self.assertEqual(['dofus3', 'dofus2', 'touch'],
                         canonical_versions('dofus-and-trophies'))
        self.assertEqual('dofus3', guide_canonical_version('dofus-and-trophies', 'beta'))
        self.assertEqual('dofus3', guide_canonical_version('dofus-and-trophies', 'retro'))
        self.assertEqual(['dofus3'], canonical_versions('getting-started'))


class _Links(HTMLParser):

    def __init__(self):
        super().__init__()
        self.canonical = []
        self.alternates = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag != 'link':
            return
        if attrs.get('rel') == 'canonical':
            self.canonical.append(attrs.get('href'))
        elif attrs.get('rel') == 'alternate' and attrs.get('hreflang'):
            self.alternates[attrs['hreflang']] = attrs.get('href')


class TheSitemapAndTheHeadFollowTheCanonicalTests(TestCase):

    SLUGS = ('lock-and-dodge', 'dofus-and-trophies', 'getting-started')

    def test_the_sitemap_lists_each_self_canonical_page_once_per_language(self):
        from chardata.guides_content import (alternate_slugs, canonical_versions,
                                             ordered_slugs)
        from chardata.guides_view import _guide_url
        from chardata.url_language import SITE_URL
        from fashionistapulp.game_versions import version_keys
        response = self.client.get('/sitemap-pages.xml')
        self.assertEqual(200, response.status_code)
        locs = re.findall(r'<loc>([^<]+)</loc>', response.content.decode('utf-8'))
        guide_locs = [loc for loc in locs if '/guides/' in loc and not loc.endswith('/guides/')]
        self.assertEqual(len(guide_locs), len(set(guide_locs)))
        expected = set()
        for key in ordered_slugs():
            own = canonical_versions(key)
            for slug in set(alternate_slugs(key).values()) or {key}:
                for version in version_keys():
                    url = SITE_URL + _guide_url(version, slug)
                    with self.subTest(key=key, slug=slug, version=version):
                        self.assertEqual(version in own, url in locs)
                    if version in own:
                        expected.add(url)
        self.assertEqual(expected, set(guide_locs))

    def test_each_page_declares_its_canonical_and_alternates_in_that_version(self):
        from chardata.guides_content import (alternate_slugs, guide_canonical_version,
                                             slug_for)
        from chardata.guides_view import _guide_url
        from chardata.url_language import SITE_URL
        from fashionistapulp.game_versions import version_keys
        for key in self.SLUGS:
            for version in version_keys():
                canonical = guide_canonical_version(key, version)
                alternates = {language: SITE_URL + _guide_url(canonical, slug)
                              for language, slug in alternate_slugs(key).items()}
                alternates['x-default'] = alternates['en']
                for language in ('en', 'pt'):
                    slug = slug_for(key, language)
                    path = _guide_url(version, slug)
                    response = self.client.get(path)
                    with self.subTest(path=path):
                        self.assertEqual(200, response.status_code)
                        links = _Links()
                        links.feed(response.content.decode('utf-8'))
                        self.assertEqual([SITE_URL + _guide_url(canonical, slug)],
                                         links.canonical)
                        self.assertEqual(alternates, links.alternates)

    def test_a_page_with_its_own_numbers_points_at_itself(self):
        from chardata.url_language import SITE_URL
        for path, canonical in (
                ('/touch/guides/lock-and-dodge/', '/touch/guides/lock-and-dodge/'),
                ('/dofus2/guides/dofus-and-trophies/', '/dofus2/guides/dofus-and-trophies/'),
                ('/beta/guides/dofus-and-trophies/', '/guides/dofus-and-trophies/'),
                ('/retro/guides/dofus-and-trophies/', '/guides/dofus-and-trophies/')):
            links = _Links()
            links.feed(self.client.get(path).content.decode('utf-8'))
            with self.subTest(path=path):
                self.assertEqual([SITE_URL + canonical], links.canonical)
                self.assertTrue(links.alternates)
                prefix = SITE_URL + canonical.split('/guides/')[0] + '/guides/'
                for href in links.alternates.values():
                    self.assertTrue(href.startswith(prefix), href)


class APageDifferingOnlyByItsOwnNamePointsAtTheFirstTests(SimpleTestCase):

    def test_the_own_version_and_slot_version_tokens_do_not_split_a_page(self):
        from unittest import mock
        from chardata import guides_content
        block = {'title': 'T [[version]]', 'desc': 'D', 'lead': 'L',
                 'body': '<p>On [[slot-version]], x.</p>'}
        guide = {'published': '2026-10-01',
                 'i18n': {language: dict(block) for language in LANGUAGES}}
        with mock.patch.dict(guides_content.GUIDES, {'a-test-guide': guide}):
            self.assertEqual(['dofus3'], guides_content.canonical_versions('a-test-guide'))
            self.assertIn('On Dofus 3, x.',
                          guides_content.get_guide('a-test-guide', 'en', 'retro')['body'])


class EachSelfCanonicalPageHasItsOwnHeadTests(TestCase):

    def test_titles_and_descriptions_differ_between_the_self_canonical_pages(self):
        from chardata.guides_content import (_version_name, canonical_versions,
                                             head_title_and_desc, ordered_slugs)
        named = 0
        for slug in ordered_slugs():
            versions = canonical_versions(slug)
            for language in LANGUAGES:
                heads = [head_title_and_desc(slug, language, version) for version in versions]
                with self.subTest(slug=slug, language=language):
                    self.assertEqual(len(versions), len({title for title, _desc in heads}))
                    self.assertEqual(len(versions), len({desc for _title, desc in heads}))
                named += sum(1 for version, (title, _desc) in zip(versions, heads)
                             if title.endswith(' · %s' % _version_name(version, 'en')))
        self.assertGreater(named, 0)

    def test_the_dofus_3_head_is_the_guides_own_title_and_description(self):
        from chardata.guides_content import get_guide, head_title_and_desc, ordered_slugs
        for slug in ordered_slugs():
            for language in LANGUAGES:
                guide = get_guide(slug, language, 'dofus3')
                with self.subTest(slug=slug, language=language):
                    self.assertEqual((guide['title'], guide['desc']),
                                     head_title_and_desc(slug, language, 'dofus3'))

    def test_the_served_head_is_the_one_that_names_its_version(self):
        from chardata.guides_content import _version_name, head_title_and_desc, slug_for
        from chardata.guides_view import _guide_url
        for key, version in (('dofus-and-trophies', 'dofus2'), ('dofus-and-trophies', 'touch'),
                             ('lock-and-dodge', 'dofus2'), ('dofus-and-trophies', 'dofus3')):
            for language in ('en', 'fr'):
                title, desc = head_title_and_desc(key, language, version)
                head = _Head()
                head.feed(self.client.get(_guide_url(version, slug_for(key, language)))
                          .content.decode('utf-8'))
                with self.subTest(key=key, version=version, language=language):
                    self.assertEqual(title, head.title.rsplit(' · ', 1)[0])
                    self.assertEqual(title, head.meta['og:title'])
                    self.assertEqual(desc, head.meta['description'])
                    self.assertEqual(desc, head.meta['og:description'])
                    self.assertEqual(version != 'dofus3', title.endswith(
                        ' · %s' % _version_name(version, 'en')))


class _Head(HTMLParser):

    def __init__(self):
        super().__init__()
        self.title = ''
        self.meta = {}
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'title':
            self._in_title = True
        elif tag == 'meta' and (attrs.get('name') or attrs.get('property')):
            self.meta.setdefault(attrs.get('name') or attrs.get('property'), attrs.get('content'))

    def handle_endtag(self, tag):
        if tag == 'title':
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data
