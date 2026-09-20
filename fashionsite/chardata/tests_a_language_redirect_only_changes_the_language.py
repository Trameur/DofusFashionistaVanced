# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A language redirect keeps the reader on the version they were browsing."""

import re

from django.contrib.auth.models import User
from django.test import TestCase

from chardata import guides_content
from chardata.models import UserAlias

VERSIONS = ('beta', 'dofus2', 'touch', 'retro')

# Three ordinary guides whose canonical is the global page, and one system guide whose canonical carries its version
_ORDINAIRES = ('set-boni', 'dofus-werte', 'losung-lesen')
_PROPRE_AU_SYSTEME = 'kritische-treffer'

_CANONIQUE = re.compile(r'rel="canonical"[^>]*href="([^"]+)"')
_CANONIQUE_INVERSE = re.compile(r'href="([^"]+)"[^>]*rel="canonical"')


def _version_de(chemin):
    for morceau in chemin.split('/'):
        if morceau in VERSIONS:
            return morceau
    return 'dofus3'


def _langue_de_slug(slug):
    _cle, langue = guides_content.resolve_slug(slug)
    return langue


class _LecteurConnecteEnFrancais(TestCase):

    def setUp(self):
        self.lecteur = User.objects.create_user('lecteur', 'l@x.test', 'pw')
        UserAlias.objects.create(user=self.lecteur, language='fr')
        self.client.force_login(self.lecteur)

    def _ouvre(self, chemin):
        reponse = self.client.get(chemin, follow=True)
        self.assertEqual(200, reponse.status_code, chemin)
        arrivee = reponse.redirect_chain[-1][0] if reponse.redirect_chain \
            else chemin
        return arrivee, reponse.content.decode('utf-8')

    def _canonique(self, html):
        trouve = _CANONIQUE.search(html) or _CANONIQUE_INVERSE.search(html)
        return trouve.group(1) if trouve else None


class TheRedirectKeepsTheVersionTests(_LecteurConnecteEnFrancais):

    def test_the_redirect_happens_at_all(self):
        arrivee, _html = self._ouvre('/retro/guides/%s/' % _ORDINAIRES[0])
        self.assertNotEqual('/retro/guides/%s/' % _ORDINAIRES[0], arrivee)
        self.assertEqual('fr', _langue_de_slug(arrivee.rstrip('/')
                                               .rsplit('/', 1)[-1]))

    def test_it_keeps_the_version_the_reader_was_on(self):
        for version in VERSIONS:
            for slug in _ORDINAIRES:
                with self.subTest(version=version, guide=slug):
                    depart = '/%s/guides/%s/' % (version, slug)
                    arrivee, _html = self._ouvre(depart)
                    self.assertEqual(version, _version_de(arrivee),
                                     '%s -> %s' % (depart, arrivee))

    def test_a_guide_of_its_own_system_keeps_its_version_too(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                arrivee, _html = self._ouvre(
                    '/%s/guides/%s/' % (version, _PROPRE_AU_SYSTEME))
                self.assertEqual(version, _version_de(arrivee))

    def test_it_still_changes_the_language(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                arrivee, _html = self._ouvre(
                    '/%s/guides/%s/' % (version, _ORDINAIRES[0]))
                dernier = arrivee.rstrip('/').rsplit('/', 1)[-1]
                self.assertEqual('fr', _langue_de_slug(dernier))


class TheCanonicalDoesNotMoveTests(_LecteurConnecteEnFrancais):

    def test_a_plain_guide_stays_canonical_at_the_global_url(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                _arrivee, html = self._ouvre(
                    '/%s/guides/%s/' % (version, _ORDINAIRES[0]))
                canonique = self._canonique(html)
                self.assertIsNotNone(canonique)
                self.assertEqual('dofus3', _version_de(canonique), canonique)

    def test_a_system_guide_stays_canonical_at_its_own_url(self):
        _arrivee, html = self._ouvre('/retro/guides/%s/'
                                     % _PROPRE_AU_SYSTEME)
        canonique = self._canonique(html)
        self.assertIsNotNone(canonique)
        self.assertEqual('retro', _version_de(canonique), canonique)


class ACrawlerIsNeverMovedTests(TestCase):

    def test_an_anonymous_reader_stays_where_he_asked(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                chemin = '/%s/guides/%s/' % (version, _ORDINAIRES[0])
                reponse = self.client.get(chemin)
                self.assertEqual(200, reponse.status_code)
                self.assertEqual([], getattr(reponse, 'redirect_chain', []))
