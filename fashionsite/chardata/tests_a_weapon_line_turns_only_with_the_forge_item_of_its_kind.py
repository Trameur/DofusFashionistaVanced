# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A neutral weapon line turns only with the forge item of its own kind, chosen per build."""
import copy
import pickle

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase

from chardata import spell_modifier_values as modifier_values
from chardata.item_exchange import _get_weapon_rate
from chardata.models import Char, CharBaseStats
from chardata.solution import get_solution
from chardata.solution_result import evolve_result_item
from chardata.solution_view import _get_shared_solution_cache_key
from chardata.spell_combo import WeaponCastable
from chardata.util import get_picker_cache_key
from fashionistapulp import weapon_forge
from fashionistapulp.dofus_constants import (DAMAGE_TYPES, FIRE, NEUTRAL, STATS_NAMES,
                                             WATER, DamageDigest, calculate_damage)
from fashionistapulp.modelresult import (ModelResult, ModelResultItem, ModelResultMinimal,
                                         model_result_from_minimal)
from fashionistapulp.structure import get_structure, set_current_game_version

_FORGE_VERSIONS = ('dofus3', 'beta')
_VERSIONS = ('dofus3', 'beta', 'dofus2', 'touch', 'retro')
_MALLEFISK_WAND = 15216
_GOLDEN_SCARABUGLY_WAND = 8118
_HIDSAD_BOW = 1355
_WEAPON_CURSE = 19637
_KUKRI_KURA = 8932
_SRAM_DAGGERS = 13208
_SACRIER_DAGGERS = 13215
_FORGE_FIELDS = ('forge_base', 'conversions', 'forge_key', 'steal_element', 'heal_element')
_BASE = {'Vitality': 0, 'Wisdom': 0, 'Strength': 0, 'Intelligence': 0,
         'Chance': 0, 'Agility': 0}
_OPTIONS = {'ap_exo': False, 'mp_exo': False, 'range_exo': False,
            'dofus': True, 'trophies': True, 'dragoturkey': True,
            'seemyool': True, 'rhineetle': True, 'prysmaradite': False,
            'dofuses': {}, 'dofusnotforchar': set()}


def _rows(hits):
    if hits is None:
        return None
    return [(hit.min_dam, hit.max_dam, hit.element, bool(hit.steals), bool(hit.heals))
            for hit in hits]


def _tabs(tabs):
    return None if tabs is None else {element: _rows(tabs[element]) for element in DAMAGE_TYPES}


def _kind(hit):
    return 'steal' if hit.steals else 'heal' if hit.heals else 'damage'


def _elements(hits, kind):
    return [hit.element for hit in hits if _kind(hit) == kind]


def _shown(weapon):
    return weapon.non_crit_hits[weapon.element_maged if weapon.is_mageable else NEUTRAL]


def _old_convert(hit, rate):
    return (int((hit.min_dam - 1) * rate + 1),
            int((hit.min_dam - 1) * rate) + int((hit.max_dam - hit.min_dam + 1) * rate))


def _in(test, version):
    test.addCleanup(set_current_game_version, 'dofus3')
    set_current_game_version(version)
    return get_structure(version)


def _worn(test, version, ankama_id, choice=None, **base):
    structure = _in(test, version)
    result = ModelResult({'options': dict(_OPTIONS),
                          'base_stats_by_attr': dict(_BASE, **base),
                          'char_level': 200})
    result.forge_choice = choice
    result.add_item_at_slot(structure.get_item_by_ankama_id(ankama_id), 'weapon')
    result.calculate_stats()
    return result, result.items['Weapon'][0]


def _shared(structure, ankama_id):
    return structure.get_weapon_for_item(structure.get_item_by_ankama_id(ankama_id))


def _zero_stats(structure):
    return {stat.key: 0 for stat in structure.get_stats_list()}


def _input(**base):
    return {'char_class': 'Iop', 'char_level': 200, 'origin': 'generated',
            'options': dict(_OPTIONS), 'base_stats_by_attr': dict(_BASE, **base),
            'locked_equips': {}}


