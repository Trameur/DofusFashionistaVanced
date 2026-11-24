# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A spell whose casts each boost its later casts until turn end shows one Stack per cast of the turn."""
from unittest import mock

from django.test import SimpleTestCase

from chardata.spell_buffs import get_damage_spells_for_version
from chardata.spell_combo import Castable, best_turn
from chardata.spell_reference import get_spell_reference

PYGMACHIA = 13146
VERSIONS = ('dofus3', 'beta')
LANGUAGES = ('en', 'fr', 'es', 'pt', 'de')
BOOST = 18
CASTS = 4
QUOTE = 'Les dommages du sort sont augmentés après chaque lancer pour le tour en cours.'
LADDER = [('Stack %d' % stack, [stack]) for stack in range(CASTS)]
PLAIN = [['9-11'], ['27-29'], ['45-47'], ['63-65']]
CRITICAL = [['12-14'], ['30-32'], ['48-50'], ['66-68']]

SAYS_IT_GROWS_THIS_TURN = {'en': 'increased after each casting for the current turn',
                           'fr': 'augmentés après chaque lancer pour le tour en cours',
                           'es': 'tras cada lanzamiento durante el turno en curso',
                           'pt': 'após cada lançamento no turno em andamento',
                           'de': 'in der aktuellen runde nach jedem wirken erhöht'}

_STATS = {'str': 100, 'int': 0, 'cha': 0, 'agi': 0, 'pow': 0, 'dam': 0, 'cridam': 0,
          'heals': 0, 'perspedam': 0, 'perweadam': 0, 'permedam': 0, 'perrandam': 0,
          'earthdam': 0, 'firedam': 0, 'waterdam': 0, 'airdam': 0, 'neutdam': 0, 'ch': 0,
          'final': 0, 'negfinal': 0, 'pshdam': 0, 'ap': 12}


def _generator():
    from chardata.tests import itemscraper_module
    return itemscraper_module('generate_damage_spells')


def _in_version(test, version):
    from fashionistapulp.structure import set_current_game_version
    test.addCleanup(set_current_game_version, 'dofus3')
    set_current_game_version(version)


def _spell(version):
    return next(spell for spells in get_damage_spells_for_version(version).values()
                for spell in spells if spell.spell_id == PYGMACHIA)


def _card(version, language):
    for entries in get_spell_reference(version).values():
        for entry in entries:
            if entry.get('id') == PYGMACHIA:
                return ((entry.get('description') or {}).get(language) or '').lower()
    return ''


def _effects(low, spell_id, value, boosted=None, boosts=1, delay=0, duration=1, mask='C',
             triggers='I', flags=79, removal=True, removed=None, removal_triggers='TE'):
    hit = {'effect_id': 97, 'triggers': 'I', 'delay': 0, 'duration': 0, 'target_mask': 'g,A',
           'dice': {'min': low, 'max': low + 2}, 'flags': 79, 'effect_metadata': {'category': 2}}
    boost = {'effect_id': 293, 'value': value, 'dice': {'min': boosted or spell_id, 'max': 0},
             'triggers': triggers, 'delay': delay, 'duration': duration, 'target_mask': mask,
             'flags': flags}
    rows = [hit] + [dict(boost) for _count in range(boosts)]
    if removal:
        rows.append({'effect_id': 406, 'value': removed or spell_id, 'dice': {'min': 0, 'max': 0},
                     'triggers': removal_triggers, 'delay': 0, 'duration': 0,
                     'target_mask': 'C', 'flags': 64})
    return rows


def _raw(spell_id=PYGMACHIA, text=QUOTE, critical=None, max_stack=-1, casts=CASTS,
         per_target=1, rows=1, stackable=None, **shape):
    """Pygmachia's rows as the scraper hands them, with one part of their shape changed."""
    own = dict(shape, value=shape.get('value', BOOST))
    crit = dict(own, **(critical or {}))
    levels = [{'grade': 1, 'max_stack': max_stack, 'max_cast_per_turn': casts,
               'max_cast_per_target': per_target,
               'effects': _effects(9, spell_id, **own),
               'critical_effects': _effects(12, spell_id, **crit)}]
    row = {'element': 'EARTH', 'ranges': ['9-11'], 'situation': 'g,A|67,2,0', 'triggers': 'I'}
    crit_row = dict(row, ranges=['12-14'])
    return {'ankama_id': spell_id, 'name_en': 'Probe', 'level_requirements': [160],
            'description_fr': 'Occasionne des dommages Terre en zone.\n' + text, 'levels': levels,
            'damage_templates': {'normal': [dict(row) for _count in range(rows)],
                                 'critical': [dict(crit_row) for _count in range(rows)],
                                 'stackable_damage': stackable}}


