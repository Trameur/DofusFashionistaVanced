# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The quick start and the class change keep a locked seal to its own class and to the level its spell rank needs."""

import pickle
import re

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase

from chardata.coaching_view import included_item_for
from chardata.lock_forbid import get_inclusions_dict, set_inclusions_dict_and_check_exclusions
from chardata.models import Char
from chardata.solution import get_solution
from chardata.solution_result import evolve_result_item
from chardata.tests_a_touch_build_saved_before_the_seals_still_loads import (
    _OPTIONS, sixteen_slot_minimal)
from chardata.wear_conditions import class_condition_text
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
        self.retribution = self.structure.get_item_by_name('Sacrier Seal: Retribution')
        self.power = self.structure.get_item_by_name('Iop Seal: Power')
        self.insignia = self.structure.get_item_by_ankama_id(23485)

    def _quick_start(self, char_class, level, item):
        answer = self.client.post('/touch/quickstart/', {
            'char_class': char_class, 'char_level': str(level),
            'play_style': 'solo_pvm', 'element': 'str', 'item': str(item.id)})
        self.assertEqual(302, answer.status_code)
        char = Char.objects.order_by('-id').first()
        self.assertEqual((char_class, level, 'touch'),
                         (char.char_class, char.level, char.game_version))
        return get_inclusions_dict(char)


class TheQuickStartLocksASealOnlyForItsClassAndLevelTests(_Touch):

    def test_the_helper_gives_the_seal_its_class_and_its_rank_level(self):
        found = included_item_for('touch', self.retribution.id, language='en')
        self.assertEqual(('Sacrier',), found['classes'])
        self.assertEqual(200, found['level'])
        self.assertLess(self.retribution.level, found['level'])
        self.assertEqual('emblem1', found['slot'])

    def test_the_form_offers_only_the_seal_class_and_no_level_below_200(self):
        page = self.client.get('/touch/quickstart/', {'item': self.retribution.id},
                               HTTP_ACCEPT_LANGUAGE='en').content.decode('utf-8')
        select = re.search(r'<select name="char_class".*?</select>', page, re.S)
        self.assertIsNotNone(select)
        self.assertEqual(['Sacrier'], re.findall(r'value="([^"]+)"', select.group(0)))
        levels = re.search(r'<select name="char_level".*?</select>', page, re.S)
        self.assertEqual(['200'], re.findall(r'value="(\d+)"', levels.group(0)))

    def test_a_piece_for_every_class_keeps_every_class_offered(self):
        page = self.client.get('/touch/quickstart/', {'item': self.insignia.id},
                               HTTP_ACCEPT_LANGUAGE='en').content.decode('utf-8')
        select = re.search(r'<select name="char_class".*?</select>', page, re.S)
        self.assertGreater(len(re.findall(r'<option', select.group(0))), 10)

    def test_an_iop_asking_for_a_sacrier_seal_gets_no_lock(self):
        self.assertEqual({}, self._quick_start('Iop', 200, self.retribution))

    def test_a_sacrier_below_the_rank_level_gets_no_lock(self):
        self.assertEqual({}, self._quick_start('Sacrier', 190, self.retribution))
        self.assertEqual({}, self._quick_start('Sacrier', 199, self.retribution))

    def test_a_sacrier_at_200_wears_the_seal_locked_in_its_slot(self):
        self.assertEqual({'emblem1': self.retribution.id},
                         self._quick_start('Sacrier', 200, self.retribution))


class ChangingTheClassUnlocksTheOtherClassSealTests(_Touch):

    def _char(self):
        owner = User.objects.create_user('class-change', 'cc@test.local',
                                         'pw-42-solid')
        self.client.force_login(owner)
        minimal = sixteen_slot_minimal(self.structure)
        minimal.item_per_slot['emblem1'] = self.power.id
        char = Char.objects.create(
            name='Class change', char_name='', char_class='Iop', char_build='',
            level=200, minimum_stats=b'', minimum_crits=b'',
            stats_weight=pickle.dumps({}), options=pickle.dumps(dict(_OPTIONS)),
            inclusions=b'', exclusions=b'', owner=owner, link_shared=False,
            game_version='touch', minimal_solution=pickle.dumps(minimal))
        set_inclusions_dict_and_check_exclusions(
            char, {'emblem1': self.power.id, 'emblem2': self.insignia.id})
        return char

    def _save_details(self, char, char_class):
        answer = self.client.post('/touch/saveproject/%d/' % char.id, {
            'project': char.name, 'charname': '', 'class': char_class,
            'level': str(char.level), 'byhand': '1'})
        self.assertEqual(200, answer.status_code)
        char.refresh_from_db()
        self.assertEqual(char_class, char.char_class)
        return get_inclusions_dict(char)

    def test_a_feca_keeps_the_insignia_lock_and_loses_the_iop_seal_lock(self):
        char = self._char()
        self.assertEqual({'emblem2': self.insignia.id},
                         self._save_details(char, 'Feca'))

    def test_keeping_the_class_keeps_both_locks(self):
        char = self._char()
        self.assertEqual({'emblem1': self.power.id, 'emblem2': self.insignia.id},
                         self._save_details(char, 'Iop'))

    def test_the_next_feca_solve_wears_no_iop_seal(self):
        char = self._char()
        locked = self._save_details(char, 'Feca')
        base = {name: 0 for name, _key in STATS_NAMES}
        base.update({'AP': 7, 'MP': 3, 'Summon': 1, 'Prospecting': 100,
                     'Pods': 1000})
        model = Model()
        model.setup(ModelInput(200, base, {}, locked, [],
                               {'vit': 1, 'str': 3, 'ap': 400, 'mp': 300},
                               dict(_OPTIONS), 'Feca', 995))
        model.run()
        self.assertEqual('Optimal', model.get_solved_status())
        worn = model.get_result_minimal().item_per_slot
        self.assertNotIn(self.power.id, worn.values())
        self.assertEqual(self.insignia.id, worn['emblem2'])

    def test_the_stored_iop_seal_shows_its_class_line_in_red_on_a_feca(self):
        char = self._char()
        self._save_details(char, 'Feca')
        solution = get_solution(char)
        seal = next(item for item in solution.item_list if item.slot == 'emblem1')
        self.assertEqual(self.power.id, seal.id)
        wanted = class_condition_text(('Iop',))
        for char_class, formatting in (('Feca', '#r'), ('Iop', ''), (None, '')):
            with self.subTest(char_class=char_class):
                evolve_result_item(seal, solution, char_class)
                line = next(line for line in seal.condition_lines
                            if line.text == wanted)
                self.assertEqual(formatting, line.formatting)
