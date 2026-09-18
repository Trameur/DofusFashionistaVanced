# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The scroll field offers what the game allows, per version and level."""

import io
import os
import re

from django.test import SimpleTestCase, TestCase

from chardata.base_stats_view import _clamped_to_what_the_game_allows
from fashionistapulp.dofus_constants import max_scroll_for_version

# (below level 200, from level 200)
_PLAFONDS = {
    'dofus3': (100, 100),
    'beta': (100, 100),
    'dofus2': (100, 100),
    'retro': (101, 101),
    'touch': (100, 150),
}

# Touch scroll tiers above 100 need PL>199
_NIVEAU_TOUCH = 200


def _gabarit(nom):
    chemin = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          'templates', 'chardata', nom)
    with io.open(chemin, encoding='utf-8') as fichier:
        return fichier.read()


class TheCeilingFollowsTheVersionAndTheLevelTests(SimpleTestCase):

    def test_touch_only_reaches_its_top_tiers_from_level_200(self):
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
        """Retro scroll items carry no level condition."""
        bougent = [version for version, (bas, haut) in _PLAFONDS.items()
                   if bas != haut]
        self.assertEqual(['touch'], bougent)

    def test_without_a_level_it_answers_the_version_ceiling(self):
        """`char_level` None means no character in play."""
        self.assertEqual(150, max_scroll_for_version('touch'))
        self.assertEqual(101, max_scroll_for_version('retro'))
        self.assertEqual(100, max_scroll_for_version('dofus3'))


class TheFieldNeverRefusesItsOwnValueTests(SimpleTestCase):

    def test_the_field_bound_comes_from_the_view_not_from_a_constant(self):
        source = _gabarit('chardata_line.html')
        self.assertIn('max="{{ max_scroll }}"', source)
        self.assertNotIn('name="scrolled_{{key}}" min="0" max="100"', source)

    def test_the_bound_is_not_written_twice(self):
        """No hardcoded max in the template field."""
        source = _gabarit('chardata_line.html')
        champ = re.search(r'<input\b[^>]*scrolled_\{\{key\}\}[^>]*>', source)
        self.assertIsNotNone(champ, 'the scroll field moved or was renamed')
        self.assertNotIn('max="1', champ.group(0),
                         'the field writes a ceiling of its own again')


class BothEndsOfTheRoundTripUseTheSameDefaultTests(SimpleTestCase):
    """Build text omits the default scroll line; both ends must use the level."""

    # (module, the call that must pass a level)
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
        """dofus3 has no url prefix."""
        return '' if version == 'dofus3' else '/%s' % version

    def _cree(self, version, niveau, nom):
        from django.contrib.auth.models import User
        from chardata.models import Char
        user = User.objects.create_user(nom, '%s@test.local' % nom, 'pw-1234')
        self.client.force_login(user)
        # A wrong field name silently falls back to level 200
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
        """Max of each scroll field; the minifier sorts attributes, in tests too."""
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
