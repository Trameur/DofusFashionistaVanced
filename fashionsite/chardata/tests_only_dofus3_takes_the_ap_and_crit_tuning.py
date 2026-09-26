# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Dofus 3 alone takes the AP and crit floor tuning of its weights."""
from types import SimpleNamespace

from django.test import SimpleTestCase, TestCase

OTHER_VERSIONS = ('beta', 'dofus2', 'touch', 'retro')
ELEMENTS = {1: {'int'}, 2: {'str', 'int'}, 3: {'str', 'int', 'agi'},
            4: {'str', 'int', 'cha', 'agi'}}
CLASSES = ('Feca', 'Osamodas', 'Enutrof', 'Sram', 'Xelor', 'Ecaflip', 'Eniripsa',
           'Iop', 'Cra', 'Sadida', 'Sacrier', 'Pandawa', 'Rogue', 'Masqueraider',
           'Foggernaut', 'Eliotrope', 'Huppermage', 'Ouginak', 'Forgelance')
CRIT_FLOORS = {
    'Cra': {1: 840, 2: 1600, 3: 1200, 4: 280},
    'Iop': {1: 1200, 2: 1000, 3: 600, 4: 400},
    'Masqueraider': {1: 960, 2: 800, 3: 480, 4: 320},
    'Sacrier': {1: 840, 2: 700, 3: 420, 4: 280},
    'Xelor': {1: 960, 2: 800, 3: 480, 4: 320},
}


def weights(version, aspects, race='Feca', level=200):
    from chardata.smart_build import _set_weights
    char = SimpleNamespace(char_class=race, level=level, game_version=version)
    return _set_weights(char, set(aspects), apply=False)


class TheApWeightFollowsTheElementCountOnDofus3Tests(SimpleTestCase):

    def test_dofus3_ap_weight_per_element_count(self):
        for count, expected in ((1, 22080), (2, 37100), (3, 34200), (4, 23240)):
            with self.subTest(elements=count):
                w = weights('dofus3', ELEMENTS[count])
                self.assertEqual(expected, w['ap'])
                self.assertEqual(2400, w['ap_before_floor'])

    def test_glasscannon_raises_the_ap_weight_with_the_characteristics(self):
        self.assertEqual(33120, weights('dofus3', {'int', 'glasscannon'})['ap'])

    def test_below_level_200_the_ap_weight_keeps_the_old_level_curve(self):
        for level in (1, 60, 100, 150, 199):
            for count, aspects in ELEMENTS.items():
                with self.subTest(level=level, elements=count):
                    w = weights('dofus3', aspects, level=level)
                    self.assertEqual(round((20 + level / 2) * 20), w['ap'])
                    self.assertNotIn('ap_before_floor', w)

    def test_a_build_without_element_keeps_its_ap_weight(self):
        w = weights('dofus3', {'vit'})
        self.assertEqual(2400, w['ap'])
        self.assertNotIn('ap_before_floor', w)

    def test_other_versions_keep_the_ap_weight(self):
        for version in OTHER_VERSIONS:
            for count, aspects in ELEMENTS.items():
                with self.subTest(version=version, elements=count):
                    w = weights(version, aspects)
                    self.assertEqual(2400, w['ap'])
                    self.assertNotIn('ap_before_floor', w)


