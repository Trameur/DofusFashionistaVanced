# -*- coding: utf-8 -*-
"""Retro is the one ruleset whose smithmagic odds Ankama actually published.

The page used to tell every reader that Ankama never published the success
formula. For the modern game that is still true; for the Retro line it was
wrong, and it had a cost: the Retro column of the weight table kept a figure
measured on the modern game "for want of a Retro measurement", while a dev
post of 18 May 2009 had described the 1.27 system and put numbers on six
situations.

These tests hold three things: the figures as transcribed, the fact that they
reach the Retro page and only the Retro page, and the rule from the same post
that the workbench was breaking -- a malus can be cancelled, never turned into
a bonus.
"""

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
        # "Les probabilités maximums de résultat Neutre sont de 50%" and
        # "les probabilités de Succès Critique sont toujours au minimum de 1%".
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
        # The ordering carries meaning on the page: easiest first, and the
        # 99% failure row last. A reordering that broke it would mislead.
        worst = DOCUMENTED_ODDS[-1]
        self.assertEqual('create_nosink', worst['key'])
        self.assertEqual(99, worst['ec'])
        self.assertEqual(max(row['ec'] for row in DOCUMENTED_ODDS),
                         worst['ec'])

    def test_only_retro_has_a_published_source(self):
        self.assertEqual(6, len(get_documented_odds('retro')))
        # Controls: handing these to a ruleset they never described would be
        # worse than saying nothing.
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
        # A copied block that was never translated shows up as the English
        # string sitting in another language.
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
        # Control. Without it, a fix that simply deleted the disclaimer
        # everywhere would pass the test above.
        body = self._body('/forgemagie/')
        self.assertIn(LOCALIZED_UI['en']['how_disclaimer'], body)
        self.assertNotIn(LOCALIZED_UI['en']['odds_title'], body)

    def test_every_page_states_the_malus_rule(self):
        # This one is not Retro-only: no version of the game turns a malus
        # into a bonus, and the workbench enforces it for all of them.
        for path in ('/forgemagie/', '/retro/forgemagie/'):
            with self.subTest(path=path):
                self.assertIn(LOCALIZED_UI['en']['how_malus'],
                              self._body(path))

    def test_the_table_is_whole(self):
        """A table opened and never closed swallows the rest of the page."""
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
    """The workbench let a -30 agility line be targeted at +101.

    The ceiling is computed in the page script, so the test reads the script
    the page actually serves rather than a copy of the rule.
    """

    def _script(self):
        body = self.client.get('/retro/forgemagie/').content.decode('utf-8')
        match = re.search(r'function lineCeiling\(row\)\s*\{(.*?)\n        \}',
                          body, re.S)
        self.assertIsNotNone(match, msg='lineCeiling is no longer in the page')
        return match.group(1)

    def test_the_ceiling_returns_zero_for_a_negative_roll(self):
        script = self._script()
        self.assertIn('maxRoll < 0', script)
        # Control: the cap for ordinary lines must still be there, or the
        # test above would pass on a function that returns 0 for everything.
        self.assertIn('config.overCap', script)

    def test_the_items_that_need_it_are_not_a_handful(self):
        # A rule worth enforcing on 21% of mageable items, not on a curiosity.
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
    """The split between a critical success and a neutral one was a fitted
    40/60, which put neutral at 59% on an easy throw. The same dev post caps
    it at 50% and never shows a critical success under 1%. For Retro the split
    is now read off the six published points instead.

    The maths live in the page script, so these run it: the node harness the
    modern odds tests already use, handed a Retro config.
    """

    PAGE = SmithmagicOddsTests.PAGE
    MATHS = SmithmagicOddsTests.MATHS
    _function = SmithmagicOddsTests._function
    _model = SmithmagicOddsTests._model
    _ring_rows = SmithmagicOddsTests._ring_rows
    _run = SmithmagicOddsTests._run

    version = 'retro'

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
        # Without this, every loop below passes on an empty list: a harness
        # that returned nothing would look like a model that never errs.
        rows = self._run(self.SWEEP)
        self.assertEqual(101, len(rows))
        self.assertEqual(4, len(rows[0]))

    def test_the_three_outcomes_always_add_to_one(self):
        for step, sc, sn, ec in self._run(self.SWEEP):
            with self.subTest(pass_rate=step):
                self.assertAlmostEqual(1.0, sc + sn + ec, places=9)

    def test_neutral_never_passes_the_published_ceiling(self):
        # "Les probabilités maximums de résultat Neutre sont de 50%."
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
        # Control on the interpolation: a ladder read backwards, or two rungs
        # swapped, shows up here and nowhere else.
        rows = self._run(self.SWEEP)
        criticals = [sc for _step, sc, _sn, _ec in rows]
        self.assertEqual(criticals, sorted(criticals),
                         msg='critical success is not monotone in ease')

    def test_a_real_retro_throw_is_no_longer_mostly_neutral(self):
        read = self._run(self.EASY_THROW)
        self.assertLessEqual(read['sn'], 0.50 + 1e-9)
        self.assertGreater(read['sc'], read['sn'])
        # The same throw the modern model reads as 39 / 59 / 2. Pinned so the
        # figures quoted for this change stay measured rather than recomputed.
        self.assertAlmostEqual(0.594, read['sc'], places=3)
        self.assertAlmostEqual(0.386, read['sn'], places=3)
        self.assertAlmostEqual(0.020, read['ec'], places=3)
        self.assertAlmostEqual(1.0, read['sc'] + read['sn'] + read['ec'],
                               places=9)


class TheModernModelIsUntouched(TheSimulatorReadsThePublishedLadder):
    """Control, and the measurement of what was wrong.

    Nothing was ever published for the modern game, so its fitted split stays
    exactly as it was -- including the neutral share above 50% that the Retro
    source forbids. Correcting it from a 1.27 document would be inventing a
    measurement, not making one.
    """

    version = 'dofus3'

    def test_the_ladder_is_empty_for_this_version(self):
        self.assertEqual([], self._config()['oddsLadder'])

    def test_the_same_throw_still_reads_more_than_half_neutral(self):
        read = self._run(self.EASY_THROW)
        self.assertGreater(read['sn'], 0.50)
        self.assertAlmostEqual(0.588, read['sn'], places=3)

    # The ladder tests above have nothing to run without a ladder.
    test_the_sweep_actually_read_something = None
    test_the_three_outcomes_always_add_to_one = None
    test_neutral_never_passes_the_published_ceiling = None
    test_a_critical_success_never_falls_under_one_percent = None
    test_the_two_ends_are_the_rows_as_published = None
    test_a_critical_success_only_gets_rarer_as_failure_grows = None
    test_a_real_retro_throw_is_no_longer_mostly_neutral = None
