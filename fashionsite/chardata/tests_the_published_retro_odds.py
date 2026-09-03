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
