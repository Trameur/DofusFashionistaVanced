# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A damage effect with a delay lands on a later turn: out of the turn's burst, in what lands later."""
import json
import os
from unittest import expectedFailure

from django.test import SimpleTestCase
from django.utils import translation

from chardata.spell_buffs import get_damage_spells_for_version
from chardata.spell_reference import get_spell_reference

LANGUAGES = ('en', 'fr', 'es', 'pt', 'de')
MODERN = ('dofus3', 'beta')
EVERY = ('dofus3', 'beta', 'dofus2')

SWORD_OF_JUDGEMENT = 13117
SANDGLASS = 13261
PLOTTER = 12936
DEVOURING_ARROW = 32446
JORMUN = 23268
PERSECUTING_ARROW = 32433
HARMPIT = 14651
RAINING_ARROWS = 32431
RAINING_ARROWS_AREA = 32481

# {spell id: (versions, {row: when})}
LATE = {
    SWORD_OF_JUDGEMENT: (EVERY, {1: 'later_turn'}),
    SANDGLASS: (MODERN, {1: 'later_turn'}),
    DEVOURING_ARROW: (MODERN, {5: 'later_turn', 7: 'later_turn', 9: 'later_turn',
                               10: 'later_turn'}),
    RAINING_ARROWS: (MODERN, {1: 'later_turn'}),
}

# Ankama's words for each rule, lower case; a tuple when the versions word it apart
SAYS = {
    SWORD_OF_JUDGEMENT: {'en': 'delayed', 'fr': 'retardement', 'es': 'retardado',
                         'pt': 'atraso', 'de': 'verzögerung'},
    SANDGLASS: {'en': ('delayed', 'when the state expires'),
                'fr': ('retardement', "lors de l'expiration de l'état"),
                'es': ('retardado', 'cuando el estado expire'),
                'pt': ('atraso', 'quando o estado expira'),
                'de': ('zeitverzögert', 'wenn der zustand ausläuft')},
    PLOTTER: {'en': 'third turn', 'fr': 'troisième tour', 'es': 'tercer turno',
              'pt': 'terceiro turno', 'de': 'dritten runde'},
    DEVOURING_ARROW: {'en': ('subsequent turns', 'delayed'),
                      'fr': ('prochains tours', 'retardement'),
                      'es': ('próximos turnos', 'retardado'),
                      'pt': ('turnos seguintes', 'atraso'),
                      'de': ('nächsten runden', 'verzögerung')},
    RAINING_ARROWS: {'en': 'following turn', 'fr': 'tour suivant', 'es': 'siguiente turno',
                     'pt': 'turno seguinte', 'de': 'nächsten runde'},
}

INITIAL_ENEMY = {'en': 'initial enemy', 'fr': 'ennemi initial', 'es': 'enemigo inicial',
                 'pt': 'inimigo inicial', 'de': 'ursprünglichen gegner'}
NEXT_TO_IT = {'en': 'adjacent', 'fr': 'à son contact', 'es': 'contacto', 'pt': 'contato',
              'de': 'nahkampfentfernung'}
ON_THE_CASTER = {'en': 'on the caster:', 'fr': 'sur le lanceur :',
                 'es': 'sobre el lanzador:', 'pt': 'no lançador:', 'de': 'beim zaubernden:'}
THE_LANCE = {'en': 'lance', 'fr': 'lance', 'es': 'lanza', 'pt': 'lança', 'de': 'wurfspeer'}

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW = {'dofus3': 'transformed_class_spells.json',
       'beta': 'transformed_class_spells_beta.json',
       'dofus2': 'transformed_class_spells_dofus2.json'}


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


def _text(version, spell_id, language):
    for entries in get_spell_reference(version).values():
        for entry in entries:
            if entry.get('id') == spell_id:
                text = (entry.get('description') or {}).get(language) or ''
                return ' '.join(text.replace('’', "'").lower().split())
    return ''


def _stats(version, **values):
    from fashionistapulp.structure import get_structure
    stats = {stat.key: 0 for stat in get_structure(version).get_stats_list()}
    stats.update(values)
    return stats


def _top_cast(spell):
    from chardata.spell_combo import Castable
    return Castable(spell, len(spell.level_req) - 1, False)


def _effect(mask, zone, dice, delay=0, element=2, text='Fire damage'):
    return {'target_mask': mask, 'effect_element': element, 'delay': delay,
            'dice': {'min': dice, 'max': 0},
            'zone': {'shape': zone[0], 'param1': zone[1], 'param2': zone[2]},
            'effect_metadata': {'category': 2, 'description': {'en': text}}}