class TheStealTurnsWithTheEngravingTests(SimpleTestCase):

    def test_auto_turns_the_steal_and_the_heals_to_the_intelligence_element(self):
        for version in _FORGE_VERSIONS:
            with self.subTest(version=version):
                _result, weapon = _worn(self, version, _MALLEFISK_WAND, Intelligence=500)
                self.assertFalse(weapon.is_mageable)
                self.assertEqual([FIRE], _elements(_shown(weapon), 'steal'))
                self.assertEqual([FIRE, FIRE], _elements(_shown(weapon), 'heal'))
                self.assertEqual([FIRE, FIRE, FIRE],
                                 [hit.element for hit in weapon.crit_hits[NEUTRAL]])

    def test_the_damage_potion_leaves_the_steal_neutral(self):
        for version in _FORGE_VERSIONS:
            with self.subTest(version=version):
                _result, weapon = _worn(self, version, _MALLEFISK_WAND,
                                        {'damage': (FIRE, 'strong'), 'steal': None,
                                         'heal': None}, Intelligence=500)
                self.assertFalse(weapon.is_mageable)
                self.assertNotIn('damage', weapon.conversions)
                for element in DAMAGE_TYPES:
                    self.assertEqual(_rows(weapon.forge_base),
                                     _rows(weapon.non_crit_hits[element]))

    def test_the_engraving_alone_turns_the_steal(self):
        for version in _FORGE_VERSIONS:
            with self.subTest(version=version):
                _result, weapon = _worn(self, version, _MALLEFISK_WAND,
                                        {'steal': (WATER, 'strong'), 'heal': None},
                                        Intelligence=500)
                self.assertEqual(WATER, weapon.steal_element)
                self.assertEqual([WATER], _elements(_shown(weapon), 'steal'))
                self.assertEqual([NEUTRAL, NEUTRAL], _elements(_shown(weapon), 'heal'))
                self.assertEqual([hit.min_dam for hit in weapon.forge_base],
                                 [hit.min_dam for hit in _shown(weapon)])


class TheHealTurnsWithTheShardTests(SimpleTestCase):

    def test_auto_turns_the_heal_fire_and_it_scales_on_intelligence(self):
        for version in _FORGE_VERSIONS:
            with self.subTest(version=version):
                result, weapon = _worn(self, version, _GOLDEN_SCARABUGLY_WAND,
                                       Intelligence=500)
                stats = result.get_stats_total()
                self.assertEqual(FIRE, weapon.heal_element)
                self.assertEqual([(11, 30, FIRE, False, True)], _rows(_shown(weapon)))
                fire = calculate_damage(_shown(weapon), stats, False, False)
                neutral = calculate_damage(weapon.forge_base, stats, False, False)
                self.assertGreater(fire[0].average(), neutral[0].average())

    def test_the_damage_potion_leaves_the_heal_neutral(self):
        for version in _FORGE_VERSIONS:
            with self.subTest(version=version):
                _result, weapon = _worn(self, version, _GOLDEN_SCARABUGLY_WAND,
                                        {'damage': (FIRE, 'strong'), 'heal': None},
                                        Intelligence=500)
                self.assertFalse(weapon.is_mageable)
                self.assertEqual([(11, 30, NEUTRAL, False, True)], _rows(_shown(weapon)))


