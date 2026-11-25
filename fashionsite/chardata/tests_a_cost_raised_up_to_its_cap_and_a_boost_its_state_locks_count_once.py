# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A spell whose casts raise its AP cost up to a cap pays that cost and no more, and a boost its own state locks shows one Stack."""
from unittest import mock

from django.test import SimpleTestCase
from django.utils import translation
from django.utils.translation import gettext

from chardata.spell_buffs import get_damage_spells_for_version
from chardata.spell_combo import Castable, best_turn, cast_cost

EXPLOSIVE_PALM = 12781
REDEMPTION_ARROW = 13074
PROBE = 99001
VERSIONS = ('dofus3', 'beta', 'dofus2')
MODERN = ('dofus3', 'beta')
COSTS = "Le coût en PA du sort est augmenté après le premier lancer."
ONCE = 'Chaque effet est cumulable une fois.'
DRUNK, BOOSTED = 498, 3533
CAPPED = {'en': '2 AP, then +1 per cast up to 3 AP',
          'fr': "2 PA, puis +1 par lancer jusqu'à 3 PA",
          'es': '2 PA, luego +1 por lanzamiento hasta 3 PA',
          'pt': '2 PA, depois +1 por lançamento até 3 PA',
          'de': '2 AP, dann +1 pro Einsatz bis 3 AP'}

_STATS = {'str': 200, 'int': 200, 'cha': 200, 'agi': 200, 'pow': 0, 'dam': 0,
          'cridam': 0, 'heals': 0, 'perspedam': 0, 'perweadam': 0,
          'permedam': 0, 'perrandam': 0, 'earthdam': 0, 'firedam': 0,
          'waterdam': 0, 'airdam': 0, 'neutdam': 0, 'ch': 0, 'final': 0,
          'negfinal': 0, 'pshdam': 0, 'ap': 12}


def _generator():
    from chardata.tests import itemscraper_module
    return itemscraper_module('generate_damage_spells')


def _in_version(test, version):
    from fashionistapulp.structure import set_current_game_version
    test.addCleanup(set_current_game_version, 'dofus3')
    set_current_game_version(version)


def _spell(version, spell_id):
    return next(spell for spells in get_damage_spells_for_version(version).values()
                for spell in spells if spell.spell_id == spell_id)


def _cast(spell):
    return Castable(spell, len(spell.level_req) - 1, crit=False)


def _cost_row(spell_id=PROBE, value=1, duration=1, delay=0, mask='C', triggers='I', flags=75,
              raised=None):
    return {'effect_id': 296, 'value': value, 'dice': {'min': raised or spell_id, 'max': 0},
            'duration': duration, 'delay': delay, 'target_mask': mask, 'triggers': triggers,
            'flags': flags, 'random': 0}


def _costly(text=COSTS, max_stack=1, casts=3, critical=None, **shape):
    hit = {'effect_id': 99, 'dice': {'min': 12, 'max': 0}, 'value': 0, 'duration': 0, 'delay': 0,
           'target_mask': 'g,A', 'triggers': 'I', 'flags': 79}
    level = {'grade': 1, 'ap_cost': 2, 'max_stack': max_stack, 'max_cast_per_turn': casts,
             'effects': [hit, _cost_row(**shape)],
             'critical_effects': [hit, _cost_row(**dict(shape, **(critical or {})))]}
    return {'ankama_id': PROBE, 'description_fr': 'Occasionne des dommages Feu.\n' + text,
            'levels': [level]}


def _locked_level(max_stack=1, gives=BOOSTED, forbids=BOOSTED):
    gate = 'C,*E%d,*e%d' % (DRUNK, forbids)
    effects = [{'effect_id': 99, 'dice': {'min': 12, 'max': 0}, 'value': 0, 'duration': 0,
                'delay': 0, 'target_mask': 'g,A', 'triggers': 'I', 'flags': 79},
               {'effect_id': 293, 'value': 6, 'dice': {'min': PROBE, 'max': 0}, 'duration': 1,
                'delay': 0, 'target_mask': gate, 'triggers': 'I', 'flags': 79}]
    if gives:
        effects.append({'effect_id': 950, 'value': gives, 'dice': {'min': 0, 'max': 0},
                        'duration': 0, 'delay': 0, 'target_mask': gate, 'triggers': 'I',
                        'flags': 64})
    return {'grade': 1, 'ap_cost': 2, 'max_stack': max_stack, 'max_cast_per_turn': 3,
            'effects': effects, 'critical_effects': [dict(effect) for effect in effects]}


