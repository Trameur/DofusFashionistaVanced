# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A spell whose card grows its damage per MP used this turn keeps its MP ladder on either tooltip trigger."""
from unittest import mock

from django.test import SimpleTestCase

from chardata.spell_buffs import get_damage_spells_for_version
from chardata.spell_combo import Castable, best_turn
from chardata.spell_reference import get_spell_reference

PEAT_BOG = 13358
VERSIONS = ('dofus3', 'beta')
LANGUAGES = ('en', 'fr', 'es', 'pt', 'de')
PER_MP = 5
MP_CAP = 10
QUOTE = 'Les dommages du sort sont augmentés pour chaque PM utilisé pour le tour en cours.'
LABELS = ['%d MP used this turn' % count for count in range(MP_CAP + 1)]

SAYS_EACH_MP_COUNTS = {'en': 'increased for each mp used in the current turn',
                       'fr': 'augmentés pour chaque pm utilisé pour le tour en cours',
                       'es': 'por cada pm utilizado durante el turno en curso',
                       'pt': 'por pm utilizado no turno em andamento',
                       'de': 'für jeden verwendeten bp erhöht'}

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
                for spell in spells if spell.spell_id == PEAT_BOG)


def _card(version, language):
    for entries in get_spell_reference(version).values():
        for entry in entries:
            if entry.get('id') == PEAT_BOG:
                return ((entry.get('description') or {}).get(language) or '').lower()
    return ''


def _effects(low, spell_id, value, boosted=None, boosts=1, delay=0, duration=1, mask='C',
             triggers='I', flags=95):
    hit = {'effect_id': 97, 'triggers': 'I', 'delay': 0, 'duration': 0, 'target_mask': 'a,A',
           'dice': {'min': low, 'max': low + 4}, 'flags': 79, 'effect_metadata': {'category': 2}}
    boost = {'effect_id': 293, 'value': value, 'dice': {'min': boosted or spell_id, 'max': 0},
             'triggers': triggers, 'delay': delay, 'duration': duration, 'target_mask': mask,
             'flags': flags}
    return [hit] + [dict(boost) for _count in range(boosts)]


def _raw(spell_id=PEAT_BOG, text=QUOTE, critical=None, **shape):
    """Peat Bog's rows as the scraper hands them, with one part of their shape changed."""
    own = dict(shape, value=shape.get('value', PER_MP))
    crit = dict(own, **(critical or {}))
    levels = [{'grade': 1, 'max_stack': -1, 'max_cast_per_turn': 1, 'max_cast_per_target': 0,
               'effects': _effects(31, spell_id, **own),
               'critical_effects': _effects(37, spell_id, **crit)}]
    row = {'element': 'EARTH', 'ranges': ['31-35'], 'situation': 'a,A|76,2,0', 'triggers': 'I'}
    return {'ankama_id': spell_id, 'name_en': 'Probe', 'level_requirements': [155],
            'description_fr': 'Occasionne des dommages Terre en zone.\n' + text, 'levels': levels,
            'damage_templates': {'normal': [dict(row)],
                                 'critical': [dict(row, ranges=['37-42'])]}}


def _ladder(entry):
    return [(label, entry.non_crit_ranges[indices[0]], entry.crit_ranges[indices[0]])
            for label, indices in entry.aggregates]


EXPECTED = [(LABELS[count], ['%d-%d' % (31 + PER_MP * count, 35 + PER_MP * count)],
             ['%d-%d' % (37 + PER_MP * count, 42 + PER_MP * count)])
            for count in range(MP_CAP + 1)]


class TheGeneratorReadsTheMpLadderFromTheCardTests(SimpleTestCase):

    def test_the_tooltip_row_on_cast_gives_one_row_per_mp_used(self):
        self.assertEqual(_ladder(_generator().convert_spell(_raw())), EXPECTED)

    def test_the_tooltip_row_on_the_mp_trigger_gives_the_same_ladder(self):
        self.assertEqual(_ladder(_generator().convert_spell(_raw(triggers='CCMPARR'))), EXPECTED)

    def test_an_unlisted_spell_on_the_cast_trigger_keeps_its_one_row(self):
        gen = _generator()
        with mock.patch.object(gen, 'MP_STACKS_FROM_THE_CARD', {}):
            entry = gen.convert_spell(_raw())
        self.assertEqual(entry.non_crit_ranges, [['31-35']])
        self.assertFalse(entry.aggregates)

    def test_a_row_off_its_shape_stops_the_generator(self):
        cases = {
            'card lost the sentence': _raw(text='Occasionne des dommages.'),
            'a real row, not the tooltip': _raw(flags=79),
            'boost waits a turn': _raw(delay=1),
            'boost lasts two turns': _raw(duration=2),
            'boost on another trigger': _raw(triggers='TE'),
            'boost on the allies': _raw(mask='a'),
            'boost of another spell': _raw(boosted=PEAT_BOG + 1),
            'two boosts': _raw(boosts=2),
            'no boost value': _raw(value=0),
            'critical boost differs': _raw(critical={'value': 6}),
            'critical boost missing': _raw(critical={'boosts': 0}),
        }
        for case, raw in cases.items():
            with self.subTest(case=case):
                with self.assertRaises(SystemExit):
                    _generator().convert_spell(raw)

    def test_the_listed_quote_is_in_each_versions_french_card(self):
        gen = _generator()
        for version in VERSIONS:
            with self.subTest(version=version):
                self.assertIn(gen.MP_STACKS_FROM_THE_CARD_BY_VERSION[version][PEAT_BOG].lower(),
                              _card(version, 'fr'))


class PeatBogShowsTheMpLadderInEachVersionTests(SimpleTestCase):

    def test_the_card_says_each_mp_used_this_turn_counts_in_every_language(self):
        for version in VERSIONS:
            for language in LANGUAGES:
                with self.subTest(version=version, language=language):
                    self.assertIn(SAYS_EACH_MP_COUNTS[language], _card(version, language))

    def test_each_version_shows_one_row_per_mp_used_up_to_ten(self):
        for version in VERSIONS:
            spell = _spell(version)
            digest = spell.get_effects_digest()
            with self.subTest(version=version):
                self.assertEqual([label for label, _rows in spell.aggregates], LABELS)
                for ranks in (digest.non_crit_dams, digest.crit_dams):
                    first = ranks[0][0]
                    self.assertEqual([(row.min_dam, row.max_dam) for row in ranks[0]],
                                     [(first.min_dam + PER_MP * count,
                                       first.max_dam + PER_MP * count)
                                      for count in range(MP_CAP + 1)])

    def test_the_beta_ladder_is_the_main_games_ladder(self):
        main, beta = _spell('dofus3'), _spell('beta')
        self.assertEqual(beta.aggregates, main.aggregates)
        for field in ('non_crit_dams', 'crit_dams'):
            with self.subTest(field=field):
                self.assertEqual(
                    [[(row.min_dam, row.max_dam, row.element) for row in rank]
                     for rank in getattr(beta.get_effects_digest(), field)],
                    [[(row.min_dam, row.max_dam, row.element) for row in rank]
                     for rank in getattr(main.get_effects_digest(), field)])

    def test_the_turn_scores_the_cast_with_no_mp_used(self):
        for version in VERSIONS:
            _in_version(self, version)
            spell = _spell(version)
            cast = Castable(spell, 0, crit=False)
            total, (scored,) = best_turn(dict(_STATS), [cast], cast.cost,
                                         game_version=version, caster_level=200)
            with self.subTest(version=version):
                self.assertEqual(cast.scored_group, LABELS[0])
                self.assertAlmostEqual(total, scored[1])
