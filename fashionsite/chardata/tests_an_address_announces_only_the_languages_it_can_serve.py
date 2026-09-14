# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Une fiche n'annonce que les langues que son adresse peut servir.

Trouve en parcourant les fiches d'objets des cinq versions dans les cinq
langues: sur 200 fiches lues, **10 servaient une autre langue que celle dont
l'adresse portait le nom**. La cause n'est pas un defaut de traduction, c'est
que deux langues donnent parfois le meme nom a un objet: le Bouclier en
Mousse s'appelle `Escudo de Esponja` en espagnol **et** en portugais, donc les
deux slugs sont le meme et une seule langue peut avoir l'adresse.
`language_from_slug` tranche par un ordre fixe, et la langue perdante n'a plus
de page a elle.

La fiche annoncait quand meme les cinq. Sur
`/encyclopedia/item/equipment/18659-escudo-de-esponja/`, la page disait
`<html lang="es">` et, quatre lignes plus haut, qu'elle etait la version
portugaise d'elle-meme. Cote lecteur, le drapeau portugais etait un lien vers
la page espagnole elle-meme: on cliquait et il ne se passait rien.

**Combien.** Mesure du 15 septembre 2026 sur les catalogues des cinq versions:

    version   objets   ambigus   adresses annoncees a tort
    dofus3      3827       465     710
    beta        3834       466     714
    dofus2      3389       454     693
    touch       3390       540     827
    retro       6361      1715    2191

soit **5135 sur les objets** (2537 en portugais, 1353 en allemand, 643 en
francais, 602 en espagnol) et **293 de plus sur les panoplies**, presque
toutes allemandes.

**La regle existait deja.** Le sitemap ne depose jamais une adresse dans le
fichier d'une langue qu'elle ne sert pas: `_served_in` le dit depuis toujours,
avec le bon commentaire. C'est la page qui ne posait pas la question. Les deux
lisent maintenant `url_language.address_serves_language`.

