# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
import json
from pathlib import Path
import sys
import tempfile
from unittest import TestCase

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'itemscraper'))
import build_wakfu_recipes as recipes  # noqa: E402


class AWakfuIngredientTitledInOneLanguageKeepsAnEnglishRowTests(TestCase):
    """The site joins ingredient names on English, so every named ingredient gets an English row."""

    def names(self, jobs_items):
        with tempfile.TemporaryDirectory() as raw:
            Path(raw, 'items.json').write_text(json.dumps([
                {'definition': {'item': {'id': 1}}, 'title': {'en': 'Ring', 'fr': 'Anneau', 'es': '', 'pt': ''}},
            ]), encoding='utf-8')
            Path(raw, 'jobsItems.json').write_text(json.dumps(jobs_items), encoding='utf-8')
            return recipes.every_name(raw)

    def test_a_resource_titled_in_french_only_is_named_in_english_by_its_french_title(self):
        names = self.names([{'definition': {'id': 33496},
                             'title': {'fr': 'Bouquet roselier', 'en': '', 'es': '', 'pt': ''}}])
        self.assertEqual({'en': 'Bouquet roselier', 'fr': 'Bouquet roselier', 'de': 'Bouquet roselier'}, names[33496])

    def test_spanish_stands_in_when_french_is_missing_too(self):
        names = self.names([{'definition': {'id': 7}, 'title': {'es': 'Ramo', 'pt': 'Buque'}}])
        self.assertEqual('Ramo', names[7]['en'])
        self.assertEqual('Buque', names[7]['pt'])
        self.assertNotIn('fr', names[7])

    def test_an_english_title_is_kept_as_it_is(self):
        names = self.names([{'definition': {'id': 8}, 'title': {'en': 'Wheat', 'fr': 'Blé'}}])
        self.assertEqual({'en': 'Wheat', 'fr': 'Blé', 'de': 'Wheat'}, names[8])
        self.assertEqual({'en': 'Ring', 'fr': 'Anneau', 'de': 'Ring'}, names[1])

    def test_a_resource_titled_in_no_language_stays_unnamed(self):
        names = self.names([{'definition': {'id': 9}, 'title': {'fr': '', 'en': ''}}])
        self.assertNotIn(9, names)
