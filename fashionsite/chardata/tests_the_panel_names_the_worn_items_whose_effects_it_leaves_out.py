# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The best-turn panel names the worn items whose special effects its total leaves out."""

import html
import json
import re
from types import SimpleNamespace

from django.test import SimpleTestCase, TestCase
from django.utils.translation import gettext, override

LANGUAGES = ('en', 'fr', 'es', 'pt', 'de')
VERSION = 'dofus3'

NOTE = re.compile(r'<span[^>]*best-combo-item-effects-note[^>]*>(.*?)</span>', re.S)
BUILD_ROW = re.compile(r'<tr[^>]*solution-best-turn-row[^>]*>(.*?)</tr>', re.S)
COMPARE_NOTE = re.compile(r'<td[^>]*compare-best-turn-note[^>]*>(.*?)</td>', re.S)
TITLE = re.compile(r'title="([^"]*)"')

SENTENCE = 'Special effects of worn items are not counted here: %(items)s.'
WITH_FINAL_DAMAGE = ('Special effects of worn items, such as final damage, are not counted '
                     'here: %(items)s.')


def _text(fragment):
    return html.unescape(re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', fragment)).strip())


def _expected(names, language='en', sentence=WITH_FINAL_DAMAGE):
    with override(language):
        return gettext(sentence) % {'items': ', '.join(names)}


def _entries(test):
    from fashionistapulp.item_effects import load_effect_table
    entries = list(((load_effect_table(VERSION) or {}).get('items') or {}).values())
    return [entry for entry in entries if test(entry)]


def _final_damage_dofus():
    """Effect-table Dofus whose special effect is worth final damage, lowest level first."""
    found = _entries(lambda entry: entry.get('family') == 'dofus'
                     and not entry.get('removed')
                     and (entry.get('equivalents') or {}).get('final', 0) > 0
                     and entry.get('status', '').startswith('measured'))
    return sorted(found, key=lambda entry: (entry.get('level') or 0, entry['site_ids'][0]))


def _site_id(test):
    found = _entries(test)
    if not found:
        raise AssertionError('no effect-table entry matches')
    return found[0]['site_ids'][0]


def _piece(item_id, name='Piece', added=True):
    return SimpleNamespace(id=item_id, name=name, localized_name=name, item_added=added)


def _note(pieces, version=VERSION):
    from chardata.spells_view import _item_effects_note
    return _item_effects_note([SimpleNamespace(item_list=pieces)], version)


class TheItemsAreFoundInTheEffectTableTests(SimpleTestCase):

    def test_a_worn_item_with_a_final_damage_effect_is_named(self):
        item_id = _final_damage_dofus()[0]['site_ids'][0]
        self.assertEqual(_expected(['Piece']), _note([_piece(item_id)]))

    def test_an_item_is_found_by_its_id_not_its_name(self):
        entry = _final_damage_dofus()[0]
        stranger = max(item_id for found in _entries(lambda entry: True)
                       for item_id in found['site_ids'] if isinstance(item_id, int)) + 1
        pieces = [_piece(stranger, entry['name']['en']),
                  _piece(entry['site_ids'][0], 'Renamed')]
        self.assertEqual(_expected(['Renamed']), _note(pieces))

    def test_a_piece_in_an_empty_slot_is_not_named(self):
        item_id = _final_damage_dofus()[0]['site_ids'][0]
        self.assertEqual('', _note([_piece(item_id, added=False)]))

    def test_a_class_item_is_left_to_the_spells_it_changes(self):
        item_id = _site_id(lambda entry: entry.get('rule') == 'class_item_spell_modifiers')
        self.assertEqual('', _note([_piece(item_id)]))

    def test_an_item_without_effect_text_is_not_named(self):
        item_id = _site_id(lambda entry: entry.get('status') == 'no_effect_text')
        self.assertEqual('', _note([_piece(item_id)]))

    def test_an_effect_worth_nothing_to_the_bearer_is_not_named(self):
        item_id = _site_id(lambda entry: entry.get('status') == 'no_value_for_bearer')
        self.assertEqual('', _note([_piece(item_id)]))

    def test_an_effect_worth_only_effective_health_is_not_named(self):
        item_id = _site_id(lambda entry: set(entry.get('equivalents') or ()) == {'hp'})
        self.assertEqual('', _note([_piece(item_id)]))

    def test_an_effect_worth_only_movement_points_is_not_named(self):
        item_id = _site_id(lambda entry: set(entry.get('equivalents') or ()) == {'mp'})
        self.assertEqual('', _note([_piece(item_id)]))

    def test_an_effect_the_table_could_not_value_is_not_named(self):
        item_id = _site_id(lambda entry: entry.get('status') == 'not_valued'
                           and not entry.get('equivalents'))
        self.assertEqual('', _note([_piece(item_id)]))

    def test_an_effect_without_final_damage_is_named_without_the_example(self):
        item_id = _site_id(lambda entry: set(entry.get('equivalents') or ()) == {'dam'})
        self.assertEqual(_expected(['Piece'], sentence=SENTENCE), _note([_piece(item_id)]))

    def test_one_named_item_with_final_damage_brings_the_example(self):
        plain = _site_id(lambda entry: set(entry.get('equivalents') or ()) == {'dam'})
        final = _final_damage_dofus()[0]['site_ids'][0]
        pieces = [_piece(plain, 'Plain'), _piece(final, 'Final')]
        self.assertEqual(_expected(['Plain', 'Final']), _note(pieces))

    def test_two_worn_items_are_named_in_the_order_worn(self):
        first, second = [entry['site_ids'][0] for entry in _final_damage_dofus()[:2]]
        pieces = [_piece(second, 'Second'), _piece(first, 'First')]
        self.assertEqual(_expected(['Second', 'First']), _note(pieces))

    def test_a_version_without_an_effect_table_names_nothing(self):
        from fashionistapulp.game_versions import version_keys
        from fashionistapulp.item_effects import load_effect_table
        item_id = _final_damage_dofus()[0]['site_ids'][0]
        without = [version for version in version_keys(include_experimental=True)
                   if load_effect_table(version) is None]
        self.assertIn('beta', without)
        for version in without:
            with self.subTest(version=version):
                self.assertEqual('', _note([_piece(item_id)], version))


class _WithBuilds(TestCase):

    def setUp(self):
        from django.contrib.auth.models import User
        self.author = User.objects.create_user('author', 'a@x.test', 'pw')
        self.client.force_login(self.author)

    def _structure(self):
        from fashionistapulp.structure import get_structure, set_current_game_version
        set_current_game_version(VERSION)
        return get_structure(VERSION)

    def _name(self, item_id, language='en'):
        structure = self._structure()
        return structure.get_item_name_in_language(structure.get_item_by_id(item_id), language)

    def _build(self, names):
        from chardata.models import Char
        self.client.post('/import/text/', {
            'text': '\n'.join(names), 'confirm': '1',
            'char_class': 'Cra', 'level': '200'})
        char = Char.objects.order_by('-id').first()
        char.link_shared = True
        char.save()
        return char

    def _worn_ids(self, char):
        from chardata.solution import get_solution
        self._structure()
        return {piece.id for piece in get_solution(char).item_list if piece.item_added}

    def _concerned_build(self, rank=0):
        item_id = _final_damage_dofus()[rank]['site_ids'][0]
        char = self._build([self._name(item_id)])
        self.assertIn(item_id, self._worn_ids(char), 'the import did not wear the Dofus')
        return char, item_id

    def _ordinary_build(self):
        listed = {item_id for entry in _entries(lambda entry: True)
                  for item_id in entry.get('site_ids') or ()}
        for item in self._structure().types[200]['Hat']:
            if not item.removed and item.ankama_id and item.id not in listed:
                char = self._build([self._name(item.id)])
                self.assertEqual({item.id}, self._worn_ids(char))
                return char
        self.fail('every hat is in the effect table')

    def _page(self, path, language='en'):
        return self.client.get(path, HTTP_ACCEPT_LANGUAGE=language,
                               follow=True).content.decode('utf-8')


class TheSpellsPanelSaysItTests(_WithBuilds):

    def test_a_build_wearing_a_final_damage_dofus_is_told_its_name(self):
        char, item_id = self._concerned_build()
        found = NOTE.search(self._page('/spells/%d/' % char.id))
        self.assertIsNotNone(found, 'the panel has no place for the sentence')
        self.assertEqual(_expected([self._name(item_id)]), _text(found.group(1)))

    def test_a_build_wearing_none_leaves_the_sentence_empty(self):
        char = self._ordinary_build()
        found = NOTE.search(self._page('/spells/%d/' % char.id))
        self.assertIsNotNone(found, 'the panel has no place for the sentence')
        self.assertEqual('', _text(found.group(1)))

    def test_the_five_languages_name_the_item_in_their_own_words(self):
        char, item_id = self._concerned_build()
        for language in LANGUAGES:
            with self.subTest(language=language):
                found = NOTE.search(self._page('/spells/%d/' % char.id, language))
                self.assertIsNotNone(found)
                self.assertEqual(_expected([self._name(item_id, language)], language),
                                 _text(found.group(1)))
                if language != 'en':
                    self.assertNotEqual(_expected([self._name(item_id, language)], language),
                                        _expected([self._name(item_id)]))

    def test_the_ajax_answer_carries_it(self):
        char, item_id = self._concerned_build()
        response = self.client.post('/best_combo/%d/' % char.id, {
            'buff_state': json.dumps({}), 'spell_levels': json.dumps({}),
            'pushback': 'false'})
        self.assertEqual(200, response.status_code)
        combo = json.loads(response.content.decode('utf-8'))['best_combo']
        self.assertEqual(_expected([self._name(item_id)]), combo['item_effects_note'])

    def test_the_page_script_refreshes_it_from_the_ajax_answer(self):
        import os
        path = os.path.join(os.path.dirname(__file__), 'templates', 'chardata', 'spells.html')
        with open(path, encoding='utf-8') as handle:
            template = handle.read()
        self.assertRegex(template, r"\.best-combo-item-effects-note'\)\s*\.text\(combo\.item_effects_note")


class TheBuildAndComparePagesSayItTests(_WithBuilds):

    def test_the_build_page_puts_it_in_the_best_turn_title(self):
        char, item_id = self._concerned_build()
        row = BUILD_ROW.search(self._page('/solution/%d/' % char.id))
        self.assertIsNotNone(row)
        title = TITLE.search(row.group(1))
        self.assertIsNotNone(title)
        self.assertIn(_expected([self._name(item_id)]), html.unescape(title.group(1)))

    def test_the_comparison_names_the_items_of_both_builds(self):
        first, first_id = self._concerned_build(0)
        second, second_id = self._concerned_build(1)
        note = COMPARE_NOTE.search(self._page('/compare_sets/%d/%d/' % (first.id, second.id)))
        self.assertIsNotNone(note)
        self.assertIn(_expected([self._name(first_id), self._name(second_id)]),
                      _text(note.group(1)))
