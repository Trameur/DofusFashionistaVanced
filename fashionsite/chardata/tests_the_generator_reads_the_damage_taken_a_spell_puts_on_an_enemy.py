# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""generate_damage_spells reads a "x#1% damage sustained" row a spell puts on an enemy into DAMAGE_TAKEN."""
import json
import os

from django.test import SimpleTestCase

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TAKEN_TEXT = {'en': 'x#1% damage sustained', 'fr': 'Dommages subis x#1%'}
FIRE_TEXT = {'en': '#1{{~1~2 to }}#2 Fire damage'}

BREWING = 12816
MORTUARY_MARK = 14313
SECOND_CHANCE = 12842
DOFUS2_REPRISAL = 13088
CONJURATION = 14614
VENDETTA = 32473


def _generator():
    from chardata.tests import itemscraper_module
    return itemscraper_module('generate_damage_spells')


def _taken(percent=110, mask='A', triggers='D', etd=2, flags=79, uid=1):
    return {'effect_uid': uid, 'effect_id': 1163, 'target_mask': mask, 'triggers': triggers,
            'dice': {'min': percent, 'max': 0}, 'effect_trigger_duration': etd, 'duration': 0,
            'delay': 0, 'random': 0, 'flags': flags, 'effect_element': -1, 'value': 0,
            'effect_metadata': {'category': 1, 'description': dict(TAKEN_TEXT)}}


def _fire_hit():
    return {'effect_uid': 2, 'effect_id': 99, 'target_mask': 'a,A', 'triggers': 'I',
            'dice': {'min': 34, 'max': 38}, 'effect_trigger_duration': 0, 'duration': 0,
            'delay': 0, 'random': 0, 'flags': 79, 'effect_element': 2, 'value': 0,
            'effect_metadata': {'category': 2, 'description': dict(FIRE_TEXT)}}


def _removes(spell_id):
    return {'effect_uid': 3, 'effect_id': 406, 'target_mask': 'a,A', 'triggers': 'D',
            'dice': {'min': 0, 'max': 0}, 'effect_trigger_duration': 2, 'duration': 0,
            'delay': 0, 'random': 0, 'flags': 79, 'effect_element': -1, 'value': spell_id,
            'effect_metadata': {'category': 0, 'description': {}}}


def _places(effect_id, child_id, mask='a,A'):
    return {'effect_uid': 4, 'effect_id': effect_id, 'target_mask': mask, 'triggers': 'I',
            'dice': {'min': child_id, 'max': 1}, 'effect_trigger_duration': 0, 'duration': 0,
            'delay': 0, 'random': 0, 'flags': 79, 'effect_element': -1, 'value': 0,
            'effect_metadata': {'category': 0, 'description': {}}}


def _casts(spell_id, mask, effect_id=2960, triggers='I', flags=64):
    return {'effect_uid': 5, 'effect_id': effect_id, 'target_mask': mask, 'triggers': triggers,
            'dice': {'min': spell_id, 'max': 1}, 'effect_trigger_duration': 0, 'duration': 0,
            'delay': 0, 'random': 0, 'flags': flags, 'effect_element': -1, 'value': 999,
            'effect_metadata': {'category': 0, 'description': {'en': '#1'}}}


def _hot_iron_like(child_id, percent=107, masks=('a,A,*E3360', 'a,A,*E3589')):
    """A parent whose own row is the tooltip copy, casting child_id in each caster state."""
    effects = [_fire_hit(), _taken(107, flags=95)] + [_casts(child_id, mask) for mask in masks]
    child = _spell(child_id, [_fire_hit(), _taken(percent)])
    return _spell(40, effects, crit=15, critical_effects=list(effects)), {child_id: child}


def _spell(spell_id, effects, max_stack=1, crit=0, critical_effects=None):
    level = {'grade': 1, 'ap_cost': 2, 'max_cast_per_turn': 1, 'critical_hit_probability': crit,
             'max_stack': max_stack, 'effects': effects,
             'critical_effects': critical_effects if critical_effects is not None else []}
    return {'ankama_id': spell_id, 'name_en': 'Spell %d' % spell_id,
            'level_requirements': [200], 'levels': [level]}


def _class_spells(file_name, *spell_ids):
    path = os.path.join(REPO, 'itemscraper', file_name)
    if not os.path.exists(path):
        return None
    with open(path, encoding='utf-8') as handle:
        data = json.load(handle)
    return {spell['ankama_id']: spell for block in data.values() for spell in block['spells']
            if spell['ankama_id'] in spell_ids}


