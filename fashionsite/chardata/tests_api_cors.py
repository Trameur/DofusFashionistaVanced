# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""L'API repond en JSON et avec CORS, y compris quand elle refuse.

L'API existe pour que d'autres outils lisent ce que la communaute partage --
overlays Twitch, bots Discord, sites de fans. Elle repondait correctement au
cas nominal et se contredisait partout ailleurs. Mesure en production le
28 aout 2026 :

  * `GET /api/v1/shared-builds/<id valide>/` -> 200, application/json,
    **trois** en-tetes Access-Control. C'est le temoin : le mecanisme marche.
  * `GET /api/v1/shared-builds/<id inconnu>/` -> 404, **text/html**, 31 532
    octets, **zero** en-tete Access-Control. Un consommateur navigateur ne
    peut pas lire la reponse, donc il ne distingue pas « ce build n'existe
    pas » d'une panne reseau.
  * `OPTIONS /api/v1/shared-builds/` -> **405**, `Allow: GET`, zero en-tete
    Access-Control -- alors que la reponse 200 de la MEME route annonce
    `Access-Control-Allow-Methods: GET, OPTIONS`.

Le dernier point n'est pas theorique. Un navigateur n'envoie de prevol que si
la requete n'est pas « simple ». Un bot cote serveur ne voit donc rien ; mais
un outil web qui pose le moindre en-tete -- Content-Type, un identifiant de
client, un jeton de proxy -- declenche le prevol, le prevol echoue, et la
requete n'a jamais lieu. C'est exactement la moitie des consommateurs que
l'API dit vouloir servir.

Ce module ENUMERE les routes depuis la table d'URL. Une quatrieme route
ajoutee demain est gardee sans que personne y pense -- et la question n'est
pas rhetorique : les trois existantes ont ete decorees a la main, une par une.
"""
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
    """Les chemins /api/v1/ qui ne prennent pas d'argument.

    Lus dans le resolveur plutot qu'ecrits en dur : c'est la seule facon
    qu'une route ajoutee plus tard entre ici toute seule.
    """
    chemins = set()
    for motif in get_resolver().url_patterns:
        brut = str(getattr(motif, 'pattern', ''))
        if 'api/v1' not in brut:
            continue
        # On ne garde que les motifs sans groupe nomme : les autres exigent un
        # identifiant, et le test du detail les couvre separement.
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
        """Le plancher du temoin.

        Un motif qui ne trouverait aucune route rendrait tous les tests
        suivants verts en n'interrogeant rien.
        """
        routes = _routes_api()
        self.assertGreaterEqual(
            len(routes), 3,
            'only %d api route(s) found (%s); the scan is too narrow to be '
            'guarding anything' % (len(routes), routes))

    def test_a_normal_get_still_answers_json_with_cors(self):
        """Le controle positif.

        Sans lui, une API entierement cassee -- toutes routes en 500 --
        passerait les tests de refus sans rien servir a personne.
        """
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
        """La contradiction d'origine, prise a la racine.

        Ce que l'en-tete annonce et ce que la route accepte doivent etre la
        meme liste. C'etait faux : `GET, OPTIONS` annonce, OPTIONS refuse.
        """
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
