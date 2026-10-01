# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The solution page, the picker, the lock, the imports and the quick start say why a build cannot wear a piece, and keep what the player stored."""

import html
import json
import pickle
import re
import tempfile
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase

from chardata.char_blobs import read_char_blob
from chardata.coaching_view import included_item_for, level_options_for
from chardata.lock_forbid import get_inclusions_dict, set_item_included
from chardata.models import Char
from chardata.solution_result import evolve_result_item
from chardata.tests import itemscraper_module
from chardata.tests_a_piece_for_one_sex_or_one_name_is_worn_only_by_that_character import (
    condition_lines)
from chardata.tests_a_piece_its_build_cannot_wear_is_refused_at_every_door import (
    APPRENTICE_PILGRIM_STAFF, BELLADONNAS_BITTERNESS, BELLADONNAS_CRUELTY,
    FIRST_BLOOD_STAFF, THE_ENUTROFION, WORN_KOOLICH_HEADGEAR, _Build)
from fashionistapulp.modelresult import ModelResultItem
from fashionistapulp.structure import get_structure, set_current_game_version

TATTY_BIM_BONNET = 11603

_ITEMS_PER_TYPE = re.compile(r'var allItemsPerType = (\{.*?\});', re.S)


class _Stored(_Build):

    def _wearing(self, version, slots, char_class='Iop', level=200):
        char = self._char(version, char_class, level)
        minimal = read_char_blob(char.minimal_solution, None, 'minimal_solution', char)
        for slot, ankama_id in slots.items():
            minimal.item_per_slot[slot] = self._piece(version, ankama_id).id
        char.minimal_solution = pickle.dumps(minimal)
        char.save()
        return char

    def _page(self, char):
        prefix = '' if char.game_version == 'dofus3' else '/' + char.game_version
        page = self.client.get('%s/solution/%d/' % (prefix, char.id), follow=True)
        self.assertEqual(200, page.status_code)
        return condition_lines(page)


class TheSolutionPageSaysWhyInRedTests(_Stored):

    def test_a_stored_worn_koolich_headgear_shows_a_red_unequippable_line(self):
        char = self._wearing('touch', {'hat': WORN_KOOLICH_HEADGEAR}, level=110)
        self.assertIn(('Unequippable item', True), self._page(char))
        stored = read_char_blob(char.minimal_solution, None, 'minimal_solution', char)
        self.assertEqual(self._piece('touch', WORN_KOOLICH_HEADGEAR).id,
                         stored.item_per_slot['hat'])

    def test_the_pilgrim_staff_line_turns_red_past_level_five(self):
        at_five = self._wearing('dofus3', {'weapon': APPRENTICE_PILGRIM_STAFF}, level=5)
        self.assertIn(('Be level 5 or lower', False), self._page(at_five))
        at_six = self._wearing('dofus3', {'weapon': APPRENTICE_PILGRIM_STAFF}, level=6)
        self.assertIn(('Be level 5 or lower', True), self._page(at_six))

    def test_two_belladonna_rings_worn_together_show_the_clash_in_red(self):
        char = self._wearing('dofus2', {'ring1': BELLADONNAS_CRUELTY,
                                        'ring2': BELLADONNAS_BITTERNESS})
        lines = self._page(char)
        self.assertIn(('Not have the "Belladonna\'s Bitterness" item equipped', True), lines)
        self.assertIn(('Not have the "Belladonna\'s Cruelty" item equipped', True), lines)

    def test_one_belladonna_ring_alone_shows_the_rule_without_red(self):
        char = self._wearing('dofus2', {'ring1': BELLADONNAS_CRUELTY})
        self.assertIn(('Not have the "Belladonna\'s Bitterness" item equipped', False),
                      self._page(char))

    def test_an_exact_stat_is_one_line(self):
        char = self._wearing('dofus3', {'hat': TATTY_BIM_BONNET})
        lines = [text for text, _red in self._page(char)]
        self.assertIn('Chance = 0', lines)
        self.assertFalse([text for text in lines
                          if text.startswith(('Chance >', 'Chance <'))])


