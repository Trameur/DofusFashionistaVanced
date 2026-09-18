# -*- coding: utf-8 -*-
"""Retro is the one ruleset whose smithmagic odds Ankama published."""

import re

from django.test import TestCase

from chardata.forgemagie_odds import (CRITICAL_SUCCESS_FLOOR, DOCUMENTED_ODDS,
                                      NEUTRAL_CEILING, get_documented_odds)
from chardata.tests import SmithmagicOddsTests
from chardata.forgemagie_view import LOCALIZED_UI


class TheFiguresAsPublished(TestCase):

    def test_every_row_adds_to_a_hundred(self):
        for row in DOCUMENTED_ODDS:
            with self.subTest(case=row['key']):
                self.assertEqual(100, row['sc'] + row['n'] + row['ec'],
                                 msg=row)

    def test_no_row_breaks_the_bounds_the_same_post_states(self):
        # Neutral is at most 50%, critical success at least 1%
        for row in DOCUMENTED_ODDS:
            with self.subTest(case=row['key']):
                self.assertLessEqual(row['n'], NEUTRAL_CEILING, msg=row)
                self.assertGreaterEqual(row['sc'], CRITICAL_SUCCESS_FLOOR,
                                        msg=row)

    def test_the_six_situations_are_all_there(self):
        self.assertEqual(
            ['remount', 'perfect', 'remount_hard', 'create_best',
             'create_worst', 'create_nosink'],
            [row['key'] for row in DOCUMENTED_ODDS])

    def test_creating_without_a_sink_is_the_worst_case(self):
        # Page order: easiest first, 99% failure last
        worst = DOCUMENTED_ODDS[-1]
        self.assertEqual('create_nosink', worst['key'])
        self.assertEqual(99, worst['ec'])
        self.assertEqual(max(row['ec'] for row in DOCUMENTED_ODDS),
                         worst['ec'])

    def test_only_retro_has_a_published_source(self):
        self.assertEqual(6, len(get_documented_odds('retro')))
        for ruleset in ('modern', 'dofus2', 'touch'):
            with self.subTest(ruleset=ruleset):
                self.assertEqual((), get_documented_odds(ruleset))


class EveryLanguageCanRenderThem(TestCase):

    def test_each_row_has_a_label_in_each_language(self):
        keys = ['odds_%s' % row['key'] for row in DOCUMENTED_ODDS]
        keys += ['odds_title', 'odds_intro', 'odds_source', 'odds_col_case',
                 'odds_col_sc', 'odds_col_n', 'odds_col_ec',
                 'how_malus', 'how_disclaimer_retro']
        for language, texts in LOCALIZED_UI.items():
            for key in keys:
                with self.subTest(language=language, key=key):
                    self.assertIn(key, texts)
                    self.assertTrue(texts[key].strip(), msg=key)

    def test_no_language_left_the_english_label_behind(self):
        english = LOCALIZED_UI['en']
        for language in ('fr', 'es', 'pt', 'de'):
            with self.subTest(language=language):
                same = [key for key in ('odds_title', 'odds_intro',
                                        'odds_remount', 'how_malus')
                        if LOCALIZED_UI[language][key] == english[key]]
                self.assertEqual([], same)


