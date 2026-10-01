# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A piece the game keeps for one sex (PS) or one character name (PN) is worn only by that character, at every door, and the build's pages say so."""

import html
import pickle
import re

from django.contrib.auth.models import User
from django.test import Client, RequestFactory, SimpleTestCase
from django.utils import translation

from chardata import fashion_action
from chardata.build_import import WRONG_NAME, WRONG_SEX, plan_ankama_ids
from chardata.char_blobs import read_char_blob
from chardata.coaching_view import create_build
from chardata.lock_forbid import (get_inclusions_dict,
                                   set_inclusions_dict_and_check_exclusions,
                                   set_item_included)
from chardata.models import Char
from chardata.tests_a_piece_its_build_cannot_wear_is_refused_at_every_door import _Build
from chardata.tests_every_equip_condition_the_data_carries_is_handled import (
    BASES, _connect, _criteria, _rows, _trees)
from chardata.util import shared_build_path
from chardata.wear_conditions import condition_texts
from fashionistapulp.dofus_constants import STATS_NAMES
from fashionistapulp.model import Model, ModelInput
from fashionistapulp.structure import (fits_the_wearer, get_structure,
                                       set_current_game_version)

GROOM_HAT = 6660
BRIDE_HAT = 6662
DE_SENDARS_RING = 2154
LORDSOTH_DAGGERS = 6713

OPTIONS = {'ap_exo': False, 'mp_exo': False, 'range_exo': False,
           'dofus': True, 'trophies': True, 'dragoturkey': True,
           'seemyool': True, 'rhineetle': True, 'prysmaradite': False,
           'shields': True}

_LINE = re.compile(r'<span class="(solution-inline-stat-line[^"]*)"[^>]*>\s*'
                   r'(?:<img[^>]*>\s*)?<span>(.*?)</span>', re.S)


def condition_lines(page):
    """(text, red) for each line of the solution page's piece cards."""
    return [(html.unescape(text).replace('\xa0', '').strip(),
             'solution-negative-stat-text' in classes)
            for classes, text in _LINE.findall(page.content.decode('utf-8'))]


class TheCriteriaReadTheSexAndTheNameTests(SimpleTestCase):

    def test_a_criteria_string_gives_the_sex_and_the_name_it_asks(self):
        criteria = _criteria()
        def describe(text):
            return criteria.describe(criteria.parse(text), {}, 'dofus2')
        self.assertEqual({'sexes': [0]}, describe('PS=0'))
        self.assertEqual({'sexes': [1]}, describe('PS=1'))
        self.assertEqual({'names': ['Lordsoth']}, describe('PN~Lordsoth'))
        self.assertNotIn('sexes', describe('PS=0|PS=1'))
        self.assertNotIn('names', describe('PN~Lordsoth|PS=0'))

    def test_a_name_matches_whatever_its_case(self):
        class Piece:
            sexes = ()
            names = ('Lordsoth',)
        self.assertTrue(fits_the_wearer(Piece, 0, 'lordsoth'))
        self.assertTrue(fits_the_wearer(Piece, 0, 'LORDSOTH'))
        self.assertFalse(fits_the_wearer(Piece, 0, 'Lordsot'))
        self.assertFalse(fits_the_wearer(Piece, 0, ''))
        self.assertTrue(fits_the_wearer(Piece, 0, None))


class TheDatabaseHoldsTheSexAndTheNameTests(SimpleTestCase):

    def test_each_version_stores_the_sexes_and_names_its_criteria_ask(self):
        criteria = _criteria()
        for version in BASES:
            with self.subTest(version=version):
                sexes, names = set(), set()
                for item, tree in _trees(version).items():
                    for sex in criteria.allowed_sexes(tree) or ():
                        sexes.add((item, sex))
                    for name in criteria.allowed_names(tree) or ():
                        names.add((item, name))
                connection = _connect(version)
                try:
                    self.assertEqual(sexes, set(_rows(
                        connection, 'SELECT item, sex FROM item_sex_conditions')))
                    self.assertEqual(names, set(_rows(
                        connection, 'SELECT item, name FROM item_name_conditions')))
                finally:
                    connection.close()
                self.assertTrue(sexes)
                self.assertTrue(names)

    def test_the_groom_hat_is_for_a_male_and_the_bride_hat_for_a_female(self):
        for version in ('dofus3', 'dofus2', 'retro'):
            with self.subTest(version=version):
                structure = get_structure(version)
                self.assertEqual((0,), structure.get_item_by_ankama_id(GROOM_HAT).sexes)
                self.assertEqual((1,), structure.get_item_by_ankama_id(BRIDE_HAT).sexes)
        self.assertEqual(('Lordsoth',),
                         get_structure('touch').get_item_by_ankama_id(LORDSOTH_DAGGERS).names)


