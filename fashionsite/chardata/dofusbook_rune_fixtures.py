# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Draconized Dofus 3 pieces and mocked DofusBook answers for the rune export and import tests."""

import json
import re
from unittest import mock

from chardata import dofusbook_export, dofusbook_import
from chardata.char_blobs import read_char_blob
from chardata.models import Char
from chardata.solution import set_minimal_solution
from fashionistapulp import dracorune_terms, dracorunes
from fashionistapulp.structure import (get_structure, set_current_game_version)

VERSION = 'dofus3'
REAL_LOAD = dracorunes.load_runes
RESISTANCE_KEY = 'resistance:neutral>earth'
ELEMENT_KEY = 'element:cha>agi'
LINK = 'https://www.dofusbook.net/fr/stuff/7894460-zobal-m-200'


def stand_in_runes(testcase):
    """Lets Dofus 3 read the Beta runes file for the length of the test."""
    def fake(version, folder=None):
        return REAL_LOAD('beta' if version == VERSION else version, folder)

    for target in ('fashionistapulp.dracorunes.load_runes',
                   'fashionistapulp.modelresult.load_runes'):
        patcher = mock.patch(target, fake)
        patcher.start()
        testcase.addCleanup(patcher.stop)


def runes():
    return REAL_LOAD('beta')


def structure():
    return get_structure(VERSION)


def lines_of(item):
    """{stat key: value} of the item's catalogue lines."""
    lines = {}
    for stat_id, value in item.stats:
        key = structure().get_stat_by_id(stat_id).key
        lines[key] = lines.get(key, 0) + value
    return lines


def variant_lines(item, key):
    """{stat key: value} of the item once the rune of that variant key is on it."""
    return dict(dict(dracorunes.variants(list(lines_of(item).items()), runes()))[key])


def piece(type_name, key, number=0):
    """The number-th plain piece of that type that takes the variant, by id."""
    found = structure()
    rules = runes()
    taken = []
    for item in sorted(found.types[200][type_name], key=lambda one: one.id):
        if (item.removed or not item.ankama_id or getattr(item, 'classes', ()) or item.level > 200
                or found.get_item_by_ankama_id(item.ankama_id) is not item
                or not dracorune_terms.is_eligible(item, found, rules)):
            continue
        if key in {variant.key for variant in dracorune_terms.item_variants(item, rules, found)}:
            taken.append(item)
    return taken[number]


def code_of(stat_key):
    return next(code for code, key in dofusbook_import.FM_CODES.items() if key == stat_key)


def their_lines(lines, item=None):
    """Their sheet lines: the changed lines only when the item is given, a removed line as an explicit 0."""
    if item is None:
        return {code_of(key): value for key, value in lines.items() if value}
    base = lines_of(item)
    return {code_of(key): lines.get(key, 0) for key in set(lines) | set(base)
            if lines.get(key, 0) != base.get(key, 0)}


def public_payload(entries):
    """Their public build answer for [(their slot code, item, {stat key: value})]."""
    items, worn, forge = [], {}, {}
    for number, (slot, item, lines) in enumerate(entries, start=1):
        items.append({'id': number, 'official': item.ankama_id, 'name': item.name})
        worn[slot] = number
        forge[slot] = their_lines(lines, item)
    return {'stuff': {'name': 'Rune build', 'character_level': 200, 'stuffItem': worn},
            'items': items, 'fmItems': forge, 'fmGlobal': {}}


class Answer(object):

    def __init__(self, content):
        self.content = content

    def read(self, *args):
        return json.dumps(self.content).encode('utf-8')

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def opener(content):
    return lambda request, timeout=None: Answer(content)


def slot_code(type_name):
    return dict(dofusbook_export.GROUPS)[type_name][0]


def worn_by(client, items, class_name='Iop'):
    """The char the import page builds from those pieces' English names."""
    set_current_game_version(VERSION)
    names = [structure().get_item_name_in_language(item, 'en') for item in items]
    client.post('/import/text/', {'text': '\n'.join(names), 'confirm': '1',
                                  'char_class': class_name, 'level': '200'})
    return Char.objects.order_by('-id').first()


def draconize(char, runes_on):
    """Saves [(item, variant key)] on the char's solution, each on the slot that holds the item."""
    minimal = read_char_blob(char.minimal_solution, None, 'minimal_solution', char)
    set_current_game_version(VERSION)
    minimal.place_dracorunes([(item.id, key) for item, key in runes_on])
    set_minimal_solution(char, minimal)
    return minimal


def export_page(client, char, language='en', known=None):
    """The export page of the char, their catalogue answering with the char's pieces and their catalogue lines."""
    minimal = read_char_blob(char.minimal_solution, None, 'minimal_solution', char)
    entries = []
    for item_id in minimal.item_per_slot.values():
        if item_id:
            item = structure().get_item_by_id(item_id)
            entries.append({'official': item.ankama_id, 'effects': [
                {'name': code, 'type': 'E', 'min': value, 'max': value}
                for code, value in their_lines(lines_of(item)).items() if value > 0]})
    answer = Answer({'data': known if known is not None else entries})
    with mock.patch('chardata.dofusbook_import._urlopen_allowlisted', return_value=answer):
        return client.get('/export/dofusbook/%d/' % char.id, HTTP_ACCEPT_LANGUAGE=language)


def forge_of(page):
    """The fm array of the link on the page, decoded."""
    import urllib.parse
    found = re.search(r'stuff=([^"&\'<> ]+)', page.content.decode('utf-8'))
    assert found, 'no link on the page'
    from chardata.tests_dofusbook_export import champs
    return champs(urllib.parse.unquote(found.group(1)))[0]
