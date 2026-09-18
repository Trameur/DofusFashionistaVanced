# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A spell the level does not reach says so, instead of showing nothing."""

import io
import json
import os
import re

from django.test import SimpleTestCase, TestCase
from django.utils import translation
from django.utils.translation import gettext

from chardata.spells_view import _reach

LANGUES = ('en', 'fr', 'es', 'pt', 'de')

# msgid shown next to the spell name
_PHRASE = 'Needs level %(level)s'

# A real Retro spell ladder: out of reach at 30, in reach at 60
_DESTRUCTRICE = [60, 60, 60, 60, 60, 160]

# % of spells fully out of reach, at level 1 and at 200
_PART_HORS_DE_PORTEE = {
    'dofus3': (86, 0),
    'dofus2': (86, 0),
    'touch': (75, 0),
    'retro': (84, 0),
}


def _source(nom):
    chemin = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          'templates', 'chardata', nom)
    with io.open(chemin, encoding='utf-8') as fichier:
        return fichier.read()


class TheSpellsPageSaysWhyItShowsNoDamageTests(SimpleTestCase):

    def test_the_header_carries_the_reason_next_to_the_spell_name(self):
        """In the header, which stays visible when the block folds."""
        source = _source('spells.html')
        self.assertIn("$(\"<div class='spell-out-of-reach'></div>\")", source)
        self.assertIn('outOfReachText(spell.level[0])', source)

    def test_the_reason_is_built_from_the_string_that_is_already_translated(
            self):
        source = _source('spells.html')
        self.assertIn('function outOfReachText(', source)
        self.assertIn("data('out-of-reach')", source)
        self.assertIn('data-out-of-reach=', source)

    def test_every_language_says_it_in_its_own_words(self):
        rendus = {}
        for langue in LANGUES:
            with translation.override(langue):
                rendus[langue] = gettext(_PHRASE) % {'level': 60}
        for langue in LANGUES:
            with self.subTest(langue=langue):
                self.assertIn('60', rendus[langue])
        for langue in ('fr', 'es', 'pt', 'de'):
            with self.subTest(langue=langue):
                self.assertNotEqual(
                    rendus['en'], rendus[langue],
                    '%s falls back to English for the only sentence that '
                    'explains an empty row' % langue)

    def test_the_page_reads_the_servers_answer_instead_of_recomputing_it(self):
        """No level comparison left anywhere in the template."""
        source = _source('spells.html')
        debut = source.index('function setVisible(')
        self.assertIn('spell.available === false', source[debut:debut + 700])
        restes = re.findall(r'[^\n]*\{\{ *char_level *\}\}[^\n]*', source)
        self.assertEqual(
            [], restes,
            'the page compares the level itself again, so it can drift from '
            'the server as its three predecessors did: %s' % restes)


class WithoutTheGateThereWouldBeNothingToExplainTests(TestCase):

    def test_a_spell_above_the_level_is_out_of_reach_and_one_below_is_not(
            self):
        trop_bas = _reach(_DESTRUCTRICE, 30)
        assez_haut = _reach(_DESTRUCTRICE, 60)
        self.assertFalse(trop_bas['available'])
        self.assertTrue(assez_haut['available'])

    def test_the_required_level_the_sentence_shows_is_the_games_own(self):
        """The sentence shows `spell.level[0]`, the game's required level."""
        self.assertEqual(60, _DESTRUCTRICE[0])
        self.assertFalse(_reach(_DESTRUCTRICE, _DESTRUCTRICE[0] - 1)['available'])
        self.assertTrue(_reach(_DESTRUCTRICE, _DESTRUCTRICE[0])['available'])

    def test_at_the_level_cap_no_spell_is_out_of_reach(self):
        from chardata.spell_buffs import get_damage_spells_for_version
        for version in _PART_HORS_DE_PORTEE:
            with self.subTest(version=version):
                sorts = [sort for classe in
                         get_damage_spells_for_version(version).values()
                         for sort in classe]
                hors = [sort.name for sort in sorts
                        if not _reach(list(sort.level_req), 200)['available']]
                self.assertEqual([], hors)

    def test_a_low_level_reader_really_meets_a_lot_of_them(self):
        from chardata.spell_buffs import get_damage_spells_for_version
        for version, (attendu_a_1, _) in _PART_HORS_DE_PORTEE.items():
            with self.subTest(version=version):
                sorts = [sort for classe in
                         get_damage_spells_for_version(version).values()
                         for sort in classe]
                hors = len([1 for sort in sorts
                            if not _reach(list(sort.level_req), 1)['available']])
                part = round(100.0 * hors / len(sorts))
                self.assertGreaterEqual(
                    part, attendu_a_1 - 5,
                    '%s showed %d%% of its spells out of reach at level 1 and '
                    'now shows %d%%' % (version, attendu_a_1, part))

    def test_the_shipped_page_carries_what_the_sentence_needs(self):
        """The page ships `available` and `level`, which the sentence needs."""
        from django.contrib.auth.models import User
        user = User.objects.create_user('hors-portee',
                                        'hors-portee@test.local', 'pw-1234')
        self.client.force_login(user)
        # A wrong field name silently falls back to level 200
        cree = self.client.post('/retro/createproject/', {
            'charname': 'trente', 'class': 'Cra', 'level': '30',
            'project': 'trente', 'byhand': '1'})
        trouve = re.search(r'/(\d+)/', cree.headers.get('Location', ''))
        self.assertIsNotNone(trouve, 'could not create a level 30 Retro Cra')
        from chardata.models import Char
        self.assertEqual(
            30, Char.objects.get(id=int(trouve.group(1))).level,
            'the character came out at another level, so nothing below '
            'would be measuring the level gate')
        page = self.client.get('/retro/spells/%s/' % trouve.group(1),
                               follow=True)
        self.assertEqual(200, page.status_code)
        corps = page.content.decode('utf-8')
        self.assertIn('data-out-of-reach=', corps)
        digests = re.search(r'var spellDigests = (\[.*?\]);\n', corps, re.S)
        self.assertIsNotNone(digests, 'the page ships no spell digests')
        sorts = json.loads(digests.group(1))
        hors = [sort for sort in sorts if sort.get('available') is False]
        self.assertTrue(
            hors,
            'a level 30 Retro Cra reaches every one of its spells, so the '
            'sentence would never show: %d spells' % len(sorts))
        for sort in hors:
            with self.subTest(sort=sort.get('name')):
                self.assertIsInstance(
                    sort.get('level'), list,
                    'the sentence reads level[0]; this spell ships none')

    def test_the_comparison_page_still_gets_every_rank(self):
        """`char_level` None: the comparison page decides per column."""
        sans_niveau = _reach(_DESTRUCTRICE, None)
        self.assertTrue(sans_niveau['available'])
        self.assertEqual(len(_DESTRUCTRICE) - 1, sans_niveau['highest_level'])
