# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Every string the /setup/ panel shows is in the five catalogues, and the script speaks each language."""
import json
import os
import re
import shutil
import subprocess
import tempfile

import polib
from django.test import SimpleTestCase, TestCase
from django.utils import translation

HERE = os.path.dirname(os.path.abspath(__file__))
LOCALE = os.path.join(HERE, '..', 'locale')
SCRIPT = os.path.join(HERE, 'static', 'chardata', 'setup.js')
TEMPLATE = os.path.join(HERE, 'templates', 'chardata', 'projdetails.html')
LANGUAGES = ('en', 'fr', 'es', 'pt', 'de')
TRANSLATED = LANGUAGES[1:]
MARK = re.compile(r'%\(\w+\)[a-z]|%[sd]|\{\w+\}')
DASH = re.compile('[' + chr(0x2012) + '-' + chr(0x2015) + chr(0x2212) + ']')
EMOJI = re.compile('[' + chr(0x1F000) + '-' + chr(0x1FFFF) + chr(0x2600) + '-' + chr(0x27BF)
                   + chr(0x2B00) + '-' + chr(0x2BFF) + ']')
FRENCH_FORMAL = re.compile(r'\b(vous|votre|vos|commencez|choisissez)\b', re.IGNORECASE)
FRENCH_POLITE = re.compile(r'\b(vous|votre|vos|vôtres?|\w+ez)\b', re.IGNORECASE)
SETUP_TEMPLATES = ('projdetails.html', 'weights_minimums_block.html', 'weights_minimums_row.html')

PAGE_STRINGS = (
    'What the optimizer will look for',
    'Pick a class to see the weights and minimums the optimizer will use.',
    'Preview only, it updates as you choose. Once the build exists, you can change any weight or minimum.',
    'The preview could not be updated. You can still create your build.',
    'Minimums are saved when you continue to the Wizard. Creating a set by hand saves the weights only.',
)
INTRO = 'Get started by providing details about your character.'
SCRIPT_STRINGS = (
    ('Your last choice changed %(count)s characteristic: %(names)s.',
     'Your last choice changed %(count)s characteristics: %(names)s.'),
    ('and %s more', 'and %s more'),
    ('Your last choice left the weights and minimums unchanged.', None),
    ('%s changed', '%s changed'),
    ('Weight was %s', None),
    ('Minimum was %s', None),
    ('There was no minimum', None),
    ('Safeguard: effective HP, AP, MP, Range and the other stats the priority does not aim for keep at least %(share)s of their value in the balanced build. The exact values are computed at launch.', None),
    ('Safeguard: damage stats, AP, MP, Range and the other stats the priority does not aim for keep at least %(share)s of their value in the balanced build. The exact values are computed at launch.', None),
)


def catalogue(lang, domain):
    return polib.pofile(os.path.join(LOCALE, lang, 'LC_MESSAGES', domain + '.po'))


def written_forms(entry):
    if entry.msgid_plural:
        return [entry.msgstr_plural[key] for key in sorted(entry.msgstr_plural)]
    return [entry.msgstr]


def script_literals():
    source = open(SCRIPT, encoding='utf-8').read()
    quoted = r"'((?:[^'\\]|\\.)*)'"
    plural = re.findall(r'\bngettext\(\s*%s,\s*%s' % (quoted, quoted), source)
    single = re.findall(r'(?<![A-Za-z_])gettext\(\s*%s\s*\)' % quoted, source)
    return set(plural) | {(text, None) for text in single}


class TheScriptAsksForTheStringsTheCataloguesCarryTests(SimpleTestCase):

    def test_the_script_uses_exactly_the_strings_this_module_lists(self):
        self.assertEqual(set(SCRIPT_STRINGS), script_literals())

    def test_the_page_template_uses_exactly_the_panel_strings_this_module_lists(self):
        source = open(TEMPLATE, encoding='utf-8').read()
        panel = source[source.index('<aside id="setup-preview"'):source.index('</aside>')]
        self.assertEqual(set(PAGE_STRINGS),
                         set(re.findall(r'\{%\s*trans\s+"([^"]+)"\s*%\}', panel)))