class EachKindOfOneWeaponTurnsOnItsOwnTests(SimpleTestCase):

    def test_auto_shoots_and_heals_fire(self):
        for version in _FORGE_VERSIONS:
            with self.subTest(version=version):
                _result, weapon = _worn(self, version, _HIDSAD_BOW, Intelligence=500)
                self.assertEqual(FIRE, weapon.element_maged)
                self.assertEqual([(12, 42, FIRE, False, False), (12, 42, FIRE, False, True)],
                                 _rows(_shown(weapon)))

    def test_a_fire_damage_bonus_shoots_fire_while_chance_heals_water(self):
        for version in _FORGE_VERSIONS:
            with self.subTest(version=version):
                structure = _in(self, version)
                stats = dict(_zero_stats(structure), cha=100, firedam=100)
                weapon = ModelResultItem(structure.get_item_by_ankama_id(_HIDSAD_BOW))
                weapon.mage_weapon_smartly(stats)
                self.assertEqual((FIRE, WATER), (weapon.element_maged, weapon.heal_element))
                self.assertEqual([(12, 42, FIRE, False, False), (12, 42, WATER, False, True)],
                                 _rows(_shown(weapon)))

    def test_a_neutral_heal_keeps_the_fire_damage(self):
        for version in _FORGE_VERSIONS:
            with self.subTest(version=version):
                _result, weapon = _worn(self, version, _HIDSAD_BOW, {'heal': None},
                                        Intelligence=500)
                self.assertEqual(FIRE, weapon.element_maged)
                self.assertEqual([(12, 42, FIRE, False, False),
                                  (12, 42, NEUTRAL, False, True)], _rows(_shown(weapon)))

    def test_a_weak_shard_heals_a_tenth_in_its_own_element(self):
        for version in _FORGE_VERSIONS:
            with self.subTest(version=version):
                _result, weapon = _worn(self, version, _HIDSAD_BOW,
                                        {'damage': (FIRE, 'strong'), 'heal': (WATER, 'weak')})
                bonus = weapon.crit_bonus
                self.assertEqual([(12, 42, FIRE, False, False), (2, 4, WATER, False, True)],
                                 _rows(weapon.non_crit_hits[FIRE]))
                self.assertEqual([(12 + bonus, 42 + bonus, FIRE, False, False),
                                  (2 + bonus, 4 + bonus, WATER, False, True)],
                                 _rows(weapon.crit_hits[FIRE]))
                expected = weapon_forge.convert(weapon.forge_base[1], WATER,
                                                weapon_forge.rate(version, 'heal', 'weak'))
                self.assertEqual(_rows([expected]), _rows(weapon.non_crit_hits[FIRE][1:]))


class TheTierComesFromTheChoiceTests(SimpleTestCase):

    def test_dofus2_potions_keep_half_or_two_thirds_of_the_roll(self):
        for tier, expected in (('weak', (5, 10)), ('medium', (7, 14))):
            with self.subTest(tier=tier):
                _result, weapon = _worn(self, 'dofus2', _KUKRI_KURA,
                                        {'damage': (WATER, tier)}, Strength=500)
                self.assertEqual(WATER, weapon.element_maged)
                self.assertEqual([expected + (WATER, False, False)] * 2,
                                 _rows(_shown(weapon)))
                rate = weapon_forge.rate('dofus2', 'damage', tier)
                self.assertEqual(_rows([weapon_forge.convert(hit, FIRE, rate)
                                        for hit in weapon.forge_base]),
                                 _rows(weapon.non_crit_hits[FIRE]))

    def test_a_tier_the_version_does_not_rate_keeps_its_element_at_the_strong_rate(self):
        for version, tier in (('retro', 'weak'), ('dofus3', 'medium')):
            with self.subTest(version=version, tier=tier):
                _result, auto = _worn(self, version, _KUKRI_KURA, Intelligence=500)
                _result, strong = _worn(self, version, _KUKRI_KURA,
                                        {'damage': (WATER, 'strong')}, Intelligence=500)
                _result, unrated = _worn(self, version, _KUKRI_KURA,
                                         {'damage': (WATER, tier)}, Intelligence=500)
                self.assertIsNone(weapon_forge.rate(version, 'damage', tier))
                self.assertEqual(FIRE, auto.element_maged)
                self.assertEqual({'damage': (WATER, 'strong')}, unrated.conversions)
                self.assertEqual(_tabs(strong.non_crit_hits), _tabs(unrated.non_crit_hits))


