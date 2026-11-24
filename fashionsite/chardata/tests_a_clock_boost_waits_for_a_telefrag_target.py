# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Clock's boost lands only from a cast on a Telefrag target: its boosted hit shows apart, with no ladder."""
from django.test import SimpleTestCase
from django.utils import translation

from chardata.spell_buffs import get_damage_spells_for_version
from chardata.spell_combo import Castable, best_turn, conditional_extras

CLOCK = 13256
CHILD = 19721
VERSIONS = ('dofus3', 'beta')
HELD = 'on_a_telefrag_target'
BOOSTS = [12, 18, 24]
QUOTE = ("Les dommages du sort sont augmentés avant d'appliquer les effets si la cible est "
         "téléfrag.")
LABEL = {'en': "only on a target that has Telefrag, then on the spell's next casts for 3 turns",
         'fr': 'seulement sur une cible Téléfrag, puis sur les lancers suivants du sort pendant 3 tours'}

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


def _spell(version):
    return next(spell for spells in get_damage_spells_for_version(version).values()
                for spell in spells if spell.spell_id == CLOCK)


def _cast(spell):
    return Castable(spell, len(spell.level_req) - 1, crit=False)


def _boost(value=12, duration=3, flags=0, mask='C', delay=0):
    return {'effect_id': 293, 'triggers': 'I', 'delay': delay, 'duration': duration,
            'target_mask': mask, 'value': value, 'dice': {'min': CLOCK}, 'flags': flags}


def _effects(low, cast_mask='a,E244', cast_after=False, own_flags=16, own_rows=1, casts=1, **own):
    casting = [{'effect_id': 1160, 'triggers': 'I', 'delay': 0, 'duration': 0, 'target_mask': cast_mask,
                'dice': {'min': CHILD, 'max': 1}}] * casts
    hit = [{'effect_id': 97, 'triggers': 'I', 'delay': 0, 'duration': 0, 'target_mask': 'A',
            'dice': {'min': low, 'max': low + 2}, 'effect_metadata': {'category': 2}}]
    rows = hit + casting if cast_after else casting + hit
    return rows + [_boost(flags=own_flags, **own)] * own_rows


def _lookup(**child):
    return {CHILD: {'ankama_id': CHILD, 'levels': [{'grade': 1, 'effects': [_boost(**child)]}]}}


def _row(low):
    return {'element': 'EARTH', 'ranges': ['%d-%d' % (low, low + 2)], 'situation': 'A|0,1,0', 'triggers': 'I'}


def _raw(spell_id=CLOCK, text=QUOTE, per_stack=(12,), max_stack=1, normal_rows=1, critical=None, **shape):
    """Clock's rows as the scraper hands them, with one part of their shape changed."""
    damage = {'normal': [_row(14)] * normal_rows, 'critical': [_row(17)] * normal_rows}
    if per_stack is not None:
        damage['stackable_damage'] = {'per_stack': list(per_stack), 'max_stacks': [4]}
    return {'ankama_id': spell_id, 'name_en': 'Probe', 'level_requirements': [1],
            'description_fr': 'Occasionne des dommages Terre. ' + text,
            'levels': [{'grade': 1, 'max_stack': max_stack, 'max_cast_per_turn': 3,
                        'effects': _effects(14, **shape),
                        'critical_effects': _effects(17, **dict(shape, **(critical or {})))}],
            'damage_templates': damage}


LOOKUP = _lookup()