def _locked(text=ONCE, caps=4, **level):
    rows = [{'element': 'FIRE', 'ranges': ['12'], 'situation': 'g,A,*e3532|67,1,0',
             'triggers': 'I'},
            {'element': 'FIRE', 'ranges': ['12'], 'situation': 'g,A,*E3532|67,2,0',
             'triggers': 'I'}]
    return {'ankama_id': PROBE, 'name_en': 'Probe', 'level_requirements': [1],
            'description_fr': 'Occasionne des dommages Feu.\n' + text,
            'levels': [_locked_level(**level)],
            'damage_templates': {'normal': [dict(row) for row in rows],
                                 'critical': [dict(row, ranges=['15']) for row in rows],
                                 'stackable_damage': {'per_stack': [6], 'max_stacks': [caps]}}}


class TheGeneratorReadsACostRaisedUpToItsCapTests(SimpleTestCase):

    def test_explosive_palm_costs_one_more_ap_once_on_every_version(self):
        for version in VERSIONS:
            spell = _spell(version, EXPLOSIVE_PALM)
            with self.subTest(version=version):
                self.assertEqual(spell.casting['ap_growth'], [1] * len(spell.level_req))
                self.assertEqual(spell.casting['ap_growth_cap'], [1] * len(spell.level_req))

    def test_no_other_spell_carries_a_cost_growth_on_these_versions(self):
        for version in VERSIONS:
            grown = sorted({spell.spell_id for spells in get_damage_spells_for_version(version).values()
                            for spell in spells if (spell.casting or {}).get('ap_growth')})
            with self.subTest(version=version):
                self.assertEqual(grown, [EXPLOSIVE_PALM])

    def test_the_listed_rows_give_a_growth_of_one_capped_at_the_stack_limit(self):
        gen = _generator()
        with mock.patch.object(gen, 'AP_COST_GROWS', {PROBE: COSTS.lower()}):
            self.assertEqual(gen._ap_cost_growth(_costly()), ([1], [1]))
            self.assertEqual(gen._ap_cost_growth(_costly(max_stack=2)), ([1], [2]))

    def test_a_cost_row_off_its_shape_stops_the_generator(self):
        gen = _generator()
        cases = {
            'card lost the sentence': _costly(text='Occasionne des dommages.'),
            'lasts two turns': _costly(duration=2),
            'waits a turn': _costly(delay=1),
            'lands on allies': _costly(mask='a'),
            'another trigger': _costly(triggers='TB'),
            'tooltip only': _costly(flags=95),
            'no raise': _costly(value=0),
            'critical raise differs': _costly(critical={'value': 2}),
            'another spell raised': _costly(raised=PROBE + 1),
            'no stack limit': _costly(max_stack=-1),
            'one cast a turn': _costly(casts=1),
        }
        with mock.patch.object(gen, 'AP_COST_GROWS', {PROBE: COSTS.lower()}):
            for case, raw in cases.items():
                with self.subTest(case=case), self.assertRaises(SystemExit):
                    gen._ap_cost_growth(raw)

    def test_an_unlisted_spell_raising_its_own_cost_is_a_problem(self):
        gen = _generator()
        self.assertEqual(gen._unlisted_ap_cost_growth(_costly()),
                         'its casts raise its own AP cost, which no table lists')
        self.assertIsNone(gen._unlisted_ap_cost_growth(_costly(raised=PROBE + 1)))
        with mock.patch.object(gen, 'AP_COST_GROWS', {PROBE: COSTS.lower()}):
            self.assertIsNone(gen._unlisted_ap_cost_growth(_costly()))