class AnUnforgeableWeaponIsNeverMagedTests(SimpleTestCase):

    def test_the_weapon_curse_keeps_its_neutral_line(self):
        for version in ('dofus3', 'beta', 'dofus2'):
            with self.subTest(version=version):
                _result, weapon = _worn(self, version, _WEAPON_CURSE,
                                        {'damage': (FIRE, 'strong')}, Intelligence=500)
                self.assertFalse(weapon_forge.can_forge(version, _WEAPON_CURSE))
                self.assertFalse(weapon.is_mageable)
                self.assertEqual({}, weapon.conversions)
                for element in DAMAGE_TYPES:
                    self.assertEqual([NEUTRAL], [hit.element
                                                 for hit in weapon.non_crit_hits[element]])
                shared = _shared(get_structure(version), _WEAPON_CURSE)
                self.assertFalse(shared.is_mageable)
                self.assertEqual({NEUTRAL}, {hit.element for element in DAMAGE_TYPES
                                             for hit in shared.non_crit_hits[element]})


class AStoredBuildReadsTodaysRowsTests(SimpleTestCase):

    def test_an_item_pickled_without_the_forge_fields_reads_the_shared_rows(self):
        structure = _in(self, 'dofus3')
        result, _weapon = _worn(self, 'dofus3', _KUKRI_KURA, Intelligence=500)
        legacy = pickle.loads(pickle.dumps(
            ModelResultItem(structure.get_item_by_ankama_id(_KUKRI_KURA))))
        self.assertEqual([], [field for field in _FORGE_FIELDS if field in vars(legacy)])
        legacy.mage_weapon_smartly(result.get_stats_total())
        shared = _shared(structure, _KUKRI_KURA)
        self.assertEqual(FIRE, legacy.element_maged)
        self.assertEqual(_tabs(shared.non_crit_hits), _tabs(legacy.non_crit_hits))
        self.assertEqual(_tabs(shared.crit_hits), _tabs(legacy.crit_hits))

    def test_a_minimal_read_without_a_choice_gives_the_shared_rows(self):
        structure = _in(self, 'dofus3')
        kukri = structure.get_item_by_ankama_id(_KUKRI_KURA)
        minimal = ModelResultMinimal({'weapon': kukri.id}, _input(Intelligence=500), {})
        weapon = model_result_from_minimal(pickle.loads(pickle.dumps(minimal))).items['Weapon'][0]
        shared = _shared(structure, _KUKRI_KURA)
        self.assertEqual(FIRE, weapon.element_maged)
        self.assertEqual(_tabs(shared.non_crit_hits), _tabs(weapon.non_crit_hits))
        self.assertEqual(_tabs(shared.crit_hits), _tabs(weapon.crit_hits))


class TwoBuildsKeepTheirOwnChoiceTests(SimpleTestCase):

    def test_two_builds_on_one_weapon_do_not_share_their_rows(self):
        structure = _in(self, 'beta')
        shared = _shared(structure, _HIDSAD_BOW)
        before = (_tabs(shared.non_crit_hits), _tabs(shared.crit_hits), _rows(shared.base_hit))
        _result, neutral_heal = _worn(self, 'beta', _HIDSAD_BOW,
                                      {'damage': (WATER, 'strong'), 'heal': None},
                                      Intelligence=500)
        _result, auto = _worn(self, 'beta', _HIDSAD_BOW, Intelligence=500)
        self.assertEqual((WATER, NEUTRAL), (neutral_heal.element_maged, neutral_heal.heal_element))
        self.assertEqual((FIRE, FIRE), (auto.element_maged, auto.heal_element))
        self.assertEqual([NEUTRAL], _elements(neutral_heal.non_crit_hits[WATER], 'heal'))
        self.assertEqual([FIRE], _elements(auto.non_crit_hits[WATER], 'heal'))
        self.assertEqual(before, (_tabs(shared.non_crit_hits), _tabs(shared.crit_hits),
                                  _rows(shared.base_hit)))