class EveryLanguageTranslatesTheScriptStringsTests(SimpleTestCase):

    def entries(self, lang):
        catalog = catalogue(lang, 'djangojs')
        found = []
        for singular, plural in SCRIPT_STRINGS:
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

    def test_each_foreign_language_writes_every_form(self):
        for lang in TRANSLATED:
            for entry in self.entries(lang):
                with self.subTest(lang=lang, msgid=entry.msgid):
                    forms = written_forms(entry)
                    self.assertEqual(2 if entry.msgid_plural else 1, len(forms))
                    for form in forms:
                        self.assertTrue(form.strip())
                        self.assertNotEqual(entry.msgid, form)

    def test_a_translation_keeps_the_placeholders_of_its_source(self):
        for lang in TRANSLATED:
            for entry in self.entries(lang):
                with self.subTest(lang=lang, msgid=entry.msgid):
                    wanted = sorted(MARK.findall(entry.msgid))
                    for form in written_forms(entry):
                        self.assertEqual(wanted, sorted(MARK.findall(form)), form)

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
                self.assertIsNone(FRENCH_FORMAL.search(form), form)

    def test_english_leaves_the_source_text_as_it_is(self):
        for entry in self.entries('en'):
            self.assertEqual([''] * (2 if entry.msgid_plural else 1), written_forms(entry))


class EveryLanguageTranslatesThePageStringsTests(TestCase):

    def test_the_catalogues_carry_each_string_with_the_template_as_its_source(self):
        for lang in LANGUAGES:
            catalog = catalogue(lang, 'django')
            for msgid in PAGE_STRINGS + (INTRO,):
                with self.subTest(lang=lang, msgid=msgid):
                    entry = catalog.find(msgid)
                    self.assertIsNotNone(entry)
                    self.assertNotIn('fuzzy', entry.flags)
                    self.assertFalse(entry.obsolete)
                    if lang != 'en':
                        self.assertTrue(entry.msgstr.strip())
                    if msgid in PAGE_STRINGS:
                        self.assertIn('chardata/templates/chardata/projdetails.html',
                                      [path for path, _line in entry.occurrences])

    def test_each_foreign_language_differs_from_english_when_the_string_is_looked_up(self):
        for lang in TRANSLATED:
            with translation.override(lang):
                for msgid in PAGE_STRINGS + (INTRO,):
                    with self.subTest(lang=lang, msgid=msgid):
                        self.assertNotEqual(msgid, translation.gettext(msgid))
        with translation.override('en'):
            for msgid in PAGE_STRINGS + (INTRO,):
                self.assertEqual(msgid, translation.gettext(msgid))

    def test_the_setup_page_shows_the_strings_in_the_language_of_the_reader(self):
        for lang in LANGUAGES:
            body = self.client.get('/setup/', HTTP_ACCEPT_LANGUAGE=lang).content.decode('utf-8')
            with translation.override(lang):
                for msgid in PAGE_STRINGS + (INTRO,):
                    with self.subTest(lang=lang, msgid=msgid):
                        self.assertIn(translation.gettext(msgid), body)

    def test_nothing_the_page_says_in_french_uses_vous_where_the_panel_speaks(self):
        with translation.override('fr'):
            for msgid in PAGE_STRINGS + (INTRO,):
                self.assertIsNone(FRENCH_FORMAL.search(translation.gettext(msgid)))

    def test_no_translation_has_a_dash_or_an_emoji(self):
        for lang in TRANSLATED:
            with translation.override(lang):
                for msgid in PAGE_STRINGS + (INTRO,):
                    text = translation.gettext(msgid)
                    with self.subTest(lang=lang, msgid=msgid):
                        self.assertIsNone(DASH.search(text))
                        self.assertIsNone(EMOJI.search(text))
                        self.assertEqual(sorted(MARK.findall(msgid)), sorted(MARK.findall(text)))