class TheSearchPaysTheCappedCostTests(SimpleTestCase):

    def test_the_casts_cost_two_then_three_then_three_ap(self):
        for version in VERSIONS:
            _in_version(self, version)
            cast = _cast(_spell(version, EXPLOSIVE_PALM))
            with self.subTest(version=version):
                self.assertEqual([cast_cost(cast, earlier) for earlier in range(3)], [2, 3, 3])

    def test_seven_ap_fit_two_casts_and_eight_fit_three(self):
        from chardata.spell_combo import _search_best_turn
        for version in VERSIONS:
            _in_version(self, version)
            cast = _cast(_spell(version, EXPLOSIVE_PALM))
            for ap, casts in ((4, 1), (5, 2), (7, 2), (8, 3)):
                for ceiling_scores in (4096, -1):
                    with mock.patch('chardata.spell_combo.CEILING_SCORES', ceiling_scores), \
                            self.subTest(version=version, ap=ap, ceiling_scores=ceiling_scores):
                        _total, order = _search_best_turn(dict(_STATS, ap=ap), [cast], ap,
                                                          game_version=version, caster_level=200)
                        self.assertEqual(len(order), casts)

    def test_the_spell_page_names_the_capped_cost(self):
        from chardata.spells_view import _create_spell_web_digest
        for version in VERSIONS:
            _in_version(self, version)
            digest = _create_spell_web_digest(_spell(version, EXPLOSIVE_PALM), version)
            with self.subTest(version=version):
                self.assertEqual(digest['ap_growth_cap'], [1, 1, 1])

    def test_the_capped_cost_reads_in_each_language(self):
        for language, text in CAPPED.items():
            with translation.override(language), self.subTest(language=language):
                self.assertEqual(gettext('%(ap)s AP, then +%(step)s per cast up to %(top)s AP')
                                 % {'ap': 2, 'step': 1, 'top': 3}, text)


class TheGeneratorCutsABoostItsStateLocksToOneStackTests(SimpleTestCase):

    def test_explosive_palm_shows_one_stack_of_its_boost(self):
        for version in MODERN:
            spell = _spell(version, EXPLOSIVE_PALM)
            digest = spell.get_effects_digest()
            with self.subTest(version=version):
                self.assertEqual([label for label, _rows in spell.aggregates],
                                 ['Stack 0', '', 'Stack 1', ''])
                for rank, boost in zip(digest.non_crit_dams, (6, 8, 12)):
                    self.assertEqual([row.min_dam - rank[0].min_dam for row in rank],
                                     [0, 0, boost, boost])

    def test_a_listed_locked_boost_climbs_one_stack(self):
        gen = _generator()
        with mock.patch.object(gen, 'ONE_STACK_FROM_ITS_OWN_STATE', {PROBE: ONCE.lower()}):
            entry = gen.convert_spell(_locked())
        self.assertIsNone(entry.boost_problem)
        self.assertEqual(entry.non_crit_ranges, [['12'], ['12'], ['18'], ['18']])

    def test_an_unlisted_locked_boost_past_one_stack_is_a_problem(self):
        entry = _generator().convert_spell(_locked())
        self.assertEqual(entry.boost_problem, 'its damage boost gives the caster a state that '
                                              'forbids it, yet its ladder climbs past one stack')

    def test_a_locked_boost_off_its_shape_stops_the_generator(self):
        gen = _generator()
        cases = {
            'card lost the sentence': _locked(text='Occasionne des dommages.'),
            'no state given': _locked(gives=None),
            'another state given': _locked(gives=BOOSTED + 1),
            'stacks twice': _locked(max_stack=2),
            'ladder of one already': _locked(caps=1),
        }
        with mock.patch.object(gen, 'ONE_STACK_FROM_ITS_OWN_STATE', {PROBE: ONCE.lower()}):
            for case, raw in cases.items():
                with self.subTest(case=case), self.assertRaises(SystemExit):
                    gen.convert_spell(raw)


class RedemptionArrowClimbsItsLadderOnDofus2Tests(SimpleTestCase):

    def test_each_cast_lands_the_next_stack_and_the_ally_rows_are_held(self):
        spell = _spell('dofus2', REDEMPTION_ARROW)
        self.assertTrue(spell.stacks_on_recast)
        self.assertEqual(spell.conditional, {1: 'on_ally', 3: 'on_ally', 5: 'on_ally'})

    def test_two_casts_deal_the_first_then_the_second_stack(self):
        _in_version(self, 'dofus2')
        cast = _cast(_spell('dofus2', REDEMPTION_ARROW))
        _total, order = best_turn(dict(_STATS, ap=6), [cast], 6, game_version='dofus2',
                                  caster_level=200)
        damages = [damage for _name, damage in order]
        self.assertEqual(len(damages), 2)
        self.assertGreater(damages[1], damages[0])

    def test_the_second_cast_lands_the_first_boosted_stack_and_the_third_the_next(self):
        from chardata.spell_combo import recast_alternatives
        _in_version(self, 'dofus2')
        cast = _cast(_spell('dofus2', REDEMPTION_ARROW))
        landed = [str(recast_alternatives(cast, earlier)[0][0][0]) for earlier in (1, 2, 3)]
        self.assertEqual([text.split(' ')[0] for text in landed], ['30-33', '37-40', '37-40'])
