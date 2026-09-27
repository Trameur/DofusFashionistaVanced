# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""One cast on one enemy: a drawn face, a pushback row, a Will-o'-the-Wisp ring, a flask and a ring around the target count only when they land."""
import copy

from django.test import SimpleTestCase
from django.utils import translation

from chardata.spell_buffs import get_damage_spells_for_version
from chardata.spell_reference import get_spell_reference

MODERN = ('dofus3', 'beta', 'dofus2')
LANGUAGES = ('en', 'fr', 'es', 'pt', 'de')

TOPKAJ = 12846
TYRANNICAL_ARROW = 32448
COMMOTION = 25856
ALCHEMICAL_WORD = 25802
BUSH_FIRE = 13568

DRAWN = 'Drawn at random'

# Ankama's words for each rule, lower case, in every version that has the spell
SAYS = {
    'pushback': {'en': 'pushback damage', 'fr': 'dommages de pouss',
                 'es': 'daños de empuje', 'pt': 'danos de empurr',
                 'de': 'schubsschaden'},
    'ends_its_effects': {'en': "removes the spell's effects",
                         'fr': 'retire les effets du sort',
                         'es': 'retira los efectos del hechizo',
                         'pt': 'retira os efeitos do feitiço',
                         'de': 'wirkung des zaubers wird aufgehoben'},
    'wisp': {'en': "will-o'-the-wisp", 'fr': 'feu follet', 'es': 'fuego fatuo',
             'pt': 'fogo-fátuo', 'de': 'irrlicht'},
    'final_damage': {'en': 'final damage', 'fr': 'dommages finaux',
                     'es': 'daños finales', 'pt': 'danos finais',
                     'de': 'endschaden'},
    'flask_destroyed': {'en': 'when it is destroyed', 'fr': 'lorsqu\'elle est détruite',
                        'es': 'cuando lo destruyen', 'pt': 'quando é destruído',
                        'de': 'wenn sie zerstört wird'},
    'contents': {'en': 'based on its contents', 'fr': 'selon son contenu',
                 'es': 'según su contenido', 'pt': 'de acordo com seu conteúdo',
                 'de': 'je nach inhalt'},
    'around_the_target_at_turn_end': {'en': 'around the target', 'fr': "autour d'elle",
                                      'es': 'alrededor de este', 'pt': 'ao redor dele',
                                      'de': 'ende der runde des ziels'},
}


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
                return text.replace('’', "'").lower()
    return ''


def _top_cast(spell, crit=False):
    from chardata.spell_combo import Castable
    return Castable(spell, len(spell.level_req) - 1, crit)


def _stats(version, **values):
    from fashionistapulp.structure import get_structure
    stats = {stat.key: 0 for stat in get_structure(version).get_stats_list()}
    stats.update(values)
    return stats


def _effect(order, group, mask, element, dice, text, chance=16.67):
    return {'order': order, 'group': group, 'random': chance, 'target_mask': mask,
            'effect_element': element, 'dice': {'min': dice, 'max': 0},
            'effect_metadata': {'category': 2, 'description': {'en': text}}}


def _row(mask, ranges, heals=False):
    return {'element': 'FIRE', 'steals': False, 'heals': heals, 'ranges': ranges,
            'triggers': 'I', 'situation': '%s|80,1,0' % mask}


def _topkaj_shape(chances=(16.67, 16.67, 16.67)):
    """Two grades; each effect group holds one enemy hit and one ally heal of one value."""
    levels = []
    for dice in ((7, 10, 13), (16, 19, 22)):
        effects = []
        for group, (value, chance) in enumerate(zip(dice, chances), start=1):
            effects.append(_effect(2 * group, group, 'A', 2, value, 'Fire damage', chance))
            effects.append(_effect(2 * group + 1, group, 'a', 2, value, 'Fire heals', chance))
        levels.append({'effects': effects, 'critical_effects': []})
    rows = [_row('A', ['7', '16']), _row('a', ['7', '16'], heals=True),
            _row('A', ['10', '19']), _row('a', ['10', '19'], heals=True),
            _row('a', ['13', '22'], heals=True), _row('A', ['13', '22'])]
    return {'ankama_id': 1, 'levels': levels}, rows


