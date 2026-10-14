# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Every string the preset chips, the share link and the saved setups show is in the five catalogues, and the script speaks each language."""
import json
import os
import re
import shutil
import subprocess
import tempfile

from django.test import SimpleTestCase, TestCase
from django.utils import translation

from chardata.presets import RECIPES, setup_recipes
from chardata.tests_every_preset_keeps_its_weights_and_minimums import VERSIONS
from chardata.tests_the_setup_page_draws_the_live_weights_panel import setup_page
from chardata.tests_the_setup_panel_strings_are_translated_in_five_languages import (
    DASH, EMOJI, FRENCH_FORMAL, FRENCH_POLITE, LANGUAGES, MARK, SCRIPT, SCRIPT_STRINGS, TEMPLATE,
    TRANSLATED, catalogue, script_literals, written_forms)

PRESETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'presets.py')
SAVED_LIMIT_SENTENCE = 'You can keep up to %s setups. Delete one to save another.'
RECIPE_SCRIPT_STRINGS = (
    ('Link copied.', None),
    ('Select the link and copy it.', None),
    ('Mules need no element: leave the Elements column unchecked, or pick one if the character also fights.', None),
    ('Presets never choose an element: pick yours in the Elements column.', None),
    ('Setup saved.', None),
    ('Setup deleted.', None),
    ('Setup loaded.', None),
    ('Give the setup a name first.', None),
    (SAVED_LIMIT_SENTENCE, None),
    ('This setup could not be loaded.', None),
    ('No saved setup yet.', None),
    ('Load', None),
    ('Delete', None),
    ('Your browser did not let this page save the setup.', None),
    ('Your browser did not let this page delete the setup.', None),
    ('This setup has too many edited values to save or share. Reset some of them first.', None),
)
RECIPE_PAGE_STRINGS = (
    'Start from a preset',
    'Copy link',
    'Link to this setup',
    'My setups',
    'Name this setup',
    'Save this setup',
)
RECIPE_LABELS = (
    'All-round', 'Damage dealer', 'Tank', 'Healer', 'Pusher', 'Summoner', 'Trapper', 'XP mule',
    'Prospecting mule', 'Farm', 'Pod carrier',
)
# Loanwords the language writes as English does
SAME_AS_ENGLISH = {('fr', 'Tank'), ('de', 'Tank'), ('fr', 'Farm'), ('pt', 'Farm')}


class TheScriptAsksForTheStringsTheCataloguesCarryTests(SimpleTestCase):

    def test_every_string_this_module_lists_is_one_the_script_asks_for(self):
        self.assertLessEqual(set(RECIPE_SCRIPT_STRINGS), script_literals())

    def test_the_script_asks_for_no_string_that_neither_module_lists(self):
        self.assertEqual(set(SCRIPT_STRINGS) | set(RECIPE_SCRIPT_STRINGS), script_literals())

    def test_the_template_asks_for_exactly_the_chip_strings_this_module_lists_outside_the_panel(self):
        source = open(TEMPLATE, encoding='utf-8').read()
        section = source[source.index('<section id="setup-recipes"'):source.index('</section>')]
        found = re.findall(r'\{%\s*trans\s+(?:"([^"]+)"|\'([^\']+)\')\s*%\}', section)
        asked = {double or single for double, single in found if double or single}
        self.assertEqual(set(RECIPE_PAGE_STRINGS), asked)

    def test_every_label_of_a_recipe_is_one_this_module_lists_or_one_the_french_catalogue_already_had(self):
        with translation.override('en'):
            labels = {str(recipe.label) for recipe in RECIPES}
        french = catalogue('fr', 'django')
        for label in labels - set(RECIPE_LABELS):
            with self.subTest(label=label):
                self.assertIsNotNone(french.find(label))
        self.assertLessEqual(set(RECIPE_LABELS), labels)


