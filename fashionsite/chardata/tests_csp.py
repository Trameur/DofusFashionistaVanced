# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Tests for the report-only Content-Security-Policy."""

import json

from django.test import SimpleTestCase, TestCase, override_settings

from chardata.csp import (REPORT_PATH, _SOURCES, build_policy,
                          policy_is_enabled)
from chardata.csp_report_view import MAX_CORPS, MAX_PAR_MINUTE


class ThePolicyCoversWhatTheSiteActuallyLoadsTests(SimpleTestCase):

    def test_the_two_origins_that_are_written_in_the_repo_are_allowed(self):
        politique = build_policy()
        for origine in ('https://ajax.googleapis.com',
                        'https://www.googletagmanager.com'):
            self.assertIn(origine, politique)

    def test_the_analytics_region_is_matched_by_a_wildcard(self):
        """The analytics subdomain is the account's region (region1, region5...)."""
        connect = _SOURCES['connect-src']
        self.assertIn('https://*.analytics.google.com', connect)
        self.assertNotIn('https://region1.analytics.google.com', connect)

    def test_the_recaptcha_country_domain_is_left_to_the_reports(self):
        """reCAPTCHA loads from the visitor's national domain, no CSP source matches it."""
        frames = _SOURCES['frame-src']
        self.assertNotIn('https://www.google.*', frames)
        self.assertNotIn('https://www.google.fr', frames)
        self.assertIn('https://www.google.com', frames)

    def test_the_policy_names_the_report_endpoint(self):
        self.assertIn('report-uri %s' % REPORT_PATH, build_policy())

    def test_every_directive_carries_at_least_one_source(self):
        """An empty directive blocks everything."""
        vides = [d for d, sources in _SOURCES.items() if not sources]
        self.assertEqual([], vides)

    def test_no_source_puts_its_wildcard_on_the_wrong_side(self):
        """`*.google.com` is valid, `www.google.*` is dropped by the browser."""
        import re
        mauvais = []
        for directive, sources in sorted(_SOURCES.items()):
            for source in sources:
                if source.startswith("'") or source.endswith(':'):
                    continue
                hote = re.sub(r'^https?://', '', source).split('/')[0]
                if '*' in hote and not hote.startswith('*.'):
                    mauvais.append((directive, source))
        self.assertFalse(
            mauvais,
            'a CSP wildcard only works on the left of a host, so the browser '
            'throws these away without telling the server: %s' % mauvais)

    def test_the_ad_verification_domain_nobody_could_guess_is_allowed(self):
        """Ads load from *.adtrafficquality.google, which no template names."""
        for directive in ('script-src', 'connect-src', 'frame-src'):
            with self.subTest(directive=directive):
                self.assertIn('https://*.adtrafficquality.google',
                              _SOURCES[directive])

    def test_the_policy_is_one_line_and_ends_each_directive(self):
        politique = build_policy()
        self.assertNotIn('\n', politique)
        self.assertEqual(len(_SOURCES) + 1, len(politique.split(';')))


class TheHeaderIsReportOnlyTests(TestCase):

    def test_an_html_page_carries_the_report_only_header(self):
        reponse = self.client.get('/faq/')
        self.assertEqual(200, reponse.status_code)
        self.assertIn('Content-Security-Policy-Report-Only', reponse)

    def test_no_page_carries_the_blocking_header(self):
        for chemin in ('/faq/', '/privacy/', '/import/text/', '/about/'):
            with self.subTest(chemin=chemin):
                reponse = self.client.get(chemin)
                self.assertNotIn('Content-Security-Policy', reponse)

    def test_the_header_says_the_same_thing_as_the_builder(self):
        reponse = self.client.get('/faq/')
        self.assertEqual(build_policy(),
                         reponse['Content-Security-Policy-Report-Only'])

    def test_a_non_html_response_carries_nothing(self):
        reponse = self.client.get('/jsi18n/')
        self.assertEqual(200, reponse.status_code)
        self.assertNotIn('Content-Security-Policy-Report-Only', reponse)

    @override_settings(CSP_REPORT_ONLY_ENABLED=False)
    def test_the_setting_can_turn_it_off_without_a_deploy(self):
        self.assertFalse(policy_is_enabled())
        reponse = self.client.get('/faq/')
        self.assertNotIn('Content-Security-Policy-Report-Only', reponse)


