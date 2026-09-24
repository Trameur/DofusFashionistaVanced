# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
import os
from unittest import mock
from urllib.parse import unquote

from django.conf import settings
from django.test import SimpleTestCase, TestCase

from chardata.spell_buffs import get_damage_spells_for_version
from chardata.spells_view import _create_spell_web_digest

STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')

HOMONYMS = (
    ('dofus3', 'Forgelance', 'Collapse', 23736, 'Collapse (23736).png'),
    ('dofus3', 'Enutrof', 'Collapse', 13352, 'Collapse.png'),
    ('dofus3', 'Eliotrope', 'Wandering', 14604, 'Wandering (14604).png'),
    ('beta', 'Forgelance', 'Collapse', 23736, 'Collapse (23736).png'),
    ('beta', 'Enutrof', 'Collapse', 13352, 'Collapse.png'),
    ('beta', 'Eliotrope', 'Wandering', 14604, 'Wandering (14604).png'),
    ('dofus2', 'Forgelance', 'Collapse', 23736, 'Collapse (23736).png'),
    ('dofus2', 'Enutrof', 'Collapse', 13352, 'Collapse.png'),
)


def _damage_spell(version, char_class, spell_id):
    return next(spell for spell in get_damage_spells_for_version(version)[char_class]
                if spell.spell_id == spell_id)


def _on_disk(url):
    relative = unquote(url.split('?', 1)[0])
    if relative.startswith(settings.STATIC_URL):
        relative = relative[len(settings.STATIC_URL):]
    return os.path.isfile(os.path.join(STATIC, *relative.split('/')))


class TheSpellCardAsksForItsOwnIconTests(SimpleTestCase):

    def test_each_homonym_card_asks_for_the_file_of_its_id(self):
        for version, char_class, name, spell_id, icon in HOMONYMS:
            with self.subTest(version=version, char_class=char_class):
                spell = _damage_spell(version, char_class, spell_id)
                self.assertEqual(name, spell.name)
                url = _create_spell_web_digest(spell, version)['image_url']
                self.assertEqual(icon, unquote(url).rsplit('/', 1)[1])
                self.assertTrue(_on_disk(url), url)

    def test_the_two_collapse_cards_ask_for_two_files(self):
        for version in ('dofus3', 'beta', 'dofus2'):
            with self.subTest(version=version):
                urls = {_create_spell_web_digest(
                            _damage_spell(version, char_class, spell_id),
                            version)['image_url']
                        for char_class, spell_id in (('Enutrof', 13352),
                                                     ('Forgelance', 23736))}
                self.assertEqual(2, len(urls), urls)


class TheBestTurnShowsTheIconOfItsIdTests(TestCase):

    def _char(self, char_class):
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

    def test_a_forgelance_collapse_cast_shows_the_forgelance_icon(self):
        from chardata import spell_combo
        char = self._char('Forgelance')
        names = {spell.name for spell in
                 spell_combo.castable_spells('Forgelance', 200, 'dofus3')}
        self.assertIn('Collapse', names)
        with mock.patch.object(spell_combo, 'best_turn',
                               return_value=(100, [('Collapse', 100)])):
            page = self.client.get('/spells/%d/' % char.id,
                                   HTTP_ACCEPT_LANGUAGE='en'
                                   ).content.decode('utf-8')
        start = page.index('best-combo-icon')
        cast = page[start:page.index('>', start)]
        self.assertIn('Collapse%20(23736).png', cast)
