# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A pasted or linked roll too large for the solver is left out of the build and listed as too large, a roll at the bound is written, and a number past Python's digit limit is read as no roll."""
from django.test import TestCase
from django.utils import translation

from chardata import text_build_view
from chardata.fashionista_build import MAX_STAT_VALUE
from chardata.lock_forbid import get_stat_overrides
from chardata.models import Char
from chardata.text_build_import import read_items
from fashionistapulp.structure import get_structure

TOO_LARGE = ('9' * 400, str(MAX_STAT_VALUE + 1))
PAST_THE_DIGIT_LIMIT = '9' * 5000
OVERSIZED_MESSAGE = 'These rolls were left out, because the value is too large:'
LINK = 'https://www.dofusbook.net/fr/stuff/123-a'


class APastedRollTooLargeForTheSolverIsLeftOutTests(TestCase):

    def setUp(self):
        structure = get_structure('dofus3')
        self.item = next(item for item in structure.types[200]['Hat']
                         if not item.removed and item.stats)
        self.name = structure.get_item_name_in_language(self.item, 'en')
        self.stat = structure.get_stat_by_id(self.item.stats[0][0])

    def text(self, value):
        return '%s\n%s %s' % (self.name, value, self.stat.name)

    def confirm(self, value):
        builds = Char.objects.count()
        response = self.client.post('/import/text/', {
            'text': self.text(value), 'confirm': '1', 'char_class': 'Iop', 'level': '200'})
        self.assertEqual(302, response.status_code)
        self.assertEqual(builds + 1, Char.objects.count())
        char = Char.objects.order_by('-id').first()
        return get_stat_overrides(char).get(self.item.id, {}).get(self.stat.id)

    def test_a_roll_past_the_bound_is_not_written_on_the_build(self):
        for value in TOO_LARGE:
            with self.subTest(value=value[:12]):
                self.assertIsNone(self.confirm(value))

    def test_a_roll_past_the_bound_is_read_but_not_applied(self):
        for value in TOO_LARGE:
            with self.subTest(value=value[:12]):
                lu = read_items(self.text(value), 'dofus3', 'en')
                roll = lu['matched'][0]['rolls'][0]
                self.assertFalse(roll['applied'], roll)
                self.assertTrue(roll['too_large'], roll)
                self.assertEqual([True], [refused['too_large'] for refused in lu['refused_rolls']])

    def test_the_preview_lists_a_roll_past_the_bound_as_too_large_not_as_missing_from_the_item(self):
        response = self.client.post('/import/text/', {'text': self.text(TOO_LARGE[0])})
        self.assertEqual(200, response.status_code)
        self.assertEqual([], list(response.context['refused_rolls']))
        self.assertEqual([self.stat.name], [roll['stat'] for roll in response.context['oversized_rolls']])
        self.assertContains(response, 'id="import-oversized-rolls"')

    def test_a_roll_at_the_bound_is_written_on_the_build(self):
        self.assertEqual(MAX_STAT_VALUE, self.confirm(str(MAX_STAT_VALUE)))

    def test_a_number_past_the_digit_limit_is_read_as_no_roll(self):
        lu = read_items(self.text(PAST_THE_DIGIT_LIMIT), 'dofus3', 'en')
        self.assertEqual([], lu['matched'][0]['rolls'])
        response = self.client.post('/import/text/', {'text': self.text(PAST_THE_DIGIT_LIMIT)})
        self.assertEqual(200, response.status_code)
        self.assertIsNone(self.confirm(PAST_THE_DIGIT_LIMIT))


class ALinkedRollTooLargeForTheSolverIsLeftOutTests(TestCase):

    def setUp(self):
        self.addCleanup(setattr, text_build_view, 'read_build', text_build_view.read_build)
        structure = get_structure('dofus3')
        self.item = next(item for item in structure.types[200]['Hat']
                         if not item.removed and item.stats)
        self.stat = structure.get_stat_by_id(self.item.stats[0][0])

    def link(self, value):
        build = {'game_version': 'dofus3', 'source_host': 'www.dofusbook.net',
                 'build_id': '1', 'name': 'Imported', 'level': 200,
                 'item_ids': [self.item.id], 'missing': [], 'class_is_unknown': True,
                 'rolls': {self.item.id: [{'key': self.stat.key, 'value': value}]}}
        text_build_view.read_build = lambda url, opener=None: build

    def confirm(self, value):
        self.link(value)
        builds = Char.objects.count()
        response = self.client.post('/import/text/', {
            'text': LINK, 'confirm': '1', 'char_class': 'Iop', 'level': '200'})
        self.assertEqual(302, response.status_code)
        self.assertEqual(builds + 1, Char.objects.count())
        char = Char.objects.order_by('-id').first()
        return get_stat_overrides(char).get(self.item.id, {}).get(self.stat.id)

    def test_a_linked_roll_past_the_bound_is_not_written_on_the_build(self):
        for value in (MAX_STAT_VALUE + 1, -MAX_STAT_VALUE - 1, 10 ** 400):
            with self.subTest(value=str(value)[:12]):
                self.assertIsNone(self.confirm(value))

    def test_the_preview_lists_a_linked_roll_past_the_bound_as_too_large(self):
        self.link(MAX_STAT_VALUE + 1)
        response = self.client.post('/import/text/', {'text': LINK})
        self.assertEqual(200, response.status_code)
        self.assertEqual([], list(response.context['refused_rolls']))
        self.assertEqual([self.stat.name], [roll['stat'] for roll in response.context['oversized_rolls']])

    def test_a_linked_roll_at_the_bound_is_written_on_the_build(self):
        self.assertEqual(MAX_STAT_VALUE, self.confirm(MAX_STAT_VALUE))


class TheTooLargeRollMessageIsTranslatedTests(TestCase):

    def test_every_language_but_english_translates_the_message(self):
        for language in ('de', 'es', 'fr', 'pt'):
            with self.subTest(language=language), translation.override(language):
                self.assertNotEqual(OVERSIZED_MESSAGE, translation.gettext(OVERSIZED_MESSAGE))
