# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Links on the home page keep the reader's language."""
import pickle
import re

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import translation

from chardata import game_urls
from chardata.context_processors import ACTIVE_GAME_VERSIONS
from chardata.data_versions import current_data_version
from chardata.models import Char

from fashionistapulp.modelresult import ModelResultMinimal
from fashionistapulp.translation import SUPPORTED_LANGUAGES

LANGUAGES = tuple(SUPPORTED_LANGUAGES)
VERSIONS = tuple(slug for slug, _label in ACTIVE_GAME_VERSIONS)

# Whole tag: the minifier sorts attributes, class can come before or after href
_ANCHOR = re.compile(r'<a\b[^>]*>', re.I)
_HREF = re.compile(r'href="([^"]*)"', re.I)
_LANG = re.compile(r'<html[^>]*\slang="([^"]+)"')

# Not pages served by the site
_NOT_A_PAGE = ('/static/', '/media/', '/admin/', '/out/', '/logout',
               '/jsi18n/', '/sitemap', '/robots', '/manifest', '/sw.js',
               '/favicon', '/i18n/', 'http://', 'https://', '//')


def _language_of(html):
    found = _LANG.search(html)
    return found.group(1) if found else None


def _home_path(version, language):
    parts = []
    if language != 'en':
        parts.append(language)
    if version != 'dofus3':
        parts.append(version)
    return '/' + '/'.join(parts) + ('/' if parts else '')


def _language_carried_by(path):
    """The language the path itself carries."""
    head = path.lstrip('/').split('/', 1)[0]
    return head if head in LANGUAGES and head != 'en' else 'en'


def _links_written_by(html):
    """Links on the page, minus the language switcher."""
    links = []
    for tag in _ANCHOR.findall(html):
        if 'flag-btn' in tag:
            continue
        href = _HREF.search(tag)
        if href is None:
            continue
        target = href.group(1)
        if not target.startswith('/') or target.startswith(_NOT_A_PAGE):
            continue
        path = target.split('?')[0].split('#')[0]
        if not path or '.' in path.rsplit('/', 1)[-1]:
            continue
        if path not in links:
            links.append(path)
    return links


def _solved_on_the_current_update(version):
    return dict(minimal_solution=pickle.dumps(
                    ModelResultMinimal({}, {'origin': 'generated'}, {})),
                solved_version=current_data_version(version))


def _seed_shared_builds(owner):
    """Two shared builds per version for the featured cards."""
    made = {}
    for index, version in enumerate(VERSIONS):
        made[version] = [Char.objects.create(
            name='projet %s %d' % (version, rank),
            char_name='temoin %d' % (index * 10 + rank),
            char_class='Iop', char_build='build', level=200,
            minimum_stats=b'', minimum_crits=b'',
            stats_weight=pickle.dumps({'vit': 1}), options=b'',
            inclusions=b'', exclusions=b'',
            owner=owner, game_version=version,
            link_shared=True, deleted=False,
            **_solved_on_the_current_update(version))
            for rank in range(2)]
    return made


class TheHomeLinksKeepTheReadersLanguageTests(TestCase):

    def setUp(self):
        cache.clear()
        self.owner = User.objects.create_user(
            username='home-links-witness', email='h@test.local',
            password='pw-42-solid')
        _seed_shared_builds(self.owner)

    def _home(self, version, language):
        page = self.client.get(_home_path(version, language))
        self.assertEqual(page.status_code, 200,
                         'no home at %s' % _home_path(version, language))
        return page.content.decode('utf-8', 'replace')

    def test_there_are_versions_and_languages_to_walk(self):
        self.assertGreaterEqual(len(VERSIONS), 5)
        self.assertGreaterEqual(len(LANGUAGES), 5)
        self.assertIn('dofus3', VERSIONS)

    def test_each_home_writes_links_to_check(self):
        thin = []
        for version in VERSIONS:
            for language in LANGUAGES:
                found = _links_written_by(self._home(version, language))
                if len(found) < 20:
                    thin.append((version, language, len(found)))
        self.assertEqual([], thin)

    def test_every_link_carries_the_language_of_the_page_that_wrote_it(self):
        wrong = []
        for version in VERSIONS:
            for language in LANGUAGES:
                html = self._home(version, language)
                self.assertEqual(_language_of(html), language)
                for path in _links_written_by(html):
                    if _language_carried_by(path) != language:
                        wrong.append((version, language, path))
        self.assertEqual([], wrong)

    def test_the_language_switcher_is_the_only_thing_exempted(self):
        html = self._home('dofus3', 'fr')
        exempted = [tag for tag in _ANCHOR.findall(html) if 'flag-btn' in tag]
        self.assertEqual(len(exempted), len(LANGUAGES) - 1,
                         'the switcher should be the other four languages, '
                         'found %d exempted links' % len(exempted))
        targets = {_HREF.search(tag).group(1) for tag in exempted}
        self.assertEqual(targets, {'/', '/es/', '/pt/', '/de/'})


