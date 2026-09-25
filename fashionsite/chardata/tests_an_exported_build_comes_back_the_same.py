# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A build exported as fashionista-build and sent back shows and creates the same items, characteristics, scrolls, rolls and exos."""

import html
import html.parser
import json
import pickle
import unittest

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase

from chardata import fashionista_build
from chardata.char_blobs import read_char_blob
from chardata.encoded_char_id import encode_char_id
from chardata.lock_forbid import get_stat_overrides, set_stat_overrides
from chardata.models import Char, CharBaseStats
from chardata.options import get_options
from fashionistapulp.dofus_constants import STATS_NAMES, TYPE_NAME_TO_SLOT
from fashionistapulp.game_versions import version_keys
from fashionistapulp.modelresult import ModelResultMinimal
from fashionistapulp.structure import get_structure, set_current_game_version

BROWSER = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
           '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36')

POINTS = {'Vitality': 120, 'Wisdom': 0, 'Strength': 301, 'Intelligence': 0,
          'Chance': 15, 'Agility': 0}


def _prefix(game):
    return '' if game == 'dofus3' else '/' + game


def _example_items(game):
    structure = get_structure(game)
    return [structure.get_item_by_ankama_id(entry['id'] if isinstance(entry, dict) else entry)
            for entry in fashionista_build.example_payload(game)['items']]


def _per_slot(structure, items):
    slots = {}
    for item in items:
        slot = TYPE_NAME_TO_SLOT[structure.get_type_name_by_id(item.type)]
        if slot in ('ring', 'dofus'):
            slot = next('%s%d' % (slot, n) for n in range(1, 7)
                        if '%s%d' % (slot, n) not in slots)
        slots[slot] = item.id
    return slots


def _worn(char):
    solution = read_char_blob(char.minimal_solution, None, 'minimal_solution', char)
    return sorted(i for i in solution.item_per_slot.values() if i)


def _base_stats(char):
    return {row.stat: (row.total_value, row.scrolled_value)
            for row in CharBaseStats.objects.filter(char=char)}


class _HiddenAndLinks(html.parser.HTMLParser):

    def __init__(self):
        super().__init__()
        self.hidden = {}
        self.forms = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'input' and attrs.get('type') == 'hidden':
            self.hidden.setdefault(attrs.get('name'), []).append(attrs.get('value'))
        if tag == 'form':
            self.forms.append(attrs)


def _parsed(page):
    parser = _HiddenAndLinks()
    parser.feed(page.content.decode('utf-8'))
    return parser


class _RoundTrip(TestCase):

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.addCleanup(set_current_game_version, 'dofus3')
        self.owner = User.objects.create_user('round-trip', 'rt@test.local', 'pw-42-solid')
        self.client.force_login(self.owner)

    def _build(self, game, items, char_class, level, scrolls, overrides, options,
               shared=True):
        set_current_game_version(game)
        structure = get_structure(game)
        model_input = {'char_class': char_class, 'char_level': level, 'origin': 'generated',
                       'options': options,
                       'base_stats_by_attr': {name: 0 for name, _key in STATS_NAMES},
                       'locked_equips': {}}
        char = Char.objects.create(
            name='Round trip', char_name='', char_class=char_class, char_build='',
            level=level, minimum_stats=b'', minimum_crits=b'',
            stats_weight=pickle.dumps({}), options=pickle.dumps(options),
            inclusions=b'', exclusions=b'', owner=self.owner, link_shared=shared,
            game_version=game,
            minimal_solution=pickle.dumps(ModelResultMinimal(
                _per_slot(structure, items), model_input, {})))
        for name, _key in STATS_NAMES:
            CharBaseStats.objects.create(char=char, stat=name,
                                         total_value=POINTS[name] + scrolls[name],
                                         scrolled_value=scrolls[name])
        if overrides:
            set_stat_overrides(char, overrides)
        set_current_game_version('dofus3')
        return char

    def _export(self, char):
        answer = self.client.get('%s/export/fashionista/%d/' % (_prefix(char.game_version),
                                                                char.id))
        self.assertEqual(200, answer.status_code)
        return answer.json()

    def _send_back_and_confirm(self, payload, char_class):
        preview = self.client.get('%s/import/build/' % _prefix(payload['game']),
                                  {'data': fashionista_build.encode_link_data(payload)},
                                  HTTP_ACCEPT_LANGUAGE='en', HTTP_USER_AGENT=BROWSER)
        self.assertEqual(200, preview.status_code)
        parsed = _parsed(preview)
        action = next(form['action'] for form in parsed.forms
                      if form.get('action', '').endswith('/import/text/'))
        done = self.client.post(action, {
            'text': parsed.hidden['text'][-1], 'confirm': '1',
            'char_class': char_class, 'level': str(payload['level']),
            'count_token': (parsed.hidden.get('count_token') or [''])[0]},
            HTTP_USER_AGENT=BROWSER)
        self.assertEqual(302, done.status_code)
        return preview, Char.objects.order_by('-id').first()

    def _assert_same(self, original, copy):
        self.assertNotEqual(original.id, copy.id)
        self.assertEqual((original.game_version, original.char_class, original.level),
                         (copy.game_version, copy.char_class, copy.level))
        self.assertEqual(_worn(original), _worn(copy))
        self.assertEqual(_base_stats(original), _base_stats(copy))
        self.assertEqual(get_stat_overrides(original), get_stat_overrides(copy))


