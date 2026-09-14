# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Une page qui existe en cinq langues le declare, et ne ment jamais.

Trouve en suivant les liens du site depuis ses 25 racines, deux niveaux de
profondeur. Mesure du 15 septembre 2026: **585 pages repondaient 200 et 530
n'annoncaient aucune traduction**. Seules trois formes le faisaient -- la
racine, l'encyclopedie et l'index des guides -- parce que la liste des pages
autorisees a publier un groupe etait ecrite a la main, avec six noms, et avec
cette note:

    /es/faq/ does not exist, and announcing it in hreflang would point Google
    at a 404, which is worse than announcing nothing.

La regle etait juste. Le fait avait cesse d'etre vrai: depuis la section 91 la
version par defaut prefixe les 115 routes dont le chemin ne nomme pas deja une
langue, donc /es/faq/ repond 200 en espagnol. Le routeur et le bloc hreflang
repondaient a la meme question avec deux listes, et les listes avaient
diverge.

Les deux lisent maintenant `game_urls.routes_published_once_per_language`.

**Publier un groupe faux est pire que n'en publier aucun.** Google lit un
groupe par la reference qu'il fait a lui-meme et abandonne l'ensemble des
qu'un membre se renie. Deux familles se renient, et les deux se taisent
desormais:

- les cinq adresses d'un build sont canoniques a la MEME, parce que
  `shared_build_path` porte la version et jamais la langue;
- les copies d'`/about/`, `/faq/`, `/support/` et `/license/` servies sous un
  prefixe de version sont canoniques a la page sans version.

Le garde du canonique existait deja mais lisait `canonical_url`, alors que ces
pages ecrivent leur canonique ailleurs: `canonical_path`, ou un `{% url %}`
dans le gabarit. Il comparait donc a None et laissait tout passer: **225 des
585 pages auraient publie un groupe contredisant leur propre canonique.**

