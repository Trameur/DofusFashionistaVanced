# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A Touch spell that needs, forbids, gives or takes a caster state is only cast in a turn where the game allows it."""
import itertools

from django.test import SimpleTestCase

from chardata.spell_buffs import get_damage_spells_for_version
from chardata.spell_combo import best_turn, castable_spells

VERSIONS = ('touch', 'touchbeta')
DRUNK, GLYPH_CAST, STATE_7, STATE_781 = 1, 208, 7, 781
ABSINTHE, HOOCH, TIPPLE, PANDATAK = 7029, 7017, 7051, 7039
FECA_GLYPHS = (6149, 4708, 4706)
MUMMIFICATION, PENDULUM = 7983, 7373
CLASSES_WITH_STATES = ('Feca', 'Pandawa', 'Xelor')
ELEMENT_STATS = ('str', 'int', 'cha', 'agi')

_STATS = {'str': 100, 'int': 100, 'cha': 100, 'agi': 100, 'pow': 0, 'dam': 0,
          'cridam': 0, 'heals': 0, 'perspedam': 0, 'perweadam': 0,
          'permedam': 0, 'perrandam': 0, 'earthdam': 0, 'firedam': 0,
          'waterdam': 0, 'airdam': 0, 'neutdam': 0, 'ch': 0, 'final': 0,
          'negfinal': 0, 'pshdam': 0, 'ap': 12}


def _reader():
    from chardata.tests import itemscraper_module
    return itemscraper_module('get_spells_touch')


def _state_row(effect_id, state, mask='C', **extra):
    row = {'effectId': effect_id, 'diceNum': 0, 'diceSide': 0, 'value': state, 'targetMask': mask,
           'triggers': 'I', 'delay': 0, 'duration': -1 if effect_id == 950 else 0, 'random': 0,
           'rawZone': 'P', 'isPreview': False}
    row.update(extra)
    return row


def _hit():
    return {'effectId': 97, 'diceNum': 10, 'diceSide': 14, 'value': 0, 'targetMask': 'a,A',
            'triggers': 'I', 'delay': 0, 'duration': 0, 'random': 0, 'rawZone': 'P',
            'isPreview': False}


def _class(*ranks, extra_spells=None):
    """(entries, raw spells, spells, spell levels) of one spell per rank dict."""
    entries, raws, spells, levels = [], [], {}, {}
    for number, rank in enumerate(ranks, 1):
        spell_id = 4200 + number
        level = {'effects': [_hit()] + rank.get('rows', []),
                 'criticalEffect': [_hit()] + rank.get('crit_rows', rank.get('rows', [])),
                 'statesRequired': rank.get('needs', []),
                 'statesForbidden': rank.get('forbids', [])}
        levels[str(spell_id * 10)] = level
        raw = {'id': spell_id, 'spellLevels': [spell_id * 10]}
        spells[str(spell_id)] = raw
        raws.append(raw)
        entries.append({'spell_id': spell_id})
    for spell_id, level in (extra_spells or {}).items():
        levels[str(spell_id * 10)] = level
        spells[str(spell_id)] = {'id': spell_id, 'spellLevels': [spell_id * 10]}
    _reader().add_caster_states(entries, raws, spells, levels)
    return entries


def _spell(version, spell_id):
    return next(spell for spells in get_damage_spells_for_version(version).values()
                for spell in spells if spell.spell_id == spell_id)


def _in_version(test, version):
    from fashionistapulp.structure import set_current_game_version
    test.addCleanup(set_current_game_version, 'dofus3')
    set_current_game_version(version)


def _legal_from_some_start(order, by_name):
    """True when some starting set of the needed states lets the game cast the order as listed."""
    casts = [by_name[name] for name, _damage in order]
    wanted = sorted(set().union(*(cast.needs_states for cast in casts)) if casts else ())
    for size in range(len(wanted) + 1):
        for start in itertools.combinations(wanted, size):
            held = set(start)
            for cast in casts:
                if not cast.needs_states <= held or cast.forbids_states & held:
                    break
                held = (held - cast.takes_states) | cast.gives_states
            else:
                return True
    return False


class TheTouchReaderNamesTheCasterStatesOfASpellTests(SimpleTestCase):

    def test_a_state_one_spell_gives_and_another_needs_is_carried_on_both(self):
        giver, taker, user = _class(
            {'rows': [_state_row(950, 5, mask='C,e5')], 'forbids': [5]},
            {'rows': [_state_row(951, 5)], 'needs': [5]},
            {'needs': [5]})
        self.assertEqual(giver['caster_states'], {'forbids': [[5]], 'gives': [[5]]})
        self.assertEqual(taker['caster_states'], {'needs': [[5]], 'takes': [[5]]})
        self.assertEqual(user['caster_states'], {'needs': [[5]]})

    def test_a_forbidden_state_no_spell_of_the_class_moves_is_left_out(self):
        giver, plain = _class({'rows': [_state_row(950, 5, mask='C,e5')], 'forbids': [3, 5]},
                              {'forbids': [3]})
        self.assertEqual(giver['caster_states'], {'forbids': [[5]], 'gives': [[5]]})
        self.assertNotIn('caster_states', plain)

    def test_a_needed_state_no_spell_of_the_class_gives_stops_the_reader(self):
        with self.assertRaises(SystemExit):
            _class({'needs': [5]})

    def test_a_state_put_on_at_turn_begin_stops_the_reader(self):
        with self.assertRaises(SystemExit):
            _class({'rows': [_state_row(950, 5, triggers='TB')], 'forbids': [5]}, {'needs': [5]})

    def test_a_state_put_on_by_the_critical_hit_only_stops_the_reader(self):
        with self.assertRaises(SystemExit):
            _class({'rows': [], 'crit_rows': [_state_row(950, 5)], 'forbids': [5]},
                   {'needs': [5]})

    def test_a_spell_cast_by_the_rank_that_moves_the_state_stops_the_reader(self):
        child = {'effects': [_state_row(951, 5)], 'criticalEffect': []}
        cast = {'effectId': 1160, 'diceNum': 4300, 'diceSide': 1, 'value': 0, 'targetMask': 'C',
                'triggers': 'I', 'delay': 0, 'duration': 0, 'random': 0, 'rawZone': 'P',
                'isPreview': False}
        with self.assertRaises(SystemExit):
            _class({'rows': [_state_row(950, 5)], 'forbids': [5]},
                   {'rows': [cast], 'needs': [5]}, extra_spells={4300: child})


