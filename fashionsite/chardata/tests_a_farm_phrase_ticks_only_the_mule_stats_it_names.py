# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A Smart Build farm phrase ticks Wisdom for XP words, Prospecting for drop words, both only when it names both or neither."""
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase

from chardata.char_blobs import read_char_blob
from chardata.models import Char
from chardata.nl_parser import parse_build_request
from fashionistapulp.dofus_constants import NON_STAT_WEIGHT_KEYS
from fashionistapulp.structure import set_current_game_version

VERSIONS = ('dofus3', 'beta', 'dofus2', 'touch', 'retro')
XP_PHRASES = ('Iop XP mule', 'Iop sagesse 150', 'Iop wisdom', 'Iop leveling', 'Iop Weisheit',
              'Iop exp rush 120')
DROP_PHRASES = ('Sram pp', 'Enutrof prospection 100', 'Enutrof drop', 'Enutrof farm drop 100',
                'Enutrof Prospektion', 'Enutrof prospecting 200')
BOTH_PHRASES = ('Enutrof farm 100', 'Enutrof farmen Stufe 100', 'Enutrof xp drop',
                'Enutrof sagesse prospection', 'Enutrof farming', 'Enutrof recolte')


class TheParserTicksTheNamedMuleStatsTests(SimpleTestCase):

    def _check(self, phrases, expected):
        for version in (None,) + VERSIONS:
            for phrase in phrases:
                with self.subTest(version=version, phrase=phrase):
                    parsed = parse_build_request(phrase, version)
                    self.assertEqual('farm', parsed['style'])
                    self.assertFalse(parsed['matched_element'])
                    self.assertEqual(expected, parsed['aspects'])

    def test_xp_words_tick_wisdom_alone(self):
        self._check(XP_PHRASES, {'wis'})

    def test_drop_words_tick_prospecting_alone(self):
        self._check(DROP_PHRASES, {'pp'})

    def test_both_or_neither_named_tick_both(self):
        self._check(BOTH_PHRASES, {'wis', 'pp'})

    def test_an_element_keeps_the_named_stat_alone(self):
        for phrase, expected in (('Ecaflip chance prospection 60', {'cha', 'pp'}),
                                 ('Halsabschneider Glück Weisheit 60', {'cha', 'wis'}),
                                 ('Iop terre farm 200', {'str', 'wis', 'pp'})):
            with self.subTest(phrase=phrase):
                self.assertEqual(expected, parse_build_request(phrase, 'dofus3')['aspects'])

    def test_a_third_focus_word_still_obeys_the_focus_cap(self):
        self.assertEqual({'wis', 'pods'}, parse_build_request('Iop xp pods', 'dofus3')['aspects'])


class ASingleStatMulePhraseWeighsThatStatTests(TestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')
        owner = User.objects.create_user('farm-phrase', 'farm@test.local', 'pw-farm-phrase-7')
        self.client.force_login(owner)

    def _build(self, version, phrase):
        set_current_game_version(version)
        path = '/smartbuild/' if version == 'dofus3' else '/%s/smartbuild/' % version
        response = self.client.post(path, {'q': phrase, 'confirm': '1', 'element': 'none'},
                                    HTTP_ACCEPT_LANGUAGE='en')
        self.assertEqual(302, response.status_code)
        char = Char.objects.order_by('-id').first()
        weights = read_char_blob(char.stats_weight, {}, 'stats_weight', char)
        minimums = read_char_blob(char.minimum_stats, {}, 'minimum_stats', char)
        weighed = {key for key, value in weights.items()
                   if value and key not in NON_STAT_WEIGHT_KEYS}
        return (read_char_blob(char.aspects, set(), 'aspects', char), weighed,
                tuple(minimums[key] for key in ('AP', 'MP', 'Range')))

    def test_an_xp_phrase_weighs_wisdom_alone(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                self.assertEqual(({'wis'}, {'wis'}, (0, 0, 0)),
                                 self._build(version, 'Iop XP mule'))

    def test_a_drop_phrase_weighs_prospecting_and_the_chance_that_gives_it(self):
        for version in VERSIONS:
            chance = set() if version == 'touch' else {'cha'}
            with self.subTest(version=version):
                self.assertEqual(({'pp'}, {'pp'} | chance, (0, 0, 0)),
                                 self._build(version, 'Enutrof drop'))

    def test_a_farm_phrase_weighs_both(self):
        for version in VERSIONS:
            chance = set() if version == 'touch' else {'cha'}
            with self.subTest(version=version):
                self.assertEqual(({'wis', 'pp'}, {'wis', 'pp'} | chance, (0, 0, 0)),
                                 self._build(version, 'Enutrof farm 100'))
