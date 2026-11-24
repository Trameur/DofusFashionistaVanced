# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A Touch special-spell line and the tooltip of the spell it names carry no untranslated tag."""
import os
import pickle
import sqlite3
import tempfile
from unittest import mock

from django.test import SimpleTestCase

from chardata.tests import itemscraper_module

CAST_SPELL = 2822
SPELL_ID = 4242
TAGGED_NAME = '[!] Les cages Brâkmariennes hautes'
FRENCH_NAME = 'Les cages Brâkmariennes hautes'
TEMPLATE = {'en': 'Casts the #1 spell at the start of the fight',
            'fr': 'Lance le sort #1 en début de combat'}


def _lines(name_by_lang):
    module = itemscraper_module('store_touch_special_spells')
    items = {'18815': {'possibleEffects': [{'effectId': CAST_SPELL, 'diceNum': SPELL_ID}]}}
    spells = {lang: {} for lang in module.LANGUAGES}
    effects = {lang: {} for lang in module.LANGUAGES}
    for lang, name in name_by_lang.items():
        spells[lang][str(SPELL_ID)] = {'nameId': name}
        effects[lang][str(CAST_SPELL)] = {'descriptionId': TEMPLATE[lang]}
    return module.special_spell_lines(items, spells, effects)[18815]


class ATouchSpecialSpellLineDropsTheUntranslatedTagTests(SimpleTestCase):

    def test_a_tagged_spell_name_leaves_the_french_name_in_the_line(self):
        lines = _lines({'en': TAGGED_NAME, 'fr': FRENCH_NAME})
        self.assertEqual(['Lance le sort %s en début de combat' % FRENCH_NAME], lines['fr'])
        self.assertEqual(1, len(lines['en']))
        self.assertNotIn('[!]', lines['en'][0])
        self.assertIn(FRENCH_NAME, lines['en'][0])

    def test_the_tooltip_of_a_tagged_spell_is_kept_under_its_clean_name(self):
        tooltips = itemscraper_module('store_spell_tooltips')
        line = _lines({'en': TAGGED_NAME})['en']
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, 'items.db')
            conn = sqlite3.connect(path)
            conn.execute('CREATE TABLE items (id INTEGER, ankama_id INTEGER, '
                         'ankama_type text, dofustouch INTEGER)')
            conn.execute("INSERT INTO items VALUES (18815, 18815, 'equipment', 1)")
            conn.execute('CREATE TABLE extra_lines (item INTEGER, line text, language text)')
            conn.execute('INSERT INTO extra_lines VALUES (18815, ?, ?)',
                         (pickle.dumps(line), 'en'))
            conn.commit()
            conn.close()
            with mock.patch.object(tooltips, '_open_items_db',
                                   lambda version: sqlite3.connect(path)), \
                    mock.patch.object(tooltips, '_save_db_to_dump', lambda *args: None), \
                    mock.patch.object(tooltips, 'get_items_db_path', lambda version: path):
                tooltips.store('touch', {18815: {'en': {TAGGED_NAME: '[!] Invoque : Boufballe'}}})
            conn = sqlite3.connect(path)
            try:
                stored = [pickle.loads(blob) for blob, in
                          conn.execute('SELECT tooltips FROM spell_tooltips')]
            finally:
                conn.close()
        self.assertEqual([{FRENCH_NAME: 'Invoque : Boufballe'}], stored)