class TheRowIsReadTests(SimpleTestCase):

    def test_a_hit_then_the_row_gives_its_percent_stack_cap_and_text(self):
        entry = _generator().damage_taken_entry(_spell(10, [_fire_hit(), _taken(110)],
                                                       max_stack=2))
        self.assertEqual([110], entry['percent'])
        self.assertEqual([2], entry['stacks'])
        self.assertEqual(TAKEN_TEXT, entry['text'])
        self.assertEqual({'ap': [2], 'per_turn': [1]}, entry['casting'])
        self.assertNotIn('ends_on_hit', entry)

    def test_a_row_the_next_hit_removes_ends_on_hit(self):
        entry = _generator().damage_taken_entry(_spell(11, [_taken(115), _removes(11)]))
        self.assertEqual([True], entry['ends_on_hit'])

    def test_a_trap_carries_the_row_of_its_child_spell(self):
        child = _spell(21, [_fire_hit(), _taken(110)])
        entry = _generator().damage_taken_entry(_spell(20, [_places(400, 21)]), {21: child})
        self.assertEqual(20, entry['spell_id'])
        self.assertEqual([110], entry['percent'])
        self.assertEqual(['trap'], entry['placed'])

    def test_each_placed_thing_says_when_its_row_lands(self):
        generator = _generator()
        before = generator.BOMB_SPELLS
        self.addCleanup(setattr, generator, 'BOMB_SPELLS', before)
        generator.BOMB_SPELLS = {900: 22}
        lookup = {22: _spell(22, [_fire_hit(), _taken(110)])}
        for effect, when in ((_places(401, 22), 'turn_begin'), (_places(402, 22), 'turn_end'),
                             (_places(1165, 22), 'glyph'), (_places(1091, 22), 'aura'),
                             (_places(1008, 900), 'bomb'),
                             (_places(400, 22, mask='a,A,*E3531'), 'state')):
            with self.subTest(when=when):
                entry = generator.damage_taken_entry(_spell(23, [effect]), lookup)
                self.assertEqual([when], entry['placed'])

    def test_a_row_of_the_cast_itself_is_not_placed(self):
        entry = _generator().damage_taken_entry(_spell(24, [_fire_hit(), _taken(110)]))
        self.assertNotIn('placed', entry)

    def test_a_tooltip_copy_reads_the_row_of_the_spell_the_cast_casts(self):
        parent, lookup = _hot_iron_like(41)
        entry = _generator().damage_taken_entry(parent, lookup)
        self.assertEqual(40, entry['spell_id'])
        self.assertEqual([107], entry['percent'])
        self.assertEqual([1], entry['stacks'])
        self.assertNotIn('ends_on_hit', entry)


class TheRowIsNotReadTests(SimpleTestCase):

    def test_a_row_on_allies_only_is_not_read(self):
        self.assertIsNone(_generator().damage_taken_entry(_spell(30, [_taken(mask='a')])))

    def test_a_row_waiting_on_a_state_is_not_read(self):
        self.assertIsNone(_generator().damage_taken_entry(
            _spell(31, [_taken(mask='a,A,*E3531')])))

    def test_a_row_only_the_tooltip_shows_is_not_read(self):
        self.assertIsNone(_generator().damage_taken_entry(_spell(32, [_taken(flags=95)])))

    def test_a_row_raised_by_damage_the_caster_takes_is_not_read(self):
        self.assertIsNone(_generator().damage_taken_entry(_spell(33, [_taken(triggers='DR')])))

    def test_a_row_that_lasts_no_turn_is_not_read(self):
        self.assertIsNone(_generator().damage_taken_entry(_spell(34, [_taken(etd=0)])))

    def test_a_row_before_the_cast_own_hit_stops_the_generator(self):
        with self.assertRaises(RuntimeError):
            _generator().damage_taken_entry(_spell(35, [_taken(), _fire_hit()]))

    def test_a_critical_hit_putting_another_percent_stops_the_generator(self):
        with self.assertRaises(RuntimeError):
            _generator().damage_taken_entry(_spell(36, [_fire_hit(), _taken(110)], crit=10,
                                                   critical_effects=[_fire_hit(), _taken(120)]))

    def test_a_spell_cast_without_a_tooltip_copy_is_not_followed(self):
        child = _spell(43, [_fire_hit(), _taken(107)])
        parent = _spell(42, [_fire_hit(), _casts(43, 'a,A')])
        self.assertIsNone(_generator().damage_taken_entry(parent, {43: child}))

    def test_a_spell_cast_only_on_some_other_target_is_not_followed(self):
        parent, lookup = _hot_iron_like(44, masks=('A,R', 'a,P,F7139,*E3361'))
        self.assertIsNone(_generator().damage_taken_entry(parent, lookup))

    def test_a_spell_cast_later_is_not_followed(self):
        parent, lookup = _hot_iron_like(45, masks=())
        parent['levels'][0]['effects'].append(_casts(45, 'A', effect_id=1160, triggers='PT'))
        self.assertIsNone(_generator().damage_taken_entry(parent, lookup))

    def test_two_cast_spells_putting_the_row_stop_the_generator(self):
        parent, lookup = _hot_iron_like(47, masks=('a,A,*E3360',))
        parent['levels'][0]['effects'].append(_casts(48, 'a,A,*E3589'))
        parent['levels'][0]['critical_effects'] = list(parent['levels'][0]['effects'])
        lookup[48] = _spell(48, [_fire_hit(), _taken(107)])
        with self.assertRaises(RuntimeError):
            _generator().damage_taken_entry(parent, lookup)

    def test_a_cast_spell_putting_another_percent_than_its_tooltip_stops_the_generator(self):
        parent, lookup = _hot_iron_like(46, percent=110)
        with self.assertRaises(RuntimeError):
            _generator().damage_taken_entry(parent, lookup)