class ADofus3BuildComesBackTheSameTests(_RoundTrip):

    def _original(self):
        structure = get_structure('dofus3')
        items = _example_items('dofus3')
        mount = next(item for item in structure.get_items_list()
                     if item.ankama_type == 'mounts' and not item.removed)
        items.append(mount)
        hat, cloak = items[0], items[1]
        stat_id, value = next((s, v) for s, v in hat.stats if v > 1)
        mp = structure.get_stat_by_key('mp').id
        self.assertNotIn(mp, dict(cloak.stats))
        scrolls = dict.fromkeys(POINTS, 100)
        scrolls['Wisdom'] = 37
        return self._build('dofus3', items, 'Sacrier', 200, scrolls,
                           {hat.id: {stat_id: value - 1}, cloak.id: {mp: 1}},
                           {'ap_exo': True, 'mp_exo': False, 'range_exo': True})

    def test_the_export_is_a_valid_build_the_schema_accepts(self):
        payload = self._export(self._original())
        answer = fashionista_build.report(payload)
        self.assertTrue(answer['valid'], answer['errors'])
        self.assertEqual([], answer['warnings'])
        self.assertEqual('mount', payload['items'][-1]['type'])
        try:
            import jsonschema
        except ImportError:
            raise unittest.SkipTest('jsonschema not installed')
        jsonschema.validate(payload, fashionista_build.json_schema(),
                            cls=jsonschema.Draft202012Validator)

    def test_the_preview_shows_the_same_items_characteristics_and_scrolls(self):
        original = self._original()
        payload = self._export(original)
        preview = self.client.get('/import/build/',
                                  {'data': fashionista_build.encode_link_data(payload)},
                                  HTTP_ACCEPT_LANGUAGE='en')
        body = preview.content.decode('utf-8')
        structure = get_structure('dofus3')
        for item_id in _worn(original):
            name = structure.get_item_name_in_language(structure.get_item_by_id(item_id), 'en')
            self.assertTrue(name in body or html.escape(name) in body, name)
        for line in ('Vitality: 120 + 100 scrolled', 'Wisdom: 0 + 37 scrolled',
                     'Strength: 301 + 100 scrolled', 'Chance: 15 + 100 scrolled',
                     'Agility: 0 + 100 scrolled'):
            self.assertIn(line, body)
        self.assertIn('Imported from dofusfashionista.gg', body)

    def test_the_confirmed_copy_holds_the_same_build(self):
        original = self._original()
        payload = self._export(original)
        _preview, copy = self._send_back_and_confirm(payload, 'Sacrier')
        self._assert_same(original, copy)
        options = get_options(copy)
        self.assertEqual((True, False, True),
                         (options['ap_exo'], options['mp_exo'], options['range_exo']))
        self.assertEqual(2, Char.objects.count())


