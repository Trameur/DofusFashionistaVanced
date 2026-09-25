# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Every language a monster is named in has to be a language its page actually serves."""
import collections
import re
import sqlite3

from django.test import TestCase

VERSIONS = ('dofus3', 'beta', 'dofus2', 'retro', 'touch')
LANGUES = ('fr', 'es', 'pt', 'de')
NAVIGATEUR = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36')


def _noms_par_monstre(game_version):
    """{monster_ankama_id: {language: name}} for one version, or {}."""
    from fashionistapulp.fashionista_config import get_items_db_path
    connexion = sqlite3.connect(
        'file:%s?mode=ro' % get_items_db_path(game_version), uri=True)
    try:
        curseur = connexion.cursor()
        curseur.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' "
                        "AND name = 'monster_names'")
        if curseur.fetchone() is None:
            return {}
        trouve = collections.defaultdict(dict)
        for monstre, langue, nom in curseur.execute(
                'SELECT monster_ankama_id, language, name FROM monster_names'):
            if nom:
                trouve[monstre][langue] = nom
        return dict(trouve)
    finally:
        connexion.close()


class EveryNamedLanguageIsAServedLanguageTests(TestCase):
    """The database and the site have to agree on which languages exist."""

    def _compte_par_langue(self, game_version):
        noms = _noms_par_monstre(game_version)
        return noms, {langue: sum(1 for d in noms.values() if d.get(langue))
                      for langue in LANGUES}

    def test_no_version_lost_a_language_of_monster_names(self):
        """A language that empties would otherwise stop being published in silence."""
        vides = []
        mesures = 0
        for game_version in VERSIONS:
            noms, comptes = self._compte_par_langue(game_version)
            if not noms:
                continue
            for langue in LANGUES:
                mesures += 1
                if not comptes[langue]:
                    vides.append((game_version, langue, len(noms)))
        self.assertFalse(
            vides, 'these versions name no monster in that language '
            '(version, language, monsters): %s' % vides)
        # counted per pair rather than in total: dofus3 alone could reach a
        # sufficient total while a whole other version goes unexamined
        self.assertEqual(mesures, len(VERSIONS) * len(LANGUES),
                         'only %d version/language pairs measured' % mesures)

    def test_a_localised_monster_page_answers_in_its_own_language(self):
        """The witness is chosen by the site's own language rule, not by differing from the English name."""
        from chardata.encyclopedia_view import _normalized_slug
        from chardata.official_site import get_monster_link
        from chardata.url_language import language_from_slug

        def sert(noms_du_monstre, langue):
            nom = noms_du_monstre.get(langue)
            return bool(nom) and language_from_slug(
                noms_du_monstre, _normalized_slug(nom),
                _normalized_slug) == langue

        manques = []
        verifiees = 0
        for game_version in VERSIONS:
            noms = _noms_par_monstre(game_version)
            if not noms:
                continue
            for langue in LANGUES:
                candidat = next(
                    ((monstre, d) for monstre, d in sorted(noms.items())
                     if sert(d, langue)), None)
                with self.subTest(version=game_version, langue=langue):
                    self.assertIsNotNone(
                        candidat, 'no monster has a url of its own in %s '
                        'for %s' % (langue, game_version))
                if candidat is None:
                    continue
                monstre, d = candidat
                lien = get_monster_link(monstre, d[langue],
                                        game_version=game_version)
                if not lien:
                    manques.append((game_version, langue, monstre, 'no link'))
                    continue
                reponse = self.client.get(lien, HTTP_ACCEPT_LANGUAGE='en',
                                          HTTP_USER_AGENT=NAVIGATEUR)
                verifiees += 1
                if reponse.status_code != 200:
                    manques.append((game_version, langue, lien,
                                    reponse.status_code))
                    continue
                html = reponse.content.decode('utf-8', 'replace')
                titre = re.search('<title>(.*?)</title>', html, re.S)
                titre = titre.group(1) if titre else ''
                # the template re-cases the name, so casing differs
                if d[langue].lower() not in titre.lower():
                    manques.append((game_version, langue, lien, titre[:60]))
        self.assertFalse(
            manques, 'these localised monster pages do not carry their own '
            'name (version, language, page, what came back): %s' % manques[:4])
        self.assertGreaterEqual(
            verifiees, len(VERSIONS) * len(LANGUES),
            'only %d localised monster pages checked' % verifiees)
