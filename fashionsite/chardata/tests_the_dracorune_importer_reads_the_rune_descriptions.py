# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The importer gives each rune the description its item has in every language file of the dump, and none without them."""

import json
import os
import tempfile

from django.test import SimpleTestCase

from chardata.tests import itemscraper_module
from chardata.tests_the_dracorune_importer_reads_the_runes_by_their_effects import _dump
from fashionistapulp.dracorunes import load_runes, rune_description, rune_of

TEXTS = {'en': {'601': 'Turns Strength into Agility.', '602': 'Turns everything into Power.'},
         'fr': {'601': 'Change la Force en Agilite.'}}


class TheDracoruneImporterReadsTheRuneDescriptionsTests(SimpleTestCase):

    def setUp(self):
        self.store = itemscraper_module('store_dracorunes')
        self.raw = tempfile.TemporaryDirectory()
        self.out = tempfile.TemporaryDirectory()
        self.addCleanup(self.raw.cleanup)
        self.addCleanup(self.out.cleanup)
        _dump(self.raw.name, {10: [(4081, 4)], 15: [(4083, 0, 70)]})
        path = os.path.join(self.raw.name, 'items.json')
        with open(path, encoding='utf-8') as handle:
            data = json.load(handle)
        by_rid = {ref['rid']: ref for ref in data['references']['RefIds']}
        for value, description_id in zip(data['objectsById']['m_values']['Array'], (601, 602)):
            by_rid[value['rid']]['data']['descriptionId'] = description_id
        with open(path, 'w', encoding='utf-8') as handle:
            json.dump(data, handle)

    def write_languages(self):
        for lang, entries in TEXTS.items():
            with open(os.path.join(self.raw.name, '%s.json' % lang), 'w', encoding='utf-8') as handle:
                json.dump({'entries': entries}, handle)

    def test_each_rune_takes_the_description_of_each_language_file(self):
        self.write_languages()
        self.store.write(self.raw.name, '9.9.9.9', 'beta', self.out.name)
        runes = load_runes('beta', self.out.name)
        self.assertEqual([{'en': 'Turns Strength into Agility.', 'fr': 'Change la Force en Agilite.'},
                          {'en': 'Turns everything into Power.'}],
                         [rune['descriptions'] for rune in runes['runes']])

    def test_a_dump_without_language_files_writes_no_description(self):
        self.store.write(self.raw.name, '9.9.9.9', 'beta', self.out.name)
        runes = load_runes('beta', self.out.name)
        self.assertFalse(any('descriptions' in rune for rune in runes['runes']))
        self.assertIsNone(rune_description(rune_of('power', runes), 'fr'))

    def test_a_language_without_a_text_reads_the_english_one(self):
        self.write_languages()
        self.store.write(self.raw.name, '9.9.9.9', 'beta', self.out.name)
        runes = load_runes('beta', self.out.name)
        power = rune_of('power', runes)
        self.assertEqual('Turns everything into Power.', rune_description(power, 'fr'))
        self.assertEqual('Change la Force en Agilite.', rune_description(rune_of('element:str>agi', runes), 'fr'))

    def test_the_shipped_runes_file_describes_every_rune_in_the_five_languages(self):
        for rune in load_runes('beta')['runes']:
            self.assertEqual({'de', 'en', 'es', 'fr', 'pt'}, set(rune.get('descriptions', ())), rune['item_id'])
