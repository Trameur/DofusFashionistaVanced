# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The power slider and the quick search lines are in the five catalogues, French and German speaking as tu and du."""
from django.test import SimpleTestCase
from django.utils import translation

from chardata.power_steps import POWER_STEPS, step_text
from chardata.tests_the_setup_panel_strings_are_translated_in_five_languages import (
    DASH, EMOJI, FRENCH_POLITE, MARK, TRANSLATED, catalogue, template_message_ids)

QUICK_STRINGS = (
    'Flash', 'Fast', 'Standard', 'Search effort',
    'The search stops as soon as its set is within %(gap)s%% of the best on your criteria, '
    'or after %(seconds)s s per search. The build page tells you which.',
    'Looks for the best set on your criteria for up to %(seconds)s s per search. '
    'The build page tells you whether it was proven.',
    'Quick search: the solver stopped as soon as it knew this set is within %(gap)s%% of the best '
    'on your criteria. A better set may exist, so this is not a proof.',
    'Within %(gap)s%% of the best, not a proof',
)
GERMAN_POLITE = ('Sie', 'Ihr', 'Ihre', 'Ihren', 'Ihnen')


class EveryCatalogueCarriesTheSliderTests(SimpleTestCase):

    def test_the_slider_template_and_the_quick_search_line_ask_for_listed_strings(self):
        asked = template_message_ids('setup_power.html') | template_message_ids('solution.html')
        self.assertIn('Search effort', asked)
        self.assertIn(QUICK_STRINGS[6], asked)

    def test_each_foreign_language_translates_every_string_and_keeps_its_placeholders(self):
        for lang in TRANSLATED:
            catalog = catalogue(lang, 'django')
            for msgid in QUICK_STRINGS:
                with self.subTest(lang=lang, msgid=msgid[:40]):
                    entry = catalog.find(msgid)
                    self.assertIsNotNone(entry)
                    self.assertFalse(entry.obsolete)
                    self.assertNotIn('fuzzy', entry.flags)
                    self.assertTrue(entry.msgstr.strip())
                    self.assertEqual(sorted(MARK.findall(msgid)), sorted(MARK.findall(entry.msgstr)))
                    self.assertIsNone(DASH.search(entry.msgstr))
                    self.assertIsNone(EMOJI.search(entry.msgstr))
                    if '%' in msgid:
                        self.assertIn('python-format', entry.flags)
                    if msgid != 'Standard' or lang in ('es', 'pt'):
                        self.assertNotEqual(msgid, entry.msgstr)

    def test_french_says_tu_and_german_says_du(self):
        french = catalogue('fr', 'django')
        german = catalogue('de', 'django')
        for msgid in QUICK_STRINGS:
            with self.subTest(msgid=msgid[:40]):
                self.assertIsNone(FRENCH_POLITE.search(french.find(msgid).msgstr))
                words = german.find(msgid).msgstr.replace(',', ' ').replace('.', ' ').split()
                self.assertFalse(set(GERMAN_POLITE) & set(words[1:]))

    def test_the_step_explanations_are_written_in_the_language_of_the_reader(self):
        for lang in TRANSLATED:
            with translation.override(lang):
                for step in POWER_STEPS:
                    with self.subTest(lang=lang, step=step.key):
                        written = step_text(step)
                        with translation.override('en'):
                            english = step_text(step)
                        self.assertNotEqual(english, written)
                        self.assertIn(str(step.seconds), written)