class ThePickerCardSaysTheRuleTests(SimpleTestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')
        set_current_game_version('dofus3')

    def lines(self, ankama_id):
        result_item = ModelResultItem(get_structure('dofus3').get_item_by_ankama_id(ankama_id))
        evolve_result_item(result_item)
        return [line.text for line in result_item.condition_lines]

    def test_the_bonnet_card_shows_chance_equal_to_zero(self):
        self.assertEqual(['Chance = 0'], self.lines(TATTY_BIM_BONNET))

    def test_the_pilgrim_staff_card_shows_its_highest_level(self):
        self.assertIn('Be level 5 or lower', self.lines(APPRENTICE_PILGRIM_STAFF))


class TheLockButtonSaysWhyTests(_Build):

    def test_the_second_belladonna_ring_is_refused_with_the_reason(self):
        cruelty = self._piece('dofus2', BELLADONNAS_CRUELTY)
        bitterness = self._piece('dofus2', BELLADONNAS_BITTERNESS)
        char = self._char('dofus2')
        self.assertTrue(set_item_included(char, cruelty.id, 'ring1', True))
        refused = self.client.post('/dofus2/setitemlocked/%d/' % char.id, {
            'slot': 'ring2', 'locked': 'true', 'equip': bitterness.name})
        self.assertEqual(400, refused.status_code)
        self.assertEqual('Not locked, this build cannot wear it: '
                         'Not have the "Belladonna\'s Cruelty" item equipped',
                         refused.content.decode('utf-8'))
        self.assertEqual({'ring1': cruelty.id}, get_inclusions_dict(char))

    def test_the_solution_page_puts_a_refused_lock_back_and_prints_its_plain_text_reason(self):
        cruelty = self._piece('dofus2', BELLADONNAS_CRUELTY)
        bitterness = self._piece('dofus2', BELLADONNAS_BITTERNESS)
        char = self._char('dofus2')
        self.assertTrue(set_item_included(char, cruelty.id, 'ring1', True))
        refused = self.client.post('/dofus2/setitemlocked/%d/' % char.id, {
            'slot': 'ring2', 'locked': 'true', 'equip': bitterness.name})
        self.assertEqual(400, refused.status_code)
        self.assertTrue(refused['Content-Type'].startswith('text/plain'))
        page = self.client.get('/dofus2/solution/%d/' % char.id, follow=True)
        script = re.sub(r'\s+', ' ', page.content.decode('utf-8'))
        handler = script[script.index('/setitemlocked/'):script.index('$.each(itemIsForbidden')]
        for step in ('.fail(function(xhr)', 'itemIsLocked[key] = wasLocked',
                     'itemIsForbidden[key] = wasForbidden',
                     'updateLockButtonState(lockButton, key)',
                     'updateForbidButtonState(forbidButton, key)',
                     '.indexOf("text/plain")', '.text(xhr.responseText)'):
            self.assertIn(step, handler)

    def test_the_pilgrim_staff_is_refused_past_level_five_with_the_reason(self):
        staff = self._piece('dofus3', APPRENTICE_PILGRIM_STAFF)
        char = self._char('dofus3', level=6)
        refused = self.client.post('/setitemlocked/%d/' % char.id, {
            'slot': 'weapon', 'locked': 'true', 'equip': staff.name})
        self.assertEqual(400, refused.status_code)
        self.assertIn('Be level 5 or lower', refused.content.decode('utf-8'))

    def test_a_stored_lock_of_another_class_is_refused_again_but_can_be_unlocked(self):
        ring = self._piece('touch', THE_ENUTROFION)
        char = self._char('touch', level=110)
        char.inclusions = pickle.dumps({'ring1': ring.id})
        char.save()
        refused = self.client.post('/touch/setitemlocked/%d/' % char.id, {
            'slot': 'ring2', 'locked': 'true', 'equip': ring.name})
        self.assertEqual(400, refused.status_code)
        self.assertIn('Enutrof', refused.content.decode('utf-8'))
        unlocked = self.client.post('/touch/setitemlocked/%d/' % char.id, {
            'slot': 'ring1', 'locked': 'false', 'equip': ring.name})
        self.assertEqual(200, unlocked.status_code)
        char.refresh_from_db()
        self.assertEqual('', get_inclusions_dict(char).get('ring1', ''))


class TheLockPageSaysWhyAndKeepsStoredLocksTests(_Build):

    def _listed(self, char):
        page = self.client.get('/inclusions/%d/' % char.id, follow=True)
        self.assertEqual(200, page.status_code)
        found = _ITEMS_PER_TYPE.search(page.content.decode('utf-8'))
        self.assertIsNotNone(found)
        return {int(item_id) for per_type in json.loads(found.group(1)).values()
                for item_id in per_type}

    def test_the_pilgrim_staff_is_listed_up_to_level_five_only(self):
        staff = self._piece('dofus3', APPRENTICE_PILGRIM_STAFF)
        self.assertIn(staff.id, self._listed(self._char('dofus3', level=5)))
        self.assertNotIn(staff.id, self._listed(self._char('dofus3', level=6)))

    def test_saving_another_lock_keeps_a_stored_worn_koolich_headgear_and_says_why(self):
        headgear = self._piece('touch', WORN_KOOLICH_HEADGEAR)
        ring = self._piece('touch', THE_ENUTROFION)
        char = self._char('touch', 'Enutrof', level=110)
        char.inclusions = pickle.dumps({'hat': headgear.id})
        char.save()
        answer = self.client.post('/touch/inclusionspost/%d/' % char.id, {
            'hat': str(headgear.id), 'ring1': str(ring.id)})
        self.assertEqual(200, answer.status_code)
        data = answer.json()
        self.assertEqual((headgear.id, ring.id), (data['hat'], data['ring1']))
        self.assertEqual({'hat': {'text': 'Still locked, but this build cannot wear it: '
                                          'Unequippable item', 'locked': True}},
                         data['_notes'])
        char.refresh_from_db()
        self.assertEqual({'hat': headgear.id, 'ring1': ring.id}, get_inclusions_dict(char))
        page = self.client.get('/touch/inclusions/%d/' % char.id, follow=True)
        self.assertIn('Still locked, but this build cannot wear it',
                      html.unescape(page.content.decode('utf-8')))

    def test_saving_both_belladonna_rings_keeps_one_and_says_why_not_the_other(self):
        cruelty = self._piece('dofus2', BELLADONNAS_CRUELTY)
        bitterness = self._piece('dofus2', BELLADONNAS_BITTERNESS)
        char = self._char('dofus2')
        data = self.client.post('/dofus2/inclusionspost/%d/' % char.id, {
            'ring1': str(cruelty.id), 'ring2': str(bitterness.id)}).json()
        self.assertEqual((cruelty.id, ''), (data['ring1'], data['ring2']))
        self.assertEqual({'ring2': {'text': 'Not locked, this build cannot wear it: '
                                            'Not have the "Belladonna\'s Cruelty" item equipped',
                                    'locked': False}},
                         data['_notes'])


class TheImportSaysWhyAPieceIsLeftOutTests(_Build):

    def test_the_preview_names_the_reason_and_the_build_leaves_the_piece_out(self):
        set_current_game_version('touch')
        headgear = self._piece('touch', WORN_KOOLICH_HEADGEAR)
        preview = self.client.post('/touch/import/text/', {'text': headgear.name})
        self.assertEqual(200, preview.status_code)
        self.assertIn('Left out, this build cannot wear it: Unequippable item',
                      html.unescape(preview.content.decode('utf-8')))
        answer = self.client.post('/touch/import/text/', {
            'text': headgear.name + '\nKoolich Headgear', 'confirm': '1',
            'char_class': 'Iop', 'level': '110'})
        self.assertEqual(302, answer.status_code)
        char = Char.objects.order_by('-id').first()
        stored = read_char_blob(char.minimal_solution, None, 'minimal_solution', char)
        self.assertNotIn(headgear.id, stored.item_per_slot.values())

    def test_a_sent_build_leaves_out_an_unusable_piece_and_names_it(self):
        from chardata import fashionista_build
        payload = fashionista_build.example_payload('dofus3')
        payload['items'] = list(payload['items']) + [FIRST_BLOOD_STAFF]
        reading = fashionista_build.check(payload)
        self.assertTrue(reading.valid)
        piece = reading.pieces[-1]
        self.assertEqual((FIRST_BLOOD_STAFF, True, False),
                         (piece['id'], piece['found'], piece['placed']))
        staff = self._piece('dofus3', FIRST_BLOOD_STAFF)
        self.assertEqual([staff.id], reading.build['not_wearable'])
        self.assertNotIn(staff.id, reading.build['item_ids'])


class TheQuickStartOffersOnlyWhatThePieceAllowsTests(_Build):

    def test_the_levels_stop_at_the_highest_level_of_the_piece(self):
        self.assertEqual(([1, 5], 5), level_options_for(1, 5))
        self.assertEqual(([150, 180, 200], 200), level_options_for(150, None))
        self.assertEqual(([20, 50, 100], 100), level_options_for(20, 100))

    def test_the_pilgrim_staff_form_offers_levels_up_to_five(self):
        staff = self._piece('dofus3', APPRENTICE_PILGRIM_STAFF)
        page = self.client.get('/quickstart/?item=%d' % staff.id, follow=True)
        self.assertEqual(200, page.status_code)
        self.assertEqual(5, max(page.context['level_options']))

    def test_an_unequippable_piece_is_not_built_around(self):
        staff = self._piece('dofus3', FIRST_BLOOD_STAFF)
        self.assertIsNone(included_item_for('dofus3', staff.id))
        page = self.client.get('/encyclopedia/item/equipment/%d-x/' % FIRST_BLOOD_STAFF,
                               follow=True)
        self.assertNotIn('encyclopedia-build-around', page.content.decode('utf-8'))
        page = self.client.get('/encyclopedia/item/equipment/%d-x/' % APPRENTICE_PILGRIM_STAFF,
                               follow=True)
        self.assertIn('encyclopedia-build-around', page.content.decode('utf-8'))


def _download_module():
    return itemscraper_module('download_raw_data')


class _Answer:

    def __init__(self, chunks, length):
        self.chunks, self.headers = chunks, {'Content-Length': str(length)}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size):
        return iter(self.chunks)