class TopkajDrawsOneFacePerCastTests(SimpleTestCase):

    def test_each_version_writes_the_faces_as_two_draws(self):
        for version in MODERN:
            with self.subTest(version=version):
                self.assertEqual([(DRAWN, [0]), ('', [2]), ('', [5]),
                                  (DRAWN, [1]), ('', [3]), ('', [4])],
                                 list(_spell(version, TOPKAJ).aggregates))

    def test_the_turn_takes_one_damage_face_at_its_odds(self):
        from chardata.spell_combo import best_turn
        for version in MODERN:
            _in_version(self, version)
            cast = _top_cast(_spell(version, TOPKAJ))
            with self.subTest(version=version):
                self.assertTrue(cast.random_draw)
                self.assertEqual(3, len(cast.plain_alternatives))
                self.assertEqual(3, len(cast.crit_alternatives))
                for face in cast.plain_alternatives + cast.crit_alternatives:
                    self.assertEqual(1, len(face))
                    self.assertFalse(face[0].heals)
                stats = _stats(version, int=400, pow=100)
                drawn, _order = best_turn(stats, [cast], cast.cost, game_version=version)
                alone = []
                for plain, crit in zip(cast.plain_alternatives, cast.crit_alternatives):
                    face = copy.copy(cast)
                    face.random_draw = False
                    face.plain_alternatives = face.alternatives = [plain]
                    face.crit_alternatives = [crit]
                    alone.append(best_turn(stats, [face], cast.cost,
                                           game_version=version)[0])
                self.assertAlmostEqual(sum(alone) / len(alone), drawn, places=6)
                self.assertLess(drawn, max(alone))

    def test_the_table_shows_each_draw_as_one_line_of_faces(self):
        from chardata.spells_view import convert_aggregates
        for version in MODERN:
            _in_version(self, version)
            spell = _spell(version, TOPKAJ)
            digest = spell.get_effects_digest()
            with self.subTest(version=version):
                groups = convert_aggregates(digest.aggregates, version,
                                            digest.non_crit_dams[0])
                self.assertEqual([[0, 2, 5], [1, 3, 4]], [group[1] for group in groups])
                self.assertEqual(['one', 'one'], [group[2] for group in groups])

    def test_an_effect_group_is_one_draw_at_the_odds_of_its_chances(self):
        spell, rows = _topkaj_shape()
        self.assertEqual(([[0, 2, 5], [1, 3, 4]], None),
                         _generator()._drawn_runs(spell, rows, []))

    def test_a_draw_the_turn_cannot_average_is_left_alone_and_said(self):
        generator = _generator()
        spell, rows = _topkaj_shape(chances=(50, 25, 25))
        runs, problem = generator._drawn_runs(spell, rows, [])
        self.assertIsNone(runs)
        self.assertIn('unequal odds', problem)
        spell, rows = _topkaj_shape()
        runs, problem = generator._drawn_runs(spell, rows + [_row('A', ['30', '40'])], [])
        self.assertIsNone(runs)
        self.assertIn('not drawn', problem)

    def test_a_spell_without_chances_draws_nothing(self):
        spell, rows = _topkaj_shape(chances=(0, 0, 0))
        self.assertEqual((None, None), _generator()._drawn_runs(spell, rows, []))

    def test_one_group_that_draws_one_of_its_rows_is_said(self):
        generator = _generator()
        spell = {'ankama_id': 1, 'levels': [{'effects': [
            _effect(1, 0, 'A', 2, 10, 'Fire damage', 50),
            _effect(2, 0, 'A', 2, 20, 'Fire damage', 50)], 'critical_effects': []}]}
        rows = [_row('A', ['10']), _row('A', ['20'])]
        self.assertEqual((None, 'one group draws one of its rows'),
                         generator._drawn_runs(spell, rows, []))
        spell['levels'][0]['effects'].pop()
        self.assertEqual((None, None), generator._drawn_runs(spell, rows[:1], []))

    def test_a_class_spell_it_cannot_draw_is_warned_about(self):
        import contextlib
        import io
        spell, rows = _topkaj_shape(chances=(50, 25, 25))
        levels = [1, 100]
        spell.update({'name_en': 'Uneven Draw', 'order': 1, 'level_requirements': levels,
                      'damage_templates': {'levels': levels, 'normal': rows,
                                           'critical': []}})
        loose = dict(spell, ankama_id=2, name_en='Loose Draw')
        classed = dict(spell, breed_ids=[6])
        errors = io.StringIO()
        with contextlib.redirect_stderr(errors):
            _generator().build_spell_map({'Ecaflip': {'breed_id': 6}}, [classed, loose])
        warned = [line for line in errors.getvalue().splitlines() if 'rolls a chance' in line]
        self.assertEqual(1, len(warned))
        self.assertIn('Uneven Draw (1)', warned[0])
        self.assertIn('unequal odds', warned[0])


