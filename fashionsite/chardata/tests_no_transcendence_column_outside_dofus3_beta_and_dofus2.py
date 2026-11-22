# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Only Dofus 3, its Beta and Dofus 2 get transcendence columns, and an off option writes the model of before."""

from unittest import mock

from django.test import SimpleTestCase

from fashionistapulp import transcendence
from fashionistapulp.model import Model
from fashionistapulp.structure import set_current_game_version
from fashionistapulp.transcendence_terms import TRANSCENDENCE_VERSIONS

from chardata.dracorune_fixtures import NOT_ASKED, mps
from chardata.transcendence_fixtures import plain_input, trans_columns

VERSIONS = ('dofus3', 'beta', 'dofus2', 'touch', 'retro')


def before_runes(version):
    """The MPS of a model built and set up with every rune step skipped."""
    with mock.patch.object(Model, '_build_dracorune_candidates', lambda self: None), \
            mock.patch.object(Model, '_build_transcendence_candidates', lambda self: None), \
            mock.patch.object(Model, '_rebuild_rune_terms', lambda self, *args, **kwargs: None):
        return mps(Model(), plain_input())


class NoTranscendenceColumnOutsideTheThreeVersionsTests(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.before = {}
        cls.models = {}
        try:
            for version in VERSIONS:
                set_current_game_version(version)
                cls.before[version] = before_runes(version)
                cls.models[version] = Model()
        finally:
            set_current_game_version('dofus3')

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')

    def test_the_versions_are_dofus3_beta_and_dofus2(self):
        self.assertEqual(('dofus3', 'beta', 'dofus2'), TRANSCENDENCE_VERSIONS)

    def test_no_option_or_an_off_value_writes_the_model_of_before(self):
        for version in VERSIONS:
            set_current_game_version(version)
            for allowed in (NOT_ASKED, 0, None, False, True):
                with self.subTest(version=version, allowed=allowed):
                    self.assertEqual(self.before[version],
                                     mps(self.models[version], plain_input(allowed)))

    def test_the_option_adds_rune_columns_on_the_three_versions(self):
        for version in TRANSCENDENCE_VERSIONS:
            set_current_game_version(version)
            model = self.models[version]
            with self.subTest(version=version):
                written = mps(model, plain_input(7))
                self.assertNotEqual(self.before[version], written)
                self.assertTrue(trans_columns(model))
                self.assertIn(b'trans_total', written)
                self.assertEqual(self.before[version], mps(model, plain_input()))

    def test_touch_and_retro_offer_no_column_even_with_a_rune_file(self):
        beta = [dict(rune) for rune in transcendence.load_runes('beta')]
        for version in ('touch', 'retro'):
            set_current_game_version(version)
            model = Model()
            with self.subTest(version=version):
                with mock.patch.object(transcendence, 'load_runes', lambda *a, **k: beta):
                    model._build_transcendence_candidates()
                self.assertEqual({}, model.transcendence_candidates)
                self.assertEqual(self.before[version], mps(model, plain_input(7)))
                self.assertEqual([], trans_columns(model))

    def test_a_version_without_a_rune_file_writes_the_model_of_before(self):
        set_current_game_version('beta')
        model = self.models['beta']
        self.addCleanup(model._build_transcendence_candidates)
        with mock.patch.object(transcendence, 'load_runes', lambda *args, **kwargs: []):
            model._build_transcendence_candidates()
        self.assertEqual(self.before['beta'], mps(model, plain_input(7)))
