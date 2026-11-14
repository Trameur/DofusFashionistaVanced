# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The login card of the modern design leaves the same gap above and below the forgotten password link, and the account form errors take the error colour of the theme."""
from django.test import SimpleTestCase

from chardata.tests_the_setup_stylesheet_support import chain_of, contrast, declared, rgb, stylesheet, winning

SHEETS = [(name, stylesheet(name)) for name in ('forms.css', 'modern.css')]
MODERN = SHEETS[1][1]
ROOT = 'html.fm-modern'
ERRORS = ('password-error', 'incorrect-password-error', 'username-taken-error', 'email-error',
          'wrong-password-error', 'login-error')
CARD = [('html', {}), ('div', {'class': 'fm-account-card fm-card fm-login-card fm-acct fm-seam'}),
        ('table', {}), ('tbody', {}), ('tr', {}), ('td', {})]


def error_colour(name, html_classes):
    chain = chain_of(CARD, 'label', {'id': name}, html_classes)
    return winning(SHEETS, chain, 'color', 375)[0]


class TheLoginCardTests(SimpleTestCase):

    def test_the_last_row_of_the_form_adds_no_margin_to_the_card_gap(self):
        self.assertEqual('0', declared(MODERN, ROOT + ' .fm-login-card table tr:last-child', 'margin-bottom')[0])
        self.assertEqual('var(--fm-space-4)', declared(MODERN, ROOT + ' .fm-acct table tr', 'margin')[0].split()[-1])

    def test_every_account_error_takes_the_error_colour_of_the_theme(self):
        for name in ERRORS:
            for theme in ('fm-light', 'fm-dark'):
                self.assertEqual('var(--fm-error-text)', error_colour(name, ['fm-modern', theme]), name)

    def test_the_classic_design_keeps_its_red(self):
        for name in ERRORS:
            for theme in ('fm-light', 'fm-dark'):
                self.assertEqual('red', error_colour(name, [theme]), name)

    def test_the_error_colour_is_readable_on_the_card_surfaces_of_every_theme(self):
        themes = [rule['declarations'] for rule in MODERN if '--fm-error-text' in rule['declarations']]
        self.assertEqual(3, len(themes))
        for tokens in themes:
            ink = rgb(tokens['--fm-error-text'][0])[0]
            for surface in ('--fm-surface', '--fm-surface-2'):
                self.assertGreaterEqual(contrast(ink, rgb(tokens[surface][0])[0]), 4.5, surface)

    def test_a_shown_login_error_sits_under_the_field_with_a_gap(self):
        selector = ROOT + ' .fm-login-card #incorrect-password-error:not(:empty)'
        self.assertEqual('inline-block', declared(MODERN, selector, 'display')[0])
        self.assertEqual('var(--fm-space-1)', declared(MODERN, selector, 'margin-top')[0])