def template_message_ids(name):
    """The msgids a template asks for, spelled as the catalogue spells them."""
    source = open(os.path.join(HERE, 'templates', 'chardata', name), encoding='utf-8').read()
    ids = set(re.findall(r'\{%\s*trans\s+"((?:[^"\\]|\\.)*)"', source))
    ids |= set(re.findall(r"_\('((?:[^'\\]|\\.)*)'\)", source))
    ids = {text.replace('\\"', '"').replace('%', '%%') for text in ids}
    for body in re.findall(r'\{%\s*blocktrans[^%]*%\}(.*?)\{%\s*endblocktrans', source, re.S):
        ids.add(re.sub(r'\{\{\s*(\w+)\s*\}\}', r'%(\1)s', body.replace('%', '%%')))
    return ids


class TheFrenchSetupPageSpeaksTuTests(SimpleTestCase):

    def test_every_string_the_page_and_its_panel_draw_is_in_the_french_catalogue(self):
        french = catalogue('fr', 'django')
        ids = set()
        for name in SETUP_TEMPLATES:
            ids |= template_message_ids(name)
        self.assertGreater(len(ids), 40)
        self.assertEqual([], sorted(text for text in ids if french.find(text) is None))

    def test_none_of_them_addresses_the_player_as_vous(self):
        french = catalogue('fr', 'django')
        formal = []
        for name in SETUP_TEMPLATES:
            for text in template_message_ids(name):
                entry = french.find(text)
                if entry is not None and FRENCH_POLITE.search(entry.msgstr):
                    formal.append((name, entry.msgid[:60], entry.msgstr))
        self.assertEqual([], formal)

    def test_none_of_the_sentences_the_scripts_say_addresses_the_player_as_vous(self):
        formal = []
        for entry in catalogue('fr', 'djangojs'):
            files = [path for path, _line in entry.occurrences]
            if not any(path.endswith(('chardata/setup.js', 'chardata/weights_minimums.js'))
                       for path in files):
                continue
            for form in written_forms(entry):
                if FRENCH_POLITE.search(form):
                    formal.append((entry.msgid[:60], form))
        self.assertEqual([], formal)


NODE_PROGRAM = r"""
const vm = require('vm');
const fs = require('fs');
const sandbox = {};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(process.argv[2], 'utf8'), sandbox);
const django = sandbox.django;
const source = fs.readFileSync(process.argv[3], 'utf8');
const script = new Function('gettext', 'ngettext', 'interpolate', '$', 'document', 'window',
    source + '; return {summary: setupPreviewSummary, badge: setupPreviewBadge, title: setupPreviewTitle, guard: setupPreviewGuard};')(
    django.gettext, django.ngettext, django.interpolate, function() { return {ready: function() {}}; }, {}, {});
const names = ['AP', 'Damage', 'Range', 'MP', 'HP'];
const kinds = {damage: 'effective_hp', defense: 'turn', heals: 'turn'};
process.stdout.write(JSON.stringify({
    unchanged: script.summary([], 0),
    one: script.summary(names.slice(0, 1), 1),
    two: script.summary(names.slice(0, 2), 2),
    three: script.summary(names.slice(0, 3), 3),
    four: script.summary(names.slice(0, 4), 4),
    five: script.summary(names, 5),
    badgeOne: script.badge(1),
    badgeMany: script.badge(7),
    weight: script.title({weight: true, weightWas: '5'}),
    minimum: script.title({min: true, minWas: '11'}),
    noMinimum: script.title({min: true, minWas: ''}),
    guardHp: script.guard('damage', '10', kinds),
    guardTurn: script.guard('heals', '15', kinds),
    guardNothing: script.guard('balanced', '10', kinds)
}));
"""


