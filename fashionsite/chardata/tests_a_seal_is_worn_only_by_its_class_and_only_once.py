# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A seal is worn when locked, by its own class, once, and from the level its spell rank needs."""

import json
import pickle
import re

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase

from chardata.char_blobs import read_char_blob
from chardata.lock_forbid import get_inclusions_dict
from chardata.models import Char
from chardata.solution import get_solution
from chardata.tests_a_touch_build_saved_before_the_seals_still_loads import (
    _OPTIONS, sixteen_slot_minimal)
from fashionistapulp.dofus_constants import STATS_NAMES
from fashionistapulp.model import Model, ModelInput
from fashionistapulp.structure import get_structure, set_current_game_version


class _Touch(TestCase):

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.addCleanup(set_current_game_version, 'dofus3')
        set_current_game_version('touch')
        self.structure = get_structure('touch')
        self.power = self.structure.get_item_by_name('Iop Seal: Power')
        self.jump = self.structure.get_item_by_name('Iop Seal: Jump')
        self.heroism = self.structure.get_item_by_name('Feca Seal: Heroism')
        self.insignia = self.structure.get_item_by_ankama_id(23485)
        self.doom = self.structure.get_item_by_ankama_id(24057)

    def _char(self, char_class='Iop', level=200, version='touch'):
        owner = User.objects.create_user('seal-%s-%d-%s' % (char_class, level,
                                                            version),
                                         'seal@test.local', 'pw-42-solid')
        self.client.force_login(owner)
        set_current_game_version(version)
        minimal = sixteen_slot_minimal(get_structure(version), char_class, level)
        set_current_game_version('touch')
        return Char.objects.create(
            name='Seals', char_name='', char_class=char_class, char_build='',
            level=level, minimum_stats=b'', minimum_crits=b'',
            stats_weight=pickle.dumps({}), options=pickle.dumps(dict(_OPTIONS)),
            inclusions=b'', exclusions=b'', owner=owner, link_shared=False,
            game_version=version, minimal_solution=pickle.dumps(minimal))


class ALockedSealIsWornTests(_Touch):

    def _solve(self, locked, char_class='Iop'):
        base = {name: 0 for name, _key in STATS_NAMES}
        base.update({'AP': 7, 'MP': 3, 'Summon': 1, 'Prospecting': 100,
                     'Pods': 1000})
        model = Model()
        model.setup(ModelInput(200, base, {}, locked, [],
                               {'vit': 1, 'str': 3, 'ap': 400, 'mp': 300},
                               dict(_OPTIONS), char_class, 995))
        model.run()
        self.assertEqual('Optimal', model.get_solved_status())
        return model.get_result_minimal().item_per_slot

    def test_the_two_locked_seals_are_worn_in_their_slots(self):
        worn = self._solve({'emblem1': self.power.id, 'emblem2': self.jump.id})
        self.assertEqual(self.power.id, worn['emblem1'])
        self.assertEqual(self.jump.id, worn['emblem2'])

    def test_one_seal_locked_twice_is_worn_once(self):
        worn = self._solve({'emblem1': self.power.id, 'emblem2': self.power.id})
        self.assertEqual(1, list(worn.values()).count(self.power.id))

    def test_the_same_seal_in_both_slots_is_a_repeat_the_game_refuses(self):
        char = self._char()
        solution = get_solution(char)
        solution.switch_item(self.power, 'emblem1')
        solution.switch_item(self.power, 'emblem2')
        worn = next(item for item in solution.item_list if item.slot == 'emblem2')
        kinds = [violation.condition_type
                 for violation in solution.get_violations_on_item(worn)]
        self.assertIn('repeated', kinds)


