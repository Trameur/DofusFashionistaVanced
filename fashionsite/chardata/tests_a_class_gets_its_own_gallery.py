# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
import json
import re

from django.test import TestCase
from django.urls import resolve
from django.utils import translation

from chardata.shared_builds_view import CLASS_PAGE_MIN_BUILDS

SITE = 'https://dofusfashionista.gg'
NAVIGATEUR = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36')


def _solution():
    import pickle
    from fashionistapulp.modelresult import ModelResultMinimal
    entree = {
        'options': {'ap_exo': False, 'mp_exo': False},
        'origin': 'generated',
        'char_level': 200,
        'base_stats_by_attr': {'Vitality': 0, 'Wisdom': 0, 'Strength': 0,
                               'Intelligence': 0, 'Chance': 0, 'Agility': 0},
        'locked_equips': {},
    }
    return pickle.dumps(ModelResultMinimal({}, entree, {}))


def _builds(nombre, char_class='Cra', game_version='dofus3'):
    from chardata.models import Char
    solution = _solution()
    Char.objects.bulk_create([
        Char(name='Build %d' % i, char_name='hero%d' % i,
             char_class=char_class, char_build='Str', level=200,
             minimum_stats=b'', minimum_crits=b'', stats_weight=b'',
             options=b'', inclusions=b'', exclusions=b'',
             minimal_solution=solution, link_shared=True,
             game_version=game_version)
        for i in range(nombre)])


class _Page(TestCase):

    def _get(self, chemin, langue='en'):
        return self.client.get(chemin, HTTP_ACCEPT_LANGUAGE=langue,
                               HTTP_USER_AGENT=NAVIGATEUR)

    def _html(self, chemin, langue='en'):
        reponse = self._get(chemin, langue)
        self.assertEqual(200, reponse.status_code,
                         '%s answered %s' % (chemin, reponse.status_code))
        return reponse.content.decode('utf-8', 'replace')

    @staticmethod
    def _canonical(html):
        tag = re.search(r'<link[^>]*rel="canonical"[^>]*>', html)
        return re.search(r'href="([^"]*)"', tag.group(0)).group(1) if tag else None

    @staticmethod
    def _robots(html):
        for tag in re.findall(r'<meta[^>]*>', html):
            if 'name="robots"' in tag:
                return re.search(r'content="([^"]*)"', tag).group(1)
        return None

    @staticmethod
    def _title(html):
        return re.search(r'<title>(.*?)</title>', html, re.S).group(1).strip()

    @staticmethod
    def _hreflangs(html):
        return re.findall(r'<link[^>]*hreflang="([^"]+)"[^>]*>', html)

    @staticmethod
    def _trail(html):
        for bloc in re.findall(r'<script[^>]*ld\+json[^>]*>(.*?)</script>',
                               html, re.S):
            donnees = json.loads(bloc)
            if donnees.get('@type') == 'BreadcrumbList':
                return donnees['itemListElement']
        return None