class TyrannicalArrowWaitsForPushbackTests(SimpleTestCase):

    def test_the_premature_row_waits_and_the_poison_stays_late(self):
        for version in ('dofus3', 'beta'):
            _in_version(self, version)
            spell = _spell(version, TYRANNICAL_ARROW)
            cast = _top_cast(spell)
            with self.subTest(version=version):
                self.assertEqual({2: 'pushback'}, spell.conditional)
                self.assertEqual({1: 'turn_end'}, spell.delayed)
                self.assertEqual([cast.effects[0], cast.effects[1]], cast.hits)
                self.assertEqual([(cast.effects[2], 'pushback')], cast.waiting_plain)

    def test_a_push_in_the_turn_adds_the_row_apart(self):
        from chardata.spell_combo import castable_spells, conditional_extras
        for version in ('dofus3', 'beta'):
            _in_version(self, version)
            spells = castable_spells('Cra', 200, version)
            arrow = next(spell for spell in spells if spell.spell_id == TYRANNICAL_ARROW)
            pusher = next(spell for spell in spells if spell.pushes)
            stats = _stats(version, int=400)
            with self.subTest(version=version):
                alone = conditional_extras(stats, spells, [(arrow.name, 0)],
                                           game_version=version)
                self.assertEqual([], [extra for extra in alone if extra[0] == arrow.name])
                pushed = conditional_extras(stats, spells, [(pusher.name, 0), (arrow.name, 0)],
                                            game_version=version)
                self.assertEqual(['pushback'], [trigger for name, trigger, _damage in pushed
                                                if name == arrow.name])

    def test_a_push_adds_the_early_hit_less_the_poison_it_ends(self):
        from chardata.spell_combo import castable_spells, conditional_extras
        for version in ('dofus3', 'beta'):
            _in_version(self, version)
            spells = castable_spells('Cra', 200, version)
            arrow = next(spell for spell in spells if spell.spell_id == TYRANNICAL_ARROW)
            pusher = next(spell for spell in spells if spell.pushes and not spell.buffs)
            stats = _stats(version, int=400)

            def extra(castable):
                return sum(damage for name, _trigger, damage in conditional_extras(
                    stats, [pusher, castable], [(pusher.name, 0), (arrow.name, 0)],
                    game_version=version) if name == arrow.name)

            early = copy.copy(arrow)
            early.delayed_plain = []
            poison = copy.copy(early)
            poison.waiting_plain = [(arrow.delayed_plain[0][0], 'pushback')]
            with self.subTest(version=version):
                self.assertEqual(1, len(arrow.delayed_plain))
                self.assertGreater(extra(poison), 0)
                self.assertGreater(extra(arrow), 0)
                self.assertAlmostEqual(extra(early) - extra(poison), extra(arrow), places=6)