class ThePrefixIsNotDecorativeTests(TestCase):
    """A prefixed address answers in the language of its prefix."""

    PAGES = ('/about/', '/faq/', '/contact/', '/license/', '/privacy/',
             '/support/', '/quickstart/', '/sharedbuilds/', '/forgemagie/',
             '/import/text/', '/choose_compare_sets/', '/smartbuild/')

    def test_each_page_answers_in_the_language_of_its_prefix(self):
        wrong = []
        for language in LANGUAGES:
            if language == 'en':
                continue
            for page in self.PAGES:
                path = '/%s%s' % (language, page)
                answer = self.client.get(path)
                if answer.status_code != 200:
                    wrong.append((path, answer.status_code))
                    continue
                served = _language_of(answer.content.decode('utf-8',
                                                            'replace'))
                if served != language:
                    wrong.append((path, served))
        self.assertEqual([], wrong)

    def test_the_english_page_is_still_where_it_was(self):
        moved = []
        for page in self.PAGES:
            if self.client.get(page).status_code != 200:
                moved.append(page)
        self.assertEqual([], moved)

    def test_a_prefix_that_is_not_a_language_is_still_a_404(self):
        for page in self.PAGES:
            with self.subTest(page=page):
                self.assertEqual(self.client.get('/xx%s' % page).status_code,
                                 404)


class NoEnglishAddressGainedAPrefixTests(TestCase):
    """English stays at the root."""

    @staticmethod
    def _names_without_arguments():
        return sorted({entry.name for entry in game_urls.urlpatterns
                       if getattr(entry, 'callback', None) is not None
                       and entry.name
                       and entry.pattern.regex.groups == 0})

    def test_there_are_names_to_walk(self):
        self.assertGreaterEqual(len(self._names_without_arguments()), 40)

    def test_english_keeps_the_bare_address(self):
        prefixed = []
        with translation.override('en'):
            for name in self._names_without_arguments():
                path = reverse(name)
                if _language_carried_by(path) != 'en':
                    prefixed.append((name, path))
        self.assertEqual([], prefixed)

    def test_french_gets_a_prefixed_address(self):
        bare = []
        with translation.override('fr'):
            for name in self._names_without_arguments():
                path = reverse(name)
                if _language_carried_by(path) != 'fr':
                    bare.append((name, path))
        self.assertEqual([], bare)

    def test_a_translated_slug_keeps_its_single_address(self):
        """A path with a translated slug gets no language prefix."""
        with translation.override('fr'):
            self.assertEqual(
                reverse('guide', args=['bonus-de-panoplie']),
                '/guides/bonus-de-panoplie/')
            self.assertEqual(
                reverse('encyclopedia_item',
                        args=['equipment', 44, 'epee-de-boisaille']),
                '/encyclopedia/item/equipment/44-epee-de-boisaille/')


class TheFeaturedBuildsAreBuiltForTheReaderTests(TestCase):
    """Featured cards are cached, they must not keep the first reader's language."""

    def setUp(self):
        cache.clear()
        self.owner = User.objects.create_user(
            username='featured-witness', email='f@test.local',
            password='pw-42-solid')
        _seed_shared_builds(self.owner)

    @staticmethod
    def _cards(html):
        return re.findall(r'<a[^>]*class="featured-build-card"[^>]*>', html) \
            or re.findall(r'<a[^>]*featured-build-card[^>]*>', html)

    def _card_links(self, path):
        page = self.client.get(path)
        self.assertEqual(page.status_code, 200)
        html = page.content.decode('utf-8', 'replace')
        return [_HREF.search(tag).group(1) for tag in self._cards(html)
                if _HREF.search(tag)]

    def test_the_home_really_shows_cards(self):
        self.assertGreaterEqual(len(self._card_links('/de/')), 1)

    def test_the_first_reader_does_not_decide_for_the_others(self):
        self._card_links('/de/')
        borrowed = []
        for language in LANGUAGES:
            for link in self._card_links(_home_path('dofus3', language)):
                if _language_carried_by(link) != language:
                    borrowed.append((language, link))
        self.assertEqual([], borrowed)

    def test_an_owner_less_build_is_named_in_the_readers_language(self):
        """`_('Anonymous')` must not enter the cache already translated."""
        Char.objects.create(
            name='sans proprietaire', char_name='sans proprietaire',
            char_class='Cra', char_build='build', level=200,
            minimum_stats=b'', minimum_crits=b'',
            stats_weight=pickle.dumps({'vit': 1}), options=b'',
            inclusions=b'', exclusions=b'', owner=None,
            game_version='dofus3', link_shared=True, deleted=False,
            **_solved_on_the_current_update('dofus3'))
        cache.clear()

        def authors(path):
            html = self.client.get(path).content.decode('utf-8', 'replace')
            return re.findall(r'featured-build-author"[^>]*>([^<]*)<', html)

        english = authors('/')
        french = authors('/fr/')
        self.assertTrue(english, 'no author line on the English home')
        self.assertTrue(any('Anonymous' in line for line in english), english)
        self.assertTrue(any('Anonyme' in line for line in french), french)
        self.assertFalse([line for line in french if 'Anonymous' in line],
                         french)

    def test_a_card_link_is_not_an_absolute_address(self):
        """An absolute link carries the host of the request that filled the cache."""
        absolute = [link for link in self._card_links('/fr/')
                    if '://' in link]
        self.assertEqual([], absolute)