class TheItemPickerRatesTheBuildsOwnRowsTests(SimpleTestCase):

    def test_a_build_that_keeps_the_kukri_neutral_rates_it_lower(self):
        rates = {}
        for label, choice in (('auto', None), ('neutral', {'damage': None})):
            result, _weapon = _worn(self, 'dofus3', _KUKRI_KURA, choice, Intelligence=500)
            kukri = get_structure('dofus3').get_item_by_ankama_id(_KUKRI_KURA)
            rates[label] = _get_weapon_rate(kukri, None, result)
        self.assertGreater(rates['auto'], rates['neutral'])

    def test_retro_daggers_sharing_a_name_and_rows_rate_on_their_own_odds(self):
        result, _weapon = _worn(self, 'retro', _SRAM_DAGGERS)
        structure = get_structure('retro')
        sram, sacrier = (structure.get_item_by_ankama_id(ankama_id)
                         for ankama_id in (_SRAM_DAGGERS, _SACRIER_DAGGERS))
        own = [structure.get_weapon_for_item(item) for item in (sram, sacrier)]
        for item, weapon in zip((sram, sacrier), own):
            self.assertIsNot(weapon, structure.get_weapon_by_name(item.name))
        self.assertEqual(_rows(own[0].base_hit), _rows(own[1].base_hit))
        self.assertLess(own[0].crit_chance, own[1].crit_chance)
        self.assertGreater(_get_weapon_rate(sram, None, result),
                           _get_weapon_rate(sacrier, None, result))


class TheWeaponCardListsTheCatalogueLinesTests(SimpleTestCase):

    def test_the_card_reads_the_same_whatever_the_forge_choice(self):
        _result, auto = _worn(self, 'beta', _MALLEFISK_WAND, Intelligence=500)
        _result, neutral = _worn(self, 'beta', _MALLEFISK_WAND,
                                 {'steal': None, 'heal': None}, Intelligence=500)
        self.assertEqual((FIRE, NEUTRAL), (auto.steal_element, neutral.steal_element))
        evolve_result_item(auto)
        evolve_result_item(neutral)
        self.assertEqual(neutral.damage_text, auto.damage_text)


class EachChoiceKeepsItsOwnTurnGainsTests(SimpleTestCase):

    def test_two_choices_on_one_weapon_are_cached_apart(self):
        structure = _in(self, 'beta')
        stats = dict(_zero_stats(structure), int=800, ap=12)
        self.addCleanup(modifier_values._GAINS.clear)
        modifier_values._GAINS.clear()
        for element in (FIRE, WATER):
            weapon = ModelResultItem(structure.get_item_by_ankama_id(_MALLEFISK_WAND))
            weapon.mage_weapon_smartly(stats, {'steal': (element, 'strong')})
            modifier_values.item_gains('beta', 'Cra', 200, stats, ('int',), 12,
                                       WeaponCastable(weapon))
        self.assertEqual(2, len(modifier_values._GAINS))


class AConvertedRangeNeverInvertsTests(SimpleTestCase):

    def test_a_flat_roll_keeps_its_maximum_at_its_minimum(self):
        for low, high, rate, expected in ((30, 30, 0.85, (25, 25)), (8, 10, 0.1, (1, 1))):
            with self.subTest(low=low, high=high, rate=rate):
                hit = DamageDigest(low, high, NEUTRAL)
                self.assertGreater(*_old_convert(hit, rate))
                converted = weapon_forge.convert(hit, FIRE, rate)
                self.assertEqual(expected, (converted.min_dam, converted.max_dam))

    def test_every_line_the_old_rounding_kept_in_order_is_unchanged(self):
        lifted = 0
        for version in _VERSIONS:
            structure = _in(self, version)
            rates = {weapon_forge.applied_rate(version, kind, tier)
                     for kind in weapon_forge.kinds(version) for tier in weapon_forge.TIERS}
            rates.discard(None)
            changed, inverted = [], []
            weapons = list(structure.weapons_by_key.items()) + list(
                structure.dt_weapons_by_key.items())
            for key, weapon in weapons:
                for hit in weapon.base_hit:
                    if hit.element != NEUTRAL:
                        continue
                    for rate in rates:
                        old = _old_convert(hit, rate)
                        converted = weapon_forge.convert(hit, FIRE, rate)
                        new = (converted.min_dam, converted.max_dam)
                        if old[1] >= old[0] and new != old:
                            changed.append((key, rate))
                        lifted += old[1] < old[0]
                for tabs in (weapon.non_crit_hits, weapon.crit_hits or {}):
                    inverted += [(key, element) for element, hits in tabs.items()
                                 for hit in hits if hit.max_dam < hit.min_dam]
            with self.subTest(version=version):
                self.assertTrue(rates)
                self.assertEqual([], changed)
                self.assertEqual([], inverted)
        self.assertGreater(lifted, 0)


