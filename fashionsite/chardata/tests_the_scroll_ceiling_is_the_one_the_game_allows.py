# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Le champ des parchemins offre ce que le jeu autorise, version et niveau.

Trouve en creant des personnages de bas niveau depuis les propres pages du
site, sur trois versions. Deux defauts se lisaient a l'ecran, et le second
rendait le premier mesurable sans discussion.

**Le champ refusait sa propre valeur.** `chardata_line.html` portait
`max="100"` en dur depuis le tout premier commit du depot (2020-07-11), alors
que le semis donne 101 en Retro et 150 en Touch. Mesure du 20 septembre 2026:
sur un Cra Retro et sur un Iop Touch, **les six champs de chacun se
declaraient invalides** (`validity.valid === false`), douze sur douze.

**Touch donnait a tout le monde un plafond reserve au niveau 200.** Lu a la
source le 20 septembre 2026, par le meme proxy de donnees que le scraper du
depot, sur les 13679 objets de la table Items: les six paliers qui menent a
100 ne portent aucune condition de niveau (`Puissant Parchemin de Force`,
`cs>74&cs<100`), et les **trois** qui menent de 100 a 150 portent toutes
`PL>199`:

| palier | condition |
|--------|-----------|
| Superbe | `cs>99&cs<120&PL>199` |
| Grandiose | `cs>119&cs<140&PL>199` |
| Magnifique | `cs>139&cs<150&PL>199` |

Les six caracteristiques portent exactement la meme echelle. Un personnage
Touch sous le niveau 200 s'arrete donc a 100, et le site lui en donnait 150:
**cinquante points par caracteristique, trois cents en tout**, que le jeu ne
donne pas, et sur lesquels le solveur batissait.

**Retro n'a pas ce probleme, verifie et non suppose.** Ses 61 objets a
condition de caracteristique, lus dans `itemscraper/retro_raw/items_fr.json`,
montent bien a 101 pour les six, et **aucun ne porte de condition de
niveau**. Le 101 valait donc a tout niveau, et il reste inchange.

