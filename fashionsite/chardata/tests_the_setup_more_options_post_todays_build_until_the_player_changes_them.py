# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The /setup/ "More options" section draws what a new build starts with, and its script marks only the groups the player changed."""
import json
import re

from django.contrib.auth.models import User
from django.test import TestCase

from chardata.models import Char, InventoryFolder
from chardata.options import get_options
from chardata.tests_a_setup_option_group_is_stored_only_when_the_player_changed_it import (
    _Creations, markers)
from chardata.tests_every_preset_keeps_its_weights_and_minimums import VERSIONS, _version_path
from chardata.tests_the_setup_page_draws_the_live_weights_panel import LANGUAGES, _Page, setup_page
from chardata.tests_the_setup_panel_strings_are_translated_in_five_languages import (
    DASH, EMOJI, FRENCH_POLITE, TRANSLATED, catalogue, template_message_ids)
from chardata.tests_the_setup_script_sends_the_form_and_shows_only_the_last_change import run_script
from fashionistapulp.exo_options import exo_count
from fashionistapulp.structure import get_structure, set_current_game_version

SECTION = 'setup-more'
TEMPLATE = 'setup_more_options.html'
LEVELS = (1, 60, 100, 150, 199, 200)


def section_table(html):
    found = re.findall(r'<script[^>]*id="setup-more-table"[^>]*>(.*?)</script>', html, re.S)
    assert len(found) == 1, len(found)
    return json.loads(found[0])


def group_fields(table):
    return [name for _group, names in table['groups'] for name in names]


def drawn_values(page):
    """What the untouched section posts, read from the controls the page draws."""
    values = {}
    for tag in ('input', 'select'):
        for attrs, ancestors in page.find(tag):
            if not page.inside(ancestors, 'details', SECTION) or 'name' not in attrs:
                continue
            name = attrs['name']
            values.setdefault(name, None)
            if 'disabled' in attrs:
                continue
            if attrs.get('type') in ('radio', 'checkbox'):
                if 'checked' in attrs:
                    values[name] = attrs.get('value') or 'on'
            elif tag == 'input':
                values[name] = attrs.get('value')
    return values


def script_defaults(case, table, levels):
    return run_script(case, 'var table = %s; return %s.map(function(level) {'
                            ' return setupMoreDefaults(table, level); });'
                      % (json.dumps(table), json.dumps(list(levels))))


def effective(char):
    set_current_game_version(char.game_version)
    options = get_options(Char.objects.get(pk=char.pk))
    options['range_exo'] = exo_count(options.get('range_exo'))
    return options


