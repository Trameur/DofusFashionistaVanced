# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The API answers JSON with CORS headers, refusals and preflights included; the routes come from the url table."""
import json
import pickle

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import get_resolver

from chardata.encoded_char_id import encode_char_id
from chardata.models import Char

ORIGINE = 'https://example.org'
CORS_ATTENDUS = ('Access-Control-Allow-Origin',
                 'Access-Control-Allow-Methods',
                 'Access-Control-Allow-Headers')


def _routes_api():
    chemins = set()
    for motif in get_resolver().url_patterns:
        brut = str(getattr(motif, 'pattern', ''))
        if 'api/v1' not in brut:
            continue
        # Only patterns without a named group: the others need an id, covered by the detail test
        if '(?P<' in brut:
            continue
        chemin = '/' + brut.lstrip('^').rstrip('$')
        chemins.add(chemin)
    return sorted(chemins)


class TheApiAnswersJsonAndCorsEvenWhenItRefusesTests(TestCase):

    def setUp(self):
        self.proprio = User.objects.create_user(
            username='proprio', email='p@test.local', password='pw-42-solid')
        self.char = Char.objects.create(
            name='vitrine', char_name='vitrine', char_class='Iop',
            char_build='build', level=200, minimum_stats=b'',
            minimum_crits=b'', stats_weight=pickle.dumps({'vit': 1}),
            options=b'', inclusions=b'', exclusions=b'',
            owner=self.proprio, game_version='dofus3',
            link_shared=True, deleted=False,
            minimal_solution=pickle.dumps({'marqueur': True}))
        self.detail = ('/api/v1/shared-builds/%s/'
                       % encode_char_id(int(self.char.id)))

    def _cors_manquants(self, reponse):
        return [c for c in CORS_ATTENDUS if c not in reponse]

    def test_the_route_scan_finds_the_endpoints(self):
        routes = _routes_api()
        self.assertGreaterEqual(
            len(routes), 3,
            'only %d api route(s) found (%s); the scan is too narrow to be '
            'guarding anything' % (len(routes), routes))

    def test_a_normal_get_still_answers_json_with_cors(self):
        for chemin in _routes_api() + [self.detail]:
            reponse = self.client.get(chemin, HTTP_ORIGIN=ORIGINE)
            self.assertEqual(200, reponse.status_code, chemin)
            self.assertIn('application/json', reponse['Content-Type'], chemin)
            self.assertFalse(self._cors_manquants(reponse), chemin)
            json.loads(reponse.content.decode('utf-8'))

    def test_a_preflight_is_answered_and_not_refused(self):
        mauvaises = []
        for chemin in _routes_api() + [self.detail]:
            reponse = self.client.options(
                chemin, HTTP_ORIGIN=ORIGINE,
                HTTP_ACCESS_CONTROL_REQUEST_METHOD='GET',
                HTTP_ACCESS_CONTROL_REQUEST_HEADERS='content-type')
            if reponse.status_code >= 400 or self._cors_manquants(reponse):
                mauvaises.append((chemin, reponse.status_code,
                                  self._cors_manquants(reponse)))
        self.assertFalse(
            mauvaises,
            'these refuse the preflight the same responses advertise: %s'
            % mauvaises)

    def test_an_unknown_build_answers_json_not_a_web_page(self):
        reponse = self.client.get('/api/v1/shared-builds/AAAAAAAAAAAA__/',
                                  HTTP_ORIGIN=ORIGINE)
        self.assertEqual(404, reponse.status_code)
        self.assertIn('application/json', reponse['Content-Type'])
        self.assertFalse(self._cors_manquants(reponse))
        self.assertIn('error', json.loads(reponse.content.decode('utf-8')))

    def test_a_refused_method_keeps_its_cors_and_says_what_is_allowed(self):
        reponse = self.client.post(self.detail, HTTP_ORIGIN=ORIGINE)
        self.assertEqual(405, reponse.status_code)
        self.assertFalse(self._cors_manquants(reponse))
        self.assertIn('GET', reponse.get('Allow', ''))

    def test_the_advertised_methods_are_the_ones_that_work(self):
        reponse = self.client.get(self.detail, HTTP_ORIGIN=ORIGINE)
        annonces = [m.strip() for m in
                    reponse['Access-Control-Allow-Methods'].split(',')]
        self.assertIn('OPTIONS', annonces,
                      'the header no longer advertises OPTIONS, so this test '
                      'is guarding a promise nobody makes')
        refusees = []
        for methode in annonces:
            appel = getattr(self.client, methode.lower(), None)
            if appel is None:
                continue
            if appel(self.detail, HTTP_ORIGIN=ORIGINE).status_code >= 400:
                refusees.append(methode)
        self.assertFalse(
            refusees, 'advertised but refused: %s' % refusees)
