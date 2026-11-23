# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A beta falls back to its game's main for icons and canonical pages."""

from unittest import mock

from django.test import SimpleTestCase

from fashionistapulp import game_versions
from fashionistapulp.game_versions import GameVersion

from chardata import image_store, version_content
from chardata.image_store import RETRO_PLACEHOLDER, _icon_path, get_image_url

KEY = ('equipment', 1)


def _fake_touch_beta(family='touch', key='touchbeta'):
    return GameVersion(key, 'Fake Beta', 'x.db', 'x.dump', seo_word='Fake Beta',
                       family=family, channel='beta')


class ABetaIconFollowsItsMain(SimpleTestCase):

    def _icon(self, existing, key='touchbeta', family='touch'):
        fake = _fake_touch_beta(family, key)
        with mock.patch.dict(game_versions.GAME_VERSIONS, {key: fake}), \
                mock.patch.object(image_store, '_static_exists',
                                  side_effect=lambda path: path in existing):
            return get_image_url('Ring', 'Fake Ring', key)

    def test_its_own_directory_comes_first(self):
        own = _icon_path('items', 'Fake Ring', 'touchbeta')
        main = _icon_path('items', 'Fake Ring', 'touch')
        self.assertEqual(self._icon({own, main}), own)

    def test_the_main_directory_comes_second(self):
        main = _icon_path('items', 'Fake Ring', 'touch')
        self.assertEqual(self._icon({main}), main)

    def test_the_main_directory_serves_the_base_item_of_a_variant(self):
        fake = _fake_touch_beta()
        main_base = _icon_path('items', 'Fake Ring', 'touch')
        with mock.patch.dict(game_versions.GAME_VERSIONS, {'touchbeta': fake}), \
                mock.patch.object(image_store, '_static_exists',
                                  side_effect=lambda path: path == main_base):
            self.assertEqual(get_image_url('Ring', 'Fake Ring 2', 'touchbeta'),
                             main_base)

    def test_a_game_with_dofus_3_art_ends_on_the_dofus_3_icon(self):
        self.assertEqual(self._icon(set()), _icon_path('items', 'Fake Ring'))

    def test_a_retro_game_ends_on_the_placeholder(self):
        self.assertEqual(self._icon(set(), 'retrobeta', 'retro'),
                         RETRO_PLACEHOLDER)

    def test_a_retro_beta_still_uses_the_retro_directory(self):
        main = _icon_path('items', 'Fake Ring', 'retro')
        self.assertEqual(self._icon({main}, 'retrobeta', 'retro'), main)


class ANonDofusBetaPictureFollowsItsMain(SimpleTestCase):

    def _picture(self, existing):
        fake = GameVersion('wakfubeta', 'Fake Beta', 'x.db', 'x.dump',
                           seo_word='Fake Beta', family='wakfu', channel='beta',
                           dofus=False)
        with mock.patch.dict(game_versions.GAME_VERSIONS, {'wakfubeta': fake}), \
                mock.patch.object(image_store, '_static_exists',
                                  side_effect=lambda path: path in existing):
            return get_image_url('Ring', 'Fake Ring', 'wakfubeta', picture=7)

    def test_the_main_picture_serves_a_beta_without_its_own(self):
        main = image_store._PICTURE_PATH % ('wakfu', 7)
        self.assertEqual(self._picture({main}), main)

    def test_its_own_picture_comes_first(self):
        own = image_store._PICTURE_PATH % ('wakfubeta', 7)
        main = image_store._PICTURE_PATH % ('wakfu', 7)
        self.assertEqual(self._picture({own, main}), own)

    def test_no_picture_ends_on_the_placeholder(self):
        self.assertEqual(self._picture(set()), RETRO_PLACEHOLDER)


class ABetaCanonicalFollowsItsMain(SimpleTestCase):

    def _canonical(self, signatures, existing=()):
        fake = _fake_touch_beta()

        def cached(version):
            return {KEY: signatures[version]} if version in signatures else {}

        with mock.patch.dict(game_versions.GAME_VERSIONS, {'touchbeta': fake}), \
                mock.patch.object(version_content, '_cached_signatures',
                                  side_effect=cached), \
                mock.patch.object(image_store, '_static_exists',
                                  side_effect=lambda path: path in existing):
            return (version_content.canonical_version('touchbeta', *KEY),
                    version_content.canonical_version('touch', *KEY),
                    version_content.repeats_the_live_version('touchbeta', *KEY))

    def test_a_beta_repeating_its_main_points_at_the_main(self):
        sig = ('a', 'Fake Ring', 'Ring')
        beta, main, repeats = self._canonical(
            {'dofus3': ('b', 'Fake Ring', 'Ring'), 'touch': sig,
             'touchbeta': sig})
        self.assertEqual((beta, main, repeats), ('touch', 'touch', True))

    def test_a_beta_repeating_a_main_that_repeats_dofus_3_points_at_dofus_3(self):
        sig = ('a', 'Fake Ring', 'Ring')
        beta, main, _ = self._canonical(
            {'dofus3': sig, 'touch': sig, 'touchbeta': sig})
        self.assertEqual((beta, main), ('dofus3', 'dofus3'))

    def test_a_beta_that_differs_from_its_main_keeps_its_own_page(self):
        beta, main, repeats = self._canonical(
            {'dofus3': ('b', 'Fake Ring', 'Ring'),
             'touch': ('a', 'Fake Ring', 'Ring'),
             'touchbeta': ('c', 'Fake Ring', 'Ring')})
        self.assertEqual((beta, main, repeats), ('touchbeta', 'touch', False))

    def test_a_beta_equal_to_dofus_3_but_not_to_its_main_stays_itself(self):
        sig = ('a', 'Fake Ring', 'Ring')
        beta, _, _ = self._canonical(
            {'dofus3': sig, 'touch': ('c', 'Fake Ring', 'Ring'),
             'touchbeta': sig})
        self.assertEqual(beta, 'touchbeta')

    def test_the_icon_of_a_beta_and_of_its_main_must_match_to_repeat(self):
        sig = ('a', 'Fake Ring', 'Ring')
        own = _icon_path('items', 'Fake Ring', 'touchbeta')
        main = _icon_path('items', 'Fake Ring', 'touch')
        beta, _, repeats = self._canonical(
            {'dofus3': ('b', 'Fake Ring', 'Ring'), 'touch': sig,
             'touchbeta': sig}, existing={own, main})
        self.assertEqual((beta, repeats), ('touchbeta', False))

    def test_a_beta_without_art_repeats_a_main_that_has_art(self):
        sig = ('a', 'Fake Ring', 'Ring')
        main = _icon_path('items', 'Fake Ring', 'touch')
        beta, _, repeats = self._canonical(
            {'dofus3': ('b', 'Fake Ring', 'Ring'), 'touch': sig,
             'touchbeta': sig}, existing={main})
        self.assertEqual((beta, repeats), ('touch', True))

    def test_a_main_keeps_comparing_with_dofus_3(self):
        sig = ('a', 'Fake Ring', 'Ring')
        _, main, _ = self._canonical({'dofus3': sig, 'touch': sig})
        self.assertEqual(main, 'dofus3')

    def test_dofus_3_never_points_elsewhere(self):
        self.assertFalse(version_content.repeats_the_live_version('dofus3', *KEY))
        self.assertEqual(version_content.canonical_version('dofus3', *KEY),
                         'dofus3')
