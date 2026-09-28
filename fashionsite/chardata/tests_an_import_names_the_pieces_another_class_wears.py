# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The import preview names each class-only piece's class, and lists the ones the chosen class leaves out."""

import gettext
import os
import re

from django.conf import settings
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase
from django.utils import translation

from chardata.wear_conditions import class_condition_text
from fashionistapulp.structure import get_structure, set_current_game_version

SENTENCE = 'These pieces are for another class, so they are left out:'

BROWSER = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
           '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36')


class ThePreviewNamesTheOtherClassPiecesTests(TestCase):

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.addCleanup(set_current_game_version, 'dofus3')
        set_current_game_version('touch')
        structure = get_structure('touch')
        self.power = structure.get_item_by_name('Iop Seal: Power')
        self.heroism = structure.get_item_by_name('Feca Seal: Heroism')
        self.insignia = structure.get_item_by_ankama_id(23485)
        self.text = '\n'.join(item.localized_names['en'] for item in
                              (self.heroism, self.power, self.insignia))

    def _preview(self, language='en', **fields):
        answer = self.client.post('/%stouch/import/text/' % (
            '' if language == 'en' else language + '/'),
            dict(fields, text=self.text), HTTP_ACCEPT_LANGUAGE=language,
            HTTP_USER_AGENT=BROWSER)
        self.assertEqual(200, answer.status_code)
        return answer.content.decode('utf-8')

    def _left_out(self, page):
        found = re.search(r'<p[^>]*id="?import-other-class"?[^>]*>(.*?)</p>', page, re.S)
        return found.group(1) if found else None

    def test_a_feca_preview_lists_the_iop_seal_only(self):
        left_out = self._left_out(self._preview(char_class='Feca'))
        self.assertIsNotNone(left_out)
        self.assertIn(SENTENCE, left_out)
        self.assertIn(self.power.localized_names['en'], left_out)
        self.assertNotIn(self.heroism.localized_names['en'], left_out)
        self.assertNotIn(self.insignia.localized_names['en'], left_out)

    def test_a_preview_with_no_class_chosen_lists_nothing_but_tags_each_seal(self):
        page = self._preview()
        self.assertIsNone(self._left_out(page))
        with translation.override('en'):
            for char_class in ('Iop', 'Feca'):
                self.assertIn(class_condition_text((char_class,)), page)

    def test_the_french_preview_says_it_in_french(self):
        left_out = self._left_out(self._preview('fr', char_class='Feca'))
        with translation.override('fr'):
            self.assertIn(translation.gettext(SENTENCE), left_out)
        self.assertNotIn(SENTENCE, left_out)

    def test_the_confirmed_feca_build_wears_what_the_preview_kept(self):
        from chardata.char_blobs import read_char_blob
        from chardata.models import Char
        answer = self.client.post('/touch/import/text/', {
            'text': self.text, 'confirm': '1', 'char_class': 'Feca',
            'level': '200'}, HTTP_USER_AGENT=BROWSER)
        self.assertEqual(302, answer.status_code)
        char = Char.objects.order_by('-id').first()
        stored = read_char_blob(char.minimal_solution, None,
                                'minimal_solution', char).item_per_slot
        worn = {item_id for slot, item_id in stored.items()
                if slot.startswith('emblem') and item_id}
        self.assertEqual({self.heroism.id, self.insignia.id}, worn)


class TheSentenceIsInEveryCatalogueTests(SimpleTestCase):

    def test_four_native_translations(self):
        seen = set()
        for language in ('fr', 'es', 'pt', 'de'):
            text = gettext.translation(
                'django', os.path.join(settings.BASE_DIR, 'locale'),
                languages=[language]).gettext(SENTENCE)
            self.assertNotEqual(SENTENCE, text, language)
            self.assertTrue(text.rstrip().endswith(':'), language)
            seen.add(text)
        self.assertEqual(4, len(seen))