class TheReportEndpointRecordsWithoutDrowningTests(TestCase):

    def _rapport(self, **champs):
        base = {'document-uri': 'https://dofusfashionista.gg/faq/?q=secret',
                'effective-directive': 'script-src',
                'blocked-uri': 'https://example.invalid/x.js'}
        base.update(champs)
        return json.dumps({'csp-report': base})

    def _poste(self, corps, type_contenu='application/csp-report'):
        return self.client.post(REPORT_PATH, data=corps,
                                content_type=type_contenu)

    def test_a_real_report_is_accepted(self):
        reponse = self._poste(self._rapport())
        self.assertEqual(204, reponse.status_code)

    def test_the_browser_needs_no_csrf_token(self):
        """Browsers send reports without a CSRF token."""
        reponse = self._poste(self._rapport())
        self.assertNotEqual(403, reponse.status_code)

    def test_a_get_is_refused(self):
        self.assertEqual(405, self.client.get(REPORT_PATH).status_code)

    def test_junk_is_refused_rather_than_logged(self):
        for corps in ('not json', '[]', '{}', '{"csp-report": 3}',
                      '{"csp-report": {}}'):
            with self.subTest(corps=corps):
                self.assertEqual(400, self._poste(corps).status_code)

    def test_an_oversized_body_is_refused(self):
        gros = json.dumps({'csp-report': {'blocked-uri': 'x' * (MAX_CORPS + 50)}})
        self.assertEqual(400, self._poste(gros).status_code)

    def test_what_is_logged_keeps_the_page_but_drops_the_query(self):
        with self.assertLogs('chardata.csp_report_view', level='WARNING') as vu:
            self._poste(self._rapport())
        ligne = '\n'.join(vu.output)
        self.assertIn('/faq/', ligne)
        self.assertNotIn('secret', ligne)
        self.assertIn('example.invalid', ligne)

    def test_the_same_violation_stops_being_logged_after_a_few(self):
        from django.core.cache import cache
        cache.clear()
        with self.assertLogs('chardata.csp_report_view', level='WARNING') as vu:
            for _ in range(MAX_PAR_MINUTE + 6):
                self._poste(self._rapport())
        self.assertEqual(MAX_PAR_MINUTE, len(vu.output), vu.output)

    def test_two_different_violations_are_both_kept(self):
        """The cap is per violation, not global."""
        from django.core.cache import cache
        cache.clear()
        with self.assertLogs('chardata.csp_report_view', level='WARNING') as vu:
            self._poste(self._rapport(**{'blocked-uri': 'https://a.invalid/1'}))
            self._poste(self._rapport(**{'blocked-uri': 'https://b.invalid/2'}))
        self.assertEqual(2, len(vu.output), vu.output)

    def test_the_endpoint_does_not_police_itself(self):
        reponse = self._poste(self._rapport())
        self.assertNotIn('Content-Security-Policy-Report-Only', reponse)


class AStatLabelIsANameNotAKeyTests(TestCase):
    """`localized_stat_name` translates a name ('AP'), not a key ('ap')."""

    def test_the_helper_translates_a_name_and_not_a_key(self):
        from django.utils import translation
        from chardata.translation_util import localized_stat_name
        from fashionistapulp.structure import (get_structure,
                                               set_current_game_version)
        set_current_game_version('dofus3')
        stat = get_structure('dofus3').get_stat_by_key('ap')
        with translation.override('fr'):
            self.assertEqual('ap', localized_stat_name('ap'),
                             'a key would translate, and the bug would not '
                             'exist')
            self.assertEqual('PA', localized_stat_name(stat.name))

    def test_the_shared_text_labels_follow_the_reader(self):
        from django.test import RequestFactory
        from django.utils import translation
        from chardata.models import Char
        from chardata.solution import get_solution
        from chardata.solution_view import _build_share_text
        from fashionistapulp.structure import (get_structure,
                                               set_current_game_version)
        set_current_game_version('dofus3')
        structure = get_structure('dofus3')
        item = next(i for i in structure.types[200]['Hat'] if not i.removed)
        self.client.post('/import/text/', {
            'text': structure.get_item_name_in_language(item, 'en'),
            'confirm': '1', 'char_class': 'Cra', 'level': '200'})
        char = Char.objects.order_by('-id').first()
        rendus = {}
        for langue in ('en', 'fr'):
            with translation.override(langue):
                rendus[langue] = _build_share_text(
                    RequestFactory().get('/'), char, get_solution(char))
        self.assertIn('Vitality', rendus['en'])
        self.assertIn('Vitalit\u00e9', rendus['fr'])
        self.assertNotIn('Vitality', rendus['fr'])

    def test_the_constraints_panel_shows_a_label_not_a_key(self):
        """The panel only shows with minimums: call the function that fills it."""
        from django.utils import translation
        from chardata.models import Char
        from chardata.min_stats import set_min_stats
        from chardata.solution import get_solution
        from chardata.solution_view import _constraints_reached
        from fashionistapulp.structure import (get_structure,
                                               set_current_game_version)
        set_current_game_version('dofus3')
        structure = get_structure('dofus3')
        item = next(i for i in structure.types[200]['Hat'] if not i.removed)
        self.client.post('/import/text/', {
            'text': structure.get_item_name_in_language(item, 'en'),
            'confirm': '1', 'char_class': 'Cra', 'level': '200'})
        char = Char.objects.order_by('-id').first()
        # set_min_stats is keyed by name ('AP'), not by key ('ap')
        set_min_stats(char, {'AP': 1})
        with translation.override('fr'):
            lignes = _constraints_reached(char, get_solution(char))
        self.assertTrue(lignes, 'no constraint came back, nothing is guarded')
        noms = [l['name'] for l in lignes]
        self.assertNotIn('ap', noms, 'the panel shows the raw stat key')
        self.assertIn('PA', noms, noms)