class EveryLanguageTranslatesTheScriptStringsOfThePresetsTests(SimpleTestCase):

    def entries(self, lang):
        catalog = catalogue(lang, 'djangojs')
        found = []
        for singular, plural in RECIPE_SCRIPT_STRINGS:
            entry = catalog.find(singular)
            self.assertIsNotNone(entry, (lang, singular))
            self.assertEqual(plural or '', entry.msgid_plural, (lang, singular))
            found.append(entry)
        return found

    def test_no_entry_is_fuzzy_or_obsolete_and_it_points_at_the_script(self):
        for lang in LANGUAGES:
            for entry in self.entries(lang):
                with self.subTest(lang=lang, msgid=entry.msgid):
                    self.assertNotIn('fuzzy', entry.flags)
                    self.assertFalse(entry.obsolete)
                    self.assertIn('chardata/static/chardata/setup.js',
                                  [path for path, _line in entry.occurrences])

    def test_each_foreign_language_writes_every_sentence_differently_from_english(self):
        for lang in TRANSLATED:
            for entry in self.entries(lang):
                with self.subTest(lang=lang, msgid=entry.msgid):
                    for form in written_forms(entry):
                        self.assertTrue(form.strip())
                        self.assertNotEqual(entry.msgid, form)

    def test_a_translation_keeps_the_placeholders_of_its_source(self):
        for lang in TRANSLATED:
            for entry in self.entries(lang):
                with self.subTest(lang=lang, msgid=entry.msgid):
                    for form in written_forms(entry):
                        self.assertEqual(sorted(MARK.findall(entry.msgid)), sorted(MARK.findall(form)), form)

    def test_the_sentence_with_a_number_is_marked_as_javascript_format(self):
        for lang in LANGUAGES:
            entry = catalogue(lang, 'djangojs').find(SAVED_LIMIT_SENTENCE)
            self.assertIn('javascript-format', entry.flags, lang)

    def test_no_translation_has_a_dash_or_an_emoji(self):
        for lang in TRANSLATED:
            for entry in self.entries(lang):
                for form in written_forms(entry):
                    with self.subTest(lang=lang, form=form):
                        self.assertIsNone(DASH.search(form))
                        self.assertIsNone(EMOJI.search(form))

    def test_french_speaks_to_the_player_as_tu(self):
        for entry in self.entries('fr'):
            for form in written_forms(entry):
                with self.subTest(form=form):
                    self.assertIsNone(FRENCH_FORMAL.search(form))
                    self.assertIsNone(FRENCH_POLITE.search(form))

    def test_english_leaves_the_source_text_as_it_is(self):
        for entry in self.entries('en'):
            self.assertEqual([''], written_forms(entry))


class EveryLanguageTranslatesThePageAndTheLabelsOfThePresetsTests(TestCase):

    def test_the_catalogues_carry_each_string_with_its_file_as_its_source(self):
        for lang in LANGUAGES:
            catalog = catalogue(lang, 'django')
            for msgid, source in (
                    [(text, 'chardata/templates/chardata/projdetails.html') for text in RECIPE_PAGE_STRINGS]
                    + [(text, 'chardata/presets.py') for text in RECIPE_LABELS]):
                with self.subTest(lang=lang, msgid=msgid):
                    entry = catalog.find(msgid)
                    self.assertIsNotNone(entry)
                    self.assertNotIn('fuzzy', entry.flags)
                    self.assertFalse(entry.obsolete)
                    self.assertIn(source, [path for path, _line in entry.occurrences])
                    if lang == 'en':
                        self.assertEqual('', entry.msgstr)
                    else:
                        self.assertTrue(entry.msgstr.strip())

    def test_each_foreign_language_differs_from_english_unless_it_borrows_the_word(self):
        for lang in TRANSLATED:
            with translation.override(lang):
                for msgid in RECIPE_PAGE_STRINGS + RECIPE_LABELS:
                    with self.subTest(lang=lang, msgid=msgid):
                        if (lang, msgid) in SAME_AS_ENGLISH:
                            self.assertEqual(msgid, translation.gettext(msgid))
                        else:
                            self.assertNotEqual(msgid, translation.gettext(msgid))
        with translation.override('en'):
            for msgid in RECIPE_PAGE_STRINGS + RECIPE_LABELS:
                self.assertEqual(msgid, translation.gettext(msgid))

    def test_the_setup_page_of_each_version_shows_the_strings_and_its_chip_labels_in_the_language_of_the_reader(self):
        for lang in LANGUAGES:
            for version in VERSIONS:
                body, _page = setup_page(self.client, version, lang)
                with translation.override(lang):
                    for msgid in RECIPE_PAGE_STRINGS:
                        with self.subTest(lang=lang, version=version, msgid=msgid):
                            self.assertIn(translation.gettext(msgid), body)
                    for recipe in setup_recipes(version):
                        with self.subTest(lang=lang, version=version, recipe=recipe.key):
                            self.assertIn('>%s</button>' % translation.gettext(recipe.label), body)

    def test_no_translation_has_a_dash_or_an_emoji_or_a_polite_french_form(self):
        for lang in TRANSLATED:
            with translation.override(lang):
                for msgid in RECIPE_PAGE_STRINGS + RECIPE_LABELS:
                    text = translation.gettext(msgid)
                    with self.subTest(lang=lang, msgid=msgid):
                        self.assertIsNone(DASH.search(text))
                        self.assertIsNone(EMOJI.search(text))
                        if lang == 'fr':
                            self.assertIsNone(FRENCH_POLITE.search(text))
                            self.assertIsNone(FRENCH_FORMAL.search(text))


