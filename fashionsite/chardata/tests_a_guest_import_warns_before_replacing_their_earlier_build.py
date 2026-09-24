# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A guest who already holds a build sees that before a second import
replaces it, the same way the creation page and quick start do."""

from django.test import TestCase

from chardata.models import Char
from fashionistapulp.structure import get_structure


def _an_item_name(version='dofus3'):
    structure = get_structure(version)
    for item in structure.types[200]['Hat']:
        if not item.removed:
            return structure.get_item_name_in_language(item, 'en')
    raise AssertionError('no Hat item found for the test')


class GuestSecondImportWarnsAboutTheFirstBuildTests(TestCase):

    def _import(self):
        return self.client.post('/import/text/', {
            'text': _an_item_name(), 'confirm': '1',
            'char_class': 'Iop', 'level': '200'})

    def test_the_import_page_offers_no_warning_before_any_build_exists(self):
        page = self.client.get('/import/text/')
        self.assertNotContains(page, 'already have a project')

    def test_a_second_guest_import_links_to_the_first_build(self):
        self._import()
        first_id = Char.objects.order_by('-id').first().id
        page = self.client.get('/import/text/')
        self.assertContains(page, 'already have a project')
        self.assertContains(page, '/loadprojects/')
        self.assertTrue(Char.objects.filter(pk=first_id).exists())

    def test_the_second_import_preview_warns_before_the_confirm_click(self):
        self._import()
        preview = self.client.post('/import/text/', {'text': _an_item_name()})
        self.assertContains(preview, 'already have a project')
