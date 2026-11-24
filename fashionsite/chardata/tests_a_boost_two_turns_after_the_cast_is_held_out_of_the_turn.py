# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A spell boosting its own cast two turns later shows the boosted hit apart, never in the turn."""
from unittest import mock

from django.test import SimpleTestCase
from django.utils import translation

from chardata.spell_buffs import get_damage_spells_for_version
from chardata.spell_combo import Castable, best_turn, conditional_extras

SECRET_WORD = 25882
VERSIONS = ('dofus3', 'beta')
HELD = 'cast_two_turns_later'
BOOST = 30
QUOTE = ("Les soins et les dommages sont augmentés dans 2 tours si le sort "
         "n'est pas relancé au tour suivant.")
LABEL = {'en': 'on its cast 2 turns later, and only if the spell is not cast again on '
               'the following turn',
         'fr': "lors de son lancer 2 tours plus tard, et seulement si le sort n'est pas "
               "relancé au tour suivant"}

_STATS = {'str': 100, 'int': 100, 'cha': 100, 'agi': 300, 'pow': 0, 'dam': 0,
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


def _spell(version):
    return next(spell for spells in get_damage_spells_for_version(version).values()
                for spell in spells if spell.spell_id == SECRET_WORD)


def _cast(spell):
    return Castable(spell, len(spell.level_req) - 1, crit=False)


def _effect(effect_id, **fields):
    effect = {'effect_id': effect_id, 'triggers': 'I', 'delay': 0, 'duration': 0,
              'target_mask': 'C'}
    effect.update(fields)
    return effect


def _effects(low, spell_id, boost=BOOST, delay=2, duration=1, boosted=None, removed=None,
             removal_first=False, removal=True, heal_boost=None, heal_boost_rows=1, boost_mask='C'):
    hits = [_effect(2999, target_mask='a', dice={'min': low, 'max': low + 4},
                    effect_metadata={'category': 2}),
            _effect(98, target_mask='A', dice={'min': low, 'max': low + 4},
                    effect_metadata={'category': 2})]
    removals = [_effect(406, value=removed or spell_id)] if removal else []
    boosts = [_effect(293, value=boost, dice={'min': boosted or spell_id}, delay=delay,
                      duration=duration, target_mask=boost_mask)]
    boosts += [_effect(2935, value=boost if heal_boost is None else heal_boost,
                       dice={'min': boosted or spell_id}, delay=delay, duration=duration,
                       target_mask=boost_mask)
               for _ in range(heal_boost_rows)]
    return removals + hits + boosts if removal_first else hits + removals + boosts


def _row(heals, low, mask):
    row = {'element': 'AIR', 'ranges': ['%d-%d' % (low, low + 4)],
           'situation': mask + '|76,1,0', 'triggers': 'I'}
    if heals:
        row['heals'] = True
    return row


def _raw(spell_id=SECRET_WORD, text=QUOTE, per_stack=(BOOST,), critical=None, **shape):
    """Secret Word's rows as the scraper hands them, with one part of their shape changed."""
    return {'ankama_id': spell_id, 'name_en': 'Probe', 'level_requirements': [1],
            'description_fr': 'Soigne les alliés. ' + text,
            'levels': [{'grade': 1, 'effects': _effects(28, spell_id, **shape),
                        'critical_effects': _effects(34, spell_id, **dict(shape, **(critical or {})))}],
            'damage_templates': {'normal': [_row(True, 28, 'a'), _row(False, 28, 'A')],
                                 'critical': [_row(True, 34, 'a'), _row(False, 34, 'A')],
                                 'stackable_damage': {'per_stack': list(per_stack),
                                                      'max_stacks': [4]}}}


class TheGeneratorHoldsTheBoostedCastTests(SimpleTestCase):

    def test_the_rows_get_one_boosted_copy_held_for_the_cast_two_turns_later(self):
        entry = _generator().convert_spell(_raw())
        self.assertEqual(entry.conditional, {2: HELD, 3: HELD})
        self.assertEqual(entry.aggregates, [('', [0]), ('', [1]), ('', [2]), ('', [3])])
        self.assertEqual(entry.non_crit_ranges, [['28-32'], ['28-32'], ['58-62'], ['58-62']])
        self.assertEqual(entry.crit_ranges, [['34-38'], ['34-38'], ['64-68'], ['64-68']])
        self.assertIsNone(entry.stacks)

    def test_a_boost_off_its_shape_stops_the_generator(self):
        cases = {
            'card lost the sentence': _raw(text='Les soins sont augmentés.'),
            'boost waits one turn': _raw(delay=1),
            'boost lasts two turns': _raw(duration=2),
            'boost of another spell': _raw(boosted=SECRET_WORD + 1),
            'no removal on recast': _raw(removal=False),
            'removal of another spell': _raw(removed=SECRET_WORD + 1),
            'removal before the hits': _raw(removal_first=True),
            'heal boost differs from the damage boost': _raw(heal_boost=BOOST + 5),
            'no heal boost row': _raw(heal_boost_rows=0),
            'two heal boost rows': _raw(heal_boost_rows=2),
            'boost on every target': _raw(boost_mask='a'),
            'critical boost differs': _raw(critical={'boost': BOOST + 5}),
            'stack step differs from the boost': _raw(per_stack=(BOOST + 5,)),
        }
        for case, raw in cases.items():
            with self.subTest(case=case):
                with self.assertRaises(SystemExit):
                    _generator().convert_spell(raw)

    def test_an_unlisted_spell_whose_own_boost_waits_is_flagged_not_laddered(self):
        gen = _generator()
        self.assertTrue(gen.convert_spell(_raw(spell_id=1)).boost_problem)
        self.assertIsNone(gen.convert_spell(_raw(spell_id=1, delay=0)).boost_problem)
        with mock.patch.object(gen, 'BOOSTS_AFTER_A_SKIPPED_TURN', {}):
            self.assertTrue(gen.convert_spell(_raw()).boost_problem)


class SecretWordHoldsItsBoostedCastTests(SimpleTestCase):

    def test_the_boosted_heal_and_hit_are_held_in_lines_of_their_own_and_no_ladder_is_left(self):
        for version in VERSIONS:
            spell = _spell(version)
            digest = spell.get_effects_digest()
            with self.subTest(version=version):
                self.assertEqual(spell.conditional, {2: HELD, 3: HELD})
                self.assertEqual(spell.stacks, 1)
                self.assertFalse([label for label, _rows in spell.aggregates if label])
                self.assertEqual([len(set(rows) & set(spell.conditional)) in (0, len(rows))
                                  for _label, rows in spell.aggregates],
                                 [True] * len(spell.aggregates))
                for ranks in (digest.non_crit_dams, digest.crit_dams):
                    for rank in ranks:
                        self.assertEqual([(row.min_dam + BOOST, row.max_dam + BOOST)
                                          for row in rank[:2]],
                                         [(row.min_dam, row.max_dam) for row in rank[2:4]])
                        self.assertEqual([bool(getattr(row, 'heals', False))
                                          for row in rank[:4]], [True, False, True, False])

    def test_the_cast_lands_the_base_hit_and_never_the_boosted_one(self):
        for version in VERSIONS:
            _in_version(self, version)
            cast = _cast(_spell(version))
            for alternatives in (cast.plain_alternatives, cast.crit_alternatives):
                landed = {id(effect) for alternative in alternatives for effect in alternative}
                with self.subTest(version=version):
                    self.assertTrue(landed)
                    self.assertFalse(landed & {id(effect) for effect in cast.effects[2:4]})

    def test_the_boosted_hit_shows_apart_from_the_turn_and_the_heal_stays_out(self):
        for version in VERSIONS:
            _in_version(self, version)
            spell = _spell(version)
            cast = _cast(spell)
            _total, order = best_turn(dict(_STATS), [cast], cast.cost, game_version=version,
                                      caster_level=200)
            boosted = spell.get_effects_digest().non_crit_dams[-1][3]
            hit = (1 + _STATS['agi'] / 100.0) * (boosted.min_dam + boosted.max_dam) / 2.0
            with self.subTest(version=version):
                extras = conditional_extras(dict(_STATS), [cast], order,
                                            game_version=version, caster_level=200)
                self.assertEqual([(name, trigger) for name, trigger, _damage in extras],
                                 [(cast.name, HELD)])
                self.assertAlmostEqual(extras[0][2], hit)

    def test_the_panel_names_the_boosted_hit_outside_the_total_in_each_language(self):
        from chardata import spells_view
        _in_version(self, 'dofus3')
        cast = _cast(_spell('dofus3'))
        turn, _order = best_turn(dict(_STATS), [cast], cast.cost, game_version='dofus3',
                                 caster_level=200)
        char = mock.Mock(char_class='Eniripsa', level=200)
        solution = mock.Mock(item_list=[])
        solution.get_stats_total.return_value = dict(_STATS, ap=cast.cost)
        with mock.patch('chardata.spell_combo.castable_spells', return_value=[cast]), \
                mock.patch('chardata.spell_combo.buffs_in_force', return_value={}), \
                mock.patch('chardata.spell_combo.stacks_in_force', return_value={}), \
                mock.patch('chardata.temporix_mode.solution_uses_temporix', return_value=False), \
                mock.patch.object(spells_view, 'worn_spell_modifiers', return_value={}), \
                mock.patch.object(spells_view, '_weapon_castable', return_value=None):
            for language in ('en', 'fr'):
                with translation.override(language), self.subTest(language=language):
                    combo = spells_view._best_combo(char, solution, 'dofus3',
                                                    note_without_buffs=False)
                    self.assertEqual(combo['total'], int(round(turn)))
                    self.assertEqual(combo['later'], [])
                    self.assertEqual([entry['label'] for entry in combo['conditional']
                                      if entry['damage']], [LABEL[language]])