NODE_PROGRAM = r"""
const vm = require('vm');
const fs = require('fs');
const sandbox = {};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(process.argv[2], 'utf8'), sandbox);
const django = sandbox.django;
const source = fs.readFileSync(process.argv[3], 'utf8');
const strings = JSON.parse(process.argv[4]);
const script = new Function('gettext', 'ngettext', 'interpolate', '$', 'document', 'window',
    source + '; return {note: setupRecipeNoteText, limit: SETUP_RECIPES.savedLimit};')(
    django.gettext, django.ngettext, django.interpolate, function() { return {ready: function() {}}; }, {}, {});
const said = {};
strings.forEach(function(text) { said[text] = django.gettext(text); });
process.stdout.write(JSON.stringify({
    said: said,
    mule: script.note('mule'),
    element: script.note('element'),
    none: script.note(''),
    full: django.interpolate(django.gettext(strings[strings.length - 1]), [script.limit])
}));
"""


class TheScriptSpeaksEachLanguageTests(TestCase):

    def spoken(self, lang):
        node = shutil.which('node')
        if node is None:
            self.skipTest('node is not installed')
        response = self.client.get('/jsi18n/?lang=%s' % lang, HTTP_ACCEPT_LANGUAGE=lang)
        self.assertEqual(200, response.status_code)
        texts = [text for text, _plural in RECIPE_SCRIPT_STRINGS]
        folder = tempfile.mkdtemp()
        try:
            catalog = os.path.join(folder, 'catalog.js')
            program = os.path.join(folder, 'program.js')
            with open(catalog, 'wb') as handle:
                handle.write(response.content)
            with open(program, 'w', encoding='utf-8') as handle:
                handle.write(NODE_PROGRAM)
            done = subprocess.run([node, program, catalog, SCRIPT, json.dumps(texts + [SAVED_LIMIT_SENTENCE])],
                                  capture_output=True, text=True, encoding='utf-8')
        finally:
            shutil.rmtree(folder, ignore_errors=True)
        self.assertEqual(0, done.returncode, done.stderr[-800:])
        return json.loads(done.stdout)

    def test_english_reads_as_written(self):
        said = self.spoken('en')
        for text, _plural in RECIPE_SCRIPT_STRINGS:
            self.assertEqual(text, said['said'][text])
        self.assertEqual(RECIPE_SCRIPT_STRINGS[2][0], said['mule'])
        self.assertEqual(RECIPE_SCRIPT_STRINGS[3][0], said['element'])
        self.assertEqual('', said['none'])
        self.assertEqual('You can keep up to 5 setups. Delete one to save another.', said['full'])

    def test_every_foreign_language_replaces_every_sentence_and_the_two_notes_the_script_builds(self):
        for lang in TRANSLATED:
            said = self.spoken(lang)
            with self.subTest(lang=lang):
                for text, _plural in RECIPE_SCRIPT_STRINGS:
                    self.assertNotEqual(text, said['said'][text], text)
                    self.assertIsNone(DASH.search(said['said'][text]))
                self.assertEqual(said['said'][RECIPE_SCRIPT_STRINGS[2][0]], said['mule'])
                self.assertEqual(said['said'][RECIPE_SCRIPT_STRINGS[3][0]], said['element'])
                self.assertEqual('', said['none'])

    def test_the_saved_limit_sentence_carries_the_limit_in_every_language(self):
        for lang in TRANSLATED:
            said = self.spoken(lang)
            with self.subTest(lang=lang):
                self.assertIn('5', said['full'])
                self.assertIsNone(MARK.search(said['full']))

    def test_french_speaks_to_the_player_as_tu_in_everything_the_script_says(self):
        said = self.spoken('fr')
        for text in list(said['said'].values()) + [said['mule'], said['element'], said['full']]:
            self.assertIsNone(FRENCH_FORMAL.search(text), text)
