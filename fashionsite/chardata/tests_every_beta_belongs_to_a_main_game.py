# -*- coding: utf-8 -*-
"""Every version names the main game it belongs to, and the switcher groups follow that."""
from django.test import SimpleTestCase

from fashionistapulp.game_versions import (DEFAULT_VERSION, GAME_VERSIONS,
                                           SWITCHER_FAMILY_ORDER, family_members, is_beta, main_of,
                                           reader_dofus_versions,
                                           switcher_games, version_keys)


class EveryBetaBelongsToAMainGame(SimpleTestCase):

    def test_a_family_is_named_after_a_main_version_of_that_family(self):
        for version in GAME_VERSIONS.values():
            main = GAME_VERSIONS[version.family]
            self.assertEqual(main.family, version.family, version.key)
            self.assertEqual(main.channel, 'main', version.key)

    def test_a_beta_points_to_another_key_and_a_main_to_itself(self):
        for key, version in GAME_VERSIONS.items():
            if version.channel == 'beta':
                self.assertNotEqual(main_of(key), key)
            else:
                self.assertEqual(main_of(key), key)

    def test_every_channel_is_main_or_beta(self):
        for key, version in GAME_VERSIONS.items():
            self.assertIn(version.channel, ('main', 'beta'), key)

    def test_the_dofus_3_beta_is_a_beta_of_dofus_3(self):
        self.assertTrue(is_beta('beta'))
        self.assertFalse(is_beta('dofus3'))
        self.assertEqual(main_of('beta'), 'dofus3')

    def test_labels_are_unique(self):
        labels = [version.label for version in GAME_VERSIONS.values()]
        self.assertEqual(len(labels), len(set(labels)))

    def test_keys_are_alphanumeric_and_prefixes_equal_keys_off_the_default(self):
        for key, version in GAME_VERSIONS.items():
            self.assertTrue(key.isalnum(), key)
            if key == DEFAULT_VERSION:
                self.assertEqual(version.prefix, '')
            else:
                self.assertEqual(version.prefix, key)

    def test_the_version_keys_keep_their_order(self):
        self.assertEqual(version_keys(),
                         ['dofus3', 'beta', 'dofus2', 'touch', 'retro'])
        self.assertEqual(version_keys(include_experimental=True),
                         ['dofus3', 'beta', 'dofus2', 'touch', 'touchbeta', 'retro',
                          'wakfu'])

    def test_family_members_list_the_main_first(self):
        self.assertEqual(family_members('beta'), ['dofus3', 'beta'])
        self.assertEqual(family_members('dofus3'), ['dofus3', 'beta'])
        self.assertEqual(family_members('touch'), ['touch'])

    def test_the_switcher_games_follow_the_family_order_without_experimental(self):
        games = switcher_games()
        self.assertEqual([main for main, _members in games],
                         [main for main in SWITCHER_FAMILY_ORDER
                          if main in version_keys()])
        self.assertEqual(sorted(key for _main, members in games
                                for key in members), sorted(version_keys()))

    def test_every_family_has_a_slot_in_the_switcher_order(self):
        mains = {main_of(key) for key in version_keys(include_experimental=True)}
        self.assertEqual(mains, set(SWITCHER_FAMILY_ORDER))

    def test_the_reader_dofus_versions_drop_the_experimental_ones(self):
        self.assertEqual(reader_dofus_versions(),
                         [key for key in version_keys()
                          if GAME_VERSIONS[key].dofus])
