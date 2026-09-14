# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Un lien de l'accueil garde le lecteur dans sa langue.

Trouve en suivant les liens de l'accueil, sur les cinq versions et les cinq
langues. Mesure du 14 septembre 2026 sur le serveur de developpement, en
comptant les liens dont la cible sert une autre langue que la page qui les
ecrit:

    version   en   fr   es   pt   de
    dofus3     4   20   20   20   20
    beta       4   12   12   12   12
    dofus2     4   12   12   12   12
    touch      4   12   12   12   12
    retro      4   12   12   12   12

Le plancher est 4: les quatre drapeaux du selecteur de langue, dont c'est le
travail. Tout le reste, 192 liens, emmenait le lecteur ailleurs que chez lui.

Trois causes distinctes, un seul symptome:

1. Sur la version par defaut, 15 des 16 pages que l'accueil propose n'avaient
   aucune adresse francaise, espagnole, portugaise ou allemande. /fr/retro/
   about/ repondait 200 en francais, /fr/about/ repondait 404. Les quatre
   autres versions prefixent tout `game_urls`; la version par defaut n'avait
   qu'une liste ecrite a la main -- accueil, guides, setup, encyclopedie.

2. Les six cartes de la vitrine gardaient en cache un lien absolu construit
   avec `build_absolute_uri`, qui porte l'hote ET le prefixe de langue de la
   requete qui a rempli l'entree. Demander l'accueil allemand d'abord faisait
   servir `/de/beta/s/...` aux lecteurs anglais et espagnols, pendant une
   demi-heure. `_('Anonymous')` y entrait deja traduit, pour la meme duree.

3. Un lien des guides ecrit en dur dans le gabarit de l'accueil.

Apres: 4 partout, c'est-a-dire le selecteur et rien d'autre. Verifie aussi a
deux niveaux de profondeur: 33 pages depuis /fr/ et 33 depuis /de/retro/,
aucune autre langue.
"""
import pickle
import re

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import translation

from chardata import game_urls
from chardata.context_processors import ACTIVE_GAME_VERSIONS
from chardata.models import Char

#: Les cinq langues servies, lues la ou le site les lit.
from fashionistapulp.translation import SUPPORTED_LANGUAGES

LANGUAGES = tuple(SUPPORTED_LANGUAGES)
VERSIONS = tuple(slug for slug, _label in ACTIVE_GAME_VERSIONS)

#: Le tag entier, pas seulement son href: le minificateur trie les attributs,
#: donc `class` peut passer avant ou apres `href`.
_ANCHOR = re.compile(r'<a\b[^>]*>', re.I)
_HREF = re.compile(r'href="([^"]*)"', re.I)
_LANG = re.compile(r'<html[^>]*\slang="([^"]+)"')

#: Ce qui n'est pas une page servie par le site.
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
    """La langue que l'adresse elle-meme annonce."""
    head = path.lstrip('/').split('/', 1)[0]
    return head if head in LANGUAGES and head != 'en' else 'en'


def _links_written_by(html):
    """Les liens de la page, sans le selecteur de langue.

    Le selecteur est exempte parce que changer de langue est exactement son
    travail; `test_the_language_switcher_is_the_only_thing_exempted` interdit
    que cette exemption avale tout le reste.
    """
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


def _seed_shared_builds(owner):
    """Six builds partages par version, pour que la vitrine ne soit pas vide.

    Sans eux le parcours passerait sans jamais regarder une carte, et la
    cause 2 ne serait gardee par rien.
    """
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
            link_shared=True, deleted=False)
            for rank in range(2)]
    return made


class TheHomeLinksKeepTheReadersLanguageTests(TestCase):
    """Le parcours: chaque lien que l'accueil ecrit porte sa propre langue."""

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
        """Un produit vide est un test vert qui n'a rien regarde."""
        self.assertGreaterEqual(len(VERSIONS), 5)
        self.assertGreaterEqual(len(LANGUAGES), 5)
        self.assertIn('dofus3', VERSIONS)

    def test_each_home_writes_links_to_check(self):
        """Le plancher du parcours: une extraction vide passerait tout."""
        thin = []
        for version in VERSIONS:
            for language in LANGUAGES:
                found = _links_written_by(self._home(version, language))
                if len(found) < 20:
                    thin.append((version, language, len(found)))
        self.assertEqual([], thin)

    def test_every_link_carries_the_language_of_the_page_that_wrote_it(self):
        """Le test qui aurait attrape les trois causes."""
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
        """Sans lui, exempter le selecteur pourrait exempter toute la page."""
        html = self._home('dofus3', 'fr')
        exempted = [tag for tag in _ANCHOR.findall(html) if 'flag-btn' in tag]
        self.assertEqual(len(exempted), len(LANGUAGES) - 1,
                         'the switcher should be the other four languages, '
                         'found %d exempted links' % len(exempted))
        targets = {_HREF.search(tag).group(1) for tag in exempted}
        self.assertEqual(targets, {'/', '/es/', '/pt/', '/de/'})