Apres: 330 pages publient, 1650 membres verifies un par un, **zero en faute**
-- chacun repond 200, dans la langue qu'il annonce, et se nomme lui-meme.
255 se taisent, et chacune pour une raison nommee.
"""
import pickle
import re

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from chardata.game_urls import routes_published_once_per_language
from chardata.models import Char
from chardata.url_language import (SITE_URL, canonical_the_page_will_render,
                                   prefixed_page_names)

_LANG = re.compile(r'<html[^>]*\slang="([^"]+)"')
_ALTERNATE = re.compile(r'<link\b[^>]*hreflang=[^>]*>', re.I)
_HREFLANG = re.compile(r'hreflang="([^"]+)"')
_HREF = re.compile(r'href="([^"]*)"')
_CANONICAL = re.compile(r'<link[^>]*rel="canonical"[^>]*>', re.I)
#: Le tag entier: le minificateur trie les attributs, donc rel et href
#: arrivent dans l'ordre qu'il veut.
_ANCHOR = re.compile(r'<(?:a|button)\b[^>]*flag-btn[^>]*>', re.I)

LANGUAGES = ('en', 'fr', 'es', 'pt', 'de')


def _language_of(html):
    found = _LANG.search(html)
    return found.group(1) if found else None


def _canonical_of(html):
    tag = _CANONICAL.search(html)
    if tag is None:
        return None
    href = _HREF.search(tag.group(0))
    return href.group(1) if href else None


def _alternates_of(html):
    found = {}
    for tag in _ALTERNATE.findall(html):
        code = _HREFLANG.search(tag)
        href = _HREF.search(tag)
        if code and href:
            found[code.group(1)] = href.group(1)
    return found


class TheRuleIsReadFromTheRoutesTests(TestCase):
    """Le routeur et le bloc hreflang repondent a la meme question."""

    def test_the_names_come_from_the_routes_themselves(self):
        from_routes = {entry.name
                       for entry in routes_published_once_per_language()
                       if entry.name}
        self.assertTrue(from_routes <= prefixed_page_names(),
                        'these routes are prefixed but may not say so: %s'
                        % sorted(from_routes - prefixed_page_names()))

    def test_there_are_enough_of_them_to_be_the_rule_and_not_a_list(self):
        """Le plancher: la liste ecrite a la main en comptait six."""
        self.assertGreaterEqual(len(prefixed_page_names()), 100)

    def test_a_page_whose_path_names_its_language_is_left_alone(self):
        """Une fiche d'objet ou un guide porte sa langue dans son slug: elle
        a UNE adresse, et lui donner un prefixe la dupliquerait."""
        for name in ('guide', 'encyclopedia_item', 'encyclopedia_set',
                     'encyclopedia_monster', 'encyclopedia_resource'):
            with self.subTest(name=name):
                self.assertNotIn(name, prefixed_page_names())


class TheGateReadsTheCanonicalThePageRendersTests(TestCase):
    """Trois orthographes du canonique; le garde doit lire la bonne."""

    def setUp(self):
        self.request = RequestFactory().get('/fr/retro/about/')

    def test_an_absolute_canonical_url_wins(self):
        self.assertEqual(
            canonical_the_page_will_render(
                self.request, {'canonical_url': SITE_URL + '/x/',
                               'canonical_path': '/y/'}),
            SITE_URL + '/x/')

    def test_a_relative_canonical_path_is_made_absolute(self):
        self.assertEqual(
            canonical_the_page_will_render(self.request,
                                           {'canonical_path': '/fr/about/'}),
            SITE_URL + '/fr/about/')

    def test_with_neither_it_is_the_page_itself(self):
        """Ce que base.html rend par defaut."""
        self.assertEqual(canonical_the_page_will_render(self.request, {}),
                         SITE_URL + '/fr/retro/about/')


class EveryGroupPublishedIsReciprocalTests(TestCase):
    """Un membre qui se renie fait abandonner le groupe entier."""

    #: Des pages qui n'existaient dans aucune autre langue avant la section 91,
    #: plus deux carrefours qui publiaient deja, comme temoins.
    PAGES = ('/fr/about/', '/es/faq/', '/pt/support/', '/de/license/',
             '/fr/sharedbuilds/', '/es/quickstart/', '/fr/forgemagie/',
             '/de/import/text/', '/fr/choose_compare_sets/',
             '/es/smartbuild/', '/fr/retro/sharedbuilds/',
             '/fr/guides/', '/es/encyclopedia/')

    def _html(self, path):
        page = self.client.get(path)
        self.assertEqual(page.status_code, 200, path)
        return page.content.decode('utf-8', 'replace')

    def test_each_page_announces_its_five_languages(self):
        thin = []
        for path in self.PAGES:
            announced = _alternates_of(self._html(path))
            missing = [code for code in LANGUAGES if code not in announced]
            if missing or 'x-default' not in announced:
                thin.append((path, missing, sorted(announced)))
        self.assertEqual([], thin)

    def test_every_member_answers_in_its_language_and_names_itself(self):
        """La mesure qui compte, faite membre par membre."""
        checked = 0
        wrong = []
        for path in self.PAGES:
            for code, url in _alternates_of(self._html(path)).items():
                if code == 'x-default':
                    continue
                target = url.replace(SITE_URL, '')
                answer = self.client.get(target)
                checked += 1
                if answer.status_code != 200:
                    wrong.append((path, code, target, answer.status_code))
                    continue
                html = answer.content.decode('utf-8', 'replace')
                if _language_of(html) != code:
                    wrong.append((path, code, target, _language_of(html)))
                elif _canonical_of(html) != url:
                    wrong.append((path, code, target, _canonical_of(html)))
        self.assertEqual([], wrong)
        self.assertGreaterEqual(checked, len(self.PAGES) * len(LANGUAGES))


class AGroupThatWouldNotBeReciprocalIsNotPublishedTests(TestCase):
    """Les deux familles qui se renient, et la raison de chacune."""

    def setUp(self):
        self.owner = User.objects.create_user(
            username='five-languages-witness', email='f@test.local',
            password='pw-42-solid')
        self.build = Char.objects.create(
            name='projet temoin', char_name='NoSpaceHere',
            char_class='Iop', char_build='build', level=200,
            minimum_stats=b'', minimum_crits=b'',
            stats_weight=pickle.dumps({'vit': 1}), options=b'',
            inclusions=b'', exclusions=b'', owner=self.owner,
            game_version='dofus3', link_shared=True, deleted=False,
            minimal_solution=self._a_solution())

    @staticmethod
    def _a_solution():
        """Sans solution enregistree, /s/ rend 404 pour une raison qui n'a
        rien a voir avec ce qui est mesure ici."""
        from fashionistapulp.modelresult import ModelResultMinimal
        from fashionistapulp.structure import get_structure
        structure = get_structure('dofus3')
        hats = [item for item in structure.get_items_list()
                if structure.get_type_name_by_id(item.type) == 'Hat'
                and not getattr(item, 'removed', False)]
        return pickle.dumps(ModelResultMinimal(
            {'hat': hats[0].id},
            {'options': {'ap_exo': False, 'mp_exo': False},
             'origin': 'generated', 'char_level': 200,
             'base_stats_by_attr': {'Vitality': 0, 'Wisdom': 0,
                                    'Strength': 0, 'Intelligence': 0,
                                    'Chance': 0, 'Agility': 0},
             'locked_equips': {}}, {}))

    def _build_path(self, language=''):
        from chardata.solution_view import shared_build_path
        prefix = '/%s' % language if language else ''
        return prefix + shared_build_path(self.build)

    def test_the_build_page_is_really_there(self):
        """Le plancher: un 404 rendrait le test suivant vrai pour rien."""
        for language in ('', 'fr'):
            with self.subTest(language=language or 'en'):
                self.assertEqual(
                    self.client.get(self._build_path(language)).status_code,
                    200)

    def test_a_build_page_announces_no_group(self):
        """Son nom ne contient pas d'espace, donc rien ne le sauve par
        accident d'echappement: c'est la vue qui dit non."""
        for language in ('', 'fr', 'es'):
            with self.subTest(language=language or 'en'):
                html = self.client.get(
                    self._build_path(language)).content.decode('utf-8')
                self.assertEqual({}, _alternates_of(html))

    def test_a_build_page_keeps_its_language_flags(self):
        """Le lecteur, lui, veut bien changer de langue: seuls les moteurs
        sont concernes par le groupe."""
        html = self.client.get(self._build_path('fr')).content.decode('utf-8')
        links = [tag for tag in _ANCHOR.findall(html) if tag.startswith('<a')]
        self.assertEqual(len(LANGUAGES) - 1, len(links), links)

    def test_a_version_prefixed_copy_announces_none(self):
        """/fr/retro/about/ est canonique sur /fr/about/: une page, une
        adresse, et le groupe appartient a celle qui est canonique."""
        for path in ('/fr/retro/about/', '/es/dofus2/faq/',
                     '/de/touch/support/', '/pt/beta/license/'):
            with self.subTest(path=path):
                page = self.client.get(path)
                self.assertEqual(page.status_code, 200)
                html = page.content.decode('utf-8', 'replace')
                self.assertEqual({}, _alternates_of(html))
                self.assertNotEqual(_canonical_of(html), SITE_URL + path)


class TheFlagsAreLinksWhereThePageHasTranslationsTests(TestCase):
    """Un bouton n'est pas un lien: un robot n'en suit aucun."""

    def test_a_page_that_has_translations_offers_four_links(self):
        for path in ('/fr/about/', '/es/sharedbuilds/', '/fr/quickstart/'):
            with self.subTest(path=path):
                html = self.client.get(path).content.decode('utf-8')
                links = [tag for tag in _ANCHOR.findall(html)
                         if tag.startswith('<a')]
                self.assertEqual(len(LANGUAGES) - 1, len(links),
                                 '%s offers %d language links' % (path,
                                                                  len(links)))