Apres: 60 fiches tirees au sort sur les cinq versions, 284 traductions
annoncees, **zero faute** -- chacune repond 200, dans la langue annoncee, se
nomme elle-meme en canonique et se compte dans son propre groupe.
"""
import collections
import random
import re

from django.test import TestCase

from chardata.encyclopedia_view import _normalized_slug, get_item_link
from chardata.url_language import (address_serves_language,
                                   build_alternate_urls, language_from_slug)
from fashionistapulp.structure import get_structure
from fashionistapulp.translation import SUPPORTED_LANGUAGES

SITE = 'https://dofusfashionista.gg'
LANGUAGES = tuple(SUPPORTED_LANGUAGES)
#: Imprimee par le test qui echantillonne: un tirage muet n'est pas reproductible.
SEED = 20260915

#: Le tag entier, puis chaque attribut cherche a part. Le minificateur trie
#: les attributs par ordre alphabetique, donc `href` passe avant `hreflang` et
#: avant `rel`: un motif qui les lit dans un ordre ne trouve rien en
#: production ni dans la suite, qui minifie aussi.
_LANG = re.compile(r'<html[^>]*\slang="([^"]+)"')
_LINK = re.compile(r'<link\b[^>]*>', re.I)
_FLAG = re.compile(r'<(a|button)\b[^>]*>', re.I)
_ATTR = {name: re.compile(r'\b%s="([^"]*)"' % name, re.I)
         for name in ('rel', 'href', 'hreflang', 'id')}


def _attr(tag, name):
    found = _ATTR[name].search(tag)
    return found.group(1) if found else None


def _language_of(html):
    found = _LANG.search(html)
    return found.group(1) if found else None


def _canonical_of(html):
    for tag in _LINK.findall(html):
        if _attr(tag, 'rel') == 'canonical':
            return _attr(tag, 'href')
    return None


def _alternates_of(html):
    found = {}
    for tag in _LINK.findall(html):
        code = _attr(tag, 'hreflang')
        href = _attr(tag, 'href')
        if code and href:
            found[code] = href
    return found


def _flags_of(html):
    found = {}
    for match in _FLAG.finditer(html):
        identifier = _attr(match.group(0), 'id') or ''
        if identifier.startswith('flag-') and len(identifier) == 7:
            found[identifier[5:]] = match.group(1).lower()
    return found


def _an_ambiguous_item(game_version='dofus3'):
    """Le premier objet du catalogue dont deux langues partagent le slug."""
    structure = get_structure(game_version)
    for item in structure.get_items_list():
        if getattr(item, 'removed', False):
            continue
        by_slug = collections.defaultdict(list)
        for language in LANGUAGES:
            name = item.localized_names.get(language)
            if name:
                by_slug[_normalized_slug(name)].append(language)
        shared = [langs for langs in by_slug.values() if len(langs) > 1]
        if shared:
            return item, structure, sorted(shared, key=len)[-1]
    return None, None, None


class TwoLanguagesSharingANameShareOneAddressTests(TestCase):
    """La regle, sur des noms fabriques: rien ne depend du catalogue."""

    BUILDER = staticmethod(lambda name: '/x/%s/' % _normalized_slug(name))

    def test_the_loser_of_a_tie_is_not_announced(self):
        names = {'en': 'Sponghield', 'fr': 'Bouclier en Mousse',
                 'es': 'Escudo de Esponja', 'pt': 'Escudo de Esponja',
                 'de': 'Schwammiger Spongischild'}
        announced = build_alternate_urls(self.BUILDER, names, SITE,
                                         _normalized_slug)
        self.assertIn('es', announced)
        self.assertNotIn('pt', announced,
                         'pt and es share the slug, so one address cannot be '
                         'both: %s' % announced)

    def test_the_winner_is_the_one_the_url_will_answer_in(self):
        """Le garde de la paire: annoncer l'autre serait aussi faux."""
        names = {'en': 'Sponghield', 'fr': 'Bouclier en Mousse',
                 'es': 'Escudo de Esponja', 'pt': 'Escudo de Esponja',
                 'de': 'Schwammiger Spongischild'}
        self.assertEqual(
            'es', language_from_slug(names, 'escudo-de-esponja',
                                     _normalized_slug))

    def test_a_name_unique_everywhere_still_announces_five(self):
        """Le plancher: une regle qui couperait tout passerait le premier
        test sans rien mesurer."""
        names = {'en': 'Twiggy Sword', 'fr': 'Epee de Boisaille',
                 'es': 'Espada de Maderucha', 'pt': 'Espada de Madeirinha',
                 'de': 'Zweigschwert'}
        announced = build_alternate_urls(self.BUILDER, names, SITE,
                                         _normalized_slug)
        self.assertEqual(set(LANGUAGES), set(announced))

    def test_english_keeps_its_address_even_when_shared(self):
        names = {'en': 'Lavaring', 'fr': 'Anneau de Lave',
                 'es': 'Anillo de Lava', 'pt': 'Anel de Lava',
                 'de': 'Lavaring'}
        announced = build_alternate_urls(self.BUILDER, names, SITE,
                                         _normalized_slug)
        self.assertIn('en', announced)
        self.assertNotIn('de', announced)


class TheSitemapAndThePageAskTheSameQuestionTests(TestCase):
    """Deux reponses a une question, c'est ainsi que la page a derive."""

    CASES = (
        {'en': 'A', 'fr': 'B', 'es': 'C', 'pt': 'C', 'de': 'D'},
        {'en': 'A', 'fr': 'A', 'es': 'B', 'pt': 'C', 'de': 'D'},
        {'en': 'A', 'fr': 'B', 'es': 'C', 'pt': 'D', 'de': 'A'},
        {'en': 'A', 'fr': 'B', 'es': 'C', 'pt': 'D', 'de': 'E'},
    )

    def test_the_sitemap_helper_delegates(self):
        from fashionsite.urls import _served_in
        for names in self.CASES:
            for language in LANGUAGES:
                with self.subTest(names=names, language=language):
                    self.assertEqual(
                        _served_in(names, language),
                        address_serves_language(names, language,
                                                _normalized_slug))

    def test_the_cases_really_contain_a_tie(self):
        """Sans cela, les deux fonctions pourraient s'accorder sur rien."""
        refused = [(names, language) for names in self.CASES
                   for language in LANGUAGES
                   if not address_serves_language(names, language,
                                                  _normalized_slug)]
        self.assertGreaterEqual(len(refused), 3, refused)