**Ce que borner a l'affichage n'efface pas.** Le champ ayant toujours porte
`max="100"`, aucun lecteur n'a jamais pu taper davantage: toute valeur
au-dessus vient du semis du site. Voir
[[feedback-no-retrofit-user-builds]]: la ligne en base n'est pas touchee,
seule la page montre la valeur legale, et `_post` la borne deja au moment ou
le lecteur enregistre.
"""

import io
import os
import re

from django.test import SimpleTestCase, TestCase

from chardata.base_stats_view import _clamped_to_what_the_game_allows
from fashionistapulp.dofus_constants import max_scroll_for_version

#: Ce que chaque version autorise, sous le niveau 200 puis a partir de 200.
#: Lu dans les fichiers du jeu le 20 septembre 2026, pas suppose.
_PLAFONDS = {
    'dofus3': (100, 100),
    'beta': (100, 100),
    'dofus2': (100, 100),
    'retro': (101, 101),
    'touch': (100, 150),
}

#: Le niveau que Touch exige pour ses trois paliers hauts, `PL>199`.
_NIVEAU_TOUCH = 200


def _gabarit(nom):
    chemin = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          'templates', 'chardata', nom)
    with io.open(chemin, encoding='utf-8') as fichier:
        return fichier.read()


class TheCeilingFollowsTheVersionAndTheLevelTests(SimpleTestCase):

    def test_touch_only_reaches_its_top_tiers_from_level_200(self):
        """Le test qui aurait attrape le defaut."""
        for niveau in (1, 50, 150, 199):
            with self.subTest(niveau=niveau):
                self.assertEqual(
                    100, max_scroll_for_version('touch', niveau),
                    'the game gates every tier above 100 on PL>199')
        for niveau in (200, 201, 230):
            with self.subTest(niveau=niveau):
                self.assertEqual(150, max_scroll_for_version('touch', niveau))

    def test_every_version_answers_what_its_own_files_say(self):
        for version, (bas, haut) in _PLAFONDS.items():
            with self.subTest(version=version):
                self.assertEqual(bas, max_scroll_for_version(version, 50))
                self.assertEqual(haut, max_scroll_for_version(version, 200))

    def test_only_touch_changes_with_the_level(self):
        """Le plancher qui empeche d'etendre la porte a une version qui ne
        la demande pas. Les 61 objets Retro a condition de caracteristique
        ne portent aucun terme de niveau, verifie le 20 septembre 2026."""
        bougent = [version for version, (bas, haut) in _PLAFONDS.items()
                   if bas != haut]
        self.assertEqual(['touch'], bougent)

    def test_without_a_level_it_answers_the_version_ceiling(self):
        """`char_level` a None veut dire <<l'appelant ne parle pas d'un
        personnage>>, comme `_reach` du cote des sorts."""
        self.assertEqual(150, max_scroll_for_version('touch'))
        self.assertEqual(101, max_scroll_for_version('retro'))
        self.assertEqual(100, max_scroll_for_version('dofus3'))


class TheFieldNeverRefusesItsOwnValueTests(SimpleTestCase):

    def test_the_field_bound_comes_from_the_view_not_from_a_constant(self):
        source = _gabarit('chardata_line.html')
        self.assertIn('max="{{ max_scroll }}"', source)
        self.assertNotIn('name="scrolled_{{key}}" min="0" max="100"', source)

    def test_the_bound_is_not_written_twice(self):
        """La borne ne doit exister qu'a un endroit.

        Le gabarit en portait une copie, `max="100"`, qui contredisait la
        fonction sur les deux versions qui montent plus haut. Chercher un
        nombre en dur dans ce champ est ce qui aurait dit que les deux
        s'etaient ecartees.
        """
        source = _gabarit('chardata_line.html')
        champ = re.search(r'<input\b[^>]*scrolled_\{\{key\}\}[^>]*>', source)
        self.assertIsNotNone(champ, 'the scroll field moved or was renamed')
        self.assertNotIn('max="1', champ.group(0),
                         'the field writes a ceiling of its own again')


class BothEndsOfTheRoundTripUseTheSameDefaultTests(SimpleTestCase):
    """Le texte de build n'ecrit la ligne <<Parchemins>> que lorsqu'elle
    s'ecarte du defaut, et l'import repose sur le semis pour le reste. Si un
    seul des deux bouts apprenait le niveau, un Touch de niveau 50 partirait
    a 100 et reviendrait a 150.

    Voir [[feedback-change-both-ends-of-a-round-trip]]: traduire l'export
    seul avait deja casse la relecture dans quatre langues.
    """

    #: (module, la ligne qui doit porter un niveau)
    _DEUX_BOUTS = (
        ('solution_view.py', 'plein = max_scroll_for_version('),
        ('coaching_view.py', 'full_scroll = max_scroll_for_version('),
        ('create_project_view.py', 'full_scroll = max_scroll_for_version('),
    )

    def test_neither_end_asks_without_saying_which_character(self):
        aveugles = []
        for module, debut in self._DEUX_BOUTS:
            chemin = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  module)
            with io.open(chemin, encoding='utf-8') as fichier:
                source = fichier.read()
            appel = re.search(re.escape(debut) + r'([^)]*)\)', source)
            self.assertIsNotNone(appel, '%s no longer asks for a ceiling'
                                 % module)
            if 'char.level' not in appel.group(1):
                aveugles.append((module, appel.group(1)))
        self.assertEqual(
            [], aveugles,
            'these ask for a ceiling without saying which character, so the '
            'two ends of the round trip can disagree: %s' % aveugles)


class ShowingTheLegalValueKeepsThePointsTests(SimpleTestCase):

    def test_a_scroll_above_the_ceiling_comes_down_without_giving_points(self):
        """Baisser le parchemin seul offrirait au personnage les points
        ainsi liberes, qu'il n'a jamais distribues."""
        avant = {'scrolled_str': 150, 'total_str': 150,
                 'scrolled_int': 150, 'total_int': 400}
        apres = _clamped_to_what_the_game_allows(avant, 100)
        self.assertEqual(100, apres['scrolled_str'])
        self.assertEqual(100, apres['total_str'])
        self.assertEqual(100, apres['scrolled_int'])
        self.assertEqual(350, apres['total_int'])
        for cle in ('str', 'int'):
            with self.subTest(stat=cle):
                self.assertEqual(
                    avant['total_%s' % cle] - avant['scrolled_%s' % cle],
                    apres['total_%s' % cle] - apres['scrolled_%s' % cle],
                    'the distributed points moved')

    def test_a_value_under_the_ceiling_is_left_alone(self):
        avant = {'scrolled_str': 42, 'total_str': 300}
        self.assertEqual(avant, _clamped_to_what_the_game_allows(avant, 100))


class TheShippedPageOffersTheGamesCeilingTests(TestCase):

    @staticmethod
    def _prefixe(version):
        """dofus3 est la racine du site et ne porte pas de prefixe."""
        return '' if version == 'dofus3' else '/%s' % version

    def _cree(self, version, niveau, nom):
        from django.contrib.auth.models import User
        from chardata.models import Char
        user = User.objects.create_user(nom, '%s@test.local' % nom, 'pw-1234')
        self.client.force_login(user)
        # Les noms de champ sont ceux que la vue lit: `charname`, `level`,
        # `class`. Les ecrire autrement retombe en silence sur le niveau 200.
        cree = self.client.post('%s/createproject/' % self._prefixe(version), {
            'charname': nom, 'class': 'Iop', 'level': str(niveau),
            'project': nom, 'byhand': '1'})
        trouve = re.search(r'/(\d+)/', cree.headers.get('Location', ''))
        self.assertIsNotNone(trouve, 'could not create %s %s' % (version, niveau))
        char = Char.objects.get(id=int(trouve.group(1)))
        self.assertEqual(niveau, char.level,
                         'the character came out at another level, so nothing '
                         'below would be measuring the level gate')
        return char

    def _bornes(self, version, char_id):
        """Le `max` de chaque champ de parchemin, quel que soit l'ordre des
        attributs: le minifieur les trie, y compris dans les tests."""
        page = self.client.get('%s/setup/%s/' % (self._prefixe(version), char_id),
                               follow=True)
        self.assertEqual(200, page.status_code)
        corps = page.content.decode('utf-8')
        balises = [b for b in re.findall(r'<input\b[^>]*>', corps)
                   if 'scrolled_' in b]
        self.assertEqual(6, len(balises),
                         'the page ships %d scroll fields, not six'
                         % len(balises))
        bornes = []
        for balise in balises:
            trouve = re.search(r'\bmax="(\d+)"', balise)
            self.assertIsNotNone(trouve, 'a scroll field ships no max: %s'
                                 % balise[:120])
            bornes.append(trouve.group(1))
        return bornes

    def test_a_low_level_touch_build_is_offered_one_hundred(self):
        char = self._cree('touch', 50, 'touch-bas')
        self.assertEqual(['100'] * 6, self._bornes('touch', char.id))
        from chardata.models import CharBaseStats
        semes = list(CharBaseStats.objects.filter(char=char)
                     .values_list('scrolled_value', flat=True))
        self.assertEqual([100] * 6, sorted(semes),
                         'the build was seeded above what the game allows')

    def test_a_level_200_touch_build_keeps_its_hundred_and_fifty(self):
        char = self._cree('touch', 200, 'touch-haut')
        self.assertEqual(['150'] * 6, self._bornes('touch', char.id))

    def test_no_page_ships_a_value_its_own_field_refuses(self):
        """L'invariant qui manquait, mesure sur la page livree.

        Avant ce lot, sur un Cra Retro et un Iop Touch, les six champs de
        chacun se declaraient invalides: la valeur servie depassait la borne
        servie, douze fois sur douze. Comparer la fonction a elle-meme ne
        l'aurait pas dit; il faut confronter les deux choses que la page
        envoie vraiment.
        """
        import json
        cas = (('touch', 50), ('touch', 200), ('retro', 30), ('dofus2', 45),
               ('dofus3', 1))
        for version, niveau in cas:
            with self.subTest(version=version, niveau=niveau):
                char = self._cree(version, niveau,
                                  'borne-%s-%d' % (version, niveau))
                bornes = [int(b) for b in self._bornes(version, char.id)]
                page = self.client.get('%s/setup/%s/' % (self._prefixe(version), char.id),
                                       follow=True).content.decode('utf-8')
                brut = re.search(r'initialStats\s*=\s*(\{.*?\})\s*;', page, re.S)
                self.assertIsNotNone(brut, 'the page ships no stats')
                stats = json.loads(brut.group(1))
                valeurs = [v for cle, v in stats.items()
                           if cle.startswith('scrolled_')]
                self.assertEqual(6, len(valeurs))
                self.assertTrue(
                    all(v <= max(bornes) for v in valeurs),
                    '%s level %d ships %s in fields bounded at %s'
                    % (version, niveau, valeurs, bornes))

    def test_retro_offers_its_own_hundred_and_one_at_any_level(self):
        char = self._cree('retro', 30, 'retro-bas')
        self.assertEqual(['101'] * 6, self._bornes('retro', char.id))