class TheCritFloorIsPerClassOnDofus3Tests(SimpleTestCase):

    def test_dofus3_crit_floor_per_class_and_element_count(self):
        for race, by_count in CRIT_FLOORS.items():
            for count, expected in by_count.items():
                with self.subTest(race=race, elements=count):
                    w = weights('dofus3', ELEMENTS[count], race=race)
                    self.assertEqual(expected, w['ch'])
                    self.assertEqual(240, w['ch_before_floor'])

    def test_below_level_200_no_class_takes_the_crit_floor(self):
        for level in (1, 60, 100, 150, 199):
            for race in CRIT_FLOORS:
                with self.subTest(level=level, race=race):
                    w = weights('dofus3', {'int'}, race=race, level=level)
                    self.assertEqual(240, w['ch'])
                    self.assertNotIn('ch_before_floor', w)

    def test_other_dofus3_classes_keep_the_crit_weight(self):
        for race in CLASSES:
            if race in CRIT_FLOORS:
                continue
            with self.subTest(race=race):
                w = weights('dofus3', {'int'}, race=race)
                self.assertEqual(240, w['ch'])
                self.assertNotIn('ch_before_floor', w)

    def test_other_versions_keep_the_crit_weight_for_every_class(self):
        for version in OTHER_VERSIONS:
            for race in CLASSES:
                with self.subTest(version=version, race=race):
                    w = weights(version, {'int'}, race=race)
                    self.assertEqual(240, w['ch'])
                    self.assertNotIn('ch_before_floor', w)

    def test_the_crit_aspects_keep_their_weight(self):
        self.assertEqual(2800, weights('dofus3', {'int', 'crit'}, race='Iop')['ch'])
        self.assertEqual(-80, weights('dofus3', {'int', 'noncrit'}, race='Iop')['ch'])
        for aspect in ('crit', 'noncrit'):
            with self.subTest(aspect=aspect):
                w = weights('dofus3', {'int', aspect}, race='Iop')
                self.assertNotIn('ch_before_floor', w)


class FinalDamageKeepsTwelvePowerPerPercentTests(SimpleTestCase):

    def _per_power(self, w):
        return ((w['permedam'] + w['perrandam']) / w['pow'],
                (w['perweadam'] + w['perspedam']) / w['pow'])

    def test_dofus3_beta_and_dofus2_pay_twelve_power_per_percent(self):
        for version in ('dofus3', 'beta', 'dofus2'):
            for count, aspects in ELEMENTS.items():
                with self.subTest(version=version, elements=count):
                    for value in self._per_power(weights(version, aspects)):
                        self.assertAlmostEqual(12, value, delta=0.02)

    def test_dofus3_has_no_final_damage_tuning(self):
        from chardata.smart_build import VERSION_WEIGHT_TUNING
        self.assertNotIn('final_damage_per_pow', VERSION_WEIGHT_TUNING['dofus3'])

    def test_touch_and_retro_keep_final_damage_at_zero(self):
        for version in ('touch', 'retro'):
            w = weights(version, {'int'})
            for key in ('permedam', 'perrandam', 'perweadam', 'perspedam'):
                with self.subTest(version=version, key=key):
                    self.assertEqual(0, w[key])


class ItemEffectsReadTheWeightsBeforeTheFloorsOnDofus3Tests(SimpleTestCase):

    def _terms(self, version, objective_values):
        from fashionistapulp.model import Model
        from fashionistapulp.structure import (get_structure,
                                               set_current_game_version)
        self.addCleanup(set_current_game_version, 'dofus3')
        set_current_game_version(version)
        model = Model.__new__(Model)
        model.structure = get_structure(version)

        class Collector(object):
            def __init__(self):
                self.terms = {}

            def add_to_of(self, category, item_id, weight):
                key = (category, item_id)
                self.terms[key] = self.terms.get(key, 0) + weight

        model.problem = Collector()
        model.add_weird_item_weights_to_objective_funcion(objective_values, 200)

        def term(name):
            return model.problem.terms[('p', model.structure.get_item_by_name(name).id)]
        return term

    def test_dofus3_values_surpryz_and_ap_effects_before_the_floors(self):
        w = weights('dofus3', {'int'}, race='Iop')
        term = self._terms('dofus3', w)
        self.assertEqual(240 * 20, term('Surpryz'))
        self.assertEqual(2400 * 2.5 + w['mp'] * 2.5, term('Abyssal Dofus'))
        self.assertEqual(2400 * 0.5, term('Prysipitate-O-Mat'))
        self.assertEqual(2400, term("Ganymede's Diadem"))
        self.assertEqual(1200 * 5, term('Turquoise Dofus'))

    def test_beta_reads_the_weights_it_is_given(self):
        w = weights('dofus3', {'int'}, race='Iop')
        term = self._terms('beta', w)
        self.assertEqual(w['ch'] * 20, term('Surpryz'))
        self.assertEqual(w['ap'] * 2.5 + w['mp'] * 2.5, term('Abyssal Dofus'))
        self.assertEqual(w['ap'] * 0.5, term('Prysipitate-O-Mat'))

    def test_a_weights_dict_without_the_extra_keys_is_read_as_before(self):
        w = weights('beta', {'int'}, race='Iop')
        term = self._terms('dofus3', w)
        self.assertEqual(w['ch'] * 20, term('Surpryz'))
        self.assertEqual(w['ap'] * 0.5, term('Prysipitate-O-Mat'))