class TheClientRowsTests(SimpleTestCase):

    def test_beta_skips_brewing_mortuary_mark_and_second_chance(self):
        spells = _class_spells('transformed_class_spells_beta.json', BREWING, MORTUARY_MARK,
                               SECOND_CHANCE)
        if spells is None:
            self.skipTest('no Beta class spell file')
        self.assertEqual({BREWING, MORTUARY_MARK, SECOND_CHANCE}, set(spells))
        generator = _generator()
        for spell_id, spell in spells.items():
            with self.subTest(spell_id=spell_id):
                rows = [effect for level in spell['levels'] for effect in level['effects']
                        if effect['effect_id'] == generator.DAMAGE_TAKEN_EFFECT_ID]
                self.assertTrue(rows)
                self.assertIsNone(generator.damage_taken_entry(spell))

    def test_dofus2_skips_reprisal_and_conjuration_for_their_client_only_rows(self):
        spells = _class_spells('transformed_class_spells_dofus2.json', DOFUS2_REPRISAL,
                               CONJURATION)
        if spells is None:
            self.skipTest('no Dofus 2 class spell file')
        generator = _generator()
        try:
            client_only = generator._client_only_effects('dofus2')
        except SystemExit:
            self.skipTest('no Dofus 2 raw spell levels')
        before = generator.CLIENT_ONLY_EFFECTS
        self.addCleanup(setattr, generator, 'CLIENT_ONLY_EFFECTS', before)
        for spell_id, spell in spells.items():
            with self.subTest(spell_id=spell_id):
                generator.CLIENT_ONLY_EFFECTS = frozenset()
                self.assertIsNotNone(generator.damage_taken_entry(spell))
                generator.CLIENT_ONLY_EFFECTS = client_only
                self.assertIsNone(generator.damage_taken_entry(spell))

    def test_beta_vendetta_puts_its_row_on_the_trap_it_places(self):
        path = os.path.join(REPO, 'itemscraper', 'transformed_spells_beta.json')
        if not os.path.exists(path):
            self.skipTest('no Beta spell file')
        with open(path, encoding='utf-8') as handle:
            generator = _generator()
            lookup = generator._build_spell_lookup(json.load(handle))
        entry = generator.damage_taken_entry(lookup[VENDETTA], lookup)
        self.assertEqual([110], entry['percent'])
        self.assertEqual(['trap'], entry['placed'])


def _touch_reader():
    from chardata.tests import itemscraper_module
    return itemscraper_module('get_spells_touch')


def _touch_row(effect_id, dice, mask='a,A', triggers='D', duration=2, value=0):
    return {'effectId': effect_id, 'diceNum': dice, 'diceSide': 0, 'value': value,
            'targetMask': mask, 'triggers': triggers, 'duration': duration, 'delay': 0,
            'random': 0, 'rawZone': 'P'}


def _touch_hit():
    return _touch_row(99, 20, mask='A', triggers='I', duration=0)


def _touch_spell(spell_id, effects, critical=None, crit=5, levels=None, rank_id=None):
    rank_id = rank_id or spell_id * 10
    levels = dict(levels or {})
    levels[str(rank_id)] = {'minPlayerLevel': 200, 'apCost': 3, 'maxCastPerTurn': 1,
                            'criticalHitProbability': crit, 'maxStack': 2,
                            'effects': effects, 'criticalEffect': critical or []}
    return {'id': spell_id, 'nameId': 'Sort %d' % spell_id, 'spellLevels': [rank_id]}, levels