class TheGeneratorHoldsTheTelefragBoostTests(SimpleTestCase):

    def test_the_rows_get_one_boosted_copy_held_for_a_telefrag_target_and_no_ladder(self):
        entry = _generator().convert_spell(_raw(), spell_lookup=LOOKUP)
        self.assertEqual(entry.conditional, {1: HELD})
        self.assertEqual(entry.non_crit_ranges, [['14-16'], ['26-28']])
        self.assertEqual(entry.crit_ranges, [['17-19'], ['29-31']])
        self.assertFalse([label for label, _rows in entry.aggregates or [] if label])
        self.assertIsNone(entry.stacks)

    def test_the_other_telefrag_state_gates_the_cast_as_well(self):
        entry = _generator().convert_spell(_raw(cast_mask='A,E251'), spell_lookup=LOOKUP)
        self.assertEqual(entry.conditional, {1: HELD})

    def test_a_boost_off_its_shape_stops_the_generator(self):
        cases = {
            'card lost the sentence': (_raw(text='Occasionne des dommages.'), LOOKUP),
            'own boost lands for real': (_raw(own_flags=0), LOOKUP),
            'two own boosts': (_raw(own_rows=2), LOOKUP),
            'cast on every target': (_raw(cast_mask='a'), LOOKUP),
            'cast forbids a state': (_raw(cast_mask='a,E244,e8'), LOOKUP),
            'cast needs two states': (_raw(cast_mask='a,E244,E251'), LOOKUP),
            'cast after the hit': (_raw(cast_after=True), LOOKUP),
            'no cast raises the spell': (_raw(), {}),
            'child boost differs': (_raw(), _lookup(value=13)),
            'child boost is shown only': (_raw(), _lookup(flags=16)),
            'child boost lasts two turns': (_raw(), _lookup(duration=2)),
            'child boost on every target': (_raw(), _lookup(mask='a')),
            'own boost lasts two turns': (_raw(duration=2), _lookup(duration=2)),
            'the boost stacks': (_raw(max_stack=2), LOOKUP),
            'critical boost differs': (_raw(critical={'value': 13}), LOOKUP),
            'stack step differs from the boost': (_raw(per_stack=(13,)), LOOKUP),
            'two hit rows': (_raw(normal_rows=2), LOOKUP),
        }
        for case, (raw, lookup) in cases.items():
            with self.subTest(case=case):
                with self.assertRaises(SystemExit):
                    _generator().convert_spell(raw, spell_lookup=lookup)

    def test_an_unlisted_spell_of_that_shape_keeps_its_rows(self):
        entry = _generator().convert_spell(_raw(spell_id=1), spell_lookup=LOOKUP)
        self.assertFalse(entry.conditional)


class ClockHoldsItsTelefragHitTests(SimpleTestCase):

    def test_the_boosted_hit_is_one_held_copy_and_no_stack_ladder_is_left(self):
        for version in VERSIONS:
            spell = _spell(version)
            digest = spell.get_effects_digest()
            with self.subTest(version=version):
                self.assertEqual(spell.conditional, {1: HELD})
                self.assertFalse([label for label, _rows in spell.aggregates or [] if label])
                self.assertIn(spell.stacks, (None, 1))
                for ranks in (digest.non_crit_dams, digest.crit_dams):
                    self.assertEqual(len(ranks), len(BOOSTS))
                    for grade, rank in enumerate(ranks):
                        self.assertEqual(len(rank), 2)
                        self.assertEqual((rank[1].min_dam, rank[1].max_dam),
                                         (rank[0].min_dam + BOOSTS[grade], rank[0].max_dam + BOOSTS[grade]))

    def test_the_turn_lands_the_base_hit_and_no_cast_arms_the_boosted_one(self):
        for version in VERSIONS:
            _in_version(self, version)
            spell = _spell(version)
            cast = _cast(spell)
            landed = {id(effect) for alternative in cast.plain_alternatives + cast.crit_alternatives
                      for effect in alternative}
            _total, order = best_turn(dict(_STATS), [cast], _STATS['ap'], game_version=version,
                                      caster_level=200)
            with self.subTest(version=version):
                self.assertTrue(landed)
                self.assertNotIn(id(cast.effects[1]), landed)
                self.assertEqual({name for name, _damage in order}, {cast.name})
                self.assertEqual(conditional_extras(dict(_STATS), [cast], order, game_version=version,
                                                    caster_level=200), [])

    def test_the_spell_page_labels_the_boosted_hit_in_each_language(self):
        from chardata import spells_view
        _in_version(self, 'dofus3')
        spell = _spell('dofus3')
        for language in ('en', 'fr'):
            with translation.override(language), self.subTest(language=language):
                digest = spells_view._create_spell_web_digest(spell, 'dofus3', char_level=200)
                self.assertEqual(digest['conditional'], {'1': LABEL[language]})
                self.assertFalse([group for group in digest['aggregates'] or []
                                  if 'Stack' in str(group)])
