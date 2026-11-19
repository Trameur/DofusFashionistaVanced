# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""With no rune allowed or no runes file, the solver writes the model it wrote before runes."""

from unittest import mock

from django.test import SimpleTestCase

from fashionistapulp import dracorunes
from fashionistapulp.model import Model
from fashionistapulp.structure import set_current_game_version

from chardata.dracorune_fixtures import NOT_ASKED, written

VERSIONS = ('dofus3', 'beta')


def before_runes():
    """The MPS of a model built and set up with the rune code skipped."""
    with mock.patch.object(Model, '_build_dracorune_candidates', lambda self: None), \
            mock.patch.object(Model, 'modify_dracorune_terms', lambda self, count, given: None):
        return written(Model())


class AModelWithoutRunesIsTheModelOfBeforeTests(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.before = {}
        cls.models = {}
        try:
            for version in VERSIONS:
                set_current_game_version(version)
                cls.before[version] = before_runes()
                cls.models[version] = Model()
        finally:
            set_current_game_version('dofus3')

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')

    def test_the_compared_model_holds_the_effective_hp_row(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                self.assertIn(b'effective_hp_minimum', self.before[version])

    def test_no_option_or_zero_runes_writes_the_same_model(self):
        for version in VERSIONS:
            set_current_game_version(version)
            for runes_allowed in (NOT_ASKED, 0, None, False):
                with self.subTest(version=version, runes_allowed=runes_allowed):
                    self.assertEqual(self.before[version],
                                     written(self.models[version], runes_allowed))

    def test_a_version_without_a_runes_file_ignores_the_option(self):
        without = [version for version in VERSIONS if dracorunes.load_runes(version) is None]
        for version in without:
            set_current_game_version(version)
            with self.subTest(version=version):
                self.assertEqual({}, self.models[version].dracorune_candidates)
                self.assertEqual(self.before[version], written(self.models[version], 2))

    def test_a_version_whose_runes_file_is_gone_ignores_the_option(self):
        set_current_game_version('beta')
        self.assertIsNotNone(dracorunes.load_runes('beta'))
        with mock.patch.object(dracorunes, 'load_runes', lambda version, folder=None: None):
            model = Model()
        self.assertEqual(self.before['beta'], written(model, 2))

    def test_the_runes_option_does_change_the_beta_model(self):
        set_current_game_version('beta')
        self.assertNotEqual(self.before['beta'], written(self.models['beta'], 2))
        self.assertEqual(self.before['beta'], written(self.models['beta'], 0))
