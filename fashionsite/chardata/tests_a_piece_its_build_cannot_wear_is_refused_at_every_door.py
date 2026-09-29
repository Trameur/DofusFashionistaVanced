# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The picker, the switch, the lock and the import refuse a piece the build's class, level or other pieces rule out, and the item page says why."""

import html
import pickle
import re

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.utils import translation

from chardata.build_import import (NOT_WORN_TOGETHER, PAST_MAX_LEVEL, UNUSABLE,
                                   WRONG_CLASS, plan_ankama_ids)
from chardata.char_blobs import read_char_blob
from chardata.lock_forbid import (get_inclusions_dict, remove_invalid_inclusions,
                                   set_inclusions_dict_and_check_exclusions,
                                   set_item_included)
from chardata.models import Char
from chardata.tests_a_touch_build_saved_before_the_seals_still_loads import _OPTIONS
from chardata.wear_conditions import condition_texts
from fashionistapulp.dofus_constants import SLOT_NAME_TO_TYPE, STATS_NAMES, slots_for
from fashionistapulp.modelresult import ModelResultMinimal
from fashionistapulp.structure import (fits_the_class, fits_the_level,
                                       get_structure, set_current_game_version)

WORN_KOOLICH_HEADGEAR = 7887
KOOLICH_HEADGEAR = 18447
FIRST_BLOOD_STAFF = 8575
APPRENTICE_PILGRIM_STAFF = 9627
THE_ENUTROFION = 1499
BELLADONNAS_CRUELTY = 27547
BELLADONNAS_BITTERNESS = 27548
JIVA_NECKLACE = 2155
BLACK_SPOTTED_DOFUS = 7112
DOMAKURO = 23237
DORIGAMI = 23408


def _minimal(version, char_class, level):
    """A stored build wearing the first plain piece of each slot its level allows."""
    structure = get_structure(version)
    per_slot, taken = {}, set()
    for slot in slots_for(version):
        item = next((item for item in structure.types[level][SLOT_NAME_TO_TYPE[slot]]
                     if not item.removed and item.id not in taken and item.set is None
                     and fits_the_class(item, char_class)
                     and fits_the_level(item, level)), None)
        if item is not None:
            taken.add(item.id)
        per_slot[slot] = item.id if item is not None else None
    model_input = {'char_class': char_class, 'char_level': level,
                   'origin': 'generated', 'options': dict(_OPTIONS),
                   'base_stats_by_attr': {name: 0 for name, _key in STATS_NAMES},
                   'locked_equips': {}}
    return ModelResultMinimal(per_slot, model_input, {})


class _Build(TestCase):

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.addCleanup(set_current_game_version, 'dofus3')

    def _char(self, version, char_class='Iop', level=200):
        set_current_game_version(version)
        owner = User.objects.create_user('door-%s-%s-%d' % (version, char_class, level),
                                         'door@test.local', 'pw-42-solid')
        self.client.force_login(owner)
        minimal = _minimal(version, char_class, level)
        return Char.objects.create(
            name='Doors', char_name='', char_class=char_class, char_build='',
            level=level, minimum_stats=b'', minimum_crits=b'',
            stats_weight=pickle.dumps({}), options=pickle.dumps(dict(_OPTIONS)),
            inclusions=b'', exclusions=b'', owner=owner, link_shared=False,
            game_version=version, minimal_solution=pickle.dumps(minimal))

    def _offered(self, char, slot, term):
        prefix = '' if char.game_version == 'dofus3' else '/' + char.game_version
        answer = self.client.post('%s/itemadd/%d/' % (prefix, char.id),
                                  {'slot': slot, 'page': '1', 'search_term': term})
        self.assertEqual(200, answer.status_code)
        return {int(number) for number in re.findall(
            r'"id"\s*:\s*(\d+)', answer.content.decode('utf-8'))}

    def _piece(self, version, ankama_id):
        piece = get_structure(version).get_item_by_ankama_id(ankama_id)
        self.assertIsNotNone(piece)
        return piece