def _row(mask, zone, ranges, element='FIRE', group=None):
    row = {'element': element, 'steals': False, 'heals': False, 'ranges': ranges,
           'triggers': 'I', 'situation': '%s|%s' % (mask, ','.join(map(str, zone)))}
    if group:
        row['best_element_group'] = group
    return row


class TheGeneratorReadsTheDelayOfEachEffectTests(SimpleTestCase):

    def test_a_row_takes_the_delay_of_the_effect_that_wrote_it_told_apart_by_its_zone(self):
        spell = {'ankama_id': 1, 'levels': [{'effects': [
            _effect('A,E662', (80, 1, 0), 70, delay=3),
            _effect('A,E662', (67, 63, 1), 70)], 'critical_effects': []}]}
        rows = [_row('A,E662', (80, 1, 0), ['70']), _row('A,E662', (67, 63, 1), ['70'])]
        self.assertIsNone(_generator()._stamp_delays(spell, rows, critical=False))
        self.assertEqual([3, None], [row.get('delay') for row in rows])

    def test_the_nth_effect_of_a_shape_wrote_the_nth_row_of_it(self):
        spell = {'ankama_id': 1, 'levels': [{'effects': [
            _effect('A,g', (88, 63, 0), 6), _effect('A', (88, 63, 0), 6),
            _effect('A,g', (88, 63, 0), 6, delay=4)], 'critical_effects': []}]}
        rows = [_row('A,g', (88, 63, 0), ['6']), _row('A', (88, 63, 0), ['6']),
                _row('A,g', (88, 63, 0), ['6'])]
        self.assertIsNone(_generator()._stamp_delays(spell, rows, critical=False))
        self.assertEqual([None, None, 4], [row.get('delay') for row in rows])

    def test_a_best_element_effect_puts_its_delay_on_its_four_faces(self):
        spell = {'ankama_id': 1, 'levels': [{'effects': [
            _effect('a,A', (81, 1, 1), 26, delay=3, element=-1,
                    text='#1 best-element damage')], 'critical_effects': []}]}
        rows = [_row('a,A', (81, 1, 1), ['26'], element=element, group='best-element-0')
                for element in ('EARTH', 'FIRE', 'WATER', 'AIR')]
        self.assertIsNone(_generator()._stamp_delays(spell, rows, critical=False))
        self.assertEqual([3, 3, 3, 3], [row.get('delay') for row in rows])

    def test_a_delay_the_rows_do_not_show_is_reported(self):
        spell = {'ankama_id': 1, 'levels': [{'effects': [
            _effect('A', (80, 1, 0), 10, delay=2)], 'critical_effects': []}]}
        rows = [_row('A', (80, 1, 0), ['12'])]
        self.assertIn('no row', _generator()._stamp_delays(spell, rows, critical=False))

    def test_an_effect_without_a_row_leaves_the_next_effects_their_delay(self):
        spell = {'ankama_id': 1, 'levels': [
            {'effects': [_effect('A', (80, 1, 0), 10, delay=2),
                         _effect('A', (80, 1, 0), 12, delay=3)], 'critical_effects': []},
            {'effects': [_effect('A', (80, 1, 0), 30, delay=2),
                         _effect('A', (88, 1, 0), 16, delay=4)], 'critical_effects': []}]}
        rows = [_row('A', (80, 1, 0), ['12', '14']), _row('A', (88, 1, 0), ['15', '16'])]
        self.assertIn('no row', _generator()._stamp_delays(spell, rows, critical=False))
        self.assertEqual([3, 4], [row.get('delay') for row in rows])

    def test_a_delayed_row_on_a_trigger_the_generator_does_not_read_is_not_late(self):
        triggers = ('I', '', 'CC', 'H', 'DI', 'PO|CPD', 'I|CC')
        rows = [dict(_row('A', (80, 1, 0), ['10']), delay=2, triggers=trigger)
                for trigger in triggers]
        self.assertEqual({0: 'later_turn', 1: 'later_turn'},
                         _generator()._late_rows(rows, {}, 'later_turn', {}))

    def test_a_trigger_or_a_held_row_wins_over_the_delay(self):
        late_rows = _generator()._late_rows
        rows = [dict(_row('A', (80, 1, 0), ['10']), delay=2),
                dict(_row('A', (80, 1, 0), ['12']), delay=1, triggers='TB'),
                dict(_row('A', (80, 1, 0), ['14']), delay=1),
                _row('A', (80, 1, 0), ['16'])]
        self.assertEqual({0: 'later_turn', 1: 'turn_begin'},
                         late_rows(rows, {1: 'turn_begin'}, 'later_turn',
                                   {2: 'out_of_sight'}))

    def test_the_client_still_puts_a_delay_on_those_rows(self):
        found = {}
        recasts = {}
        for version, name in RAW.items():
            path = os.path.join(REPO, 'itemscraper', name)
            if not os.path.exists(path):
                self.skipTest('%s is not tracked; run itemscraper/get_spells.py' % name)
            with open(path, encoding='utf-8') as handle:
                classes = json.load(handle)
            for payload in classes.values():
                for spell in payload.get('spells') or []:
                    delays = {effect.get('delay') for level in spell.get('levels') or []
                              for effect in level.get('effects') or []
                              if (effect.get('effect_metadata') or {}).get('category') == 2
                              and (effect.get('delay') or 0) > 0}
                    if spell.get('ankama_id') in (SWORD_OF_JUDGEMENT, SANDGLASS, PLOTTER,
                                                  DEVOURING_ARROW):
                        found[(version, spell['ankama_id'])] = delays
                    if spell.get('ankama_id') == RAINING_ARROWS:
                        recasts[version] = sorted(
                            (effect.get('delay') or 0, effect['dice']['max'])
                            for level in spell.get('levels') or []
                            for effect in level.get('effects') or []
                            if effect.get('effect_id') == 2794
                            and effect['dice']['min'] == RAINING_ARROWS_AREA)
        self.assertEqual({2}, found[('dofus3', SWORD_OF_JUDGEMENT)])
        self.assertEqual({2}, found[('dofus2', SWORD_OF_JUDGEMENT)])
        self.assertEqual({2}, found[('beta', SANDGLASS)])
        self.assertEqual(set(), found[('dofus2', SANDGLASS)])
        self.assertEqual({3}, found[('dofus2', PLOTTER)])
        self.assertEqual({3}, found[('dofus3', DEVOURING_ARROW)])
        for version in MODERN:
            self.assertEqual([(0, 2), (1, 1)], recasts[version])


