# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A trans tag on a string with a literal percent still translates."""

from django.template import Context, Template
from django.test import SimpleTestCase, TestCase
from django.utils import translation

from chardata.models import Char

LANGUAGES = ('fr', 'es', 'pt', 'de')

WITNESSES = (
    'All % Resists',
    '% Spells Damage',
    'Use %pointsUsed% points to increase to %newTotal% at %ratio%:1',
    'Scrolled stats must be between 0 and %max%.',
)


class PercentLabelsTranslateInEveryLanguageTests(SimpleTestCase):

    def test_each_witness_translates_out_of_english(self):
        for msgid in WITNESSES:
            gabarit = Template('{%% load i18n %%}{%% trans "%s" %%}' % msgid)
            with translation.override('en'):
                english = gabarit.render(Context())
            for langue in LANGUAGES:
                with translation.override(langue):
                    rendu = gabarit.render(Context())
                with self.subTest(msgid=msgid, langue=langue):
                    self.assertNotEqual(english, rendu)
                    self.assertNotIn('%%', rendu)


class SetupAndStatsPagesShowTranslatedPercentLabelsTests(TestCase):

    def _make_char(self):
        response = self.client.post('/quickstart/', {
            'char_class': 'Iop', 'char_level': '200', 'play_style': 'solo_pvm',
        })
        self.assertEqual(302, response.status_code)
        return Char.objects.order_by('-id').first()

    def test_stats_page_shows_the_translated_weight_labels(self):
        char = self._make_char()
        temoins = {
            'fr': ('% Dommages aux Sorts', 'Toutes les Résistances (%)'),
            'de': ('% Zauberschaden', 'Alle % Widerstände'),
        }
        for langue, (spells_damage, all_resists) in temoins.items():
            page = self.client.get(
                '/%s/stats/%d/' % (langue, char.id)).content.decode('utf-8')
            with self.subTest(langue=langue):
                self.assertIn(spells_damage, page)
                self.assertIn(all_resists, page)
                self.assertNotIn('% Spells Damage', page)

    def test_setup_page_shows_the_translated_tooltip_and_error(self):
        char = self._make_char()
        temoins = {
            'fr': ('pointsUsed', 'caractéristiques montées via parchemin'),
            'de': ('pointsUsed', 'gescrollten Statistiken'),
        }
        for langue, (tooltip_word, error_phrase) in temoins.items():
            page = self.client.get(
                '/%s/setup/%d/' % (langue, char.id)).content.decode('utf-8')
            with self.subTest(langue=langue):
                self.assertIn(tooltip_word, page)
                self.assertIn(error_phrase, page)
                self.assertNotIn(
                    'Use %pointsUsed% points to increase', page)
                self.assertNotIn(
                    'Scrolled stats must be between 0 and %max%.', page)