class TheScriptSpeaksEachLanguageTests(TestCase):

    def spoken(self, lang):
        node = shutil.which('node')
        if node is None:
            self.skipTest('node is not installed')
        response = self.client.get('/jsi18n/?lang=%s' % lang, HTTP_ACCEPT_LANGUAGE=lang)
        self.assertEqual(200, response.status_code)
        folder = tempfile.mkdtemp()
        try:
            catalog = os.path.join(folder, 'catalog.js')
            program = os.path.join(folder, 'program.js')
            with open(catalog, 'wb') as handle:
                handle.write(response.content)
            with open(program, 'w', encoding='utf-8') as handle:
                handle.write(NODE_PROGRAM)
            done = subprocess.run([node, program, catalog, SCRIPT], capture_output=True,
                                  text=True, encoding='utf-8')
        finally:
            shutil.rmtree(folder, ignore_errors=True)
        self.assertEqual(0, done.returncode, done.stderr[-800:])
        return json.loads(done.stdout)

    def test_english_reads_as_written(self):
        said = self.spoken('en')
        self.assertEqual({
            'unchanged': 'Your last choice left the weights and minimums unchanged.',
            'one': 'Your last choice changed 1 characteristic: AP.',
            'two': 'Your last choice changed 2 characteristics: AP, Damage.',
            'three': 'Your last choice changed 3 characteristics: AP, Damage, Range.',
            'four': 'Your last choice changed 4 characteristics: AP, Damage, Range and 1 more.',
            'five': 'Your last choice changed 5 characteristics: AP, Damage, Range and 2 more.',
            'badgeOne': '1 changed', 'badgeMany': '7 changed', 'weight': 'Weight was 5',
            'minimum': 'Minimum was 11', 'noMinimum': 'There was no minimum',
            'guardHp': 'Safeguard: effective HP, AP, MP, Range and the other stats the priority '
                       'does not aim for keep at least 90% of their value in the balanced build. '
                       'The exact values are computed at launch.',
            'guardTurn': 'Safeguard: damage stats, AP, MP, Range and the other stats the priority '
                         'does not aim for keep at least 85% of their value in the balanced build. '
                         'The exact values are computed at launch.',
            'guardNothing': None}, said)

    def test_every_foreign_language_replaces_every_sentence_and_leaves_no_placeholder(self):
        english = self.spoken('en')
        for lang in TRANSLATED:
            said = self.spoken(lang)
            self.assertEqual(set(english), set(said))
            for key, text in said.items():
                with self.subTest(lang=lang, key=key):
                    if english[key] is None:
                        self.assertIsNone(text)
                        continue
                    self.assertNotEqual(english[key], text)
                    self.assertIsNone(MARK.search(text))
                    self.assertIsNone(DASH.search(text))
            for key, names in (('one', 'AP'), ('three', 'AP, Damage, Range'),
                               ('five', 'AP, Damage, Range')):
                self.assertIn(names, said[key], (lang, key))
            self.assertIn('5', said['five'])
            self.assertIn('4', said['four'])
            self.assertIn('5', said['weight'])
            self.assertIn('11', said['minimum'])
            self.assertIn('90%', said['guardHp'])
            self.assertIn('85%', said['guardTurn'])
            self.assertNotEqual(said['guardHp'], said['guardTurn'])

    def test_french_picks_the_singular_for_one_and_the_plural_after(self):
        said = self.spoken('fr')
        self.assertEqual('Ton dernier choix a changé 1 caractéristique : AP.', said['one'])
        self.assertEqual('Ton dernier choix a changé 2 caractéristiques : AP, Damage.',
                         said['two'])
        self.assertTrue(said['four'].endswith('Range et 1 autre.'), said['four'])
        self.assertTrue(said['five'].endswith('Range et 2 autres.'), said['five'])
        self.assertEqual('1 modifié', said['badgeOne'])
        self.assertEqual('7 modifiés', said['badgeMany'])
        self.assertIsNone(FRENCH_FORMAL.search(' '.join(text for text in said.values() if text)))

    def test_the_other_languages_pick_the_plural_from_two_up(self):
        wanted = {
            'es': ('Tu última elección ha cambiado 1 característica: AP.',
                   'Tu última elección ha cambiado 2 características: AP, Damage.'),
            'pt': ('A sua última escolha alterou 1 característica: AP.',
                   'A sua última escolha alterou 2 características: AP, Damage.'),
            'de': ('Ihre letzte Auswahl hat 1 Eigenschaft geändert: AP.',
                   'Ihre letzte Auswahl hat 2 Eigenschaften geändert: AP, Damage.')}
        for lang, (one, two) in wanted.items():
            said = self.spoken(lang)
            with self.subTest(lang=lang):
                self.assertEqual(one, said['one'])
                self.assertEqual(two, said['two'])