class TheTouchReaderTests(SimpleTestCase):

    def test_a_critical_hit_gives_its_own_percent(self):
        spell, levels = _touch_spell(60, [_touch_row(1163, 115)], [_touch_row(1163, 117)])
        entry = _touch_reader().damage_taken_entry(spell, levels, {}, {}, TAKEN_TEXT)
        self.assertEqual([115], entry['percent'])
        self.assertEqual([117], entry['percent_critical'])
        self.assertEqual([2], entry['stacks'])
        self.assertEqual({'ap': [3], 'per_turn': [1], 'crit': [5]}, entry['casting'])
        self.assertEqual(TAKEN_TEXT, entry['text'])
        self.assertNotIn('placed', entry)

    def test_a_spell_that_cannot_crit_has_one_percent(self):
        spell, levels = _touch_spell(61, [_touch_row(1163, 110)], crit=0)
        entry = _touch_reader().damage_taken_entry(spell, levels)
        self.assertEqual([110], entry['percent'])
        self.assertNotIn('percent_critical', entry)

    def test_a_row_lowering_the_damage_taken_is_not_read(self):
        spell, levels = _touch_spell(62, [_touch_row(1163, 70)], [_touch_row(1163, 65)])
        self.assertIsNone(_touch_reader().damage_taken_entry(spell, levels))

    def test_a_row_on_the_caster_or_allies_only_is_not_read(self):
        for mask in ('C', 'a', 'a,C'):
            with self.subTest(mask=mask):
                spell, levels = _touch_spell(63, [_touch_row(1163, 110, mask=mask)], crit=0)
                self.assertIsNone(_touch_reader().damage_taken_entry(spell, levels))

    def test_a_row_behind_a_life_gate_or_on_cast_is_not_read(self):
        for row in (_touch_row(1163, 105, mask='a,A,V50'), _touch_row(1163, 110, triggers='I')):
            with self.subTest(row=row):
                spell, levels = _touch_spell(64, [row], crit=0)
                self.assertIsNone(_touch_reader().damage_taken_entry(spell, levels))

    def test_a_row_the_next_hit_removes_ends_on_hit(self):
        spell, levels = _touch_spell(65, [_touch_row(1163, 115), _touch_row(406, 0, value=65)],
                                     crit=0)
        self.assertEqual([True], _touch_reader().damage_taken_entry(spell, levels)['ends_on_hit'])

    def test_a_trap_carries_the_row_of_its_child_spell(self):
        child, levels = _touch_spell(67, [_touch_hit(), _touch_row(1163, 110)], crit=0)
        trap = _touch_row(400, 67, triggers='I', duration=0)
        trap['diceSide'] = 1
        spell, levels = _touch_spell(66, [trap], crit=0, levels=levels)
        entry = _touch_reader().damage_taken_entry(spell, levels, {'66': spell, '67': child}, {})
        self.assertEqual([110], entry['percent'])
        self.assertEqual(['trap'], entry['placed'])

    def test_a_row_before_the_cast_own_hit_stops_the_reader(self):
        spell, levels = _touch_spell(68, [_touch_row(1163, 110), _touch_hit()], crit=0)
        with self.assertRaises(SystemExit):
            _touch_reader().damage_taken_entry(spell, levels)

    def test_a_critical_hit_without_the_row_stops_the_reader(self):
        spell, levels = _touch_spell(69, [_touch_row(1163, 110)], [_touch_hit()])
        with self.assertRaises(SystemExit):
            _touch_reader().damage_taken_entry(spell, levels)

    def test_a_spell_cast_with_the_row_stops_the_reader(self):
        child, levels = _touch_spell(71, [_touch_row(1163, 110)], crit=0)
        cast = _touch_row(1160, 71, triggers='I', duration=0)
        cast['diceSide'] = 1
        spell, levels = _touch_spell(70, [cast], crit=0, levels=levels)
        with self.assertRaises(SystemExit):
            _touch_reader().damage_taken_entry(spell, levels, {'70': spell, '71': child}, {})

    def test_a_tooltip_only_row_is_not_read(self):
        preview = dict(_touch_row(1163, 115), isPreview=True)
        spell, levels = _touch_spell(72, [preview], crit=0)
        self.assertIsNone(_touch_reader().damage_taken_entry(spell, levels))
        lowering = dict(_touch_row(1163, 90), isPreview=True)
        spell, levels = _touch_spell(73, [_touch_hit(), lowering], crit=0)
        self.assertIsNone(_touch_reader().damage_taken_entry(spell, levels))

    def test_a_row_lowering_what_the_hit_enemy_takes_stops_the_reader(self):
        for percent in (90, 100):
            with self.subTest(percent=percent):
                spell, levels = _touch_spell(74, [_touch_hit(), _touch_row(1163, percent)],
                                             crit=0)
                with self.assertRaises(SystemExit):
                    _touch_reader().damage_taken_entry(spell, levels)

    def test_a_row_on_a_critical_hit_only_stops_the_reader(self):
        spell, levels = _touch_spell(75, [_touch_hit()], [_touch_hit(), _touch_row(1163, 115)])
        with self.assertRaises(SystemExit):
            _touch_reader().damage_taken_entry(spell, levels)