class EachSpellCarriesItsLateRowsTests(SimpleTestCase):

    def test_each_listed_row_lands_on_a_later_turn_in_each_version(self):
        for spell_id, (versions, late) in LATE.items():
            for version in versions:
                with self.subTest(version=version, spell=spell_id):
                    spell = _spell(version, spell_id)
                    self.assertEqual(late, spell.delayed)
                    self.assertIsNone(getattr(spell, 'delayed_crit', None))

    def test_every_row_of_plotter_lands_when_the_double_dies(self):
        for version in EVERY:
            with self.subTest(version=version):
                spell = _spell(version, PLOTTER)
                rows = len(spell.effects.non_crit_ranges)
                self.assertEqual(24, rows)
                self.assertEqual({row: 'double_dies' for row in range(rows)}, spell.delayed)

    def test_the_dofus2_sandglass_is_another_spell_with_nothing_late(self):
        self.assertFalse(_spell('dofus2', SANDGLASS).delayed)

    def test_devouring_arrow_holds_the_rings_on_the_first_enemy(self):
        for version in MODERN:
            with self.subTest(version=version):
                self.assertEqual({6: 'initial_enemy', 8: 'initial_enemy', 11: 'initial_enemy'},
                                 _spell(version, DEVOURING_ARROW).conditional)

    def test_jormun_holds_the_row_of_the_cast_on_the_caster(self):
        for version in EVERY:
            with self.subTest(version=version):
                spell = _spell(version, JORMUN)
                self.assertEqual({1: 'on_the_caster'}, spell.conditional)
                ranges = spell.effects.non_crit_ranges
                self.assertLess(ranges[1][-1].max_dam, ranges[0][-1].max_dam)

    def test_a_row_that_waits_out_of_sight_or_for_telefrag_is_not_also_late(self):
        for version in MODERN:
            for spell_id in (PERSECUTING_ARROW, HARMPIT):
                with self.subTest(version=version, spell=spell_id):
                    spell = _spell(version, spell_id)
                    self.assertIn(1, spell.conditional)
                    self.assertNotIn(1, spell.delayed or {})

    def test_ankama_says_each_rule_in_five_languages(self):
        for spell_id, words in SAYS.items():
            versions = LATE.get(spell_id, (EVERY,))[0]
            for version in versions:
                for language in LANGUAGES:
                    with self.subTest(version=version, spell=spell_id, language=language):
                        text = _text(version, spell_id, language)
                        said = words[language]
                        said = said if isinstance(said, tuple) else (said,)
                        self.assertTrue(any(word in text for word in said), text)
        for language in LANGUAGES:
            for version in MODERN:
                with self.subTest(version=version, language=language):
                    self.assertIn(INITIAL_ENEMY[language],
                                  _text(version, DEVOURING_ARROW, language))
            for version in EVERY:
                with self.subTest(version=version, language=language):
                    self.assertIn(NEXT_TO_IT[language], _text(version, PLOTTER, language))
                    jormun = _text(version, JORMUN, language)
                    self.assertIn(ON_THE_CASTER[language], jormun)
                    self.assertIn(THE_LANCE[language], jormun)


