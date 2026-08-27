# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The trail a page declares about itself.

A BreadcrumbList is what Google prints in place of the bare url in a result,
so the last step of the trail has to be the page itself -- at the same address
its canonical gives, or the two halves of the same <head> disagree.

The hubs are enumerated from the routing table rather than typed out. The last
time a rule here was checked against a hand-written list, it passed on the
default game version and was wrong on the four others.
"""
import json
import re

from django.test import TestCase

SITE = 'https://dofusfashionista.gg'

#: Every list the site publishes, once per game version. Written as a product
#: of two axes rather than twenty addresses, so adding a version or a list
#: cannot quietly leave a page unchecked.
VERSIONS = ('', '/retro', '/beta', '/dofus2', '/touch')
HUBS = ('/encyclopedia/', '/encyclopedia/sets/', '/encyclopedia/monsters/',
        '/sharedbuilds/')


def _breadcrumbs(html):
    """Every BreadcrumbList on the page, parsed, or raises on invalid JSON."""
    found = []
    for block in re.findall(
            r'<script[^>]*ld\+json[^>]*>(.*?)</script>', html, re.S):
        data = json.loads(block)
        for entry in (data if isinstance(data, list) else [data]):
            if isinstance(entry, dict) and entry.get('@type') == \
                    'BreadcrumbList':
                found.append(entry)
    return found


class EveryListDeclaresWhereItSitsTests(TestCase):
    """/encyclopedia/ was the only page of its family without a trail.

    Its sets and its monsters declared one, and so did every item page below
    it; the hub itself, which carries more impressions than any of them and
    the worst click rate on the site, declared nothing. /sharedbuilds/ had
    none either.
    """

    NAVIGATEUR = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0'

    def _page(self, url):
        response = self.client.get(url, HTTP_ACCEPT_LANGUAGE='en',
                                   HTTP_USER_AGENT=self.NAVIGATEUR)
        self.assertEqual(response.status_code, 200,
                         '%s answered %s' % (url, response.status_code))
        return response.content.decode('utf-8', 'replace')

    def _canonical(self, html):
        tag = re.search(r'<link[^>]*canonical[^>]*>', html)
        self.assertIsNotNone(tag, 'no canonical on the page')
        return re.search(r'href="([^"]*)"', tag.group(0)).group(1)

    def test_every_list_declares_a_trail(self):
        missing = []
        checked = 0
        for version in VERSIONS:
            for hub in HUBS:
                url = version + hub
                trails = _breadcrumbs(self._page(url))
                checked += 1
                if not trails:
                    missing.append(url)
        self.assertFalse(missing, 'these lists declare no trail: %s' % missing)
        self.assertEqual(checked, len(VERSIONS) * len(HUBS))

    def test_the_trail_ends_on_the_page_itself(self):
        # The half that would stay silent: a trail can be present, valid and
        # name somebody else. It is the same <head> as the canonical, and two
        # answers to "which page is this" is worse than one.
        wrong = []
        examined = 0
        for version in VERSIONS:
            for hub in HUBS:
                url = version + hub
                html = self._page(url)
                canonical = self._canonical(html)
                for trail in _breadcrumbs(html):
                    examined += 1
                    last = trail['itemListElement'][-1]
                    if last.get('item') != canonical:
                        wrong.append((url, last.get('item'), canonical))
        self.assertFalse(
            wrong, 'the trail ends elsewhere than the canonical '
            '(page, trail, canonical): %s' % wrong[:4])
        # Counting is the point: with no trail anywhere the loop above runs
        # zero times and this test passes while checking nothing. It was green
        # against the templates that had no trail at all.
        self.assertGreaterEqual(
            examined, len(VERSIONS) * len(HUBS),
            'examined %d trails over %d lists' % (examined,
                                                  len(VERSIONS) * len(HUBS)))

    def test_a_trail_starts_at_the_site_and_is_numbered_in_order(self):
        examined = 0
        for version in VERSIONS:
            for hub in HUBS:
                url = version + hub
                for trail in _breadcrumbs(self._page(url)):
                    examined += 1
                    steps = trail['itemListElement']
                    with self.subTest(page=url):
                        self.assertGreaterEqual(len(steps), 2)
                        self.assertEqual(steps[0].get('item'), SITE + '/')
                        self.assertEqual(
                            [step.get('position') for step in steps],
                            list(range(1, len(steps) + 1)))
                        for step in steps:
                            self.assertTrue(step.get('name'), url)
        self.assertGreaterEqual(examined, len(VERSIONS) * len(HUBS),
                                'examined %d trails' % examined)

    def test_a_paginated_slice_keeps_its_page_number_in_the_trail(self):
        # The trail and the canonical are built from the same address, so this
        # is really a check that they stayed built from the same address.
        for url in ('/encyclopedia/?page=7', '/encyclopedia/monsters/?page=5',
                    '/retro/encyclopedia/?page=3'):
            with self.subTest(page=url):
                html = self._page(url)
                canonical = self._canonical(html)
                trails = _breadcrumbs(html)
                self.assertTrue(trails, '%s declares no trail' % url)
                self.assertEqual(trails[0]['itemListElement'][-1]['item'],
                                 canonical)

    def test_the_most_used_page_declares_its_trail_too(self):
        """The page that carries the quotable number was the last of the family
        without one. It is not in HUBS because it exists only on the default
        game version -- the others have 25, 17, 10 and 1 build behind them, and
        a ranking built on seventeen would be an invented authority.
        """
        for url in ('/encyclopedia/most-used/', '/fr/encyclopedia/most-used/',
                    '/de/encyclopedia/most-used/'):
            with self.subTest(page=url):
                html = self._page(url)
                trails = _breadcrumbs(html)
                self.assertTrue(trails, '%s declares no trail' % url)
                steps = trails[0]['itemListElement']
                self.assertEqual(len(steps), 3, 'expected site > hub > page')
                self.assertEqual(steps[-1]['item'], self._canonical(html))
                # L'etape du milieu doit rester dans la langue de la page :
                # renvoyer le lecteur allemand au carrefour anglais serait dire
                # a Google que les deux pages sont le meme document.
                prefix = url.split('/')[1] if url.startswith(
                    ('/fr/', '/de/', '/es/', '/pt/')) else ''
                if prefix:
                    self.assertIn('/%s/encyclopedia/' % prefix,
                                  steps[1]['item'],
                                  'the middle step leaves %s' % prefix)

    def test_the_trail_speaks_the_language_of_the_page(self):
        # A French page whose trail reads "Encyclopedia" tells Google the two
        # are the same document in one place and different in another.
        html = self.client.get('/fr/encyclopedia/').content.decode(
            'utf-8', 'replace')
        trails = _breadcrumbs(html)
        self.assertTrue(trails)
        names = [step['name'] for step in trails[0]['itemListElement']]
        self.assertNotIn('Encyclopedia', names,
                         'the French hub declares an English trail: %s' % names)


class ASharedBuildDeclaresItsTrailTests(TestCase):
    """The richest pages on the site declared no structured data at all.

    A shared build carries 5897 characters of median content against 1132 for
    an item page, it is the only family that grows without anyone writing it,
    and 2313 of them are submitted. Their list page got a trail; they had none.

    The guard is the same one the canonical already uses, char.link_shared, so
    that both halves of the <head> answer the same question. A private build
    publishing a trail would advertise an address it refuses to serve.
    """

    def setUp(self):
        from django.contrib.auth.models import User
        self.owner = User.objects.create_user('trailowner', 'trail@test.local',
                                              'pw-42-solid')
        self.client.force_login(self.owner)

    def _char(self, shared=True, game_version='dofus3', name='Ratatouille'):
        import pickle as _pickle
        from chardata.models import Char
        from fashionistapulp.modelresult import ModelResultMinimal
        from fashionistapulp.structure import get_structure
        hat = next(item for item
                   in get_structure(game_version)
                   .get_unique_items_by_type_and_level('Hat', 200)
                   # Pas de filtre sur skin : retro n'a aucun chapeau qui
                   # en porte, et un fil d'Ariane ne depend pas du rendu 3D.
                   if not item.removed)
        return Char.objects.create(
            name=name, char_name=name, char_class='Iop', char_build='Str',
            level=200, minimum_stats=b'', minimum_crits=b'',
            stats_weight=_pickle.dumps({'vit': 1}), options=b'',
            inclusions=b'', exclusions=b'',
            minimal_solution=_pickle.dumps(ModelResultMinimal(
                {'hat': hat.id}, {'options': {'ap_exo': False, 'mp_exo': False},
                                  'origin': 'generated', 'char_level': 200,
                                  'base_stats_by_attr': {
                                      'Vitality': 0, 'Wisdom': 0, 'Strength': 0,
                                      'Intelligence': 0, 'Chance': 0,
                                      'Agility': 0},
                                  'locked_equips': {}}, {})),
            owner=self.owner, link_shared=shared, game_version=game_version)

    def _page(self, char):
        from chardata.solution_view import shared_build_path
        response = self.client.get(shared_build_path(char),
                                   HTTP_ACCEPT_LANGUAGE='en')
        self.assertEqual(response.status_code, 200)
        return response.content.decode('utf-8', 'replace')

    def _canonical(self, html):
        tag = re.search(r'<link[^>]*canonical[^>]*>', html)
        self.assertIsNotNone(tag, 'no canonical on the page')
        return re.search(r'href="([^"]*)"', tag.group(0)).group(1)

    def test_a_shared_build_ends_its_trail_on_itself(self):
        html = self._page(self._char())
        trails = _breadcrumbs(html)
        self.assertTrue(trails, 'a shared build declares no trail')
        steps = trails[0]['itemListElement']
        self.assertEqual(len(steps), 3, 'expected site > community list > build')
        self.assertEqual(steps[0]['item'], SITE + '/')
        self.assertEqual(steps[-1]['item'], self._canonical(html),
                         'the trail and the canonical name different pages')
        self.assertEqual([step['position'] for step in steps], [1, 2, 3])

    def test_the_middle_step_is_the_list_of_the_same_game_version(self):
        # A retro build whose trail points at the dofus3 list sends every
        # crawler that follows it out of the version it was reading.
        for version in ('dofus3', 'retro', 'beta'):
            with self.subTest(version=version):
                char = self._char(game_version=version)
                steps = _breadcrumbs(self._page(char))[0]['itemListElement']
                prefix = '' if version == 'dofus3' else '/' + version
                self.assertEqual(steps[1]['item'],
                                 SITE + prefix + '/sharedbuilds/')

    def test_a_private_build_declares_no_trail_at_all(self):
        # The half that would stay silent: a trail printed on every page would
        # pass every test above and still advertise an address the site denies.
        # Asked through /s/, a private build answers 403 and renders nothing at
        # all, so the guard has to be exercised where the owner really sees it,
        # /solution/<id>/, which serves the same template.
        from chardata.solution_view import shared_build_path
        char = self._char(shared=False)
        self.assertEqual(
            self.client.get(shared_build_path(char)).status_code, 403,
            'a private build was served at its shared address')
        response = self.client.get('/solution/%d/' % char.id,
                                   HTTP_ACCEPT_LANGUAGE='en')
        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8', 'replace')
        self.assertFalse(_breadcrumbs(html),
                         'a private build published a trail')
        # Non-vacuite : la meme page, partagee, en publie un. Sans cela le test
        # resterait vert si /solution/ cessait d'utiliser ce gabarit.
        shared = self._char(name='Partage')
        temoin = self.client.get('/solution/%d/' % shared.id,
                                 HTTP_ACCEPT_LANGUAGE='en')
        self.assertTrue(_breadcrumbs(temoin.content.decode('utf-8', 'replace')),
                        'the same template published no trail when shared '
                        'either: this test proves nothing')

    def test_the_trail_does_not_carry_the_name_a_visitor_typed(self):
        """char_name is free text and it lands in the url slug, but <title>
        deliberately names the page by class, build and level instead. A
        breadcrumb is printed by Google in place of the url, so it follows the
        same decision -- otherwise the trail reintroduces in the results exactly
        what the title kept out.
        """
        marqueur = 'ZZQuidamZZ'
        char = self._char(name=marqueur)
        steps = _breadcrumbs(self._page(char))[0]['itemListElement']
        self.assertNotIn(marqueur, steps[-1]['name'],
                         'the trail prints what the visitor typed: %s'
                         % steps[-1]['name'])
        # Et le nom doit tout de meme dire quelque chose : un fil vide passerait
        # l'assertion ci-dessus sans rien nommer.
        self.assertIn('200', steps[-1]['name'])
        self.assertTrue(len(steps[-1]['name']) > 4, steps[-1]['name'])
