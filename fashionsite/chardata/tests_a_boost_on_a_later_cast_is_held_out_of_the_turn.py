# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A spell boosting its own later casts shows each boosted cast apart, labelled by when it lands, never in the turn."""
from unittest import mock

from django.test import SimpleTestCase
from django.utils import translation

from chardata.spell_buffs import get_damage_spells_for_version
from chardata.spell_combo import Castable, best_turn, conditional_extras

VERSIONS = ('dofus3', 'beta')
SWORD_OF_FATE, IOPS_WRATH, ATONEMENT_ARROW, PUNITIVE_ARROW = 13111, 13124, 32438, 32456
# {spell: (class, {trigger: boost per grade})}, from the spells' own 293 rows
LIVE = {
    SWORD_OF_FATE: ('Iop', {'later_cast_2_turns': [30, 40]}),
    IOPS_WRATH: ('Iop', {'later_cast_3_turns': [110]}),
    ATONEMENT_ARROW: ('Cra', {'later_cast_2_turns': [29, 36], 'later_cast_4_turns': [29, 36]}),
    PUNITIVE_ARROW: ('Cra', {'later_cast_1_turn': [17, 24], 'later_cast_2_turns': [25, 32]}),
}
RECOVERY = "Les dommages du sort sont augmentés à la récupération du sort."
NEXT_CASTS = "Les dommages du sort sont augmentés pour les prochains lancers."
LABEL = {'en': {'later_cast_2_turns': 'on its cast 2 turns later',
                'later_cast_3_turns': 'on its cast 3 turns later'},
         'fr': {'later_cast_2_turns': 'lors de son lancer 2 tours plus tard',
                'later_cast_3_turns': 'lors de son lancer 3 tours plus tard'}}

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


def _effects(low, spell_id, boosts, mask='C', duration=1, flags=0, extra=()):
    hit = {'effect_id': 97, 'triggers': 'I', 'delay': 0, 'duration': 0, 'target_mask': 'A',
           'dice': {'min': low, 'max': low + 4}, 'effect_metadata': {'category': 2}}
    rows = [hit]
    for delay, value in boosts:
        rows.append({'effect_id': 293, 'triggers': 'I', 'delay': delay, 'duration': duration,
                     'target_mask': mask, 'value': value, 'dice': {'min': spell_id}, 'flags': flags})
    return rows + [dict(row, dice={'min': spell_id}) for row in extra]


def _row(low):
    return {'element': 'FIRE', 'ranges': ['%d-%d' % (low, low + 4)], 'situation': 'A|0,1,0', 'triggers': 'I'}


def _raw(spell_id=SWORD_OF_FATE, text=RECOVERY, boosts=((2, 30),), crit_boosts=None, interval=2,
         normal_rows=1, stackable=None, **shape):
    """A spell's rows as the scraper hands them, its own boosts landing on the casts `boosts` turns later."""
    damage = {'normal': [_row(31)] * normal_rows, 'critical': [_row(37)] * normal_rows}
    if stackable:
        damage['stackable_damage'] = stackable
    return {'ankama_id': spell_id, 'name_en': 'Probe', 'level_requirements': [1],
            'description_fr': 'Occasionne des dommages Feu. ' + text,
            'levels': [{'grade': 1, 'min_cast_interval': interval,
                        'effects': _effects(31, spell_id, boosts, **shape),
                        'critical_effects': _effects(37, spell_id, crit_boosts or boosts, **shape)}],
            'damage_templates': damage}