class ThePageSaysIt(TestCase):

    def _body(self, path):
        response = self.client.get(path, HTTP_ACCEPT_LANGUAGE='en')
        self.assertEqual(200, response.status_code, msg=path)
        return response.content.decode('utf-8')

    def test_the_retro_page_carries_the_table(self):
        body = self._body('/retro/forgemagie/')
        self.assertIn(LOCALIZED_UI['en']['odds_title'], body)
        for row in DOCUMENTED_ODDS:
            with self.subTest(case=row['key']):
                self.assertIn(LOCALIZED_UI['en']['odds_%s' % row['key']], body)

    def test_the_retro_page_no_longer_claims_nothing_was_published(self):
        body = self._body('/retro/forgemagie/')
        self.assertIn('1.27', body)
        self.assertNotIn(LOCALIZED_UI['en']['how_disclaimer'], body)

    def test_the_modern_page_still_says_nothing_was_published(self):
        body = self._body('/forgemagie/')
        self.assertIn(LOCALIZED_UI['en']['how_disclaimer'], body)
        self.assertNotIn(LOCALIZED_UI['en']['odds_title'], body)

    def test_every_page_states_the_malus_rule(self):
        # No version turns a malus into a bonus
        for path in ('/forgemagie/', '/retro/forgemagie/'):
            with self.subTest(path=path):
                self.assertIn(LOCALIZED_UI['en']['how_malus'],
                              self._body(path))

    def test_the_table_is_whole(self):
        body = self._body('/retro/forgemagie/')
        self.assertEqual(body.count('<table'), body.count('</table>'),
                         msg='unbalanced <table> in the rendered page')
        self.assertEqual(body.count('<tbody'), body.count('</tbody>'))
        block = body[body.index(LOCALIZED_UI['en']['odds_title']):]
        block = block[:block.index('</table>')]
        self.assertEqual(len(DOCUMENTED_ODDS) + 1, block.count('<tr'),
                         msg='the odds table does not hold one row per case '
                             'plus its header')

    def test_the_french_page_reads_french(self):
        body = self._body('/fr/retro/forgemagie/')
        self.assertIn(LOCALIZED_UI['fr']['odds_title'], body)


class AMalusLineStopsAtZero(TestCase):
    """The ceiling lives in the page script, read from the served page."""

    def _script(self):
        body = self.client.get('/retro/forgemagie/').content.decode('utf-8')
        match = re.search(r'function lineCeiling\(row\)\s*\{(.*?)\n        \}',
                          body, re.S)
        self.assertIsNotNone(match, msg='lineCeiling is no longer in the page')
        return match.group(1)

    def test_the_ceiling_returns_zero_for_a_negative_roll(self):
        script = self._script()
        self.assertIn('maxRoll < 0', script)
        self.assertIn('config.overCap', script)

    def test_the_items_that_need_it_are_not_a_handful(self):
        from fashionistapulp.structure import get_structure
        from chardata.forgemagie_data import MAGEABLE_TYPES
        structure = get_structure()
        mageable = negative = 0
        for item in structure.get_items_list():
            if structure.get_type_name_by_id(item.type) not in MAGEABLE_TYPES:
                continue
            mageable += 1
            if any(value < 0 for _stat_id, value in item.stats):
                negative += 1
        self.assertGreater(mageable, 1000, msg=mageable)
        self.assertGreater(negative, 100, msg=negative)