class TheGeneratorLaddersTheTurnLongBoostTests(SimpleTestCase):

    def test_the_turn_long_boost_becomes_one_stack_per_cast_of_the_turn(self):
        entry = _generator().convert_spell(_raw())
        self.assertEqual(entry.aggregates, LADDER)
        self.assertTrue(entry.stacks_on_recast)
        self.assertEqual(entry.non_crit_ranges, PLAIN)
        self.assertEqual(entry.crit_ranges, CRITICAL)
        self.assertIsNone(entry.boost_problem)

    def test_the_ladder_has_one_stack_for_each_cast_the_turn_allows(self):
        entry = _generator().convert_spell(_raw(casts=2))
        self.assertEqual(entry.aggregates, LADDER[:2])
        self.assertEqual(entry.non_crit_ranges, PLAIN[:2])

    def test_a_boost_off_its_shape_stops_the_generator(self):
        cases = {
            'card lost the sentence': _raw(text='Occasionne des dommages.'),
            'boost waits a turn': _raw(delay=1),
            'boost lasts no turn': _raw(duration=0),
            'boost lasts three turns': _raw(duration=3),
            'boost on another trigger': _raw(triggers='TB'),
            'boost on the allies': _raw(mask='a'),
            'boost only in the tooltip': _raw(flags=95),
            'boost of another spell': _raw(boosted=PYGMACHIA + 1),
            'two boosts': _raw(boosts=2),
            'no boost value': _raw(value=0),
            'critical boost differs': _raw(critical={'value': 24}),
            'no turn end removal': _raw(removal=False),
            'removal of another spell': _raw(removed=PYGMACHIA + 1),
            'removal on cast': _raw(removal_triggers='I'),
            'critical removal missing': _raw(critical={'removal': False}),
            'a stack cap': _raw(max_stack=3),
            'one cast a turn': _raw(casts=1),
            'a stack ladder already': _raw(stackable={'per_stack': [18], 'max_stacks': [3]}),
            'two hits': _raw(rows=2),
        }
        for case, raw in cases.items():
            with self.subTest(case=case):
                with self.assertRaises(SystemExit):
                    _generator().convert_spell(raw)

    def test_an_unlisted_spell_keeps_its_one_row(self):
        gen = _generator()
        unlisted = {spell: quote for spell, quote in gen.RECAST_STACKS.items()
                    if spell != PYGMACHIA}
        with mock.patch.object(gen, 'TURN_LONG_RECASTS', frozenset()), \
                mock.patch.object(gen, 'RECAST_STACKS', unlisted):
            entry = gen.convert_spell(_raw())
        self.assertEqual(entry.non_crit_ranges, PLAIN[:1])
        self.assertFalse(entry.stacks_on_recast)

    def test_the_listed_quote_is_in_each_versions_french_card(self):
        gen = _generator()
        for version in VERSIONS:
            with self.subTest(version=version):
                self.assertIn(gen.RECAST_STACKS_BY_VERSION[version][PYGMACHIA].lower(),
                              _card(version, 'fr'))


class PygmachiaShowsOneStackPerCastOfTheTurnTests(SimpleTestCase):

    def test_the_card_says_the_damage_grows_after_each_cast_this_turn_in_every_language(self):
        for version in VERSIONS:
            for language in LANGUAGES:
                with self.subTest(version=version, language=language):
                    self.assertIn(SAYS_IT_GROWS_THIS_TURN[language], _card(version, language))

    def test_each_stack_adds_the_boost_to_both_ends_of_the_hit(self):
        for version in VERSIONS:
            spell = _spell(version)
            digest = spell.get_effects_digest()
            with self.subTest(version=version):
                self.assertEqual(spell.aggregates, LADDER)
                self.assertTrue(spell.stacks_on_recast)
                for ranks in (digest.non_crit_dams, digest.crit_dams):
                    first = ranks[0][0]
                    self.assertEqual([(row.min_dam, row.max_dam) for row in ranks[0]],
                                     [(first.min_dam + BOOST * stack, first.max_dam + BOOST * stack)
                                      for stack in range(CASTS)])

    def test_one_target_takes_one_cast_so_the_turn_scores_stack_0_once(self):
        for version in VERSIONS:
            _in_version(self, version)
            cast = Castable(_spell(version), 0, crit=False)
            one, (first,) = best_turn(dict(_STATS), [cast], cast.cost,
                                      game_version=version, caster_level=200)
            total, order = best_turn(dict(_STATS), [cast], CASTS * cast.cost,
                                     game_version=version, caster_level=200)
            with self.subTest(version=version):
                self.assertEqual(cast.limit, 1)
                self.assertEqual(cast.stack_labels, [label for label, _rows in LADDER])
                self.assertEqual(order, [first])
                self.assertAlmostEqual(total, one)

    def test_casts_on_more_targets_would_each_land_the_next_stack(self):
        scale = 1 + _STATS['str'] / 100.0
        for version in VERSIONS:
            _in_version(self, version)
            cast = Castable(_spell(version), 0, crit=False)
            cast.limit = CASTS
            _one, (first,) = best_turn(dict(_STATS), [cast], cast.cost,
                                       game_version=version, caster_level=200)
            total, order = best_turn(dict(_STATS), [cast], CASTS * cast.cost,
                                     game_version=version, caster_level=200)
            with self.subTest(version=version):
                self.assertEqual(len(order), CASTS)
                self.assertAlmostEqual(order[0][1], first[1])
                for stack, (_name, damage) in enumerate(order):
                    self.assertAlmostEqual(damage - order[0][1], scale * BOOST * stack)
                self.assertAlmostEqual(
                    total, CASTS * first[1] + scale * BOOST * sum(range(CASTS)))
