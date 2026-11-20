# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""In the new look, a recovery form spaces its fields like the login card, its error wears the theme colour, and the notices above the login card line up with it."""
import io
import os
import re

from django.test import SimpleTestCase

from chardata.tests_the_setup_stylesheet_support import declared, stylesheet

REST = stylesheet('modern-rest.css')
TEMPLATES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'chardata')
FORM = 'html.fm-modern form.fm-account-form'
RECOVERY_FORMS = ('pw_recovery_email.html', 'password_reset_form.html')
NOTE = 'html.fm-modern p.fm-login-note'


def template(name):
    with io.open(os.path.join(TEMPLATES, name), encoding='utf-8') as handle:
        return handle.read()


class TheRecoveryFormsTests(SimpleTestCase):

    def test_both_recovery_forms_carry_the_account_class_on_the_form_itself(self):
        for name in RECOVERY_FORMS:
            with self.subTest(template=name):
                self.assertRegex(template(name), r'<form class="fm-account-form[ "]')

    def test_such_a_form_stacks_its_rows_twelve_pixels_apart(self):
        self.assertEqual(('flex', False), declared(REST, FORM, 'display'))
        self.assertEqual(('column', False), declared(REST, FORM, 'flex-direction'))
        self.assertEqual(('var(--fm-space-3)', False), declared(REST, FORM, 'gap'))
        self.assertEqual(('0', False), declared(REST, FORM + ' p', 'margin'))

    def test_a_label_sits_four_pixels_above_its_field(self):
        row = FORM + ' p:has(> label)'
        self.assertEqual(('column', False), declared(REST, row, 'flex-direction'))
        self.assertEqual(('var(--fm-space-1)', False), declared(REST, row, 'gap'))
        self.assertEqual(('calc(var(--fm-space-1) - var(--fm-space-3))', False),
                         declared(REST, FORM + ' > div:has(> .big-text)', 'margin-bottom'))

    def test_the_error_of_the_reset_form_wears_the_theme_colour_over_its_inline_red(self):
        self.assertEqual(('var(--fm-error-text)', True), declared(REST, 'html.fm-modern .fm-form-error', 'color'))
        self.assertIn('<p class="text fm-form-error" style="color: red; font-weight: bold;">{{ error_message }}</p>',
                      template('password_reset_form.html'))


class TheLoginNoticesTests(SimpleTestCase):

    def test_every_notice_above_the_login_card_carries_the_class(self):
        notices = re.findall(r'<p align="center" class="([^"]*)"', template('login.html'))
        self.assertEqual(3, len(notices))
        self.assertEqual([], [classes for classes in notices if 'fm-login-note' not in classes.split()])

    def test_a_notice_is_left_aligned_and_as_wide_as_the_card(self):
        self.assertEqual(('left', False), declared(REST, NOTE, 'text-align'))
        self.assertEqual(declared(REST, 'html.fm-modern .fm-login-card', 'max-width'), declared(REST, NOTE, 'max-width'))
        self.assertIsNotNone(declared(REST, NOTE, 'max-width'))