class TheGelanoWithItsMpComesBackTheSameTests(_RoundTrip):

    def test_a_build_wearing_the_gelano_with_its_mp_comes_back_the_same(self):
        structure = get_structure('dofus3')
        with_mp = structure.get_item_by_name('Gelano (#1)')
        plain = structure.get_item_by_name('Gelano (#2)')
        items = _example_items('dofus3')
        first_ring = next(index for index, item in enumerate(items)
                          if structure.get_type_name_by_id(item.type) == 'Ring')
        items[first_ring] = with_mp
        original = self._build('dofus3', items, 'Iop', 200, dict.fromkeys(POINTS, 100), {},
                               {'ap_exo': True, 'mp_exo': 'gelano', 'range_exo': False})
        payload = self._export(original)
        self.assertEqual(len(items), len(payload['items']))
        sent = next(entry for entry in payload['items']
                    if isinstance(entry, dict) and entry['id'] == plain.ankama_id)
        self.assertEqual([('ap', 1), ('mp', 1)],
                         sorted((line['key'], line['value']) for line in sent['stats']))
        self.assertEqual({'ap': True, 'mp': False, 'range': False}, payload['exos'])
        answer = fashionista_build.report(payload)
        self.assertEqual(([], True), (answer['warnings'], answer['valid']))
        _preview, copy = self._send_back_and_confirm(payload, 'Iop')
        self.assertIn(with_mp.id, _worn(copy))
        self._assert_same(original, copy)
        options = get_options(copy)
        self.assertEqual((True, 'gelano', False),
                         (options['ap_exo'], options['mp_exo'], options['range_exo']))


class EveryWornPieceCanBeWrittenTests(TestCase):

    def test_in_every_game_the_only_piece_without_an_ankama_id_is_the_gelano_with_its_mp(self):
        for game in version_keys():
            structure = get_structure(game)
            with self.subTest(game=game):
                self.assertEqual(['Gelano (#1)'], sorted(
                    item.name for item in structure.get_items_list() if item.ankama_id is None))


class APetVariantAndACollidingMountComeBackTheSameTests(_RoundTrip):

    def test_a_retro_pet_variant_comes_back_as_that_variant(self):
        structure = get_structure('retro')
        items = _example_items('retro')
        variant = next(item for item in structure.get_items_list()
                       if item.id >= 10_000_000 and item.stats
                       and structure.get_type_name_by_id(item.type) == 'Pet')
        items.append(variant)
        original = self._build('retro', items, 'Cra', 100, dict.fromkeys(POINTS, 101),
                               {}, {})
        payload = self._export(original)
        self.assertNotIn('exos', payload)
        pet = payload['items'][-1]
        self.assertEqual(variant.ankama_id, pet['id'])
        self.assertTrue(pet['stats'])
        _preview, copy = self._send_back_and_confirm(payload, 'Cra')
        self.assertIn(variant.id, _worn(copy))
        self._assert_same(original, copy)

    def test_a_touch_mount_whose_id_an_item_also_uses_comes_back_as_the_mount(self):
        structure = get_structure('touch')
        mount = next(item for item in structure.get_items_list()
                     if item.ankama_type == 'mounts'
                     and structure.get_item_by_ankama_id(item.ankama_id) is not item)
        items = [item for item in _example_items('touch')
                 if structure.get_type_name_by_id(item.type) != 'Pet'] + [mount]
        original = self._build('touch', items, 'Iop', 200, dict.fromkeys(POINTS, 100),
                               {}, {'ap_exo': False, 'mp_exo': False, 'range_exo': False})
        payload = self._export(original)
        self.assertIn({'id': mount.ankama_id, 'type': 'mount'}, payload['items'])
        _preview, copy = self._send_back_and_confirm(payload, 'Iop')
        self.assertIn(mount.id, _worn(copy))
        self._assert_same(original, copy)