class TheTouchTablesCarryTheCasterStatesTests(SimpleTestCase):

    def test_the_pandawa_drunk_chain_and_the_one_glyph_a_turn_reach_the_tables(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                absinthe = _spell(version, ABSINTHE).caster_states
                self.assertEqual(set(absinthe), {'needs', 'takes'})
                self.assertTrue(all(states == [DRUNK] for states in absinthe['needs']))
                hooch = _spell(version, HOOCH).caster_states
                self.assertTrue(all(states == [DRUNK] for states in hooch['gives']))
                self.assertTrue(all(states == [DRUNK] for states in hooch['forbids']))
                self.assertEqual(set(_spell(version, PANDATAK).caster_states), {'forbids'})
                for glyph in FECA_GLYPHS:
                    states = _spell(version, glyph).caster_states
                    self.assertTrue(all(found == [GLYPH_CAST] for found in states['gives']))
                    self.assertTrue(all(found == [GLYPH_CAST] for found in states['forbids']))
                self.assertEqual(_spell(version, MUMMIFICATION).caster_states['gives'],
                                 [[STATE_7, STATE_781]] * 6)
                self.assertTrue(all(found == [STATE_7, STATE_781] for found in
                                    _spell(version, PENDULUM).caster_states['forbids']))

    def test_only_the_classes_whose_spells_move_a_caster_state_carry_one(self):
        for version in VERSIONS:
            for char_class, spells in get_damage_spells_for_version(version).items():
                with self.subTest(version=version, char_class=char_class):
                    self.assertEqual(any(spell.caster_states for spell in spells),
                                     char_class in CLASSES_WITH_STATES)


class TheBestTurnObeysTheCasterStatesTests(SimpleTestCase):

    def test_every_best_turn_of_the_classes_with_states_is_one_the_game_allows(self):
        for version in VERSIONS:
            _in_version(self, version)
            for char_class in CLASSES_WITH_STATES:
                casts = castable_spells(char_class, 200, version)
                by_name = {cast.name: cast for cast in casts}
                for element, ap in itertools.product(ELEMENT_STATS, range(6, 13)):
                    stats = dict(_STATS, ap=ap, **{element: 800})
                    _total, order = best_turn(stats, casts, ap, game_version=version,
                                              caster_level=200)
                    with self.subTest(version=version, char_class=char_class, element=element,
                                      ap=ap):
                        self.assertTrue(_legal_from_some_start(order, by_name), order)

    def test_a_spell_that_takes_the_state_it_needs_lands_once_a_turn(self):
        for version in VERSIONS:
            _in_version(self, version)
            absinthe = next(cast for cast in castable_spells('Pandawa', 200, version)
                            if cast.spell_id == ABSINTHE)
            once, _order = best_turn(dict(_STATS), [absinthe], absinthe.cost,
                                     game_version=version, caster_level=200)
            twice, order = best_turn(dict(_STATS), [absinthe], 2 * absinthe.cost,
                                     game_version=version, caster_level=200)
            with self.subTest(version=version):
                self.assertGreater(once, 0)
                self.assertGreater(absinthe.limit, 1)
                self.assertEqual(len(order), 1)
                self.assertAlmostEqual(twice, once)

    def test_a_spell_that_needs_a_state_it_keeps_lands_every_cast_the_game_allows(self):
        for version in VERSIONS:
            _in_version(self, version)
            tipple = next(cast for cast in castable_spells('Pandawa', 200, version)
                          if cast.spell_id == TIPPLE)
            _total, order = best_turn(dict(_STATS), [tipple], 12, game_version=version,
                                      caster_level=200)
            with self.subTest(version=version):
                self.assertEqual(len(order), min(tipple.limit, 12 // tipple.cost))

    def test_two_glyphs_of_one_turn_never_land_together(self):
        for version in VERSIONS:
            _in_version(self, version)
            glyphs = [cast for cast in castable_spells('Feca', 200, version)
                      if cast.spell_id in FECA_GLYPHS]
            _total, order = best_turn(dict(_STATS), glyphs, 12, game_version=version,
                                      caster_level=200)
            with self.subTest(version=version):
                self.assertEqual(len(glyphs), len(FECA_GLYPHS))
                self.assertEqual(len(order), 1)
