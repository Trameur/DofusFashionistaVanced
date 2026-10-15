# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Standard keeps every remembered solve: its keys are the ones computed before the power slider existed."""
from django.test import SimpleTestCase

from chardata.power_steps import POWER_BY_KEY
from fashionistapulp.model import ModelInput
from fashionistapulp.structure import set_current_game_version

# ModelInput.cache_key() of sample(), one per version
KEYS_BEFORE_THE_SLIDER = {
    'dofus3': 2754017923935570279,
    'retro': -3802799395468776746,
    'touch': -3055892054964991217,
    'beta': -4155786234228864496,
    'dofus2': -5998094555109807797,
}


def sample(**extra):
    return ModelInput(200, {'vit': 100, 'str': 250}, {'ap': 11, 'mp': 6, 'adv_mins': {'hp': 3000}},
                      {'Hat': 1234}, {55, 66}, {'str': 10, 'vit': 1, 'ap': 400},
                      {'ap_exo': False, 'mp_exo': False, 'range_exo': False, 'dofus': True},
                      'Iop', 995, ['Shield'], {}, item_terms={77: 12.5}, crit_hinges=((30, 4.0),),
                      **extra)


class TheStandardKeyIsTheKeyOfBeforeTests(SimpleTestCase):

    def tearDown(self):
        set_current_game_version('dofus3')

    def test_an_input_without_a_gap_keeps_the_key_of_before_on_every_version(self):
        for version, key in KEYS_BEFORE_THE_SLIDER.items():
            with self.subTest(version=version):
                set_current_game_version(version)
                self.assertEqual(key, sample().cache_key())

    def test_the_standard_step_keeps_the_key_and_the_hash_of_an_input_without_a_gap(self):
        for version, key in KEYS_BEFORE_THE_SLIDER.items():
            with self.subTest(version=version):
                set_current_game_version(version)
                standard = sample(gap=POWER_BY_KEY['standard'].gap)
                self.assertEqual(key, standard.cache_key())
                self.assertEqual(hash(sample()), hash(standard))


class AQuickStepHasItsOwnKeyTests(SimpleTestCase):

    def tearDown(self):
        set_current_game_version('dofus3')

    def test_flash_and_fast_get_keys_of_their_own_on_every_version(self):
        for version in KEYS_BEFORE_THE_SLIDER:
            with self.subTest(version=version):
                set_current_game_version(version)
                flash = sample(gap=POWER_BY_KEY['flash'].gap)
                fast = sample(gap=POWER_BY_KEY['fast'].gap)
                keys = {sample().cache_key(), flash.cache_key(), fast.cache_key()}
                self.assertEqual(3, len(keys))
                self.assertEqual(3, len({hash(sample()), hash(flash), hash(fast)}))
                self.assertEqual(flash.cache_key(), sample(gap=POWER_BY_KEY['flash'].gap).cache_key())
