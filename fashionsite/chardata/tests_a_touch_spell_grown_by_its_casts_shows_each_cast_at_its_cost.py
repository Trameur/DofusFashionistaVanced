# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A Touch spell whose casts grow it lands each cast at its own damage and AP cost, and holds its boosted later casts apart."""
from unittest import mock

from django.test import SimpleTestCase
from django.utils import translation

from chardata.spell_buffs import get_damage_spells_for_version
from chardata.spell_combo import (ARMED_BY_ITS_OWN_CAST, Castable, best_turn, cast_cost,
                                  conditional_extras)

VERSIONS = ('touch', 'touchbeta')
HARASSING_ARROW, IOPS_ANGER, ANGER_BOOST = 12439, 8119, 8721
GROWS = ('Occasionne des dommages Terre qui augmentent pour chaque lancer durant le même tour. '
         'Le coût en PA du sort augmente à chaque lancer.')
STACKS = ('Occasionne des dommages Terre. Les dommages sont augmentés après chaque lancer '
          '(cumul maximum de 2).')
LABEL = {'en': 'on its cast once 2 earlier casts stack their boost',
         'fr': 'lors de son lancer une fois que 2 lancers précédents cumulent leur bonus',
         'es': 'en su lanzamiento una vez que 2 lanzamientos anteriores acumulan su bonificación',
         'pt': 'no seu lançamento quando 2 lançamentos anteriores acumulam seu bônus',
         'de': 'beim Wirken, sobald sich der Bonus von 2 früheren Einsätzen stapelt'}
FOLLOWING_TURN = {'en': 'on its cast the following turn', 'fr': 'lors de son lancer au tour suivant'}

_STATS = {'str': 200, 'int': 200, 'cha': 200, 'agi': 200, 'pow': 0, 'dam': 0,
          'cridam': 0, 'heals': 0, 'perspedam': 0, 'perweadam': 0,
          'permedam': 0, 'perrandam': 0, 'earthdam': 0, 'firedam': 0,
          'waterdam': 0, 'airdam': 0, 'neutdam': 0, 'ch': 0, 'final': 0,
          'negfinal': 0, 'pshdam': 0, 'ap': 12}


def _reader():
    from chardata.tests import itemscraper_module
    return itemscraper_module('get_spells_touch')


def _in_version(test, version):
    from fashionistapulp.structure import set_current_game_version
    test.addCleanup(set_current_game_version, 'dofus3')
    set_current_game_version(version)


def _spell(version, spell_id):
    return next(spell for spells in get_damage_spells_for_version(version).values()
                for spell in spells if spell.spell_id == spell_id)


def _cast(spell):
    return Castable(spell, len(spell.level_req) - 1, crit=False)


def _row(effect_id, dice, value=0, mask='C', triggers='I', delay=0, duration=1, **extra):
    row = {'effectId': effect_id, 'diceNum': dice, 'diceSide': 0, 'value': value,
           'targetMask': mask, 'triggers': triggers, 'delay': delay, 'duration': duration,
           'random': 0, 'rawZone': 'P', 'isPreview': False}
    row.update(extra)
    return row


def _hit(low):
    return dict(_row(97, low, mask='a,A', duration=0), diceSide=low + 4)


def _record(spell_id, text, effects, critical, levels=None, child=None, **rank):
    levels = dict(levels or {})
    shape = {'minPlayerLevel': 1, 'apCost': 2, 'maxCastPerTurn': 3, 'maxStack': 0,
             'criticalHitProbability': 15, 'effects': effects, 'criticalEffect': critical}
    shape.update(rank)
    levels[str(spell_id * 10)] = shape
    spells = {str(spell_id): {'id': spell_id, 'nameId': 'Probe', 'descriptionId': text,
                              'spellLevels': [spell_id * 10]}}
    if child:
        spells[str(child['id'])] = child
    return spells[str(spell_id)], levels, spells