class TheSolverReadsTheSexAndTheNameTests(SimpleTestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')
        set_current_game_version('dofus2')
        self.structure = get_structure('dofus2')
        self.model = None

    def model_input(self, gender, char_name, locked=None):
        base = {name: 0 for name, _key in STATS_NAMES}
        base.update({'AP': 7, 'MP': 3, 'Summon': 1, 'Prospecting': 100, 'Pods': 1000})
        return ModelInput(200, base, {}, dict(locked or {}), set(), {'vit': 1},
                          dict(OPTIONS), 'Iop', 995, gender=gender, char_name=char_name)

    def open_to(self, ankama_id, gender, char_name, locked=None):
        piece = self.structure.get_item_by_ankama_id(ankama_id)
        self.model = self.model or Model()
        self.model.setup(self.model_input(gender, char_name, locked))
        return -self.model.restrictions.forbidden_items_constraints[piece.id].constant

    def test_the_groom_hat_is_open_to_a_male_only(self):
        self.assertEqual(1, self.open_to(GROOM_HAT, 0, ''))
        self.assertEqual(0, self.open_to(GROOM_HAT, 1, ''))
        self.assertEqual(1, self.open_to(BRIDE_HAT, 1, ''))
        self.assertEqual(0, self.open_to(BRIDE_HAT, 0, ''))

    def test_de_sendars_ring_is_open_to_silaisie_only(self):
        self.assertEqual(1, self.open_to(DE_SENDARS_RING, 0, 'Silaisie'))
        self.assertEqual(1, self.open_to(DE_SENDARS_RING, 0, 'silaisie'))
        self.assertEqual(0, self.open_to(DE_SENDARS_RING, 0, ''))
        self.assertEqual(0, self.open_to(DE_SENDARS_RING, 0, 'Lordsoth'))

    def test_a_locked_bride_hat_stays_on_a_male(self):
        hat = self.structure.get_item_by_ankama_id(BRIDE_HAT)
        self.assertEqual(1, self.open_to(BRIDE_HAT, 0, '', locked={'hat': hat.id}))

    def test_without_a_sex_or_name_the_input_checks_neither(self):
        self.assertEqual(1, self.open_to(BRIDE_HAT, None, None))
        self.assertEqual(1, self.open_to(DE_SENDARS_RING, None, None))

    def test_the_cache_key_follows_the_pieces_ruled_out(self):
        male, female = self.model_input(0, ''), self.model_input(1, '')
        self.assertNotEqual(male.cache_key(), female.cache_key())
        self.assertNotEqual(hash(male), hash(female))
        self.assertEqual(self.model_input(0, 'Anyone').cache_key(),
                         self.model_input(0, 'Someone').cache_key())


class TheBuildPassesItsSexAndNameToTheSolverTests(_Build):

    def test_a_female_build_asks_the_solver_to_leave_the_groom_hat(self):
        set_current_game_version('dofus2')
        request = RequestFactory().get('/dofus2/')
        request.game_version = 'dofus2'
        request.user = User.objects.create_user('sexed', 'sexed@test.local', 'pw-42-solid')
        char = create_build(request, 'Iop', 200, {'str'}, 'dofus2', gender=1)
        model_input = fashion_action._model_input(request, char, {'vit': 1})
        self.assertEqual((1, ''), (model_input.gender, model_input.char_name))
        groom = get_structure('dofus2').get_item_by_ankama_id(GROOM_HAT)
        self.assertIn(groom.id, model_input._barred_to_the_wearer())

    def test_the_solver_input_keeps_the_name_only_as_a_piece_spells_it(self):
        set_current_game_version('dofus2')
        request = RequestFactory().get('/dofus2/')
        request.game_version = 'dofus2'
        request.user = User.objects.create_user('named', 'named@test.local', 'pw-42-solid')
        char = create_build(request, 'Iop', 200, {'str'}, 'dofus2')
        char.char_name = 'Kevin'
        unnamed = fashion_action._model_input(request, char, {'vit': 1})
        self.assertEqual('', unnamed.char_name)
        self.assertNotIn(b'Kevin', pickle.dumps(unnamed))
        char.char_name = ' SILAISIE'
        named = fashion_action._model_input(request, char, {'vit': 1})
        self.assertEqual('Silaisie', named.char_name)
        ring = get_structure('dofus2').get_item_by_ankama_id(DE_SENDARS_RING)
        self.assertIn(ring.id, unnamed._barred_to_the_wearer())
        self.assertNotIn(ring.id, named._barred_to_the_wearer())


class TheBuildAroundDoorChecksTheSexAndTheNameTests(_Build):

    def _rejected(self, ankama_id, gender, char_name):
        _placed, rejected = plan_ankama_ids(get_structure('dofus2'), [ankama_id], 'dofus2',
                                            200, 'Iop', gender, char_name)
        return dict(rejected)

    def test_the_bride_hat_is_placed_on_a_female_only(self):
        self.assertEqual({BRIDE_HAT: WRONG_SEX}, self._rejected(BRIDE_HAT, 0, ''))
        self.assertEqual({}, self._rejected(BRIDE_HAT, 1, ''))

    def test_the_lordsoth_daggers_are_placed_on_lordsoth_only(self):
        self.assertEqual({LORDSOTH_DAGGERS: WRONG_NAME},
                         self._rejected(LORDSOTH_DAGGERS, 0, 'Kevin'))
        self.assertEqual({}, self._rejected(LORDSOTH_DAGGERS, 0, 'lordsoth'))

    def test_building_around_the_bride_hat_makes_a_female_build_wearing_it(self):
        set_current_game_version('dofus2')
        answer = self.client.post('/dofus2/createproject/', {
            'project': 'Bride', 'charname': 'star', 'level': '200',
            'class': 'Iop', 'byhand': '1', 'lock_item': str(BRIDE_HAT)})
        self.assertIn(answer.status_code, (301, 302))
        char = Char.objects.order_by('-id').first()
        self.assertEqual(1, char.gender)
        self.assertEqual(self._piece('dofus2', BRIDE_HAT).id,
                         get_inclusions_dict(char).get('hat'))


class EveryDoorChecksTheSexAndTheNameTests(_Build):

    def _wear(self, char, slot, item_id):
        minimal = read_char_blob(char.minimal_solution, None, 'minimal_solution', char)
        minimal.item_per_slot[slot] = item_id
        char.minimal_solution = pickle.dumps(minimal)
        char.save()

    def test_the_picker_offers_the_hat_of_the_builds_sex_only(self):
        groom = self._piece('dofus2', GROOM_HAT)
        bride = self._piece('dofus2', BRIDE_HAT)
        char = self._char('dofus2')
        self.assertIn(groom.id, self._offered(char, 'hat', 'Groom'))
        self.assertNotIn(bride.id, self._offered(char, 'hat', 'Bride'))
        char.gender = 1
        char.save()
        self.assertIn(bride.id, self._offered(char, 'hat', 'Bride'))
        self.assertNotIn(groom.id, self._offered(char, 'hat', 'Groom'))

    def test_the_picker_offers_a_named_ring_to_that_name_only(self):
        ring = self._piece('dofus2', DE_SENDARS_RING)
        char = self._char('dofus2')
        self.assertNotIn(ring.id, self._offered(char, 'ring1', 'Sendar'))
        char.char_name = 'Silaisie'
        char.save()
        self.assertIn(ring.id, self._offered(char, 'ring1', 'Sendar'))

    def test_the_lock_refuses_the_hat_of_the_other_sex_and_keeps_a_stored_one(self):
        bride = self._piece('dofus2', BRIDE_HAT)
        char = self._char('dofus2')
        self.assertFalse(set_item_included(char, bride.id, 'hat', True))
        refused = self.client.post('/dofus2/setitemlocked/%d/' % char.id, {
            'slot': 'hat', 'locked': 'true', 'equip': bride.name})
        self.assertEqual(400, refused.status_code)
        self.assertIn('Female only', refused.content.decode('utf-8'))
        char.inclusions = pickle.dumps({'hat': bride.id})
        char.save()
        ring = self._piece('dofus2', 1499)
        set_inclusions_dict_and_check_exclusions(char, {'hat': bride.id, 'ring1': ring.id})
        self.assertEqual(bride.id, get_inclusions_dict(char)['hat'])

    def test_switching_the_sex_shows_the_hat_in_red_and_keeps_the_stored_build(self):
        groom = self._piece('dofus2', GROOM_HAT)
        char = self._char('dofus2', level=60)
        minimal = read_char_blob(char.minimal_solution, None, 'minimal_solution', char)
        minimal.item_per_slot['hat'] = groom.id
        char.minimal_solution = pickle.dumps(minimal)
        char.save()
        page = self.client.get('/dofus2/solution/%d/' % char.id, follow=True)
        self.assertIn(('Male only', False), condition_lines(page))
        switched = self.client.post('/dofus2/setchargender/%d/' % char.id, {'gender': '1'})
        self.assertEqual(200, switched.status_code)
        page = self.client.get('/dofus2/solution/%d/' % char.id, follow=True)
        self.assertIn(('Male only', True), condition_lines(page))
        char.refresh_from_db()
        stored = read_char_blob(char.minimal_solution, None, 'minimal_solution', char)
        self.assertEqual(groom.id, stored.item_per_slot['hat'])

    def test_the_switch_asks_for_a_reload_only_when_a_one_sex_piece_is_worn(self):
        char = self._char('dofus2', level=60)
        self._wear(char, 'amulet', None)
        plain = self.client.post('/dofus2/setchargender/%d/' % char.id, {'gender': '1'})
        self.assertFalse(plain.json()['wears_a_one_sex_piece'])
        self._wear(char, 'hat', self._piece('dofus2', GROOM_HAT).id)
        worn = self.client.post('/dofus2/setchargender/%d/' % char.id, {'gender': '0'})
        self.assertTrue(worn.json()['wears_a_one_sex_piece'])

    def test_the_switch_keeps_the_build_date_and_reaches_a_visitor(self):
        char = self._char('dofus2', level=60)
        self._wear(char, 'hat', self._piece('dofus2', GROOM_HAT).id)
        char.link_shared = True
        char.save()
        visitor = Client()
        path = shared_build_path(char)
        self.assertIn(('Male only', False), condition_lines(visitor.get(path, follow=True)))
        char.refresh_from_db()
        saved_at = char.modified_time
        self.client.post('/dofus2/setchargender/%d/' % char.id, {'gender': '1'})
        char.refresh_from_db()
        self.assertEqual((1, saved_at), (char.gender, char.modified_time))
        self.assertIn(('Male only', True), condition_lines(visitor.get(path, follow=True)))

    def test_the_text_import_takes_the_sex_of_its_hat(self):
        set_current_game_version('dofus2')
        answer = self.client.post('/dofus2/import/text/', {
            'text': 'Bride Hat', 'char_class': 'Iop', 'level': '60',
            'confirm': '1'})
        self.assertEqual(302, answer.status_code)
        char = Char.objects.order_by('-id').first()
        self.assertEqual(1, char.gender)
        bride = self._piece('dofus2', BRIDE_HAT)
        stored = read_char_blob(char.minimal_solution, None, 'minimal_solution', char)
        self.assertEqual(bride.id, stored.item_per_slot['hat'])

    def test_the_text_import_leaves_out_a_named_piece_and_says_why(self):
        set_current_game_version('dofus2')
        preview = self.client.post('/dofus2/import/text/', {'text': "De Sendar's Ring"})
        self.assertEqual(200, preview.status_code)
        self.assertIn('Left out, this build cannot wear it: Name = Silaisie',
                      html.unescape(preview.content.decode('utf-8')))

    def test_the_quick_start_takes_the_sex_of_its_item(self):
        bride = self._piece('dofus2', BRIDE_HAT)
        answer = self.client.post('/dofus2/quickstart/', {
            'char_class': 'Iop', 'char_level': '60', 'play_style': 'solo_pvm',
            'element': 'str', 'item': str(bride.id)})
        self.assertEqual(302, answer.status_code)
        char = Char.objects.order_by('-id').first()
        self.assertEqual(1, char.gender)
        self.assertEqual({'hat': bride.id}, get_inclusions_dict(char))


class TheItemPageSaysItInEveryLanguageTests(_Build):

    EXPECTED = {
        'en': ('Male only', 'Female only', 'Name = Lordsoth'),
        'fr': ('Être de sexe masculin', 'Être de sexe féminin', 'Nom = Lordsoth'),
        'es': ('Ser de sexo masculino', 'Ser de sexo femenino', 'Nombre = Lordsoth'),
        'pt': ('Ser do sexo masculino', 'Ser do sexo feminino', 'Nome = Lordsoth'),
        'de': ('Männlich sein', 'Weiblich sein', 'Name = Lordsoth'),
    }

    def test_each_line_is_the_games_wording(self):
        groom = self._piece('dofus2', GROOM_HAT)
        bride = self._piece('dofus2', BRIDE_HAT)
        daggers = self._piece('touch', LORDSOTH_DAGGERS)
        for language, (male, female, name) in self.EXPECTED.items():
            with self.subTest(language=language), translation.override(language):
                self.assertIn(male, condition_texts('dofus2', groom))
                self.assertIn(female, condition_texts('dofus2', bride))
                self.assertIn(name, condition_texts('touch', daggers))

    def test_the_item_page_prints_the_line_and_hides_the_build_around_button(self):
        page = self.client.get('/dofus2/encyclopedia/item/equipment/%d-x/' % GROOM_HAT,
                               follow=True)
        content = html.unescape(page.content.decode('utf-8'))
        self.assertIn('Male only', content)
        self.assertIn('encyclopedia-build-around', content)
        page = self.client.get('/touch/encyclopedia/item/equipment/%d-x/' % LORDSOTH_DAGGERS,
                               follow=True)
        content = html.unescape(page.content.decode('utf-8'))
        self.assertIn('Name = Lordsoth', content)
        self.assertNotIn('encyclopedia-build-around', content)
