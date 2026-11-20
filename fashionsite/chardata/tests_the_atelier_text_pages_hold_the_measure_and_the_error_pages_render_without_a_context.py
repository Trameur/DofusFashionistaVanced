# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The content, account, error and tool pages of the modern design: the illustrated text pages are one column below 1280 and an art column plus a text column held to the measure from 1280, the account forms sit in seamed cards without losing a field, a token or an id, the error pages and the base script render without any context, and the classic stylesheet keeps the values the privacy page used inline."""
import os
import re

from django.contrib.auth.models import AnonymousUser
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase, TestCase

from chardata.tests_the_setup_stylesheet_support import media_applies, stylesheet

MODERN = stylesheet('modern.css')
FORMS = stylesheet('forms.css')
ROOT = 'html.fm-modern'
ART = ROOT + ' table.fm-page-art > tbody > tr'
END = ROOT + ' table.fm-page-art-end > tbody > tr'
TEMPLATES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'chardata')
WIDTHS = [375, 768, 900, 901, 1279, 1280, 1440, 1920, 2560]
ART_PAGES = ['about', 'license', 'faq', 'check_your_email', 'recover_password', 'password_reset_form',
             'password_was_reset', '403', '404', '500', 'error', 'contacts', 'manage_account', 'login']
ERROR_PAGES = ['403', '404', '500', 'error']


def at(selector, prop, width):
    found = None
    for rule in MODERN:
        if selector in rule['selectors'] and prop in rule['declarations'] and media_applies(rule['media'], width):
            found = rule['declarations'][prop][0]
    return found


def template(name):
    with open(os.path.join(TEMPLATES, name + '.html'), encoding='utf-8') as handle:
        return handle.read()


def track_count(value):
    return len(re.sub(r'minmax\((?:[^()]|\([^()]*\))*\)', 'x', value).split())


class TheTextPageGridTests(SimpleTestCase):

    def test_one_track_below_1280_and_two_from_1280(self):
        for width in WIDTHS:
            self.assertEqual(2 if width >= 1280 else 1, track_count(at(ART, 'grid-template-columns', width)), width)

    def test_the_text_track_is_capped_at_the_measure_from_1280(self):
        for rule in (ART, END):
            self.assertIn('minmax(0,var(--fm-measure))', at(rule, 'grid-template-columns', 1280).replace(' ', ''))

    def test_the_art_ends_the_row_on_the_end_variant_and_starts_it_otherwise(self):
        start = at(ART, 'grid-template-columns', 1440).replace(' ', '')
        end = at(END, 'grid-template-columns', 1440).replace(' ', '')
        self.assertTrue(start.startswith('minmax(150px'))
        self.assertTrue(end.endswith('minmax(150px,220px)'))

    def test_the_table_and_its_body_are_blocks_at_every_width(self):
        for width in WIDTHS:
            self.assertEqual('block', at(ROOT + ' table.fm-page-art', 'display', width))
            self.assertEqual('grid', at(ART, 'display', width))

    def test_no_rule_of_the_lot_is_unprefixed(self):
        names = ('fm-page-art', 'fm-notice', 'fm-prose', 'fm-account-card', 'fm-register-row', 'fm-login-grid',
                 'fm-tool-frame', '.support-', '.dev-', '#c_form')
        seen = 0
        for rule in MODERN:
            for selector in rule['selectors']:
                if any(name in selector for name in names):
                    seen += 1
                    self.assertTrue(selector.startswith(ROOT), selector)
        self.assertGreater(seen, 30)

    def test_the_prose_class_keeps_the_privacy_values_in_the_classic_sheet(self):
        found = [rule for rule in FORMS if '.fm-prose' in rule['selectors']]
        self.assertEqual(1, len(found))
        self.assertEqual({'max-width': '820px', 'margin': '0 auto', 'text-align': 'left'},
                         {key: value[0] for key, value in found[0]['declarations'].items()})
        html = template('privacy')
        self.assertIn('class="big-text fm-prose"', html)
        self.assertNotIn('max-width: 820px', html)

    def test_the_modern_prose_is_held_to_the_measure(self):
        for width in WIDTHS:
            self.assertEqual('var(--fm-measure)', at(ROOT + ' .fm-prose', 'max-width', width))

    def test_every_illustrated_page_carries_the_class_on_one_table(self):
        for name in ART_PAGES:
            self.assertEqual(1, len(re.findall(r'<table[^>]*class="[^"]*fm-page-art[ "]', template(name))), name)