def _harassing(text=GROWS, damage=None, crit_damage=None, cost=None, before_the_hit=False, **rank):
    def rows(low, step):
        own = [dict(_row(293, HARASSING_ARROW, step), **(damage or {})),
               dict(_row(2985, HARASSING_ARROW, 1), **(cost or {}))]
        return own + [_hit(low)] if before_the_hit else [_hit(low)] + own
    return _record(HARASSING_ARROW, text, rows(6, 15), rows(8, (crit_damage or {}).get('value', 15)),
                   **rank)


def _anger(text=STACKS, boost=None, child_rank=None, parent_rows=(), **rank):
    boost_row = _row(293, IOPS_ANGER, 20, delay=1, duration=3)
    boost_row.update(boost or {})
    child_level = {'maxStack': 2, 'effects': [boost_row], 'criticalEffect': []}
    child_level.update(child_rank or {})
    levels = {str(ANGER_BOOST * 10): child_level}
    child = {'id': ANGER_BOOST, 'spellLevels': [ANGER_BOOST * 10]}

    def rows(low):
        return ([_hit(low), _row(1160, ANGER_BOOST, mask='C', duration=0, diceSide=1)]
                + list(parent_rows))
    shape = dict({'apCost': 4, 'maxCastPerTurn': 1, 'maxStack': 2}, **rank)
    return _record(IOPS_ANGER, text, rows(14), rows(19), levels=levels, child=child, **shape)


def _decode(record):
    spell, levels, spells = record
    return _reader().decode_spell(spell, levels, spells)


class TheTouchReaderGrowsASpellByItsCastsTests(SimpleTestCase):

    def test_each_cast_of_the_turn_gets_a_stack_raised_by_one_more_step_and_one_more_ap(self):
        entry = _decode(_harassing())
        self.assertEqual(entry['non_crit_ranges'], [['6-10'], ['21-25'], ['36-40']])
        self.assertEqual(entry['crit_ranges'], [['8-12'], ['23-27'], ['38-42']])
        self.assertEqual(entry['aggregates'], [('Stack 0', [0]), ('Stack 1', [1]), ('Stack 2', [2])])
        self.assertTrue(entry['stacks_on_recast'])
        self.assertEqual(entry['casting']['ap'], [2])
        self.assertEqual(entry['casting']['ap_growth'], [1])

    def test_a_growth_off_its_shape_stops_the_reader(self):
        cases = {
            'card lost the damage sentence': _harassing(text='Le coût en PA du sort augmente '
                                                             'à chaque lancer.'),
            'card lost the cost sentence': _harassing(text='Occasionne des dommages Terre qui '
                                                           'augmentent pour chaque lancer durant le '
                                                           'même tour.'),
            'critical step differs': _harassing(crit_damage={'value': 20}),
            'damage boost lasts two turns': _harassing(damage={'duration': 2}),
            'damage boost waits a turn': _harassing(damage={'delay': 1}),
            'damage boost on the target': _harassing(damage={'targetMask': 'A'}),
            'damage boost on another trigger': _harassing(damage={'triggers': 'CC'}),
            'damage boost is shown only': _harassing(damage={'isPreview': True}),
            'damage boost is drawn': _harassing(damage={'random': 50}),
            'damage boost before the hit': _harassing(before_the_hit=True),
            'cost boost lasts two turns': _harassing(cost={'duration': 2}),
            'cost boost of zero': _harassing(cost={'value': 0}),
            'one cast a turn': _harassing(maxCastPerTurn=1),
            'stack cap below the casts': _harassing(maxStack=1),
        }
        for case, record in cases.items():
            with self.subTest(case=case):
                with self.assertRaises(SystemExit):
                    _decode(record)

    def test_an_unlisted_spell_raising_its_next_casts_stops_the_reader_unless_it_cannot_recast(self):
        reader = _reader()
        with mock.patch.object(reader, 'DAMAGE_GROWS_EACH_CAST', {}):
            with self.assertRaises(SystemExit):
                _decode(_harassing())
            with mock.patch.object(reader, 'AP_COST_GROWS_EACH_CAST', {}):
                entry = _decode(_harassing(maxCastPerTurn=1))
                self.assertNotIn('stacks_on_recast', entry)
                self.assertNotIn('ap_growth', entry['casting'])
                entry = _decode(_harassing(damage={'isPreview': True}, cost={'isPreview': True}))
                self.assertEqual(entry['non_crit_ranges'], [['6-10']])

    def test_a_boost_on_the_next_turns_gets_one_copy_per_stack_it_can_reach(self):
        entry = _decode(_anger())
        self.assertEqual(entry['non_crit_ranges'], [['14-18'], ['34-38'], ['54-58']])
        self.assertEqual(entry['crit_ranges'], [['19-23'], ['39-43'], ['59-63']])
        self.assertEqual(entry['conditional'], {1: 'later_cast_1_turn', 2: 'cast_after_two_casts'})
        self.assertFalse(entry.get('stacks_on_recast'))

    def test_a_next_turns_boost_off_its_shape_stops_the_reader(self):
        cases = {
            'card lost the sentence': _anger(text='Occasionne des dommages Terre.'),
            'boost lands this turn': _anger(boost={'delay': 0}),
            'boost lasts two turns': _anger(boost={'duration': 2}),
            'boost stacks three times': _anger(child_rank={'maxStack': 3}),
            'boost on the target': _anger(boost={'targetMask': 'A'}),
            'boost is shown only': _anger(boost={'isPreview': True}),
            'boost of zero': _anger(boost={'value': 0}),
            'boost raises another spell': _anger(boost={'diceNum': 1}),
            'boost has a critical row': _anger(child_rank={'criticalEffect': [_row(293, IOPS_ANGER, 30)]}),
            'spell casts twice a turn': _anger(maxCastPerTurn=2),
            'spell raises itself too': _anger(parent_rows=[_row(293, IOPS_ANGER, 20, delay=1)]),
        }
        for case, record in cases.items():
            with self.subTest(case=case):
                with self.assertRaises(SystemExit):
                    _decode(record)

    def test_every_copy_the_reader_holds_is_armed_by_its_own_cast_and_labelled(self):
        from chardata.spells_view import _CONDITIONAL_LABELS
        for trigger in _reader().NEXT_TURNS_COPIES:
            with self.subTest(trigger=trigger):
                self.assertIn(trigger, ARMED_BY_ITS_OWN_CAST)
                self.assertIn(trigger, _CONDITIONAL_LABELS)