class CommotionKeepsItsWispHalfOffTheTurnTests(SimpleTestCase):

    def test_the_ring_row_waits_for_a_wisp(self):
        for version in ('dofus3', 'beta'):
            _in_version(self, version)
            spell = _spell(version, COMMOTION)
            cast = _top_cast(spell)
            with self.subTest(version=version):
                self.assertEqual({4: 'around_a_wisp'}, spell.conditional)
                self.assertEqual([cast.effects[2]], cast.hits)
                self.assertEqual([(cast.effects[4], 'around_a_wisp')], cast.waiting_plain)

    def test_the_table_draws_the_ring_row_under_its_wait(self):
        from chardata.spells_view import _create_spell_web_digest
        for version in ('dofus3', 'beta'):
            _in_version(self, version)
            web = _create_spell_web_digest(_spell(version, COMMOTION), version)
            with self.subTest(version=version):
                self.assertEqual([[0], [4]], [group[1] for group in web['aggregates']])
                self.assertEqual({'0': [2], '1': [2]}, web['always_land']['non_crit'])
                self.assertEqual(['4'], list(web['conditional']))

    def test_the_wisps_final_damage_is_not_the_casters(self):
        for version in MODERN:
            _in_version(self, version)
            spell = _spell(version, COMMOTION)
            with self.subTest(version=version):
                self.assertFalse([element for element in spell.effects.elements
                                  if str(element).startswith('buff')])
                self.assertEqual({}, _top_cast(spell).buff_deltas(1))


class AlchemicalWordHitsOnlyWhenItsFlaskBreaksTests(SimpleTestCase):

    def test_the_four_elements_are_faces_of_one_hit_that_waits(self):
        from chardata.spells_view import convert_aggregates
        for version in ('dofus3', 'beta'):
            _in_version(self, version)
            spell = _spell(version, ALCHEMICAL_WORD)
            digest = spell.get_effects_digest()
            with self.subTest(version=version):
                self.assertEqual(dict.fromkeys((4, 5, 6, 7), 'flask_destroyed'),
                                 spell.conditional)
                groups = convert_aggregates(digest.aggregates, version,
                                            digest.non_crit_dams[0])
                self.assertEqual([[4, 5, 6, 7], [0, 1, 2, 3]], [group[1] for group in groups])
                self.assertEqual(['best', 'best'], [group[2] for group in groups])

    def test_the_turn_takes_nothing_from_a_cast(self):
        from chardata.spell_combo import castable_spells
        for version in ('dofus3', 'beta'):
            _in_version(self, version)
            with self.subTest(version=version):
                self.assertEqual([], _top_cast(_spell(version, ALCHEMICAL_WORD)).hits)
                self.assertNotIn(ALCHEMICAL_WORD, [spell.spell_id for spell
                                                   in castable_spells('Eniripsa', 200, version)])


def _flask(elements=('EARTH', 'FIRE', 'WATER', 'AIR'), description='des dommages selon son contenu'):
    rows = [dict(_row('A', ['10']), element=element) for element in elements]
    rows += [dict(_row('a', ['10'], heals=True), element=element) for element in elements]
    return {'ankama_id': 1, 'description_fr': description}, rows


class OneElementFacesStopWhenTheDataMovesTests(SimpleTestCase):

    def _build(self, spell, rows, crit_rows):
        from unittest import mock
        generator = _generator()
        with mock.patch.object(generator, 'ONE_ELEMENT_FACES', {1: 'des dommages selon son contenu'}):
            return generator._build_one_element_aggregates(spell, rows, crit_rows, len(rows))

    def test_the_hits_come_first_each_in_its_best_element(self):
        spell, rows = _flask()
        self.assertEqual([('Hit in best element', [0]), ('', [1]), ('', [2]), ('', [3]),
                          ('Hit in best element', [4]), ('', [5]), ('', [6]), ('', [7])],
                         self._build(spell, rows, rows))

    def test_it_stops_when_the_card_no_longer_says_it(self):
        spell, rows = _flask(description='des dommages Feu')
        with self.assertRaisesRegex(SystemExit, 'no longer says'):
            self._build(spell, rows, rows)

    def test_it_stops_when_the_rows_are_not_one_per_element(self):
        spell, rows = _flask(elements=('EARTH', 'FIRE', 'FIRE', 'AIR'))
        with self.assertRaisesRegex(SystemExit, 'no longer one per element'):
            self._build(spell, rows, rows)

    def test_it_stops_when_the_critical_rows_are_others(self):
        spell, rows = _flask()
        with self.assertRaisesRegex(SystemExit, 'critical rows are not its normal ones'):
            self._build(spell, rows, rows + [_row('A', ['10'])])


