# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
import json
import re

from django.test import SimpleTestCase, TestCase

from chardata.spell_buffs import get_damage_spells_for_version
from chardata.spell_reference import (get_spell_reference,
                                      reference_by_spell_id)

VERSIONS_WITH_SHARED_SPELLS = ('dofus3', 'beta', 'dofus2')

# The shared spells a player casts, the ones the client describes
CAST_BY_THE_PLAYER = (
    'Burnt Pie', 'Leek Pie', "Grunob's Lightning Strike", "Grunob's Lesson",
    'Kannibubble', 'Kanniboil', 'Mantiscroc', 'Dart Mocles', 'Moon Hammer',
    'Darkli Moon Hammer', 'Perfidious Boomerang', 'Diamondine Boomerang',
    'Weapon Skill')


def _shared(version):
    return {spell.name: spell
            for spell in get_damage_spells_for_version(version)['default']}


class TheReferenceAndTheGeneratorNameTheSameIdsTests(SimpleTestCase):

    def test_the_two_files_carry_the_same_ids(self):
        for version in VERSIONS_WITH_SHARED_SPELLS:
            with self.subTest(version=version):
                generated = [spell.spell_id
                             for spell in _shared(version).values()]
                self.assertNotIn(None, generated)
                self.assertEqual(sorted(generated),
                                 sorted(reference_by_spell_id(version,
                                                              'default')))

    def test_the_two_files_pick_their_spells_in_one_place(self):
        from chardata.tests import itemscraper_module
        generator = itemscraper_module('generate_damage_spells')
        transform = itemscraper_module('get_spells')
        self.assertIs(generator.select_default_spells,
                      transform.select_default_spells)

    def test_each_shared_spell_is_listed_once_in_spec_order(self):
        from chardata.tests import itemscraper_module
        specs = itemscraper_module(
            'default_damage_spells').DEFAULT_DAMAGE_SPELL_SPECS
        for version in VERSIONS_WITH_SHARED_SPELLS:
            with self.subTest(version=version):
                names = [spell.name for spell
                         in get_damage_spells_for_version(version)['default']]
                self.assertEqual([spec.name for spec in specs], names)

    def test_touch_and_retro_have_no_shared_block_to_align(self):
        for version in ('touch', 'retro'):
            with self.subTest(version=version):
                self.assertFalse(
                    get_damage_spells_for_version(version).get('default'))
                self.assertNotIn('default', get_spell_reference(version))


class TheSharedSpellsShowWhatTheGameSaysTests(SimpleTestCase):

    def test_the_ones_the_player_casts_have_a_description_and_a_cast_line(self):
        for version in VERSIONS_WITH_SHARED_SPELLS:
            with self.subTest(version=version):
                reference = reference_by_spell_id(version, 'default')
                shared = _shared(version)
                for name in CAST_BY_THE_PLAYER:
                    entry = reference[shared[name].spell_id]
                    self.assertTrue(entry['description']['en'], name)
                    self.assertTrue(entry['ap'], name)
                    self.assertTrue(entry['range'], name)

    def test_the_ebony_dofus_shows_no_cast_line(self):
        for version in VERSIONS_WITH_SHARED_SPELLS:
            with self.subTest(version=version):
                reference = reference_by_spell_id(version, 'default')
                entry = reference[_shared(version)['Ebony Dofus'].spell_id]
                self.assertEqual(18645, entry['id'])
                for key in ('ap', 'range', 'per_turn', 'per_target',
                            'cooldown', 'crit'):
                    self.assertNotIn(key, entry)

    def test_the_five_languages_describe_them(self):
        for version in VERSIONS_WITH_SHARED_SPELLS:
            with self.subTest(version=version):
                reference = reference_by_spell_id(version, 'default')
                shared = _shared(version)
                for name in CAST_BY_THE_PLAYER:
                    entry = reference[shared[name].spell_id]
                    for lang in ('en', 'fr', 'es', 'pt', 'de'):
                        self.assertTrue(entry['description'][lang],
                                        '%s %s' % (name, lang))


class TheSpellPageShowsThemTests(TestCase):

    def _char(self, char_class='Cra'):
        from chardata.models import Char
        from fashionistapulp.structure import (get_structure,
                                               set_current_game_version)
        set_current_game_version('dofus3')
        structure = get_structure('dofus3')
        item = next(i for i in structure.types[200]['Hat']
                    if not i.removed and i.ankama_id)
        self.client.post('/import/text/', {
            'text': structure.get_item_name_in_language(item, 'en'),
            'confirm': '1', 'char_class': char_class, 'level': '200'})
        char = Char.objects.order_by('-id').first()
        self.assertIsNotNone(char)
        return char

    def _digests(self, char, language='en'):
        page = self.client.get('/spells/%d/' % char.id,
                               HTTP_ACCEPT_LANGUAGE=language
                               ).content.decode('utf-8')
        found = re.search(r'var spellDigests = (\[.*?\]);\s*\n', page, re.S)
        self.assertTrue(found)
        return {digest['canonical']: digest
                for digest in json.loads(found.group(1))
                if digest.get('type') == 'spell'}

    def test_the_shared_cards_carry_the_games_words(self):
        digests = self._digests(self._char())
        for name in CAST_BY_THE_PLAYER:
            reference = digests[name].get('reference')
            self.assertTrue(reference, name)
            self.assertTrue(reference['description'], name)
            self.assertTrue(reference['ap'], name)
        self.assertTrue(digests['Ebony Dofus'].get('reference'))
        self.assertIsNone(digests['Ebony Dofus']['reference']['ap'])

    def test_each_shared_spell_is_one_card(self):
        page = self.client.get('/spells/%d/' % self._char().id,
                               HTTP_ACCEPT_LANGUAGE='en'
                               ).content.decode('utf-8')
        found = re.search(r'var spellDigests = (\[.*?\]);\s*\n', page, re.S)
        names = [digest['canonical'] for digest in json.loads(found.group(1))
                 if digest.get('type') == 'spell']
        for name in CAST_BY_THE_PLAYER + ('Ebony Dofus',):
            self.assertEqual(1, names.count(name), name)
        self.assertNotIn('Ebony Black', names)

    def test_the_words_follow_the_readers_language(self):
        char = self._char()
        french = self._digests(char, 'fr')['Moon Hammer']['reference']
        self.assertIn('Air', french['description'])
        self.assertIn('Portée', french['description'])
