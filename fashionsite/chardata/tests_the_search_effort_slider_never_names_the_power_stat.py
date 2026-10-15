# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The slider choosing how long the optimizer searches is called Search effort, never by the name of the Power stat it sits next to."""
import html
import re
import unicodedata

from django.template.loader import render_to_string
from django.test import SimpleTestCase
from django.utils import translation

from chardata.power_steps import power_context
from chardata.tests_the_setup_panel_strings_are_translated_in_five_languages import (
    LANGUAGES, catalogue)

LABEL = {'en': 'Search effort', 'fr': 'Effort de recherche',
         'es': 'Esfuerzo de b' + chr(0xFA) + 'squeda', 'pt': 'Esfor' + chr(0xE7) + 'o de busca',
         'de': 'Gr' + chr(0xFC) + 'ndlichkeit des Optimierers'}
POWER_STAT_WORDS = ('power', 'puissance', 'potencia', 'leistung', 'schlagkraft')


def folded(text):
    return ''.join(char for char in unicodedata.normalize('NFKD', text.lower())
                   if not unicodedata.combining(char))


def slider_text(lang):
    with translation.override(lang):
        rendered = render_to_string('chardata/setup_power.html', {'power': power_context()})
    return html.unescape(re.sub(r'<[^>]+>', ' ', rendered))


class TheSliderIsCalledSearchEffortTests(SimpleTestCase):

    def test_each_language_reads_its_search_effort_label(self):
        for lang in LANGUAGES:
            with self.subTest(lang=lang):
                self.assertIn(LABEL[lang], slider_text(lang))

    def test_no_slider_string_names_the_power_stat_in_any_language(self):
        for lang in LANGUAGES:
            words = set(re.findall(r'\w+', folded(slider_text(lang))))
            for word in POWER_STAT_WORDS:
                with self.subTest(lang=lang, word=word):
                    self.assertNotIn(word, words)

    def test_the_old_label_is_gone_from_every_catalogue(self):
        for lang in LANGUAGES:
            with self.subTest(lang=lang):
                self.assertIsNone(catalogue(lang, 'django').find('Optimizer power'))