class BushFireSparesItsOwnTargetTests(SimpleTestCase):

    def test_the_ring_row_waits_and_the_client_timing_stays(self):
        for version in MODERN:
            _in_version(self, version)
            spell = _spell(version, BUSH_FIRE)
            cast = _top_cast(spell)
            with self.subTest(version=version):
                self.assertEqual({1: 'around_the_target_at_turn_end'}, spell.conditional)
                self.assertEqual([cast.effects[0]], cast.hits)
                if version != 'dofus2':
                    self.assertEqual({1: 'turn_end'}, spell.delayed)

    def test_the_best_turn_counts_no_late_damage_for_it(self):
        from chardata.spell_combo import best_turn, castable_spells, delayed_damage
        for version in MODERN:
            _in_version(self, version)
            spells = [spell for spell in castable_spells('Sadida', 200, version)
                      if spell.spell_id == BUSH_FIRE]
            stats = _stats(version, int=400, pow=100)
            with self.subTest(version=version):
                self.assertEqual(1, len(spells))
                total, order = best_turn(stats, spells, 12, game_version=version)
                self.assertGreater(total, 0)
                self.assertEqual({}, delayed_damage(stats, spells, order, game_version=version))


class AnkamasTextStatesEachRuleTests(SimpleTestCase):

    RULES = (
        (('dofus3', 'beta'), TYRANNICAL_ARROW, ('pushback', 'ends_its_effects')),
        (MODERN, COMMOTION, ('wisp', 'final_damage')),
        (('dofus3', 'beta'), ALCHEMICAL_WORD, ('flask_destroyed', 'contents')),
        (MODERN, BUSH_FIRE, ('around_the_target_at_turn_end',)),
    )

    def test_in_five_languages_and_every_version_that_applies_it(self):
        for versions, spell_id, rules in self.RULES:
            for version in versions:
                for rule in rules:
                    for language, words in SAYS[rule].items():
                        with self.subTest(version=version, spell=spell_id, rule=rule,
                                          language=language):
                            self.assertIn(words, _text(version, spell_id, language))

    def test_each_push_that_ends_the_late_rows_quotes_its_card(self):
        from chardata.spell_combo import PUSH_ENDS_THE_LATE_ROWS
        self.assertEqual({'dofus3': {TYRANNICAL_ARROW}, 'beta': {TYRANNICAL_ARROW}},
                         {version: set(quotes) for version, quotes
                          in PUSH_ENDS_THE_LATE_ROWS.items()})
        for version, quotes in PUSH_ENDS_THE_LATE_ROWS.items():
            for spell_id, quote in quotes.items():
                with self.subTest(version=version, spell=spell_id):
                    self.assertIn(quote, _text(version, spell_id, 'fr'))
                    self.assertTrue(_spell(version, spell_id).delayed)


class TheNewWordsAreWrittenInFiveLanguagesTests(SimpleTestCase):

    def test_each_label_reads_differently_in_every_language(self):
        from chardata.spells_view import _CONDITIONAL_LABELS, _localized_aggregate_label
        labels = {
            'around_a_wisp': lambda: str(_CONDITIONAL_LABELS['around_a_wisp']),
            'flask_destroyed': lambda: str(_CONDITIONAL_LABELS['flask_destroyed']),
            DRAWN: lambda: str(_localized_aggregate_label(DRAWN)),
        }
        for label, render in labels.items():
            rendered = {}
            for language in LANGUAGES:
                with translation.override(language):
                    rendered[language] = render()
            with self.subTest(label=label):
                self.assertEqual(5, len(set(rendered.values())),
                                 'a language fell back to English: %s' % rendered)
