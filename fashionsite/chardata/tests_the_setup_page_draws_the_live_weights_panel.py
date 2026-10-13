# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The /setup/ page draws the read-only weights and minimums panel and sends nothing new with the form."""
import json
import os
import re
from html.parser import HTMLParser

from django.test import TestCase
from django.urls import resolve

from chardata import setup_preview
from chardata.models import Char
from chardata.presets import DEFAULT_PRIORITY, GUARD_KIND, GUARD_PERCENTS
from chardata.setup_preview import panel_context
from chardata.tests_every_preset_keeps_its_weights_and_minimums import VERSIONS, _version_path
from fashionistapulp.structure import set_current_game_version
from fashionistapulp.temporix import version_has_temporix

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'chardata', 'setup.js')
LANGUAGES = ('en', 'fr', 'es', 'pt', 'de')
VOID = frozenset(('area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta',
                  'param', 'source', 'track', 'wbr'))
PANEL_FIELD_PREFIXES = ('weight_', 'min_', 'weights_reset')


class _Page(HTMLParser):
    """Keeps the open ancestors of every tag, so a test can ask where an element sits."""

    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.h1 = 0
        self.elements = []
        self.feed(html)
        self.close()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'h1':
            self.h1 += 1
        self.elements.append((tag, attrs, tuple(self.stack)))
        if tag not in VOID:
            self.stack.append((tag, attrs))

    def handle_startendtag(self, tag, attrs):
        self.elements.append((tag, dict(attrs), tuple(self.stack)))

    def handle_endtag(self, tag):
        for depth in range(len(self.stack) - 1, -1, -1):
            if self.stack[depth][0] == tag:
                del self.stack[depth:]
                return

    def find(self, tag=None, **attrs):
        return [(a, ancestors) for name, a, ancestors in self.elements
                if (tag is None or name == tag)
                and all(a.get(key.replace('_', '-')) == value for key, value in attrs.items())]

    def inside(self, ancestors, tag, element_id):
        return any(name == tag and a.get('id') == element_id for name, a in ancestors)


def setup_page(client, version, language='en'):
    response = client.get(_version_path(version, '/setup/'), HTTP_ACCEPT_LANGUAGE=language)
    assert response.status_code == 200, (version, language, response.status_code)
    return response.content.decode('utf-8'), _Page(response.content.decode('utf-8'))


class _Versioned(object):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')