class ThePickerOffersOnlyWhatTheBuildCanWearTests(_Build):

    def test_the_worn_koolich_headgear_is_never_offered_and_the_repaired_one_is(self):
        worn = self._piece('touch', WORN_KOOLICH_HEADGEAR)
        repaired = self._piece('touch', KOOLICH_HEADGEAR)
        self.assertTrue(worn.unusable)
        offered = self._offered(self._char('touch', level=110), 'hat', 'Koolich')
        self.assertIn(repaired.id, offered)
        self.assertNotIn(worn.id, offered)

    def test_the_enutrofion_is_offered_to_an_enutrof_and_not_to_an_iop(self):
        ring = self._piece('touch', THE_ENUTROFION)
        self.assertIn(ring.id, self._offered(
            self._char('touch', 'Enutrof', 60), 'ring1', 'Enutrofion'))
        self.assertNotIn(ring.id, self._offered(
            self._char('touch', 'Iop', 60), 'ring1', 'Enutrofion'))

    def test_the_pilgrim_staff_leaves_the_list_past_level_five(self):
        staff = self._piece('dofus3', APPRENTICE_PILGRIM_STAFF)
        self.assertIn(staff.id, self._offered(self._char('dofus3', level=5),
                                              'weapon', 'Pilgrim'))
        self.assertNotIn(staff.id, self._offered(self._char('dofus3', level=6),
                                                 'weapon', 'Pilgrim'))

    def test_the_switch_refuses_an_unusable_staff(self):
        staff = self._piece('dofus3', FIRST_BLOOD_STAFF)
        char = self._char('dofus3')
        refused = self.client.post('/exchange/%d/' % char.id,
                                   {'itemName': str(staff.id), 'slot': 'weapon'})
        self.assertEqual(400, refused.status_code)

    def test_the_switch_refuses_the_pilgrim_staff_past_level_five(self):
        staff = self._piece('dofus3', APPRENTICE_PILGRIM_STAFF)
        refused = self.client.post('/exchange/%d/' % self._char('dofus3', level=6).id,
                                   {'itemName': str(staff.id), 'slot': 'weapon'})
        self.assertEqual(400, refused.status_code)
        taken = self.client.post('/exchange/%d/' % self._char('dofus3', level=5).id,
                                 {'itemName': str(staff.id), 'slot': 'weapon'})
        self.assertEqual(200, taken.status_code)


class TheImportRefusesWhatTheBuildCannotWearTests(_Build):

    def _rejected(self, version, ankama_ids, **build):
        set_current_game_version(version)
        _placed, rejected = plan_ankama_ids(get_structure(version), ankama_ids,
                                            game_version=version, **build)
        return dict(rejected)

    def test_an_unusable_piece_is_rejected_for_every_class(self):
        for char_class in ('Iop', 'Enutrof'):
            with self.subTest(char_class=char_class):
                self.assertEqual({FIRST_BLOOD_STAFF: UNUSABLE}, self._rejected(
                    'dofus3', [FIRST_BLOOD_STAFF], char_level=200,
                    char_class=char_class))

    def test_the_pilgrim_staff_is_rejected_past_level_five(self):
        self.assertEqual({APPRENTICE_PILGRIM_STAFF: PAST_MAX_LEVEL}, self._rejected(
            'dofus3', [APPRENTICE_PILGRIM_STAFF], char_level=6, char_class='Iop'))
        self.assertEqual({}, self._rejected(
            'dofus3', [APPRENTICE_PILGRIM_STAFF], char_level=5, char_class='Iop'))

    def test_a_class_ring_is_rejected_for_another_class_in_every_version(self):
        for version in ('dofus3', 'dofus2', 'touch', 'retro'):
            with self.subTest(version=version):
                self.assertEqual({THE_ENUTROFION: WRONG_CLASS}, self._rejected(
                    version, [THE_ENUTROFION], char_level=200, char_class='Iop'))
                self.assertEqual({}, self._rejected(
                    version, [THE_ENUTROFION], char_level=200, char_class='Enutrof'))

    def test_the_second_belladonna_ring_is_rejected(self):
        self.assertEqual({BELLADONNAS_BITTERNESS: NOT_WORN_TOGETHER}, self._rejected(
            'dofus2', [BELLADONNAS_CRUELTY, BELLADONNAS_BITTERNESS],
            char_level=200, char_class='Iop'))