class TheExportIsOfferedToTheRightPeopleTests(TestCase):

    def setUp(self):
        cache.clear()
        self.owner = User.objects.create_user('exporter', 'ex@test.local', 'pw-42-solid')

    def _char(self, shared):
        structure = get_structure('dofus3')
        items = _example_items('dofus3')
        return Char.objects.create(
            name='Exported', char_name='', char_class='Iop', char_build='', level=200,
            minimum_stats=b'', minimum_crits=b'', stats_weight=pickle.dumps({}),
            options=b'', inclusions=b'', exclusions=b'', owner=self.owner,
            link_shared=shared, game_version='dofus3',
            minimal_solution=pickle.dumps(ModelResultMinimal(
                _per_slot(structure, items),
                {'options': {'ap_exo': False, 'mp_exo': False}, 'origin': 'generated',
                 'char_level': 200, 'locked_equips': {},
                 'base_stats_by_attr': {name: 0 for name, _key in STATS_NAMES}}, {})))

    def test_only_the_owner_gets_the_json(self):
        char = self._char(shared=False)
        self.assertIn(self.client.get('/export/fashionista/%d/' % char.id).status_code,
                      (403, 404))
        stranger = User.objects.create_user('stranger', 's@test.local', 'pw-42-solid')
        self.client.force_login(stranger)
        self.assertIn(self.client.get('/export/fashionista/%d/' % char.id).status_code,
                      (403, 404))
        self.client.force_login(self.owner)
        answer = self.client.get('/export/fashionista/%d/' % char.id)
        self.assertEqual('fashionista-build', answer.json()['format'])
        self.assertNotIn('back_url', answer.json())

    def test_a_shared_build_is_served_to_other_sites_and_a_private_one_is_not(self):
        shared, private = self._char(shared=True), self._char(shared=False)
        answer = self.client.get('/api/v1/shared-builds/%s/fashionista-build/'
                                 % encode_char_id(shared.id))
        self.assertEqual(200, answer.status_code)
        self.assertEqual('*', answer['Access-Control-Allow-Origin'])
        payload = answer.json()
        self.assertTrue(payload['back_url'].startswith('https://dofusfashionista.gg/s/'))
        self.assertTrue(fashionista_build.report(payload)['valid'])
        self.assertEqual(404, self.client.get('/api/v1/shared-builds/%s/fashionista-build/'
                                              % encode_char_id(private.id)).status_code)

    def test_the_build_page_offers_the_button_to_its_owner_only(self):
        char = self._char(shared=True)
        self.client.force_login(self.owner)
        mine = self.client.get('/solution/%d/' % char.id, HTTP_ACCEPT_LANGUAGE='en')
        self.assertContains(mine, 'id="fashionista_export_btn"')
        self.assertContains(mine, 'Export as JSON')
        self.assertContains(mine, 'href="/export/fashionista/%d/"' % char.id)
        self.client.logout()
        stranger = User.objects.create_user('visitor', 'v@test.local', 'pw-42-solid')
        self.client.force_login(stranger)
        theirs = self.client.get('/s/Exported/%s/' % encode_char_id(char.id),
                                 HTTP_ACCEPT_LANGUAGE='en')
        self.assertEqual(200, theirs.status_code)
        self.assertNotContains(theirs, 'fashionista_export_btn')

    def test_a_generation_snapshot_offers_no_export_of_the_current_build(self):
        from chardata.solution_history import record_solution_generation
        structure = get_structure('dofus3')
        hat = next(i for i in structure.types[200]['Hat'] if not i.removed)
        self.client.post('/import/text/', {
            'text': structure.get_item_name_in_language(hat, 'en'),
            'confirm': '1', 'char_class': 'Iop', 'level': '200'})
        char = Char.objects.order_by('-id').first()
        generation = record_solution_generation(
            char, read_char_blob(char.minimal_solution, None, 'minimal_solution', char))
        current = self.client.get('/solution/%d/' % char.id)
        self.assertTrue(current.context['fashionista_export'])
        self.assertContains(current, '/export/fashionista/%d/' % char.id)
        snapshot = self.client.get('/solutiongeneration/%d/%d/' % (char.id, generation.id))
        self.assertEqual(200, snapshot.status_code)
        self.assertTrue(snapshot.context['is_generation_snapshot'])
        self.assertFalse(snapshot.context['fashionista_export'])
        self.assertNotContains(snapshot, '/export/fashionista/%d/' % char.id)