class TheStoredChoiceRoundTripsTests(SimpleTestCase):

    def test_a_choice_reads_back_as_written(self):
        choice = {'damage': (FIRE, 'strong'), 'steal': None, 'heal': (WATER, 'weak')}
        self.assertEqual(choice, weapon_forge.read_choice(weapon_forge.write_choice(choice)))
        self.assertEqual('', weapon_forge.write_choice({}))

    def test_an_empty_or_unreadable_choice_is_auto(self):
        for text in ('', 'not json', '[1]', '{"damage": ["neut", "strong"], "pick": null,'
                                              ' "heal": ["fire", "huge"]}'):
            with self.subTest(text=text):
                self.assertEqual({}, weapon_forge.read_choice(text))


class ACharacterCarriesItsOwnChoiceTests(TestCase):

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.structure = _in(self, 'dofus3')
        kukri = self.structure.get_item_by_ankama_id(_KUKRI_KURA)
        self.blob = pickle.dumps(ModelResultMinimal({'weapon': kukri.id}, _input(), {}))
        self.owner = User.objects.create_user('forger', 'forger@test.local', 'pw-42-solid')

    def _char(self, name, **fields):
        char = Char.objects.create(
            name=name, char_name=name, char_class='Iop', char_build='', level=200,
            minimum_stats=b'', minimum_crits=b'', stats_weight=pickle.dumps({}),
            options=pickle.dumps(dict(_OPTIONS)), inclusions=b'', exclusions=b'',
            owner=self.owner, link_shared=False, game_version='dofus3',
            minimal_solution=self.blob, **fields)
        for stat, _key in STATS_NAMES:
            value = 500 if stat == 'Intelligence' else 0
            CharBaseStats.objects.create(char=char, stat=stat, total_value=value,
                                         scrolled_value=value)
        return char

    def test_an_empty_choice_gives_the_shared_rows(self):
        char = self._char('Auto')
        self.assertEqual('', Char.objects.get(pk=char.pk).weapon_forge)
        weapon = get_solution(char).items['Weapon'][0]
        shared = _shared(self.structure, _KUKRI_KURA)
        self.assertEqual(FIRE, weapon.element_maged)
        self.assertEqual(_tabs(shared.non_crit_hits), _tabs(weapon.non_crit_hits))
        self.assertEqual(_tabs(shared.crit_hits), _tabs(weapon.crit_hits))

    def test_two_characters_keep_their_own_choice(self):
        shared = _shared(self.structure, _KUKRI_KURA)
        before = copy.deepcopy(_tabs(shared.non_crit_hits))
        auto = self._char('Auto')
        water = self._char('Water', weapon_forge=weapon_forge.write_choice(
            {'damage': (WATER, 'strong')}))
        for char, expected in ((auto, FIRE), (water, WATER), (auto, FIRE)):
            with self.subTest(char=char.name):
                weapon = get_solution(Char.objects.get(pk=char.pk)).items['Weapon'][0]
                self.assertEqual(expected, weapon.element_maged)
                self.assertEqual(_rows(shared.non_crit_hits[expected]), _rows(_shown(weapon)))
        self.assertEqual(before, _tabs(shared.non_crit_hits))

    def test_a_choice_written_without_a_save_moves_the_cache_keys(self):
        char = Char.objects.get(pk=self._char('Cached').pk)
        keys = (get_picker_cache_key(char, 1, '', 'true', '[]'),
                _get_shared_solution_cache_key(char))
        Char.objects.filter(pk=char.pk).update(
            weapon_forge=weapon_forge.write_choice({'damage': (WATER, 'strong')}))
        moved = Char.objects.get(pk=char.pk)
        self.assertEqual(char.modified_time, moved.modified_time)
        self.assertNotEqual(keys[0], get_picker_cache_key(moved, 1, '', 'true', '[]'))
        self.assertNotEqual(keys[1], _get_shared_solution_cache_key(moved))