class EverySetupPageDrawsOnePanelTests(_Versioned, TestCase):

    def test_every_version_and_language_draws_the_panel_once_with_one_title(self):
        problems = []
        for version in VERSIONS:
            for language in LANGUAGES:
                _html, page = setup_page(self.client, version, language)
                asides = page.find('aside', id='setup-preview')
                states = page.find('script', id='wm-state')
                defaults = page.find('script', id='wm-defaults')
                sheets = [a for a, _ in page.find('link') if 'setup.css' in a.get('href', '')]
                scripts = [a.get('src', '') for a, _ in page.find('script')]
                found = (page.h1, len(asides), len(states), len(defaults), len(sheets),
                         sum('chardata/setup.js' in src for src in scripts),
                         sum('chardata/weights_minimums.js' in src for src in scripts))
                if found != (1, 1, 1, 1, 1, 1, 1):
                    problems.append((version, language, found))
        self.assertEqual([], problems)

    def test_the_preview_address_is_the_route_of_the_same_version(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                _html, page = setup_page(self.client, version)
                address = page.find('aside', id='setup-preview')[0][0]['data-preview-url']
                self.assertEqual(_version_path(version, '/setuppreview/'), address)
                match = resolve(address)
                self.assertIs(setup_preview.setup_preview, match.func)
                self.assertEqual('setup_preview', match.url_name)

    def test_the_address_answers_with_the_state_the_panel_shows(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                _html, page = setup_page(self.client, version)
                address = page.find('aside', id='setup-preview')[0][0]['data-preview-url']
                first_class = page.find('select', id='select-char-class')
                classes = [a['value'] for a, ancestors in page.find('option')
                           if any(name == 'select' and attrs.get('id') == 'select-char-class'
                                  for name, attrs in ancestors)]
                self.assertTrue(first_class and classes)
                response = self.client.get(address, {'class': classes[0], 'level': '200'})
                self.assertEqual(200, response.status_code)
                state = response.json()
                self.assertTrue({'weights', 'minimums', 'ranges', 'members', 'caps'} <= set(state))

    def test_the_panel_is_hidden_until_the_script_has_a_preview_to_show(self):
        _html, page = setup_page(self.client, 'dofus3')
        aside = page.find('aside', id='setup-preview')[0][0]
        self.assertIn('hidden', aside)
        block = page.find('div', id='setup-preview-block')[0][0]
        self.assertIn('hidden', block)


class ThePanelSendsNothingWithTheFormTests(_Versioned, TestCase):

    def test_the_panel_is_outside_the_form_and_has_no_named_field(self):
        problems = []
        for version in VERSIONS:
            _html, page = setup_page(self.client, version)
            for tag in ('input', 'select', 'textarea', 'button'):
                for attrs, ancestors in page.find(tag):
                    if not page.inside(ancestors, 'aside', 'setup-preview'):
                        continue
                    if page.inside(ancestors, 'form', 'main_form'):
                        problems.append((version, 'inside the form', attrs.get('id')))
                    if 'name' in attrs:
                        problems.append((version, 'named', attrs['name']))
                    if tag == 'input' and 'disabled' not in attrs:
                        problems.append((version, 'editable', attrs.get('id')))
            self.assertEqual([], [a for a, ancestors in page.find('form')
                                  if page.inside(ancestors, 'aside', 'setup-preview')])
        self.assertEqual([], problems)

    def test_the_form_still_has_only_the_fields_it_had(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                _html, page = setup_page(self.client, version)
                names = {attrs['name'] for tag in ('input', 'select')
                         for attrs, ancestors in page.find(tag)
                         if 'name' in attrs and page.inside(ancestors, 'form', 'main_form')}
                self.assertFalse([name for name in names
                                  if name.startswith(PANEL_FIELD_PREFIXES)])
                self.assertTrue({'class', 'level', 'charname', 'project', 'priority', 'play_mode',
                                 'guard_pct', 'csrfmiddlewaretoken'} <= names)

    def test_every_panel_input_is_labelled_by_elements_the_page_has(self):
        _html, page = setup_page(self.client, 'dofus3')
        ids = {attrs['id'] for _tag, attrs, _ancestors in page.elements if 'id' in attrs}
        inputs = [attrs for attrs, ancestors in page.find('input')
                  if page.inside(ancestors, 'aside', 'setup-preview')]
        self.assertGreater(len(inputs), 40)
        missing = [attrs['id'] for attrs in inputs
                   if not set(attrs.get('aria-labelledby', '').split()) <= ids
                   or not attrs.get('aria-labelledby')]
        self.assertEqual([], missing)

    def test_the_panel_has_no_reset_button_and_no_slider(self):
        _html, page = setup_page(self.client, 'dofus3')
        self.assertEqual([], page.find('button', id='button-reset-weights'))
        self.assertEqual([], [a for a, _ in page.find('div')
                              if 'wm-slider' in a.get('class', '').split()])


class TheFieldsTheScriptReadsAreInTheFormTests(_Versioned, TestCase):
    """The script reads the form, so a field it reads that left the form would leave the preview wrong with every other test green."""

    FIELD_IDS = ('select-char-class', 'input-char-level', 'play-mode', 'guard-percent')
    TEMPORIX_ONLY = ('temporix-cb',)

    def script_ids(self):
        source = open(SCRIPT, encoding='utf-8').read()
        return set(re.findall(r"'#([A-Za-z][\w-]*)'", source))

    def test_the_script_names_the_ids_this_module_checks(self):
        ids = self.script_ids()
        self.assertTrue(set(self.FIELD_IDS) <= ids)
        self.assertIn('temporix-cb', ids)
        self.assertIn('main_form', ids)

    def test_every_id_the_script_looks_up_is_on_the_page(self):
        ids = self.script_ids()
        for version in VERSIONS:
            with self.subTest(version=version):
                _html, page = setup_page(self.client, version)
                drawn = {attrs['id'] for _tag, attrs, _ancestors in page.elements if 'id' in attrs}
                expected = ids if version_has_temporix(version) else ids - set(self.TEMPORIX_ONLY)
                self.assertEqual([], sorted(expected - drawn))
                if not version_has_temporix(version):
                    self.assertNotIn('temporix-cb', drawn)

    def test_every_field_the_script_reads_sits_inside_the_form(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                _html, page = setup_page(self.client, version)
                outside = []
                for element_id in self.FIELD_IDS + (self.TEMPORIX_ONLY if version_has_temporix(version) else ()):
                    found = [ancestors for attrs, ancestors in page.find(id=element_id)]
                    if len(found) != 1 or not page.inside(found[0], 'form', 'main_form'):
                        outside.append(element_id)
                self.assertEqual([], outside)

    def test_the_priority_choices_sit_inside_the_form(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                _html, page = setup_page(self.client, version)
                radios = page.find('input', type='radio', name='priority')
                self.assertGreaterEqual(len(radios), 2)
                for attrs, ancestors in radios:
                    self.assertTrue(page.inside(ancestors, 'form', 'main_form'), attrs)

    def test_the_boxes_the_page_script_draws_land_inside_the_form_under_the_name_the_script_reads(self):
        template = os.path.join(os.path.dirname(SCRIPT), '..', '..', 'templates', 'chardata',
                                'projdetails.html')
        drawn = open(template, encoding='utf-8').read()
        read = open(SCRIPT, encoding='utf-8').read()
        self.assertIn('name="check_\' + aspect', drawn)
        self.assertIn('name^="check_"', read)
        for version in VERSIONS:
            with self.subTest(version=version):
                _html, page = setup_page(self.client, version)
                table = page.find('table', id='table-checkboxes')
                self.assertEqual(1, len(table))
                self.assertTrue(page.inside(table[0][1], 'form', 'main_form'))
                for column in range(4):
                    cells = page.find('td', id='table-checkboxes-column-%d' % column)
                    self.assertEqual(1, len(cells), column)
                    self.assertTrue(page.inside(cells[0][1], 'table', 'table-checkboxes'), column)

    def test_the_hidden_mode_field_is_named_as_the_form_posts_it(self):
        _html, page = setup_page(self.client, 'dofus3')
        attrs = page.find(id='play-mode')[0][0]
        self.assertEqual('play_mode', attrs.get('name'))
        self.assertEqual('hidden', attrs.get('type'))


class TheSafeguardLineTests(_Versioned, TestCase):

    def test_the_line_waits_hidden_inside_the_panel_body(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                _html, page = setup_page(self.client, version)
                lines = page.find('p', id='setup-preview-guard')
                self.assertEqual(1, len(lines))
                attrs, ancestors = lines[0]
                self.assertIn('hidden', attrs)
                self.assertTrue(page.inside(ancestors, 'aside', 'setup-preview'))
                self.assertTrue(page.inside(ancestors, 'div', 'setup-preview-body'))

    def test_the_page_hands_the_script_the_kind_of_each_priority_that_has_a_safeguard(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                html, page = setup_page(self.client, version)
                scripts = page.find('script', id='setup-guard-kinds')
                self.assertEqual(1, len(scripts))
                match = re.search(r'<script id="setup-guard-kinds" type="application/json">(.*?)</script>',
                                  html, re.S)
                self.assertEqual(GUARD_KIND, json.loads(match.group(1)))

    def test_every_priority_but_the_default_has_a_kind_and_the_default_has_none(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                _html, page = setup_page(self.client, version)
                offered = {attrs['value'] for attrs, _ in page.find('input', type='radio', name='priority')}
                self.assertIn(DEFAULT_PRIORITY, offered)
                self.assertEqual(offered - {DEFAULT_PRIORITY}, set(GUARD_KIND))

    def test_the_select_the_line_reads_offers_the_percents_the_server_accepts(self):
        _html, page = setup_page(self.client, 'dofus3')
        offered = [attrs['value'] for attrs, ancestors in page.find('option')
                   if any(name == 'select' and a.get('id') == 'guard-percent' for name, a in ancestors)]
        self.assertEqual([str(percent) for percent in GUARD_PERCENTS], offered)


class ThePanelContextTests(_Versioned, TestCase):

    def test_each_version_gets_rows_with_nothing_saved_and_one_open_section(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                context = panel_context(version)
                self.assertTrue(context['wm_readonly'])
                self.assertEqual([], context['others'])
                self.assertFalse(context['combined_open'])
                self.assertFalse(context['temporix_on'])
                self.assertTrue(context['sections'])
                self.assertEqual(['apmprange'], [section['key'] for section in context['sections']
                                                 if section['open']])
                self.assertIn('caps', context['wm_state'])
                self.assertEqual(version == 'touch', context['temporix_switch'])

    def test_the_context_leaves_the_game_version_as_it_found_it(self):
        set_current_game_version('retro')
        panel_context('touch')
        from fashionistapulp.structure import get_current_game_version
        self.assertEqual('retro', get_current_game_version())


class TheOtherSetupPagesAreUnchangedTests(_Versioned, TestCase):

    def test_the_edit_page_draws_no_panel(self):
        post = {'project': 'Edited', 'charname': 'Edited', 'level': '200', 'class': 'Iop',
                'byhand': 'byhand'}
        self.assertEqual(302, self.client.post('/createproject/', post).status_code)
        char = Char.objects.latest('pk')
        response = self.client.get('/project/%d/' % char.pk)
        self.assertEqual(200, response.status_code)
        html = response.content.decode('utf-8')
        for marker in ('setup-preview', 'setup.css', 'setup.js', 'wm-state', 'setup-layout'):
            self.assertNotIn(marker, html)

    def test_a_visitor_who_cannot_create_another_build_gets_no_panel(self):
        post = {'project': 'First', 'charname': 'First', 'level': '200', 'class': 'Iop',
                'byhand': 'byhand'}
        self.assertEqual(302, self.client.post('/createproject/', post).status_code)
        html = self.client.get('/setup/').content.decode('utf-8')
        for marker in ('setup-preview', 'setup.css', 'setup.js', 'wm-state'):
            self.assertNotIn(marker, html)