class AClassPageAnswersUnderEveryPrefixTests(_Page):

    def test_the_route_is_the_class_route(self):
        for langue, chemin in (('en', '/sharedbuilds/cra/'),
                               ('fr', '/fr/sharedbuilds/cra/'),
                               ('en', '/touch/sharedbuilds/cra/'),
                               ('fr', '/fr/touch/sharedbuilds/cra/')):
            with self.subTest(chemin=chemin), translation.override(langue):
                self.assertEqual('shared_builds_class',
                                 resolve(chemin).url_name)

    def test_each_prefix_serves_the_page_as_its_own_canonical(self):
        _builds(2)
        _builds(2, game_version='touch')
        for chemin in ('/sharedbuilds/cra/', '/fr/sharedbuilds/cra/',
                       '/touch/sharedbuilds/cra/', '/fr/touch/sharedbuilds/cra/'):
            with self.subTest(chemin=chemin):
                self.assertEqual(SITE + chemin, self._canonical(self._html(chemin)))

    def test_the_title_names_the_class_in_the_page_language(self):
        _builds(2)
        self.assertTrue(self._title(self._html('/sharedbuilds/cra/'))
                        .startswith('Cra Builds'))
        titre = self._title(self._html('/fr/sharedbuilds/cra/', 'fr'))
        self.assertTrue(titre.startswith('Builds Crâ'), titre)
        titre = self._title(self._html('/es/sharedbuilds/cra/', 'es'))
        self.assertTrue(titre.startswith('Builds de Ocra'), titre)

    def test_the_version_stays_in_the_title(self):
        _builds(2, game_version='touch')
        self.assertIn('(Dofus Touch)',
                      self._title(self._html('/touch/sharedbuilds/cra/')))

    def test_the_page_lists_only_its_class(self):
        _builds(3)
        _builds(4, char_class='Iop')
        reponse = self._get('/sharedbuilds/cra/')
        classes = {b['char'].char_class for b in reponse.context['builds']}
        self.assertEqual({'Cra'}, classes)
        self.assertEqual(3, reponse.context['page_obj'].paginator.count)

    def test_a_class_filter_in_the_query_does_not_override_the_path(self):
        _builds(3)
        _builds(4, char_class='Iop')
        reponse = self._get('/sharedbuilds/cra/?char_class=Iop')
        self.assertEqual(3, reponse.context['page_obj'].paginator.count)

    def test_the_trail_goes_through_the_gallery_of_the_same_prefixes(self):
        _builds(2, game_version='touch')
        html = self._html('/fr/touch/sharedbuilds/cra/', 'fr')
        etapes = self._trail(html)
        self.assertEqual([1, 2, 3], [e['position'] for e in etapes])
        self.assertEqual(SITE + '/', etapes[0]['item'])
        self.assertEqual(SITE + '/fr/touch/sharedbuilds/', etapes[1]['item'])
        self.assertEqual(self._canonical(html), etapes[2]['item'])
        self.assertIn('Crâ', etapes[2]['name'])


class AnotherNameForTheClassRedirectsTests(_Page):

    def test_a_localized_name_moves_permanently_to_the_canonical_slug(self):
        cas = (
            ('/sharedbuilds/steamer/', '/sharedbuilds/foggernaut/'),
            ('/sharedbuilds/zobal/', '/sharedbuilds/masqueraider/'),
            ('/fr/sharedbuilds/roublard/', '/fr/sharedbuilds/rogue/'),
            ('/de/sharedbuilds/halsabschneider/', '/de/sharedbuilds/rogue/'),
            ('/es/sharedbuilds/ocra/', '/es/sharedbuilds/cra/'),
            ('/fr/touch/sharedbuilds/steamer/?order_by=likes&page=2',
             '/fr/touch/sharedbuilds/foggernaut/?order_by=likes&page=2'),
        )
        for chemin, cible in cas:
            with self.subTest(chemin=chemin):
                reponse = self._get(chemin)
                self.assertEqual(301, reponse.status_code)
                self.assertEqual(cible, reponse['Location'])

    def test_an_unknown_slug_is_not_found(self):
        for chemin in ('/sharedbuilds/nope/', '/sharedbuilds/a/b/',
                       '/sharedbuilds/cra/extra/', '/fr/sharedbuilds/nope/',
                       '/touch/sharedbuilds/nope/'):
            with self.subTest(chemin=chemin):
                self.assertEqual(404, self._get(chemin).status_code)

    def test_a_class_the_version_lacks_goes_back_to_that_gallery(self):
        cas = (
            ('/touch/sharedbuilds/forgelance/', '/touch/sharedbuilds/'),
            ('/fr/retro/sharedbuilds/rogue/', '/fr/retro/sharedbuilds/'),
            ('/retro/sharedbuilds/roublard/', '/retro/sharedbuilds/'),
            ('/dofus2/sharedbuilds/forgelance/', '/dofus2/sharedbuilds/'),
        )
        for chemin, cible in cas:
            with self.subTest(chemin=chemin):
                reponse = self._get(chemin)
                self.assertEqual(302, reponse.status_code)
                self.assertEqual(cible, reponse['Location'])

    def test_a_class_without_a_build_goes_back_to_that_gallery(self):
        _builds(3)
        for chemin, cible in (('/touch/sharedbuilds/cra/', '/touch/sharedbuilds/'),
                              ('/fr/retro/sharedbuilds/cra/', '/fr/retro/sharedbuilds/'),
                              ('/sharedbuilds/iop/', '/sharedbuilds/')):
            with self.subTest(chemin=chemin):
                reponse = self._get(chemin)
                self.assertEqual(302, reponse.status_code)
                self.assertEqual(cible, reponse['Location'])