class TheRawDownloadFetchesWhatItNamesWholeTests(SimpleTestCase):

    def test_a_name_with_a_dot_matches_that_file_only(self):
        module = _download_module()
        names = ['items.json', 'MAPPED_ITEMS.json', 'effects.json', 'evol_effects.json',
                 'spells.json', 'spell_levels.json']
        self.assertEqual(['items.json', 'effects.json', 'spells.json', 'spell_levels.json'],
                         [name for name in names
                          if module._match_filters(name, ['items.json', 'effects.json', 'spell'])])

    def test_a_cut_download_leaves_no_file_and_a_whole_one_lands(self):
        module = _download_module()
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'items.json'
            with mock.patch.object(module.requests, 'get',
                                   return_value=_Answer([b'{"a": '], 12)), \
                    mock.patch.object(module.sys, 'stdout'):
                with self.assertRaises(module.requests.RequestException):
                    module._download('https://example.org/items.json', target)
            self.assertEqual([], list(Path(folder).iterdir()))
            with mock.patch.object(module.requests, 'get',
                                   return_value=_Answer([b'{"a": ', b'1}'], 8)), \
                    mock.patch.object(module.sys, 'stdout'):
                module._download('https://example.org/items.json', target)
            self.assertEqual(['items.json'], [path.name for path in Path(folder).iterdir()])
            self.assertEqual(b'{"a": 1}', target.read_bytes())