class TheKeysBeforeTheFloorsSurviveTheWeightsStoreTests(TestCase):

    def _char(self, w):
        import pickle
        from django.contrib.auth.models import User
        from chardata.models import Char
        owner = User.objects.create_user('floorkeys', 'fk@test.local', 'pw-floor-81')
        char = Char.objects.create(
            name='Fk', char_name='fk', char_class='Iop', char_build='build',
            level=200, minimum_stats=b'', minimum_crits=b'',
            stats_weight=pickle.dumps(w), options=b'', inclusions=b'',
            exclusions=b'', aspects=pickle.dumps({'int'}),
            owner=owner, link_shared=False, game_version='dofus3')
        return owner, char

    def test_get_and_set_keep_the_keys_and_the_objective_skips_them(self):
        from chardata.char_blobs import read_char_blob
        from chardata.stats_weights import get_stats_weights, set_stats_weights
        from fashionistapulp.dofus_constants import NON_STAT_WEIGHT_KEYS
        _owner, char = self._char(weights('dofus3', {'int'}, race='Iop'))
        stored = get_stats_weights(char)
        self.assertEqual(2400, stored['ap_before_floor'])
        self.assertEqual(240, stored['ch_before_floor'])
        set_stats_weights(char, stored)
        char.refresh_from_db()
        again = read_char_blob(char.stats_weight, {}, 'stats_weight')
        self.assertEqual(2400, again['ap_before_floor'])
        self.assertEqual(240, again['ch_before_floor'])
        self.assertIn('ap_before_floor', NON_STAT_WEIGHT_KEYS)
        self.assertIn('ch_before_floor', NON_STAT_WEIGHT_KEYS)

    def test_saving_the_weights_page_keeps_the_keys_before_the_floors(self):
        from chardata.char_blobs import read_char_blob
        from chardata.models import Char
        from chardata.stats_weights import get_stats_weights
        from fashionistapulp.dofus_constants import NON_STAT_WEIGHT_KEYS
        w = weights('dofus3', {'int'}, race='Iop')
        owner, char = self._char(w)
        shown = get_stats_weights(char)
        posted = {'weight_%s' % key: str(int(value)) for key, value in shown.items()
                  if key not in NON_STAT_WEIGHT_KEYS}
        posted['weight_vit'] = '77'
        self.client.force_login(owner)
        response = self.client.post('/statspost/%d/' % char.id, posted)
        self.assertEqual(200, response.status_code)
        after = read_char_blob(Char.objects.get(id=char.id).stats_weight, {},
                               'stats_weight')
        self.assertEqual(77, after['vit'])
        self.assertEqual(22080, after['ap'])
        self.assertEqual(1200, after['ch'])
        self.assertEqual(2400, after['ap_before_floor'])
        self.assertEqual(240, after['ch_before_floor'])
        for key in NON_STAT_WEIGHT_KEYS:
            with self.subTest(key=key):
                self.assertEqual(w[key], after[key])
