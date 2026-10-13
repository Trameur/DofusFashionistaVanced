# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The /setup/ doors sit in a wrapping flex row inside the form column in every design and theme, so a long label or a narrow column never pushes a door past the column."""
from django.test import SimpleTestCase, TestCase

from chardata.tests_every_preset_keeps_its_weights_and_minimums import VERSIONS
from chardata.tests_the_setup_page_draws_the_live_weights_panel import _Versioned, setup_page
from chardata.tests_the_setup_stylesheet_support import (
    DESIGNS, chain_of, declared, matching, setup_sheets, stylesheet, winning)

SETUP = stylesheet('setup.css')
WIDTHS = (375, 480, 481, 900, 901, 1024, 1100, 1920)
LANGUAGES = ('en', 'fr', 'es', 'pt', 'de')


def doors(page):
    primary = [found for found in page.find('input', name='optimize')]
    secondary = [found for found in page.find('input')
                 if 'setup-secondary' in (found[0].get('class') or '').split()]
    return primary, secondary


class TheDoorsAreDrawnInAWrappingRowTests(_Versioned, TestCase):

    def test_the_optimize_door_stands_alone_and_the_other_two_share_one_wrapping_row(self):
        for version in VERSIONS:
            for language in LANGUAGES:
                with self.subTest(version=version, language=language):
                    _html, page = setup_page(self.client, version, language)
                    primary, secondary = doors(page)
                    self.assertEqual(1, len(primary))
                    self.assertTrue(page.inside(primary[0][1], 'div', 'submit-mode'))
                    self.assertEqual(['byhand', 'wizard'], [attrs['name'] for attrs, _ in secondary])
                    for attrs, ancestors in secondary:
                        self.assertTrue(page.inside(ancestors, 'div', 'submit-mode'))
                        self.assertEqual('div', ancestors[-1][0])
                        self.assertIn('setup-doors-secondary', ancestors[-1][1]['class'].split())

    def test_the_default_door_stays_first_in_the_form_so_enter_still_goes_to_the_hand_door(self):
        _html, page = setup_page(self.client, 'dofus3')
        submits = [attrs for attrs, ancestors in page.find('input', type='submit')
                   if page.inside(ancestors, 'div', 'submit-mode')]
        self.assertEqual(['setup-default-door'], submits[0]['class'].split())
        self.assertEqual('byhand', submits[0]['name'])


class TheStylesheetLetsTheRowWrapTests(SimpleTestCase):

    def test_the_container_stacks_the_primary_door_above_the_secondary_row(self):
        self.assertEqual(('flex', False), declared(SETUP, '.setup-doors', 'display'))
        self.assertEqual(('column', False), declared(SETUP, '.setup-doors', 'flex-direction'))
        self.assertEqual(('center', False), declared(SETUP, '.setup-doors', 'align-items'))

    def test_the_secondary_row_wraps_and_centres_its_doors(self):
        self.assertEqual(('flex', False), declared(SETUP, '.setup-doors-secondary', 'display'))
        self.assertEqual(('wrap', False), declared(SETUP, '.setup-doors-secondary', 'flex-wrap'))
        self.assertEqual(('center', False),
                         declared(SETUP, '.setup-doors-secondary', 'justify-content'))
        self.assertEqual(('100%', False), declared(SETUP, '.setup-doors-secondary', 'max-width'))

    def test_no_rule_gives_the_doors_a_grid_that_cannot_shrink(self):
        for rule in SETUP:
            if any('.setup-doors' in selector for selector in rule['selectors']):
                with self.subTest(selectors=rule['selectors']):
                    self.assertNotIn('grid-template-columns', rule['declarations'])
                    self.assertNotIn('grid-column', rule['declarations'])
                    self.assertNotEqual('grid', rule['declarations'].get('display', ('',))[0])

    def test_a_phone_stretches_the_doors_and_lets_the_secondary_ones_share_the_row(self):
        phone = '(max-width: 480px)'
        self.assertEqual(('stretch', False), declared(SETUP, '.setup-doors', 'align-items', phone))
        self.assertEqual(('1 1 auto', False),
                         declared(SETUP, '.setup-doors-secondary .setup-secondary', 'flex', phone))
        self.assertEqual(1, len(matching(SETUP, '.setup-doors', phone)))


class EveryDoorStaysInsideItsColumnInEveryDesignTests(_Versioned, TestCase):

    def test_the_cascade_lets_every_door_wrap_and_never_outgrow_its_row(self):
        sheets = setup_sheets()
        _html, page = setup_page(self.client, 'dofus3')
        primary, secondary = doors(page)
        for attrs, ancestors in primary + secondary:
            for design, classes in DESIGNS.items():
                chain = chain_of(ancestors, 'input', attrs, classes)
                for width in WIDTHS:
                    with self.subTest(door=attrs['name'], design=design, width=width):
                        wrap = winning(sheets, chain, 'white-space', width)
                        self.assertEqual('normal', wrap[0], wrap)
                        limit = winning(sheets, chain, 'max-width', width)
                        self.assertEqual('100%', limit[0], limit)
                        sizing = winning(sheets, chain, 'box-sizing', width)
                        self.assertEqual('border-box', sizing[0], sizing)