class AThinClassPageStaysOutOfTheIndexTests(_Page):

    def _plan(self):
        reponse = self.client.get('/sitemap-pages.xml')
        self.assertEqual(200, reponse.status_code)
        plan = reponse.content.decode('utf-8')
        self.assertIn(SITE + '/sharedbuilds/<', plan)
        return plan

    def test_below_the_threshold_it_is_noindex_and_announces_no_group(self):
        _builds(CLASS_PAGE_MIN_BUILDS - 1)
        html = self._html('/sharedbuilds/cra/')
        self.assertEqual('noindex, follow', self._robots(html))
        self.assertEqual([], self._hreflangs(html))
        self.assertNotIn('/sharedbuilds/cra/', self._plan())

    def test_at_the_threshold_it_is_indexed_and_submitted(self):
        _builds(CLASS_PAGE_MIN_BUILDS)
        html = self._html('/sharedbuilds/cra/')
        self.assertEqual('index, follow', self._robots(html))
        self.assertEqual(sorted(['en', 'fr', 'es', 'pt', 'de', 'x-default']),
                         sorted(self._hreflangs(html)))
        plan = self._plan()
        for chemin in ('/sharedbuilds/cra/', '/fr/sharedbuilds/cra/',
                       '/es/sharedbuilds/cra/', '/pt/sharedbuilds/cra/'):
            with self.subTest(chemin=chemin):
                self.assertIn('<loc>%s%s</loc>' % (SITE, chemin), plan)
        self.assertNotIn('/de/sharedbuilds/cra/', plan)
        self.assertNotIn('/touch/sharedbuilds/cra/', plan)

    def test_every_submitted_class_page_is_its_own_canonical(self):
        _builds(CLASS_PAGE_MIN_BUILDS, game_version='touch')
        plan = self._plan()
        soumises = re.findall(r'<loc>(%s[^<]*/sharedbuilds/[a-z]+/)</loc>'
                              % re.escape(SITE), plan)
        self.assertEqual(4, len(soumises), soumises)
        for adresse in soumises:
            with self.subTest(adresse=adresse):
                html = self._html(adresse.replace(SITE, ''))
                self.assertEqual(adresse, self._canonical(html))
                self.assertEqual('index, follow', self._robots(html))

    def test_a_class_the_version_lacks_is_never_submitted(self):
        _builds(CLASS_PAGE_MIN_BUILDS, char_class='Forgelance',
                game_version='touch')
        self.assertNotIn('/touch/sharedbuilds/forgelance/', self._plan())

    def test_a_filtered_class_page_points_back_at_the_plain_one(self):
        _builds(CLASS_PAGE_MIN_BUILDS)
        for requete in ('?order_by=likes', '?page=2&search=hero',
                        '?char_class=Iop'):
            with self.subTest(requete=requete):
                html = self._html('/fr/sharedbuilds/cra/' + requete, 'fr')
                self.assertEqual(SITE + '/fr/sharedbuilds/cra/',
                                 self._canonical(html))

    def test_the_second_page_names_itself_and_publishes_no_group(self):
        _builds(30)
        html = self._html('/sharedbuilds/cra/?page=2')
        self.assertEqual(SITE + '/sharedbuilds/cra/?page=2',
                         self._canonical(html))
        self.assertEqual([], self._hreflangs(html))
        self.assertEqual('index, follow', self._robots(html))


