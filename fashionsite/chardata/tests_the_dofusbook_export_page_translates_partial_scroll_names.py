# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A stat scrolled between 1 and 99 keeps its translated name on the export page."""

import json
from unittest import mock

from django.test import TestCase, override_settings

from chardata.models import Char, CharBaseStats
from fashionistapulp.structure import get_structure, set_current_game_version

TEMOINS = {
    'fr': 'Sagesse',
    'es': 'Sabiduría',
    'pt': 'Sabedoria',
    'de': 'Weisheit',
}


class _Reponse(object):
    def __init__(self, connus):
        self._connus = connus

    def read(self, *args):
        return json.dumps(
            {'data': [{'official': a} for a in self._connus]}).encode('utf-8')

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


@override_settings(BUILD_SITES_ENABLED=('dofusbook',))
class TheDofusbookExportPageTranslatesPartialScrollNamesTests(TestCase):

    def _char(self, langue):
        set_current_game_version('dofus3')
        structure = get_structure('dofus3')
        item = next(i for i in structure.types[200]['Hat']
                    if not i.removed and i.ankama_id)
        texte = structure.get_item_name_in_language(item, 'en')
        self.client.post('/%s/import/text/' % langue, {
            'text': texte, 'confirm': '1', 'char_class': 'Iop', 'level': '200'})
        char = Char.objects.order_by('-id').first()
        CharBaseStats.objects.filter(char=char, stat='Wisdom').update(
            scrolled_value=50, total_value=50)
        return char, item.ankama_id

    def test_the_partial_scroll_name_is_translated(self):
        for langue, mot in TEMOINS.items():
            char, ankama_id = self._char(langue)
            with mock.patch(
                    'chardata.dofusbook_export.urllib.request.urlopen',
                    return_value=_Reponse([ankama_id])):
                page = self.client.get(
                    '/%s/export/dofusbook/%d/' % (langue, char.id)
                ).content.decode('utf-8')
            with self.subTest(langue=langue):
                self.assertIn(mot, page)
                self.assertNotIn('Wisdom', page)