class TheLockKeepsOnlyWhatTheLevelAllowsTests(_Build):

    def test_a_lower_level_keeps_the_pilgrim_staff_and_a_higher_one_drops_it(self):
        staff = self._piece('dofus3', APPRENTICE_PILGRIM_STAFF)
        char = self._char('dofus3', level=5)
        char.inclusions = pickle.dumps({'weapon': staff.id})
        char.save()
        remove_invalid_inclusions(char, 5, 'Iop')
        self.assertEqual(staff.id, get_inclusions_dict(char)['weapon'])
        remove_invalid_inclusions(char, 6, 'Iop')
        self.assertNotIn('weapon', get_inclusions_dict(char))

    def test_the_level_and_class_checks_read_the_game_data(self):
        staff = self._piece('dofus3', APPRENTICE_PILGRIM_STAFF)
        self.assertEqual((True, False), (fits_the_level(staff, 5),
                                         fits_the_level(staff, 6)))
        headgear = self._piece('touch', WORN_KOOLICH_HEADGEAR)
        self.assertEqual({False}, {fits_the_class(headgear, char_class)
                                   for char_class in ('Iop', 'Enutrof', 'Cra')})


class AStoredBuildKeepsItsPiecesTests(_Build):

    def test_a_build_saved_with_the_jiva_necklace_still_shows_it(self):
        necklace = self._piece('dofus3', JIVA_NECKLACE)
        self.assertTrue(necklace.unusable)
        char = self._char('dofus3', level=60)
        minimal = pickle.loads(char.minimal_solution)
        minimal.item_per_slot['amulet'] = necklace.id
        char.minimal_solution = pickle.dumps(minimal)
        char.save()
        page = self.client.get('/solution/%d/' % char.id, follow=True)
        self.assertEqual(200, page.status_code)
        self.assertIn(necklace.name, html.unescape(page.content.decode('utf-8')))
        char.refresh_from_db()
        stored = read_char_blob(char.minimal_solution, None, 'minimal_solution', char)
        self.assertEqual(necklace.id, stored.item_per_slot['amulet'])


class TheItemSaysWhyInEveryLanguageTests(_Build):

    EXPECTED = {
        'en': ('Unequippable item', 'Be level 5 or lower',
               'Not have the "%s" item equipped'),
        'fr': ('Objet non équipable', 'Être niveau 5 ou moins',
               "Ne pas être équipé de l'objet '%s'"),
        'es': ('Objeto no equipable', 'Tener nivel 5 o menor',
               "No llevar equipado el objeto '%s'"),
        'pt': ('Item que não pode ser equipado', 'Estar no nível 5 ou abaixo',
               "Não ser equipado do item '%s'"),
        'de': ('Nicht ausrüstbarer Gegenstand', 'Maximal Stufe 5',
               'Nicht mit dem Objekt „%s“ ausgestattet.'),
    }

    def test_each_line_is_the_games_wording(self):
        staff = self._piece('dofus3', FIRST_BLOOD_STAFF)
        pilgrim = self._piece('dofus3', APPRENTICE_PILGRIM_STAFF)
        cruelty = self._piece('dofus2', BELLADONNAS_CRUELTY)
        dofus2 = get_structure('dofus2')
        for language, (unusable, highest, together) in self.EXPECTED.items():
            with self.subTest(language=language), translation.override(language):
                self.assertIn(unusable, condition_texts('dofus3', staff))
                self.assertIn(highest, condition_texts('dofus3', pilgrim))
                lines = condition_texts('dofus2', cruelty)
                for other_id in cruelty.not_worn_with:
                    name = dofus2.get_item_name_in_language(
                        dofus2.get_item_by_id(other_id), language)
                    self.assertIn(together % name, lines)
                self.assertEqual(2, len(cruelty.not_worn_with))

    def test_the_item_pages_print_the_lines(self):
        pages = (
            ('/encyclopedia/item/equipment/%d-x/' % FIRST_BLOOD_STAFF, 'Unequippable item'),
            ('/encyclopedia/item/equipment/%d-x/' % APPRENTICE_PILGRIM_STAFF,
             'Be level 5 or lower'),
            ('/dofus2/encyclopedia/item/equipment/%d-x/' % BELLADONNAS_CRUELTY,
             """Not have the "Belladonna's Bitterness" item equipped"""),
        )
        for url, line in pages:
            with self.subTest(url=url):
                page = self.client.get(url, follow=True)
                self.assertEqual(200, page.status_code)
                self.assertIn(line, html.unescape(page.content.decode('utf-8')))

    def test_the_encyclopedia_shows_an_exact_stat_as_one_line(self):
        from chardata.encyclopedia_view import _format_condition_groups
        structure = get_structure('dofus3')
        bonnet = structure.get_item_by_ankama_id(11603)
        groups = _format_condition_groups(structure, [bonnet], 'en')
        self.assertEqual([['Chance = 0']], groups)