class TheGalleryLinksEachClassTests(_Page):

    def _liens(self, html):
        nav = re.search(r'<nav[^>]*aria-label="Builds by class"[^>]*>(.*?)</nav>',
                        html, re.S)
        self.assertIsNotNone(nav, 'no class navigation on the page')
        return re.findall(r'<a[^>]*>.*?</a>', nav.group(1), re.S)

    def test_the_gallery_links_every_class_that_has_a_build(self):
        _builds(3)
        _builds(1, char_class='Rogue')
        liens = self._liens(self._html('/sharedbuilds/'))
        self.assertEqual(2, len(liens), liens)
        cra = [l for l in liens if 'href="/sharedbuilds/cra/"' in l]
        self.assertEqual(1, len(cra), liens)
        self.assertIn('Cra (3)', cra[0])
        self.assertTrue(any('href="/sharedbuilds/rogue/"' in l
                            and 'Rogue (1)' in l for l in liens), liens)
        self.assertFalse(any('aria-current' in l for l in liens))

    def test_the_class_page_marks_itself_and_links_back_to_all(self):
        _builds(3, game_version='touch')
        _builds(2, char_class='Iop', game_version='touch')
        liens = self._liens(self._html('/touch/sharedbuilds/cra/'))
        courant = [l for l in liens if 'aria-current="page"' in l]
        self.assertEqual(1, len(courant), liens)
        self.assertIn('href="/touch/sharedbuilds/cra/"', courant[0])
        self.assertTrue(any('href="/touch/sharedbuilds/"' in l
                            and 'All Classes' in l for l in liens), liens)
        self.assertTrue(any('href="/touch/sharedbuilds/iop/"' in l
                            for l in liens), liens)

    def test_the_labels_are_in_the_page_language(self):
        _builds(3, char_class='Rogue')
        html = self._html('/fr/sharedbuilds/', 'fr')
        nav = re.search(r'<nav[^>]*aria-label="Builds par classe"[^>]*>(.*?)</nav>',
                        html, re.S)
        self.assertIsNotNone(nav)
        self.assertIn('Roublard (3)', nav.group(1))
        self.assertIn('href="/fr/sharedbuilds/rogue/"', nav.group(1))
        option = re.search(r'<option[^>]*value="Rogue"[^>]*>(.*?)</option>',
                           html, re.S)
        self.assertEqual('Roublard', option.group(1).strip())

    def test_a_class_the_version_lacks_is_not_listed(self):
        _builds(2, char_class='Forgelance', game_version='touch')
        _builds(2, game_version='touch')
        html = self._html('/touch/sharedbuilds/')
        self.assertNotIn('forgelance', ' '.join(self._liens(html)))

    def test_the_counts_cost_nothing_once_warm(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        def comptages(contexte):
            return [q for q in contexte.captured_queries
                    if 'GROUP BY' in q['sql'] and 'char_class' in q['sql']]

        _builds(3)
        with CaptureQueriesContext(connection) as froid:
            self._html('/sharedbuilds/')
        self.assertEqual(1, len(comptages(froid)))
        with CaptureQueriesContext(connection) as tiede:
            self._html('/sharedbuilds/')
        self.assertEqual([], comptages(tiede))


class TheGalleryItselfIsUnchangedTests(_Page):

    def test_title_canonical_heading_and_trail(self):
        _builds(3)
        html = self._html('/sharedbuilds/')
        self.assertEqual('Community Dofus Builds · The Dofus Fashionista',
                         self._title(html))
        self.assertEqual(SITE + '/sharedbuilds/', self._canonical(html))
        self.assertEqual('index, follow', self._robots(html))
        self.assertRegex(html, r'<h1[^>]*>Shared Builds</h1>')
        etapes = self._trail(html)
        self.assertEqual(2, len(etapes))
        self.assertEqual(SITE + '/sharedbuilds/', etapes[1]['item'])

    def test_the_old_filter_still_filters(self):
        _builds(3)
        _builds(4, char_class='Iop')
        reponse = self._get('/sharedbuilds/?char_class=Iop')
        self.assertEqual(4, reponse.context['page_obj'].paginator.count)
        self.assertEqual(SITE + '/sharedbuilds/',
                         self._canonical(reponse.content.decode('utf-8')))


class AClassRedirectStaysOnTheSiteTests(TestCase):

    def test_a_path_naming_another_host_is_not_followed(self):
        from django.http import Http404
        from django.test import RequestFactory
        from chardata.shared_builds_view import shared_builds_for_class
        for chemin in ('//evil.example/sharedbuilds/steamer/',
                       '/\evil.example/sharedbuilds/steamer/'):
            with self.subTest(chemin=chemin):
                request = RequestFactory().get('/sharedbuilds/steamer/')
                request.path = chemin
                with self.assertRaises(Http404):
                    shared_builds_for_class(request, 'steamer')