class TheSectionIsDrawnInsideTheFormTests(TestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')

    def test_every_version_and_language_draws_one_section_with_a_control_for_each_field(self):
        problems = []
        for version in VERSIONS:
            for language in LANGUAGES:
                html, page = setup_page(self.client, version, language)
                sections = page.find('details', id=SECTION)
                inside_form = [ancestors for _attrs, ancestors in sections
                               if page.inside(ancestors, 'form', 'main_form')]
                drawn = drawn_values(page)
                missing = [name for name in group_fields(section_table(html)) if name not in drawn]
                if (len(sections), len(inside_form), missing) != (1, 1, []):
                    problems.append((version, language, len(sections), len(inside_form), missing))
        self.assertEqual([], problems)

    def test_the_section_posts_no_group_marker_of_its_own(self):
        html, page = setup_page(self.client, 'dofus3')
        self.assertEqual([], [attrs for attrs, _ in page.find('input')
                              if attrs.get('name') == 'setup_options'])

    def test_the_exos_are_counts_on_retro_and_yes_or_no_elsewhere(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                html, page = setup_page(self.client, version)
                types = {attrs.get('type') for attrs, ancestors in page.find('input')
                         if page.inside(ancestors, 'details', SECTION)
                         and attrs.get('name') in ('ap_exo', 'mp_exo', 'range_exo')}
                self.assertEqual({'number'} if version == 'retro' else {'radio'}, types)

    def test_the_dofus_row_carries_a_hidden_note_for_the_wisdom_box(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                html, page = setup_page(self.client, version)
                notes = [attrs for attrs, ancestors in page.find('p', id='setup-more-cawwot')
                         if page.inside(ancestors, 'details', SECTION)]
                self.assertEqual(1, len(notes))
                self.assertIn('hidden', notes[0])

    def test_the_item_source_is_offered_only_to_a_player_with_a_folder_of_the_version(self):
        html, page = setup_page(self.client, 'dofus3')
        self.assertNotIn('inventory_mode', drawn_values(page))
        owner = User.objects.create_user('setup-more-items', 'items@test.local', 'pw-items-5')
        self.client.force_login(owner)
        html, page = setup_page(self.client, 'dofus3')
        self.assertNotIn('inventory_mode', drawn_values(page))
        folder = InventoryFolder.objects.create(user=owner, name='mine', game_version='dofus3')
        InventoryFolder.objects.create(user=owner, name='retro', game_version='retro')
        html, page = setup_page(self.client, 'dofus3')
        self.assertEqual('all', drawn_values(page)['inventory_mode'])
        self.assertEqual([str(folder.id)], [attrs['value'] for attrs, ancestors in page.find('option')
                                            if page.inside(ancestors, 'details', SECTION)])
        self.assertIn(['inventory', ['inventory_mode']], section_table(html)['groups'])


class TheScriptKnowsWhatTheSectionDrawsTests(TestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')

    def test_the_drawn_controls_post_what_the_script_says_a_new_build_posts_at_level_200(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                html, page = setup_page(self.client, version)
                table = section_table(html)
                drawn = drawn_values(page)
                expected = script_defaults(self, table, [200])[0]
                self.assertEqual({name: expected.get(name) for name in group_fields(table)},
                                 {name: drawn.get(name) for name in group_fields(table)})

    def test_a_level_takes_the_exos_and_prysmaradite_of_that_level_and_greys_the_dofus_above_it(self):
        html, _page = setup_page(self.client, 'dofus3')
        table = section_table(html)
        low, high = script_defaults(self, table, [100, 200])
        self.assertEqual(('no', 'no', None), (low['ap_exo'], low['mp_exo'], low['prysmaradite']))
        self.assertEqual(('yes', 'yes', 'on'), (high['ap_exo'], high['mp_exo'], high['prysmaradite']))
        above = [key for key, needed in table['levels'].items() if needed > 100]
        self.assertTrue(above)
        self.assertEqual([None] * len(above), [low[key] for key in above])

    def test_the_script_marks_only_the_groups_that_differ_from_the_defaults(self):
        html, _page = setup_page(self.client, 'retro')
        table = section_table(html)
        said = run_script(self, """
var table = %s;
var defaults = setupMoreDefaults(table, 200);
function changed(edit) {
    var current = JSON.parse(JSON.stringify(defaults));
    edit(current);
    return setupMoreChanged(table.groups, defaults, current);
}
return {
    none: changed(function() {}),
    padded: changed(function(c) { c.ap_exo = ' 0' + c.ap_exo; }),
    exos: changed(function(c) { c.range_exo = '2'; }),
    cleared: changed(function(c) { c.mp_exo = ''; }),
    two: changed(function(c) { c.scrolling = 'clean'; c.choose_stats = null; })
};""" % json.dumps(table))
        self.assertEqual({'none': [], 'padded': [], 'exos': ['exos'], 'cleared': ['exos'],
                          'two': ['scrolls', 'points']}, said)

    def test_a_new_level_moves_every_field_left_alone_and_keeps_every_field_changed(self):
        html, _page = setup_page(self.client, 'dofus3')
        table = section_table(html)
        said = run_script(self, """
var table = %s;
var current = setupMoreDefaults(table, 200);
current.ap_exo = 'no';
current.mp_exo = 'gelano';
current.dragoturkey = null;
return {down: setupMoreFollow(table, 200, 100, current, {}).values, low: setupMoreDefaults(table, 100)};
""" % json.dumps(table))
        self.assertNotIn('ap_exo', said['down'])
        self.assertNotIn('mp_exo', said['down'])
        self.assertNotIn('dragoturkey', said['down'])
        self.assertEqual('no', said['low']['range_exo'])
        for key in ('range_exo', 'seemyool', 'prysmaradite', 'scrolling', 'choose_stats'):
            self.assertEqual(said['low'].get(key), said['down'].get(key, 'not moved'), key)

    def test_a_field_the_player_set_survives_a_trip_below_its_level_and_back(self):
        html, _page = setup_page(self.client, 'dofus3')
        table = section_table(html)
        said = run_script(self, """
var table = %s;
function move(state, after) {
    var moved = setupMoreFollow(table, state.level, after, state.current, state.kept, state.touched);
    var current = JSON.parse(JSON.stringify(state.current));
    for (var key in moved.values) {
        current[key] = moved.values[key];
    }
    return {level: after, current: current, kept: moved.kept, touched: state.touched};
}
var trips = {};
[150, 199].forEach(function(middle) {
    var start = {level: 200, current: setupMoreDefaults(table, 200), kept: {},
                 touched: {ap_exo: true, prysmaradite: true}};
    start.current.ap_exo = 'no';
    start.current.prysmaradite = null;
    var back = move(move(start, middle), 200).current;
    trips[middle] = [back.ap_exo, back.prysmaradite,
                     setupMoreChanged(table.groups, setupMoreDefaults(table, 200), back)];
});
return trips;
""" % json.dumps(table))
        self.assertEqual({'150': ['no', None, ['exos', 'dofus']],
                          '199': ['no', None, ['exos', 'dofus']]}, said)

    def test_a_dofus_greyed_by_a_lower_level_comes_back_as_it_was_before(self):
        html, _page = setup_page(self.client, 'dofus3')
        table = section_table(html)
        said = run_script(self, """
var table = %s;
function move(state, after) {
    var moved = setupMoreFollow(table, state.level, after, state.current, state.kept);
    var current = JSON.parse(JSON.stringify(state.current));
    for (var key in moved.values) {
        current[key] = moved.values[key];
    }
    return {level: after, current: current, kept: moved.kept};
}
function only(test) {
    return Object.keys(table.levels).filter(function(key) { return test(table.levels[key]); }).sort();
}
var full = setupMoreDefaults(table, 200);
var above = only(function(needed) { return needed > 100; }).filter(function(key) { return full[key] === 'on'; });
var below = only(function(needed) { return needed <= 100; });
var low = move({level: 200, current: setupMoreDefaults(table, 200), kept: {}}, 100);
low.current[below[0]] = null;
var touchedLow = move(low, 200).current;
var start = {level: 200, current: setupMoreDefaults(table, 200), kept: {}};
start.current[above[0]] = null;
var touchedHigh = move(move(start, 100), 200).current;
function pick(values) {
    return above.map(function(key) { return values[key] === undefined ? 'missing' : values[key]; });
}
return {full: pick(full), touchedLow: pick(touchedLow), lowBox: touchedLow[below[0]],
        touchedHigh: pick(touchedHigh), greyed: pick(low.current)};
""" % json.dumps(table))
        self.assertGreater(len(said['full']), 1)
        self.assertEqual(['on'] * len(said['full']), said['full'])
        self.assertEqual([None] * len(said['full']), said['greyed'])
        self.assertEqual(said['full'], said['touchedLow'])
        self.assertIsNone(said['lowBox'])
        self.assertEqual([None] + said['full'][1:], said['touchedHigh'])


class TheEditingPageOfABuildDrawsNoSectionTests(_Creations):

    def test_the_page_that_edits_a_stored_build_has_no_more_options(self):
        char = self.create('dofus3')
        self.client.force_login(self.owner)
        response = self.client.get('/project/%d/' % char.pk)
        self.assertEqual(200, response.status_code)
        page = _Page(response.content.decode('utf-8'))
        self.assertTrue(page.find('form', id='main_form'))
        self.assertEqual([], page.find('details', id=SECTION))


class WhatTheScriptCallsUntouchedStoresTheBuildOfTodayTests(_Creations):

    def test_every_group_posted_as_the_script_draws_it_at_any_level_stores_the_build_of_today(self):
        for version in VERSIONS:
            html, _page = setup_page(self.client, version)
            table = section_table(html)
            for level, values in zip(LEVELS, script_defaults(self, table, LEVELS)):
                with self.subTest(version=version, level=level):
                    fields = [(name, values[name]) for name in group_fields(table)
                              if values.get(name) is not None]
                    groups = [group for group, _names in table['groups']]
                    today = self.create(version, level=level)
                    posted = self.create(version, fields + markers(*groups), level=level)
                    self.assertEqual(self.stored(today)['excluded'], self.stored(posted)['excluded'])
                    self.assertEqual(self.stored(today)['scrolls'], self.stored(posted)['scrolls'])
                    self.assertEqual(self.stored(today)['distribution'],
                                     self.stored(posted)['distribution'])
                    self.assertEqual(effective(today), effective(posted))


class TheSectionSpeaksFiveLanguagesTests(TestCase):

    def test_every_string_of_the_section_is_translated_without_dash_emoji_or_vous(self):
        ids = template_message_ids(TEMPLATE)
        self.assertGreater(len(ids), 20)
        problems = []
        for lang in TRANSLATED:
            entries = catalogue(lang, 'django')
            for msgid in sorted(ids):
                entry = entries.find(msgid)
                if entry is None or entry.obsolete or 'fuzzy' in entry.flags or not entry.msgstr.strip():
                    problems.append((lang, msgid[:50], 'missing'))
                elif DASH.search(entry.msgstr) or EMOJI.search(entry.msgstr):
                    problems.append((lang, msgid[:50], entry.msgstr))
                elif lang == 'fr' and FRENCH_POLITE.search(entry.msgstr):
                    problems.append((lang, msgid[:50], entry.msgstr))
        self.assertEqual([], problems)

    def test_every_mount_label_names_the_mounts_of_the_game_in_the_language_of_the_reader(self):
        self.addCleanup(set_current_game_version, 'dofus3')
        set_current_game_version('dofus3')
        structure = get_structure()
        pets = [item for item in structure.get_items_list()
                if item.name and structure.get_type_name_by_id(item.type) == 'Pet']
        problems = []
        for msgid, family in (('Dragoturkeys', 'Dragoturkey'), ('Seemyools', 'Seemyool'),
                              ('Rhineetles', 'Rhineetle')):
            names = [item.localized_names for item in pets if family in item.name]
            self.assertTrue(names, family)
            for lang in TRANSLATED:
                label = catalogue(lang, 'django').find(msgid).msgstr
                stem = label[:-1] if label.endswith('s') else label
                if not any(stem in localized.get(lang, '') for localized in names):
                    problems.append((lang, msgid, label))
        self.assertEqual([], problems)

    def test_the_german_section_says_range_in_german(self):
        entries = catalogue('de', 'django')
        english = [(msgid[:40], entries.find(msgid).msgstr)
                   for msgid in sorted(template_message_ids(TEMPLATE))
                   if re.search(r'\bRange\b', entries.find(msgid).msgstr)]
        self.assertEqual([], english)

    def test_the_section_reads_in_the_language_of_the_reader(self):
        for language, title in (('fr', 'Plus d’options'), ('es', 'Más opciones'),
                                ('pt', 'Mais opções'), ('de', 'Weitere Optionen'),
                                ('en', 'More options')):
            with self.subTest(language=language):
                html, _page = setup_page(self.client, 'dofus3', language)
                self.assertIn(title, html)