class TheQuickStartLocksOnlyWhatTheBuildCanWearTests(_Build):

    def _quick_start(self, version, char_class, level, piece):
        prefix = '' if version == 'dofus3' else '/' + version
        answer = self.client.post('%s/quickstart/' % prefix, {
            'char_class': char_class, 'char_level': str(level),
            'play_style': 'solo_pvm', 'element': 'str', 'item': str(piece.id)})
        self.assertEqual(302, answer.status_code)
        char = Char.objects.order_by('-id').first()
        self.assertEqual((char_class, level, version),
                         (char.char_class, char.level, char.game_version))
        return get_inclusions_dict(char)

    def test_an_unusable_piece_is_not_locked(self):
        for version, ankama_id, level in (('touch', WORN_KOOLICH_HEADGEAR, 110),
                                          ('dofus3', FIRST_BLOOD_STAFF, 200)):
            with self.subTest(version=version):
                set_current_game_version(version)
                self.assertEqual({}, self._quick_start(
                    version, 'Iop', level, self._piece(version, ankama_id)))

    def test_the_repaired_headgear_is_locked(self):
        set_current_game_version('touch')
        repaired = self._piece('touch', KOOLICH_HEADGEAR)
        self.assertEqual({'hat': repaired.id},
                         self._quick_start('touch', 'Iop', 110, repaired))

    def test_the_pilgrim_staff_is_locked_up_to_level_five_only(self):
        staff = self._piece('dofus3', APPRENTICE_PILGRIM_STAFF)
        for level, expected in ((5, {'weapon': staff.id}), (6, {}), (200, {})):
            with self.subTest(level=level):
                self.assertEqual(expected, self._quick_start('dofus3', 'Iop', level, staff))