class TheGeneratorHoldsTheBoostedLaterCastsTests(SimpleTestCase):

    def test_one_boost_gets_one_copy_held_for_the_cast_it_waits_for(self):
        entry = _generator().convert_spell(_raw())
        self.assertEqual(entry.conditional, {1: 'later_cast_2_turns'})
        self.assertEqual(entry.non_crit_ranges, [['31-35'], ['61-65']])
        self.assertEqual(entry.crit_ranges, [['37-41'], ['67-71']])
        self.assertFalse([label for label, _rows in entry.aggregates or [] if label])
        self.assertIsNone(entry.stacks)

    def test_each_delay_gets_its_own_copy_and_label(self):
        entry = _generator().convert_spell(_raw(PUNITIVE_ARROW, 'Les dommages du sort sont augmentés '
                                                                'pour le prochain lancer.',
                                                boosts=((1, 17), (2, 25)), interval=0))
        self.assertEqual(entry.conditional, {1: 'later_cast_1_turn', 2: 'later_cast_2_turns'})
        self.assertEqual(entry.non_crit_ranges, [['31-35'], ['48-52'], ['56-60']])

    def test_a_boost_off_its_shape_stops_the_generator(self):
        cases = {
            'card lost the sentence': _raw(text='Occasionne des dommages.'),
            'boost lasts two turns': _raw(duration=2),
            'boost on every target': _raw(mask='a'),
            'boost lands before the spell is cast again': _raw(boosts=((1, 30),)),
            'boost waits five turns': _raw(boosts=((5, 30),), interval=5),
            'boost is shown only': _raw(flags=16),
            'boost of zero': _raw(boosts=((2, 0),)),
            'two boosts for one cast': _raw(boosts=((2, 30), (2, 30))),
            'critical boost differs': _raw(crit_boosts=((2, 35),)),
            'critical boost waits otherwise': _raw(ATONEMENT_ARROW, NEXT_CASTS, crit_boosts=((4, 30),)),
            'a recast removes the boost': _raw(extra=({'effect_id': 406, 'value': SWORD_OF_FATE},)),
            'the boost raises heals too': _raw(extra=({'effect_id': 2935, 'value': 30},)),
            'two hit rows': _raw(normal_rows=2),
            'a stack ladder from the scraper': _raw(stackable={'per_stack': [30], 'max_stacks': [4]}),
        }
        for case, raw in cases.items():
            with self.subTest(case=case):
                with self.assertRaises(SystemExit):
                    _generator().convert_spell(raw)

    def test_an_unlisted_spell_whose_own_boost_waits_is_flagged_and_a_shown_only_one_is_not(self):
        gen = _generator()
        self.assertTrue(gen.convert_spell(_raw(spell_id=1)).boost_problem)
        self.assertIsNone(gen.convert_spell(_raw(spell_id=1, flags=16)).boost_problem)
        with mock.patch.object(gen, 'BOOSTS_ON_A_LATER_CAST', {}):
            self.assertIsNone(gen.convert_spell(_raw(spell_id=1)).boost_problem)