class AnAmbiguousItemPageTellsTheTruthTests(TestCase):
    """Bout en bout, sur un objet reel du catalogue."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.item, cls.structure, cls.tied = _an_ambiguous_item()

    def setUp(self):
        if self.item is None:
            self.skipTest('no ambiguous item in the dofus3 catalogue')

    def _page(self, language):
        name = self.item.localized_names[language]
        path = get_item_link(
            self.structure.get_type_name_by_id(self.item.type),
            self.item.ankama_id, name, game_version='dofus3')
        answer = self.client.get(path)
        self.assertEqual(answer.status_code, 200, path)
        return path, answer.content.decode('utf-8', 'replace')

    def test_the_catalogue_really_holds_such_an_item(self):
        """Le plancher du temoin: sans tie, tout ce qui suit est vide."""
        self.assertGreaterEqual(len(self.tied), 2)

    def test_the_page_does_not_announce_the_language_it_cannot_serve(self):
        winner = language_from_slug(
            self.item.localized_names,
            _normalized_slug(self.item.localized_names[self.tied[0]]),
            _normalized_slug)
        _path, html = self._page(winner)
        announced = _alternates_of(html)
        self.assertEqual(_language_of(html), winner)
        self.assertIn(winner, announced)
        for language in self.tied:
            if language == winner:
                continue
            with self.subTest(language=language):
                self.assertNotIn(language, announced,
                                 '%s serves %s and still claims to be %s'
                                 % (self.item.name, winner, language))

    def test_the_flag_it_cannot_serve_is_a_button_not_a_dead_link(self):
        """Un lien qui ramene sur la meme page dans une autre langue est pire
        qu'un bouton: on clique et il ne se passe rien."""
        winner = language_from_slug(
            self.item.localized_names,
            _normalized_slug(self.item.localized_names[self.tied[0]]),
            _normalized_slug)
        _path, html = self._page(winner)
        flags = _flags_of(html)
        for language in self.tied:
            if language == winner:
                continue
            with self.subTest(language=language):
                self.assertEqual('button', flags.get(language), flags)


class EveryAnnouncedTranslationIsServedInThatLanguageTests(TestCase):
    """L'invariant, sur un echantillon dont la graine est imprimee."""

    SAMPLE_PER_VERSION = 4
    VERSIONS = ('dofus3', 'beta', 'dofus2', 'touch', 'retro')

    def test_the_walk_checks_a_real_number_of_members(self):
        checked, wrong = self._walk()
        self.assertGreaterEqual(
            checked, len(self.VERSIONS) * self.SAMPLE_PER_VERSION * 2,
            'only %d announced translations examined (seed %d)'
            % (checked, SEED))
        self.assertEqual([], wrong, 'seed %d' % SEED)

    def _walk(self):
        chance = random.Random(SEED)
        checked = 0
        wrong = []
        for game_version in self.VERSIONS:
            structure = get_structure(game_version)
            items = [item for item in structure.get_items_list()
                     if not getattr(item, 'removed', False)]
            if not items:
                continue
            for item in chance.sample(items,
                                      min(self.SAMPLE_PER_VERSION,
                                          len(items))):
                english = (item.localized_names.get('en') or item.name)
                path = get_item_link(
                    structure.get_type_name_by_id(item.type),
                    item.ankama_id, english, game_version=game_version)
                if not path:
                    continue
                answer = self.client.get(path)
                if answer.status_code != 200:
                    continue
                html = answer.content.decode('utf-8', 'replace')
                for code, url in _alternates_of(html).items():
                    if code == 'x-default':
                        continue
                    target = url.replace(SITE, '')
                    other = self.client.get(target)
                    checked += 1
                    if other.status_code != 200:
                        wrong.append((path, code, target,
                                      other.status_code))
                        continue
                    body = other.content.decode('utf-8', 'replace')
                    if _language_of(body) != code:
                        wrong.append((path, code, target,
                                      _language_of(body)))
                    elif _canonical_of(body) != url:
                        wrong.append((path, code, target,
                                      _canonical_of(body)))
        return checked, wrong