class TheSimulatorReadsThePublishedLadder(TestCase):
    """Retro splits critical and neutral on the six published points."""

    PAGE = SmithmagicOddsTests.PAGE
    MATHS = SmithmagicOddsTests.MATHS
    _function = SmithmagicOddsTests._function
    _model = SmithmagicOddsTests._model
    _ring_rows = SmithmagicOddsTests._ring_rows
    _run = SmithmagicOddsTests._run

    version = 'retro'

    def _ring_rows(self):
        # Inherited one depends on the active game version; nothing here reads it
        return []

    def _config(self):
        from chardata.forgemagie_data import (
            OVER_WEIGHT_CAP, get_fm_stats, get_one_percent_over_weight,
            get_ruleset)
        from chardata.forgemagie_odds import get_odds_ladder
        stats = {}
        for key, fm_stat in get_fm_stats(self.version).items():
            stats[key] = {
                'density': fm_stat['density'],
                'tiers': [{'name': tier, 'bonus': bonus,
                           'weight': round(bonus * fm_stat['density'], 2)}
                          for tier, bonus in fm_stat['tiers']],
            }
        return {'overCap': OVER_WEIGHT_CAP,
                'onePercentOverWeight': get_one_percent_over_weight(self.version),
                'oddsLadder': get_odds_ladder(get_ruleset(self.version)),
                'stats': stats}

    SWEEP = ("var out = [];"
             "for (var i = 0; i <= 100; i++) {"
             "    var c = documentedSplit(i / 100);"
             "    out.push([i / 100, c.sc, c.sn, c.ec]);"
             "}"
             "console.log(JSON.stringify(out));")

    EASY_THROW = ("var session = {rows: [], sink: 0};"
                  "var row = {key: 'vit', value: 20, min: 10, max: 200,"
                  "           target: 0, exo: false};"
                  "console.log(JSON.stringify("
                  "    chancesFor(row, config.stats.vit.tiers[0])));")

    def test_the_sweep_actually_read_something(self):
        rows = self._run(self.SWEEP)
        self.assertEqual(101, len(rows))
        self.assertEqual(4, len(rows[0]))

    def test_the_three_outcomes_always_add_to_one(self):
        for step, sc, sn, ec in self._run(self.SWEEP):
            with self.subTest(pass_rate=step):
                self.assertAlmostEqual(1.0, sc + sn + ec, places=9)

    def test_neutral_never_passes_the_published_ceiling(self):
        for step, _sc, sn, _ec in self._run(self.SWEEP):
            with self.subTest(pass_rate=step):
                self.assertLessEqual(sn, NEUTRAL_CEILING / 100.0 + 1e-9)

    def test_a_critical_success_never_falls_under_one_percent(self):
        for step, sc, _sn, _ec in self._run(self.SWEEP):
            with self.subTest(pass_rate=step):
                self.assertGreaterEqual(sc, CRITICAL_SUCCESS_FLOOR / 100.0 - 1e-9)

    def test_the_two_ends_are_the_rows_as_published(self):
        read = dict((round(step, 2), (sc, sn, ec))
                    for step, sc, sn, ec in self._run(self.SWEEP))
        self.assertEqual((0.66, 0.34, 0.0),
                         tuple(round(value, 4) for value in read[1.0]))
        self.assertEqual((0.01, 0.0, 0.99),
                         tuple(round(value, 4) for value in read[0.0]))

    def test_a_critical_success_only_gets_rarer_as_failure_grows(self):
        rows = self._run(self.SWEEP)
        criticals = [sc for _step, sc, _sn, _ec in rows]
        self.assertEqual(criticals, sorted(criticals),
                         msg='critical success is not monotone in ease')

    def test_a_real_retro_throw_is_no_longer_mostly_neutral(self):
        read = self._run(self.EASY_THROW)
        self.assertLessEqual(read['sn'], 0.50 + 1e-9)
        self.assertGreater(read['sc'], read['sn'])
        self.assertAlmostEqual(0.594, read['sc'], places=3)
        self.assertAlmostEqual(0.386, read['sn'], places=3)
        self.assertAlmostEqual(0.020, read['ec'], places=3)
        self.assertAlmostEqual(1.0, read['sc'] + read['sn'] + read['ec'],
                               places=9)


class TheModernModelIsUntouched(TheSimulatorReadsThePublishedLadder):
    """Nothing published for the modern game: its fitted split stays."""

    version = 'dofus3'

    def test_the_ladder_is_empty_for_this_version(self):
        self.assertEqual([], self._config()['oddsLadder'])

    def test_the_same_throw_still_reads_more_than_half_neutral(self):
        read = self._run(self.EASY_THROW)
        self.assertGreater(read['sn'], 0.50)
        self.assertAlmostEqual(0.588, read['sn'], places=3)

    # No ladder to test
    test_the_sweep_actually_read_something = None
    test_the_three_outcomes_always_add_to_one = None
    test_neutral_never_passes_the_published_ceiling = None
    test_a_critical_success_never_falls_under_one_percent = None
    test_the_two_ends_are_the_rows_as_published = None
    test_a_critical_success_only_gets_rarer_as_failure_grows = None
    test_a_real_retro_throw_is_no_longer_mostly_neutral = None