class TheAccountCardTests(SimpleTestCase):

    def test_the_forms_sit_in_one_card_rule(self):
        found = [rule for rule in MODERN if ROOT + ' .fm-account-card' in rule['selectors'] and 'background' in rule['declarations']]
        self.assertEqual(1, len(found))
        for selector in (ROOT + ' #c_form', ROOT + ' .fm-register-row'):
            self.assertIn(selector, found[0]['selectors'])
        self.assertNotIn('outline', found[0]['declarations'])
        for name in ('login', 'manage_account', 'contacts', 'password_reset_form', 'thankyou', 'nomessage'):
            self.assertIn('fm-seam', template(name), name)

    def test_the_login_template_keeps_every_field_and_token(self):
        html = template('login')
        for needle in ('id="login-username"', 'id="login-password"', 'id="login-enter"', 'id="register-form"',
                       'id="register-username"', 'id="password-confirm"', 'id="email"', 'id="password-actual"',
                       'class="google-login-form"', 'g-recaptcha'):
            self.assertIn(needle, html, needle)
        self.assertEqual(2, html.count('{% csrf_token %}'))
        self.assertIn('fm-account-card', html)
        self.assertIn('fm-register-row', html)

    def test_the_account_templates_keep_their_forms(self):
        self.assertIn('{% csrf_token %}', template('manage_account'))
        self.assertIn('id="main_form"', template('manage_account'))
        self.assertIn('{% csrf_token %}', template('password_reset_form'))
        for field in ('new_password', 'confirm_password'):
            self.assertIn('name="%s"' % field, template('password_reset_form'))
        self.assertIn('{% csrf_token %}', template('contacts'))

    def test_the_login_grid_hides_the_spacing_breaks(self):
        self.assertEqual('none', at(ROOT + ' .fm-login-grid > br', 'display', 375))


class TheMinimalContextTests(TestCase):

    def render(self, name):
        request = RequestFactory().get('/')
        request.user = AnonymousUser()
        request.session = {}
        return render_to_string('chardata/%s.html' % name, {}, request=request)

    def test_the_base_script_declares_its_two_tables_without_a_context(self):
        for name in ERROR_PAGES:
            html = self.render(name)
            self.assertNotRegex(html, r'var ajaxloader = ;')
            self.assertNotRegex(html, r'var images = ;')
            self.assertIn('var ajaxloader = {};', html)

    def test_every_error_page_renders_its_heading_and_art_table_without_a_context(self):
        for name in ERROR_PAGES:
            html = self.render(name)
            self.assertIn('<h1', html, name)
            self.assertIn('fm-page-art', html, name)

    def test_the_site_renders_its_own_404(self):
        response = self.client.get('/no-such-page-in-the-atelier/')
        self.assertEqual(404, response.status_code)
        self.assertContains(response, 'fm-page-art', status_code=404)

    def test_the_tool_pages_sit_inside_a_scrolling_frame(self):
        for name in ('edit_item', 'edit_set'):
            self.assertIn('<div class="fm-tool-frame">', template(name))
        self.assertEqual('auto', at(ROOT + ' .fm-tool-frame', 'overflow-x', 375))


class TheAdminToolsShellTests(TestCase):

    def test_the_admin_page_keeps_the_site_frame_around_its_tools(self):
        from django.contrib.auth.models import User
        User.objects.create_superuser('atelier-admin', 'atelier-admin@example.org', 'unused-in-this-test')
        self.client.force_login(User.objects.get(username='atelier-admin'))
        response = self.client.get('/admin-tools/')
        self.assertEqual(200, response.status_code)
        for needle in ('id="main-content"', 'class="maincontent"', 'class="admin-tools text"'):
            self.assertContains(response, needle)