class TheLiveSpellsHoldTheirBoostedCastsTests(SimpleTestCase):

    def test_each_boosted_cast_is_a_copy_of_the_hit_raised_by_its_boost_and_no_ladder_is_left(self):
        for version in VERSIONS:
            for spell_id, (_class, boosts) in LIVE.items():
                spell = _spell(version, spell_id)
                digest = spell.get_effects_digest()
                with self.subTest(version=version, spell=spell_id):
                    self.assertEqual(spell.conditional, dict(enumerate(boosts, 1)))
                    self.assertFalse([label for label, _rows in spell.aggregates or [] if label])
                    self.assertIn(spell.stacks, (None, 1))
                    for ranks in (digest.non_crit_dams, digest.crit_dams):
                        for grade, rank in enumerate(ranks):
                            self.assertEqual(len(rank), 1 + len(boosts))
                            self.assertEqual(
                                [(row.min_dam, row.max_dam) for row in rank[1:]],
                                [(rank[0].min_dam + per_grade[grade], rank[0].max_dam + per_grade[grade])
                                 for per_grade in boosts.values()])

    def test_the_cast_lands_the_base_hit_and_never_a_boosted_one(self):
        for version in VERSIONS:
            _in_version(self, version)
            for spell_id in LIVE:
                cast = _cast(_spell(version, spell_id))
                for alternatives in (cast.plain_alternatives, cast.crit_alternatives):
                    landed = {id(effect) for alternative in alternatives for effect in alternative}
                    with self.subTest(version=version, spell=spell_id):
                        self.assertTrue(landed)
                        self.assertFalse(landed & {id(effect) for effect in cast.effects[1:]})

    def test_the_turn_counts_the_base_hit_and_each_boosted_cast_shows_apart(self):
        for version in VERSIONS:
            _in_version(self, version)
            for spell_id, (_class, boosts) in LIVE.items():
                spell = _spell(version, spell_id)
                cast = _cast(spell)
                total, order = best_turn(dict(_STATS), [cast], cast.cost, game_version=version,
                                         caster_level=200)
                rank = spell.get_effects_digest().non_crit_dams[-1]
                with self.subTest(version=version, spell=spell_id):
                    self.assertEqual([name for name, _damage in order], [cast.name])
                    extras = conditional_extras(dict(_STATS), [cast], order,
                                                game_version=version, caster_level=200)
                    self.assertEqual([(name, trigger) for name, trigger, _damage in extras],
                                     [(cast.name, trigger) for trigger in boosts])
                    for (_name, _trigger, damage), row in zip(extras, rank[1:]):
                        self.assertAlmostEqual(damage, 3.0 * (row.min_dam + row.max_dam) / 2.0)
                    self.assertLess(total, min(damage for _name, _trigger, damage in extras))

    def test_the_panel_names_each_boosted_cast_outside_the_total_in_each_language(self):
        from chardata import spells_view
        _in_version(self, 'dofus3')
        casts = [_cast(_spell('dofus3', spell_id)) for spell_id in (SWORD_OF_FATE, IOPS_WRATH)]
        ap = sum(cast.cost for cast in casts)
        turn, _order = best_turn(dict(_STATS, ap=ap), casts, ap, game_version='dofus3', caster_level=200)
        char = mock.Mock(char_class='Iop', level=200)
        solution = mock.Mock(item_list=[])
        solution.get_stats_total.return_value = dict(_STATS, ap=ap)
        with mock.patch('chardata.spell_combo.castable_spells', return_value=casts), \
                mock.patch('chardata.spell_combo.buffs_in_force', return_value={}), \
                mock.patch('chardata.spell_combo.stacks_in_force', return_value={}), \
                mock.patch('chardata.temporix_mode.solution_uses_temporix', return_value=False), \
                mock.patch.object(spells_view, 'worn_spell_modifiers', return_value={}), \
                mock.patch.object(spells_view, '_weapon_castable', return_value=None):
            for language in ('en', 'fr'):
                with translation.override(language), self.subTest(language=language):
                    combo = spells_view._best_combo(char, solution, 'dofus3', note_without_buffs=False)
                    self.assertEqual(combo['total'], int(round(turn)))
                    self.assertEqual(sorted(entry['label'] for entry in combo['conditional']
                                            if entry['damage']),
                                     sorted(LABEL[language].values()))


class TheBlindGatePricesABoostedCastByItsBoostTests(SimpleTestCase):

    def _share(self, waiting):
        from types import SimpleNamespace
        from chardata import weight_tuning as tuning
        row = SimpleNamespace(min_dam=30, max_dam=30)
        copies = [(SimpleNamespace(min_dam=30 + boost, max_dam=30 + boost), trigger) for trigger, boost in waiting]
        cast = SimpleNamespace(spell_id=1, cost=3, plain_alternatives=[[row]], alternatives=[], waiting_plain=copies)
        reference = {'Cls': [{'id': 1, 'name': {'en': 'spell 1'}, 'description': {'en': 'Inflicts Fire damage.'}}]}
        with mock.patch('chardata.spell_reference.get_spell_reference', return_value=reference), \
                mock.patch('chardata.spell_buffs.get_damage_spells_for_version', return_value={'Cls': []}), \
                mock.patch('chardata.spell_combo.castable_spells', return_value=[cast]):
            return tuning.visible_damage_share('Cls', 200, 'dofus3')

    def test_a_boosted_later_cast_waits_for_its_boost_alone(self):
        self.assertAlmostEqual(30.0 / 40.0, self._share([('later_cast_2_turns', 10)]))

    def test_each_later_cast_adds_its_own_boost(self):
        self.assertAlmostEqual(30.0 / 50.0, self._share([('later_cast_1_turn', 10), ('later_cast_2_turns', 10)]))

    def test_a_telefrag_copy_waits_for_its_boost_alone(self):
        self.assertAlmostEqual(30.0 / 42.0, self._share([('on_a_telefrag_target', 12)]))

    def test_a_row_of_another_trigger_still_waits_whole(self):
        self.assertAlmostEqual(30.0 / 70.0, self._share([('trap', 10)]))