class OnlyTheClassSealsAreOfferedTests(_Touch):

    def _offered(self, char, slot='emblem1', prefix='/touch'):
        answer = self.client.post('%s/itemexchange/%d/' % (prefix, char.id),
                                  {'slot': slot, 'page': '1'})
        if answer.status_code != 200:
            return answer.status_code
        return {int(number) for number in re.findall(
            r'"id"\s*:\s*(\d+)', answer.content.decode('utf-8'))}

    def test_an_iop_is_offered_its_two_seals_and_the_insignia(self):
        offered = self._offered(self._char())
        self.assertEqual({self.power.id, self.jump.id, self.insignia.id},
                         offered)

    def test_the_lock_page_lists_the_same_pieces(self):
        char = self._char()
        page = self.client.get('/touch/inclusions/%d/' % char.id)
        self.assertEqual(200, page.status_code)
        listed = {int(number) for number in
                  json.loads(page.context['types_json'])['Emblem']}
        self.assertLessEqual({self.power.id, self.jump.id, self.insignia.id},
                             listed)
        self.assertEqual({'Iop'}, {char_class for number in listed
                                   for char_class in getattr(
                                       self.structure.get_item_by_id(number),
                                       'classes', ())})
        html = page.content.decode('utf-8')
        self.assertIn('id="table-emblem1"', html)
        self.assertIn('id="table-emblem2"', html)

    def test_a_dofus3_build_has_no_seal_slot(self):
        self.assertEqual(400, self._offered(self._char(version='dofus3'),
                                            prefix=''))

    def test_a_retribution_seal_waits_for_level_200(self):
        retribution = self.structure.get_item_by_name('Sacrier Seal: Retribution')
        martyr = self.structure.get_item_by_name('Sacrier Seal: Martyr Punishment')
        at_195 = self._offered(self._char('Sacrier', 195))
        self.assertIn(martyr.id, at_195)
        self.assertNotIn(retribution.id, at_195)
        self.assertIn(retribution.id, self._offered(self._char('Sacrier', 200)))


class TheDoorsRefuseAnotherClassSealTests(_Touch):

    def test_the_switch_refuses_a_feca_seal_on_an_iop(self):
        char = self._char()
        refused = self.client.post('/touch/exchange/%d/' % char.id,
                                   {'itemName': str(self.heroism.id),
                                    'slot': 'emblem1'})
        self.assertEqual(400, refused.status_code)
        taken = self.client.post('/touch/exchange/%d/' % char.id,
                                 {'itemName': str(self.power.id),
                                  'slot': 'emblem1'})
        self.assertEqual(200, taken.status_code)
        char.refresh_from_db()
        stored = read_char_blob(char.minimal_solution, None,
                                'minimal_solution', char)
        self.assertEqual(self.power.id, stored.item_per_slot['emblem1'])
        self.assertIsNone(stored.item_per_slot['emblem2'])

    def test_the_lock_page_keeps_the_iop_seal_and_drops_the_feca_one(self):
        char = self._char()
        answer = self.client.post('/touch/inclusionspost/%d/' % char.id,
                                  {'emblem1': str(self.heroism.id),
                                   'emblem2': str(self.power.id)})
        self.assertEqual(200, answer.status_code)
        char.refresh_from_db()
        locked = get_inclusions_dict(char)
        self.assertNotIn('emblem1', locked)
        self.assertEqual(self.power.id, locked['emblem2'])

    def test_the_lock_button_refuses_a_feca_seal_on_an_iop(self):
        char = self._char()
        refused = self.client.post('/touch/setitemlocked/%d/' % char.id,
                                   {'slot': 'emblem1', 'locked': 'true',
                                    'equip': self.heroism.name})
        self.assertEqual(400, refused.status_code)
        taken = self.client.post('/touch/setitemlocked/%d/' % char.id,
                                 {'slot': 'emblem1', 'locked': 'true',
                                  'equip': self.power.name})
        self.assertEqual(200, taken.status_code)

    def test_a_classic_build_is_not_offered_the_doom_spell_book(self):
        char = self._char()
        answer = self.client.post('/touch/itemadd/%d/' % char.id,
                                  {'slot': 'emblem2', 'page': '1'})
        self.assertEqual(200, answer.status_code)
        offered = {int(number) for number in re.findall(
            r'"id"\s*:\s*(\d+)', answer.content.decode('utf-8'))}
        self.assertIn(self.insignia.id, offered)
        self.assertNotIn(self.doom.id, offered)
        self.assertNotIn(self.heroism.id, offered)