class TheLockRefusesWhatTheBuildCannotWearTests(_Build):

    def test_the_lock_button_refuses_the_pilgrim_staff_past_level_five(self):
        staff = self._piece('dofus3', APPRENTICE_PILGRIM_STAFF)
        char = self._char('dofus3', level=6)
        self.assertFalse(set_item_included(char, staff.id, 'weapon', True))
        self.assertEqual({}, get_inclusions_dict(char))
        char = self._char('dofus3', 'Cra', level=5)
        self.assertTrue(set_item_included(char, staff.id, 'weapon', True))
        self.assertEqual({'weapon': staff.id}, get_inclusions_dict(char))

    def test_the_second_belladonna_ring_is_not_locked_beside_the_first(self):
        cruelty = self._piece('dofus2', BELLADONNAS_CRUELTY)
        bitterness = self._piece('dofus2', BELLADONNAS_BITTERNESS)
        char = self._char('dofus2')
        self.assertTrue(set_item_included(char, cruelty.id, 'ring1', True))
        self.assertFalse(set_item_included(char, bitterness.id, 'ring2', True))
        self.assertEqual({'ring1': cruelty.id}, get_inclusions_dict(char))

    def test_the_lock_page_keeps_one_ring_of_the_pair(self):
        cruelty = self._piece('dofus2', BELLADONNAS_CRUELTY)
        bitterness = self._piece('dofus2', BELLADONNAS_BITTERNESS)
        char = self._char('dofus2')
        answer = self.client.post('/dofus2/inclusionspost/%d/' % char.id, {
            'ring1': str(cruelty.id), 'ring2': str(bitterness.id)})
        self.assertEqual(200, answer.status_code)
        char.refresh_from_db()
        self.assertEqual({'ring1': cruelty.id}, get_inclusions_dict(char))

    def test_a_lock_stored_before_the_rule_stays_when_another_is_saved(self):
        headgear = self._piece('touch', WORN_KOOLICH_HEADGEAR)
        ring = self._piece('touch', THE_ENUTROFION)
        char = self._char('touch', 'Enutrof', level=110)
        char.inclusions = pickle.dumps({'hat': headgear.id})
        char.save()
        set_inclusions_dict_and_check_exclusions(
            char, {'hat': headgear.id, 'ring1': ring.id})
        self.assertEqual({'hat': headgear.id, 'ring1': ring.id},
                         get_inclusions_dict(char))


class ThePickerAndTheSwitchKeepAPairApartTests(_Build):

    def _wearing_the_black_spotted_dofus(self):
        black_spotted = self._piece('dofus2', BLACK_SPOTTED_DOFUS)
        char = self._char('dofus2')
        minimal = pickle.loads(char.minimal_solution)
        others = {self._piece('dofus2', number).id for number in (DOMAKURO, DORIGAMI)}
        for slot, item_id in minimal.item_per_slot.items():
            if item_id in others:
                minimal.item_per_slot[slot] = None
        minimal.item_per_slot['dofus1'] = black_spotted.id
        char.minimal_solution = pickle.dumps(minimal)
        char.save()
        return char

    def test_the_picker_leaves_out_the_two_dofus_it_came_from(self):
        domakuro = self._piece('dofus2', DOMAKURO)
        char = self._wearing_the_black_spotted_dofus()
        self.assertNotIn(domakuro.id, self._offered(char, 'dofus2', 'Domakuro'))
        self.assertIn(domakuro.id, self._offered(self._char('dofus2', 'Cra'),
                                                 'dofus2', 'Domakuro'))

    def test_the_switch_refuses_domakuro_beside_it_and_takes_it_in_its_place(self):
        domakuro = self._piece('dofus2', DOMAKURO)
        char = self._wearing_the_black_spotted_dofus()
        beside = self.client.post('/dofus2/exchange/%d/' % char.id,
                                  {'itemName': str(domakuro.id), 'slot': 'dofus2'})
        self.assertEqual(400, beside.status_code)
        instead = self.client.post('/dofus2/exchange/%d/' % char.id,
                                   {'itemName': str(domakuro.id), 'slot': 'dofus1'})
        self.assertEqual(200, instead.status_code)


class TheItemPageShowsOnlyThePiecesOwnConditionTests(_Build):

    def test_the_black_spotted_dofus_names_the_two_and_they_name_nothing(self):
        dofus2 = get_structure('dofus2')
        black_spotted = self._piece('dofus2', BLACK_SPOTTED_DOFUS)
        domakuro = self._piece('dofus2', DOMAKURO)
        with translation.override('en'):
            self.assertEqual(2, len(condition_texts('dofus2', black_spotted)))
            self.assertEqual([], condition_texts('dofus2', domakuro))
        self.assertEqual((black_spotted.id,), domakuro.not_worn_with)
        self.assertEqual(sorted((domakuro.id, dofus2.get_item_by_ankama_id(DORIGAMI).id)),
                         sorted(black_spotted.own_not_worn_with))