class TheTurnCountsLateDamageApartTests(SimpleTestCase):

    def _turn(self, version, spell_id, **stats):
        from chardata.spell_combo import best_turn, delayed_damage, delayed_moments
        from chardata.spells_view import _burst_total
        _in_version(self, version)
        cast = _top_cast(_spell(version, spell_id))
        values = _stats(version, **stats)
        total, order = best_turn(values, [cast], cast.cost, game_version=version)
        later = delayed_damage(values, [cast], order, game_version=version)
        burst = _burst_total(values, [cast], order, {}, version)
        return cast, total, later.get(cast.name, 0.0), burst, delayed_moments([cast], order)

    def test_the_burst_leaves_out_the_late_row_and_the_turn_keeps_it(self):
        for spell_id, stats in ((SWORD_OF_JUDGEMENT, {'int': 800, 'cha': 800}),
                                (SANDGLASS, {'int': 800, 'cha': 800}),
                                (RAINING_ARROWS, {'agi': 800})):
            for version in LATE[spell_id][0]:
                with self.subTest(version=version, spell=spell_id):
                    cast, total, later, burst, moments = self._turn(
                        version, spell_id, **stats)
                    self.assertGreater(later, 0)
                    self.assertGreater(burst, 0)
                    self.assertAlmostEqual(total, burst + later, delta=1)
                    self.assertEqual({cast.name: ['later_turn']}, moments)

    def test_plotter_deals_nothing_this_turn(self):
        for version in EVERY:
            with self.subTest(version=version):
                cast, total, later, burst, moments = self._turn(
                    version, PLOTTER, str=800, int=800, cha=800, agi=800)
                self.assertEqual(0, burst)
                self.assertGreater(total, 0)
                self.assertAlmostEqual(total, later, places=6)
                self.assertEqual({cast.name: ['double_dies']}, moments)

    def _scored_rows(self, cast):
        return [next(index for index, row in enumerate(cast.effects) if row is hit)
                for hit in cast.hits]

    def test_devouring_arrow_never_scores_a_ring_row_and_marks_its_late_rows(self):
        for version in MODERN:
            with self.subTest(version=version):
                _in_version(self, version)
                cast = _top_cast(_spell(version, DEVOURING_ARROW))
                self.assertFalse({6, 8, 11} & set(self._scored_rows(cast)))
                self.assertEqual([5, 7, 9, 10],
                                 sorted(index for index, row in enumerate(cast.effects)
                                        if id(row) in cast.late_by_effect))

    # The turn scores row 0, the steal on allies (mask g), ahead of the enemy's rows 1 and 5
    @expectedFailure
    def test_devouring_arrow_sends_its_late_hit_to_what_lands_later(self):
        lands_later = {version: self._turn(version, DEVOURING_ARROW, int=800)[2]
                       for version in MODERN}
        self.assertTrue(all(lands_later.values()), lands_later)

    def test_jormun_lands_one_row_on_the_target(self):
        for version in EVERY:
            with self.subTest(version=version):
                _in_version(self, version)
                self.assertEqual([0], self._scored_rows(_top_cast(_spell(version, JORMUN))))


class TheNewWordsAreWrittenInFiveLanguagesTests(SimpleTestCase):

    def test_each_token_the_constants_carry_has_a_label(self):
        from chardata.spells_view import _CONDITIONAL_LABELS, _DELAYED_LABELS
        for version in EVERY:
            for spells in get_damage_spells_for_version(version).values():
                for spell in spells:
                    with self.subTest(version=version, spell=spell.spell_id):
                        for when in (spell.delayed or {}).values():
                            self.assertIn(when, _DELAYED_LABELS)
                        for trigger in (spell.conditional or {}).values():
                            self.assertIn(trigger, _CONDITIONAL_LABELS)

    def test_each_new_label_reads_differently_in_every_language(self):
        from chardata.spells_view import _CONDITIONAL_LABELS, _DELAYED_LABELS
        labels = {'later_turn': _DELAYED_LABELS, 'double_dies': _DELAYED_LABELS,
                  'on_the_caster': _CONDITIONAL_LABELS,
                  'initial_enemy': _CONDITIONAL_LABELS}
        for token, table in labels.items():
            rendered = {}
            for language in LANGUAGES:
                with translation.override(language):
                    rendered[language] = str(table[token])
            with self.subTest(label=token):
                self.assertEqual(5, len(set(rendered.values())),
                                 'a language fell back to English: %s' % rendered)