class HarassingArrowCostsOneMoreApEachCastTests(SimpleTestCase):

    def test_each_cast_lands_the_next_stack_raised_by_fifteen(self):
        for version in VERSIONS:
            spell = _spell(version, HARASSING_ARROW)
            digest = spell.get_effects_digest()
            with self.subTest(version=version):
                self.assertTrue(spell.stacks_on_recast)
                self.assertEqual([label for label, _rows in spell.aggregates],
                                 ['Stack 0', 'Stack 1', 'Stack 2'])
                self.assertEqual(spell.casting['ap_growth'], [1] * len(spell.level_req))
                for ranks in (digest.non_crit_dams, digest.crit_dams):
                    for rank in ranks:
                        self.assertEqual([(row.min_dam - rank[0].min_dam, row.max_dam - rank[0].max_dam)
                                          for row in rank], [(0, 0), (15, 15), (30, 30)])

    def test_the_casts_cost_two_then_three_then_four_ap(self):
        for version in VERSIONS:
            _in_version(self, version)
            cast = _cast(_spell(version, HARASSING_ARROW))
            with self.subTest(version=version):
                self.assertEqual([cast_cost(cast, earlier) for earlier in range(3)], [2, 3, 4])

    def test_eight_ap_fit_two_casts_and_nine_fit_three_each_dealing_more(self):
        for version in VERSIONS:
            _in_version(self, version)
            cast = _cast(_spell(version, HARASSING_ARROW))
            for ap, casts in ((4, 1), (5, 2), (8, 2), (9, 3), (12, 3)):
                total, order = best_turn(dict(_STATS, ap=ap), [cast], ap, game_version=version,
                                         caster_level=200)
                with self.subTest(version=version, ap=ap):
                    self.assertEqual(len(order), casts)
                    damages = [damage for _name, damage in order]
                    self.assertEqual(damages, sorted(set(damages)))
                    self.assertAlmostEqual(total, sum(damages))

    def test_the_bounded_and_the_exhaustive_search_pay_the_same_grown_costs(self):
        from chardata.spell_combo import _search_best_turn
        for version in VERSIONS:
            _in_version(self, version)
            cast = _cast(_spell(version, HARASSING_ARROW))
            for ap, casts in ((8, 2), (9, 3)):
                for ceiling_scores in (4096, -1):
                    with mock.patch('chardata.spell_combo.CEILING_SCORES', ceiling_scores), \
                            self.subTest(version=version, ap=ap, ceiling_scores=ceiling_scores):
                        _total, order = _search_best_turn(dict(_STATS, ap=ap), [cast], ap,
                                                          game_version=version, caster_level=200)
                        self.assertEqual(len(order), casts)

    def test_a_growing_spell_with_no_cast_limit_keeps_paying_more_past_its_last_stack(self):
        from chardata.spell_combo import _search_best_turn
        for version in VERSIONS:
            _in_version(self, version)
            cast = _cast(_spell(version, HARASSING_ARROW))
            cast.per_turn = cast.limit = None
            for ap, casts in ((13, 3), (14, 4)):
                for ceiling_scores in (4096, -1):
                    with mock.patch('chardata.spell_combo.CEILING_SCORES', ceiling_scores), \
                            self.subTest(version=version, ap=ap, ceiling_scores=ceiling_scores):
                        _total, order = _search_best_turn(dict(_STATS, ap=ap), [cast], ap,
                                                          game_version=version, caster_level=200)
                        self.assertEqual(len(order), casts)

    def _panel(self, version, ap):
        from chardata import spells_view
        _in_version(self, version)
        casts = [_cast(_spell(version, HARASSING_ARROW))]
        char = mock.Mock(char_class='Cra', level=200)
        solution = mock.Mock(item_list=[])
        solution.get_stats_total.return_value = dict(_STATS, ap=ap)
        # The AP cap is lifted so the turn can pay for a fourth cast
        with mock.patch('chardata.spell_combo.castable_spells', return_value=casts), \
                mock.patch('chardata.spell_combo.combat_ap', side_effect=lambda total, *_args, **_kw: total), \
                mock.patch('chardata.spell_combo.buffs_in_force', return_value={}), \
                mock.patch('chardata.spell_combo.stacks_in_force', return_value={}), \
                mock.patch('chardata.temporix_mode.solution_uses_temporix', return_value=False), \
                mock.patch.object(spells_view, 'worn_spell_modifiers', return_value={}), \
                mock.patch.object(spells_view, '_weapon_castable', return_value=None):
            return spells_view._best_combo(char, solution, version, note_without_buffs=False)

    def test_the_panel_shows_each_cast_at_its_grown_cost_and_sums_them(self):
        for version in VERSIONS:
            combo = self._panel(version, 12)
            with self.subTest(version=version):
                self.assertEqual([cast['ap'] for cast in combo['casts']], [2, 3, 4])
                self.assertEqual(combo['ap_used'], 9)

    def test_the_cast_limit_is_marked_only_when_the_ap_left_pays_one_more_grown_cast(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                self.assertEqual([cast['limit_mark'] for cast in self._panel(version, 13)['casts']],
                                 ['', '', ''])
                self.assertEqual([cast['limit_mark'] for cast in self._panel(version, 14)['casts']],
                                 ['', '', '3/3'])


class IopsAngerHoldsItsStackedBoostsApartTests(SimpleTestCase):

    def test_each_stacked_boost_is_a_copy_of_the_hit_raised_by_twenty_more(self):
        for version in VERSIONS:
            spell = _spell(version, IOPS_ANGER)
            digest = spell.get_effects_digest()
            with self.subTest(version=version):
                self.assertEqual(spell.conditional, {1: 'later_cast_1_turn', 2: 'cast_after_two_casts'})
                self.assertFalse(getattr(spell, 'stacks_on_recast', False))
                for ranks in (digest.non_crit_dams, digest.crit_dams):
                    for rank in ranks:
                        self.assertEqual([(row.min_dam - rank[0].min_dam, row.max_dam - rank[0].max_dam)
                                          for row in rank], [(0, 0), (20, 20), (40, 40)])

    def test_the_turn_counts_the_base_hit_and_each_boosted_cast_shows_apart(self):
        for version in VERSIONS:
            _in_version(self, version)
            spell = _spell(version, IOPS_ANGER)
            cast = _cast(spell)
            total, order = best_turn(dict(_STATS), [cast], 12, game_version=version, caster_level=200)
            rank = spell.get_effects_digest().non_crit_dams[-1]
            extras = conditional_extras(dict(_STATS), [cast], order, game_version=version,
                                        caster_level=200)
            with self.subTest(version=version):
                self.assertEqual([name for name, _damage in order], [cast.name])
                self.assertLess(total, min(damage for _name, _trigger, damage in extras))
                self.assertEqual([trigger for _name, trigger, _damage in extras],
                                 ['later_cast_1_turn', 'cast_after_two_casts'])
                for (_name, _trigger, damage), row in zip(extras, rank[1:]):
                    self.assertAlmostEqual(damage, 3.0 * (row.min_dam + row.max_dam) / 2.0)

    def test_the_stacked_boost_label_reads_in_each_language(self):
        from chardata.spells_view import _CONDITIONAL_LABELS
        for language, text in LABEL.items():
            with translation.override(language), self.subTest(language=language):
                self.assertEqual(str(_CONDITIONAL_LABELS['cast_after_two_casts']), text)

    def test_the_panel_names_both_boosted_casts_outside_the_total(self):
        from chardata import spells_view
        _in_version(self, 'touch')
        casts = [_cast(_spell('touch', IOPS_ANGER))]
        turn, _order = best_turn(dict(_STATS), casts, 12, game_version='touch', caster_level=200)
        char = mock.Mock(char_class='Iop', level=200)
        solution = mock.Mock(item_list=[])
        solution.get_stats_total.return_value = dict(_STATS)
        with mock.patch('chardata.spell_combo.castable_spells', return_value=casts), \
                mock.patch('chardata.spell_combo.buffs_in_force', return_value={}), \
                mock.patch('chardata.spell_combo.stacks_in_force', return_value={}), \
                mock.patch('chardata.temporix_mode.solution_uses_temporix', return_value=False), \
                mock.patch.object(spells_view, 'worn_spell_modifiers', return_value={}), \
                mock.patch.object(spells_view, '_weapon_castable', return_value=None):
            for language in ('en', 'fr'):
                with translation.override(language), self.subTest(language=language):
                    combo = spells_view._best_combo(char, solution, 'touch', note_without_buffs=False)
                    self.assertEqual(combo['total'], int(round(turn)))
                    self.assertEqual(sorted(entry['label'] for entry in combo['conditional']
                                            if entry['damage']),
                                     sorted([FOLLOWING_TURN[language], LABEL[language]]))

class TheDefaultElementsFingerprintSeesTheCostGrowthTests(SimpleTestCase):

    def test_a_spell_whose_cost_grows_changes_the_class_fingerprint(self):
        import copy
        from chardata.management.commands import store_default_elements as generator
        _in_version(self, 'touchbeta')
        gear = generator.gear_line('touchbeta', 200)
        spells = generator.castable_spells('Cra', 200, 'touchbeta')
        grown = copy.deepcopy(spells)
        target = next(spell for spell in grown if getattr(spell, 'cost_growth', 0))
        target.cost_growth += 1
        digests = []
        for casts in (spells, grown):
            with mock.patch.object(generator, 'castable_spells', return_value=casts):
                digests.append(generator.inputs_fingerprint('touchbeta', 'Cra', 200, gear))
        self.assertNotEqual(digests[0], digests[1])

