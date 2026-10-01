# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""An import names the sibling version that has pieces this one lacks, and a Beta import lands on the Beta."""
import re
from unittest import mock

from django.test import TestCase

from chardata import text_build_view
from chardata.models import Char
from chardata.tests_a_build_copied_to_its_sibling_version_names_the_pieces_left_behind import renumbered_beta
from chardata.version_copy import import_offers, link_build_in
from fashionistapulp.structure import get_structure, set_current_game_version

LEVEL = 60
BETA_ONLY_PIECE = 27228

_OFFER = re.compile(r'<div[^>]*import-sibling-(\w+)[^>]*>(.*?)</div>', re.S)


def _common(level=LEVEL):
    dofus3, beta = get_structure('dofus3'), get_structure('beta')
    names = []
    for type_name in ('Hat', 'Cloak'):
        item = next(item for item in dofus3.types[level][type_name]
                    if not item.removed and item.ankama_id
                    and dofus3.get_item_by_name(item.name) is item
                    and beta.get_item_by_ankama_id(item.ankama_id) is not None
                    and not getattr(item, 'classes', ()))
        names.append(dofus3.get_item_name_in_language(item, 'en'))
    return names


def _horn():
    beta = get_structure('beta')
    return beta.get_item_name_in_language(beta.get_item_by_ankama_id(BETA_ONLY_PIECE), 'en')


def _offers(page):
    return {key: body for key, body in _OFFER.findall(page.content.decode('utf-8'))}