class ThePrefixIsNotDecorativeTests(TestCase):
    """Une adresse prefixee qui repondrait en anglais serait pire qu'un 404:
    elle aurait l'air traduite."""

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
        """Le controle de l'autre cote: rien d'indexe ne bouge."""
        moved = []
        for page in self.PAGES:
            if self.client.get(page).status_code != 200:
                moved.append(page)
        self.assertEqual([], moved)

    def test_a_prefix_that_is_not_a_language_is_still_a_404(self):
        """Sans lui, un client qui rendrait 200 pour tout passerait ci-dessus."""
        for page in self.PAGES:
            with self.subTest(page=page):
                self.assertEqual(self.client.get('/xx%s' % page).status_code,
                                 404)


class NoEnglishAddressGainedAPrefixTests(TestCase):
    """L'anglais vit a la racine et doit y rester: les adresses deja indexees
    ne bougent pas."""

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
        """Le plancher: sans lui, une configuration qui n'aurait prefixe
        personne passerait le test precedent."""
        bare = []
        with translation.override('fr'):
            for name in self._names_without_arguments():
                path = reverse(name)
                if _language_carried_by(path) != 'fr':
                    bare.append((name, path))
        self.assertEqual([], bare)

    def test_a_translated_slug_keeps_its_single_address(self):
        """Une page dont le chemin porte deja un nom traduit n'a pas besoin
        d'un prefixe, et en recevoir un la dupliquerait."""
        with translation.override('fr'):
            self.assertEqual(
                reverse('guide', args=['bonus-de-panoplie']),
                '/guides/bonus-de-panoplie/')
            self.assertEqual(
                reverse('encyclopedia_item',
                        args=['equipment', 44, 'epee-de-boisaille']),
                '/encyclopedia/item/equipment/44-epee-de-boisaille/')


class TheFeaturedBuildsAreBuiltForTheReaderTests(TestCase):
    """La vitrine de l'accueil ne garde pas la langue du premier lecteur."""

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
        """Le plancher: une vitrine vide rendrait le test suivant vrai sans
        rien mesurer."""
        self.assertGreaterEqual(len(self._card_links('/de/')), 1)

    def test_the_first_reader_does_not_decide_for_the_others(self):
        """La reproduction exacte du defaut: l'allemand remplit le cache,
        l'anglais et l'espagnol lisaient ses liens."""
        self._card_links('/de/')
        borrowed = []
        for language in LANGUAGES:
            for link in self._card_links(_home_path('dofus3', language)):
                if _language_carried_by(link) != language:
                    borrowed.append((language, link))
        self.assertEqual([], borrowed)

    def test_an_owner_less_build_is_named_in_the_readers_language(self):
        """`_('Anonymous')` entrait dans le cache **deja traduit**, donc le
        premier lecteur decidait aussi de ce mot pour une demi-heure. Il n'y
        a aucun build sans proprietaire dans l'instantane local, donc ce
        chemin n'est verifiable que par sa propre mise en scene."""
        Char.objects.create(
            name='sans proprietaire', char_name='sans proprietaire',
            char_class='Cra', char_build='build', level=200,
            minimum_stats=b'', minimum_crits=b'',
            stats_weight=pickle.dumps({'vit': 1}), options=b'',
            inclusions=b'', exclusions=b'', owner=None,
            game_version='dofus3', link_shared=True, deleted=False)
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
        """Un lien absolu porte l'hote de celui qui a rempli le cache, et la
        production en sert neuf."""
        absolute = [link for link in self._card_links('/fr/')
                    if '://' in link]
        self.assertEqual([], absolute)