class TheImportNamesTheSiblingThatHasMoreTests(TestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')

    def test_the_horn_is_a_beta_piece_only(self):
        self.assertIsNone(get_structure('dofus3').get_item_by_ankama_id(BETA_ONLY_PIECE))
        self.assertIsNotNone(get_structure('beta').get_item_by_ankama_id(BETA_ONLY_PIECE))

    def test_a_beta_piece_pasted_on_dofus3_offers_the_beta(self):
        page = self.client.post('/import/text/', {
            'text': '\n'.join(_common() + [_horn()])}, HTTP_ACCEPT_LANGUAGE='en')
        offers = _offers(page)
        self.assertEqual(['beta'], list(offers))
        self.assertEqual([_horn()], re.findall(r'<li>(.*?)</li>', offers['beta']))
        self.assertIn('Import on Dofus 3 Beta instead', offers['beta'])
        self.assertRegex(offers['beta'], r'action="?/beta/import/text/')

    def test_the_offer_counts_only_the_pieces_this_version_lacks(self):
        offers = import_offers('\n'.join(_common() + [_horn()]), 'dofus3', 'en')
        self.assertEqual([('beta', 1, [_horn()])],
                         [(o['key'], o['count'], o['names']) for o in offers])
        self.assertEqual([], import_offers('\n'.join(_common()), 'dofus3', 'en'))
        self.assertEqual([], import_offers('\n'.join(_common() + [_horn()]), 'beta', 'en'))
        self.assertEqual([], import_offers('\n'.join(_common()), 'dofus2', 'en'))

    def test_a_paste_both_versions_carry_offers_nothing(self):
        page = self.client.post('/import/text/', {'text': '\n'.join(_common())})
        self.assertContains(page, 'Bring this build in')
        self.assertEqual({}, _offers(page))

    def test_the_offer_takes_the_paste_to_the_beta_preview(self):
        page = self.client.post('/beta/import/text/', {
            'text': '\n'.join(_common() + [_horn()])}, HTTP_ACCEPT_LANGUAGE='en')
        self.assertContains(page, 'Bring this build in')
        self.assertContains(page, _horn())
        self.assertEqual({}, _offers(page))


class ABetaImportLandsOnTheBetaTests(TestCase):

    def setUp(self):
        self.addCleanup(setattr, text_build_view, 'read_build',
                        text_build_view.read_build)
        self.addCleanup(set_current_game_version, 'dofus3')

    def _dofus3_link(self):
        structure = get_structure('dofus3')
        ids = [structure.get_item_by_name(name).id for name in _common()]
        build = {'game_version': 'dofus3', 'source_host': 'www.dofusbook.net',
                 'build_id': '1', 'name': 'Linked', 'level': LEVEL,
                 'item_ids': ids, 'missing': [], 'class_is_unknown': True,
                 'rolls': {}, 'fm_unmapped': []}
        text_build_view.read_build = lambda url, opener=None: build
        return build

    def _worn(self, char):
        from chardata.solution import get_solution
        set_current_game_version(char.game_version)
        return sorted(item.ankama_id for item in get_solution(char).item_list
                      if getattr(item, 'item_added', False))

    def test_a_dofus3_link_imported_under_the_beta_prefix_lands_on_the_beta(self):
        build = self._dofus3_link()
        answer = self.client.post('/beta/import/text/', {
            'text': 'https://www.dofusbook.net/fr/stuff/123-a',
            'confirm': '1', 'char_class': 'Cra', 'level': str(LEVEL)})
        self.assertEqual(302, answer.status_code)
        self.assertTrue(answer['Location'].startswith('/beta/solution/'),
                        answer['Location'])
        char = Char.objects.get()
        self.assertEqual('beta', char.game_version)
        dofus3 = get_structure('dofus3')
        self.assertEqual(sorted(dofus3.get_item_by_id(item_id).ankama_id
                                for item_id in build['item_ids']), self._worn(char))

    def test_the_same_link_on_the_dofus3_page_stays_on_dofus3(self):
        self._dofus3_link()
        answer = self.client.post('/import/text/', {
            'text': 'https://www.dofusbook.net/fr/stuff/123-a',
            'confirm': '1', 'char_class': 'Cra', 'level': str(LEVEL)})
        self.assertTrue(answer['Location'].startswith('/solution/'),
                        answer['Location'])
        self.assertEqual('dofus3', Char.objects.get().game_version)

    def test_a_dofus3_export_is_read_on_the_beta_page(self):
        from chardata.solution import get_solution
        from chardata.solution_view import _build_share_text
        from django.test import RequestFactory
        self.client.post('/import/text/', {
            'text': '\n'.join(_common()), 'confirm': '1',
            'char_class': 'Cra', 'level': str(LEVEL)})
        char = Char.objects.get()
        set_current_game_version('dofus3')
        exported = _build_share_text(RequestFactory().get('/'), char,
                                     get_solution(char))
        page = self.client.post('/beta/import/text/', {'text': exported},
                                HTTP_ACCEPT_LANGUAGE='en')
        self.assertNotContains(page, 'a different item in each game')
        self.assertContains(page, 'Bring this build in')


def _stuffer_link(ankama_ids_by_type):
    from chardata import dofusbook_export
    grouped = [list(ankama_ids_by_type.get(type_name, ()))
               for type_name, _codes in dofusbook_export.GROUPS]
    stuff = dofusbook_export.payload(grouped, LEVEL)
    return dofusbook_export.build_url('dofus3', 'fr', stuff)


class ALinksBetaPiecesAreFoundOnTheBetaTests(TestCase):
    """A DofusBook link is read as Dofus 3; the pieces only the Beta has are found there."""

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')
        dofus3 = get_structure('dofus3')
        self.common = [next(item for item in dofus3.types[LEVEL][type_name]
                            if not item.removed and item.ankama_id
                            and get_structure('beta').get_item_by_ankama_id(item.ankama_id)
                            and not getattr(item, 'classes', ()))
                       for type_name in ('Hat', 'Cloak')]
        self.link = _stuffer_link({'Hat': [self.common[0].ankama_id],
                                   'Cloak': [self.common[1].ankama_id],
                                   'Dofus': [BETA_ONLY_PIECE]})

    def test_the_reader_keeps_the_ankama_id_of_the_piece_it_could_not_place(self):
        from chardata import build_link_import
        build = build_link_import.read(self.link)
        self.assertEqual('dofus3', build['game_version'])
        self.assertEqual([str(BETA_ONLY_PIECE)], build['missing'])
        self.assertEqual([BETA_ONLY_PIECE], build['missing_ankama_ids'])

    def test_the_link_imported_on_the_beta_wears_the_beta_piece(self):
        preview = self.client.post('/beta/import/text/', {'text': self.link},
                                   HTTP_ACCEPT_LANGUAGE='en')
        self.assertContains(preview, _horn())
        answer = self.client.post('/beta/import/text/', {
            'text': self.link, 'confirm': '1', 'char_class': 'Cra',
            'level': str(LEVEL)})
        self.assertEqual(302, answer.status_code)
        char = Char.objects.get()
        self.assertEqual('beta', char.game_version)
        from chardata.solution import get_solution
        set_current_game_version('beta')
        worn = sorted(item.ankama_id for item in get_solution(char).item_list
                      if getattr(item, 'item_added', False))
        self.assertEqual(sorted([item.ankama_id for item in self.common]
                                + [BETA_ONLY_PIECE]), worn)

    def test_the_link_on_the_dofus3_page_offers_the_beta(self):
        page = self.client.post('/import/text/', {'text': self.link},
                                HTTP_ACCEPT_LANGUAGE='en')
        offers = _offers(page)
        self.assertEqual(['beta'], list(offers))
        self.assertEqual([_horn()], re.findall(r'<li>(.*?)</li>', offers['beta']))


class ALinkMovedToTheBetaUsesTheBetasIdsTests(TestCase):
    """The Beta renumbered: a moved link carries the Beta's ids, never Dofus 3's."""

    SHIFT = 1

    def test_pieces_rolls_and_unplaced_pieces_take_the_betas_ids(self):
        dofus3, beta = get_structure('dofus3'), get_structure('beta')
        hat, cloak = [dofus3.get_item_by_name(name) for name in _common()]
        build = {'game_version': 'dofus3', 'item_ids': [hat.id, cloak.id],
                 'missing': [str(BETA_ONLY_PIECE)],
                 'missing_ankama_ids': [BETA_ONLY_PIECE],
                 'rolls': {hat.id: [{'key': 'vit', 'value': 40}]},
                 'fm_unmapped': [(cloak.id, 'xx', 3)],
                 'fm_not_carried': [hat.id]}
        with mock.patch('chardata.version_copy.get_structure', renumbered_beta(self.SHIFT)):
            moved = link_build_in(build, 'beta', 'en')

        def there(item):
            return beta.get_item_by_ankama_id(item.ankama_id).id + self.SHIFT
        horn = beta.get_item_by_ankama_id(BETA_ONLY_PIECE).id + self.SHIFT
        self.assertEqual('beta', moved['game_version'])
        self.assertEqual([there(hat), there(cloak), horn], moved['item_ids'])
        self.assertEqual([], moved['missing'])
        self.assertEqual([], moved['missing_ankama_ids'])
        self.assertEqual({there(hat): [{'key': 'vit', 'value': 40}]}, moved['rolls'])
        self.assertEqual([(there(cloak), 'xx', 3)], moved['fm_unmapped'])
        self.assertEqual([there(hat)], moved['fm_not_carried'])
        self.assertNotIn(hat.id, moved['item_ids'])
        self.assertEqual(['dofus3', [hat.id, cloak.id]],
                         [build['game_version'], build['item_ids']])
