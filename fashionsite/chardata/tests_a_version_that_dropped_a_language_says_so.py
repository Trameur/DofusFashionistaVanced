# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A version that no longer ships a language says so."""
from django.test import SimpleTestCase, TestCase
from django.utils import translation
from django.utils.translation import gettext

from chardata.spells_view import (_languages_left_english, _names_are_english)

PHRASE = ('This game version no longer provides spell names in your language, '
          'so they are shown in English.')

LANGUES = ('en', 'fr', 'es', 'pt', 'de')


class AVersionThatDroppedALanguageSaysSoTests(SimpleTestCase):

    def test_touch_no_longer_names_a_spell_in_german(self):
        from fashionistapulp.dofus_constants_touch_spells import (
            TOUCH_DAMAGE_SPELLS, TOUCH_SPELL_NAMES)
        expected = {spell.name for spells in TOUCH_DAMAGE_SPELLS.values()
                    for spell in spells}
        self.assertTrue(expected)
        self.assertEqual(expected, set(TOUCH_SPELL_NAMES))
        noms = list(TOUCH_SPELL_NAMES.values())
        anglais = [par_langue for par_langue in noms
                   if par_langue.get('de') == par_langue.get('en')]
        self.assertEqual(len(noms), len(anglais),
                         '%d of %d Touch spells still carry a German name'
                         % (len(noms) - len(anglais), len(noms)))
        self.assertEqual({'de'}, _languages_left_english('touch'))

    def test_retro_still_names_its_spells_in_german(self):
        from fashionistapulp.dofus_constants_retro_spells import (
            RETRO_SPELL_NAMES)
        noms = list(RETRO_SPELL_NAMES.values())
        identiques = [par_langue for par_langue in noms
                      if par_langue.get('de') == par_langue.get('en')]
        self.assertEqual(4, len(identiques), len(identiques))
        self.assertGreater(len(noms), 100, len(noms))
        self.assertEqual(set(), _languages_left_english('retro'))
        self.assertEqual(set(), _languages_left_english('dofus3'))

    def test_only_the_reader_who_sees_english_is_told(self):
        for version, langue, attendu in (
                ('touch', 'de', True),
                ('touch', 'fr', False),
                ('touch', 'en', False),
                ('dofus3', 'de', False),
                ('retro', 'de', False)):
            with self.subTest(version=version, langue=langue):
                with translation.override(langue):
                    self.assertEqual(attendu, _names_are_english(version))

    def test_the_sentence_reads_in_five_languages(self):
        rendus = {}
        for langue in LANGUES:
            with translation.override(langue):
                rendus[langue] = gettext(PHRASE)
        self.assertEqual(PHRASE, rendus['en'])
        for langue in LANGUES:
            with self.subTest(langue=langue):
                self.assertTrue(rendus[langue])
                if langue != 'en':
                    self.assertNotEqual(PHRASE, rendus[langue],
                                        'still untranslated')
        self.assertEqual(len(set(rendus.values())), len(LANGUES),
                         'two languages read the same sentence')


class TheTouchPageCarriesTheSentenceTests(TestCase):

    def _char(self):
        from fashionistapulp.structure import (get_structure,
                                               set_current_game_version)
        from chardata.models import Char
        set_current_game_version('touch')
        structure = get_structure('touch')
        noms = []
        for type_name in ('Hat', 'Cloak', 'Belt', 'Boots', 'Amulet'):
            item = next(i for i in structure.types[200][type_name]
                        if not i.removed and i.ankama_id)
            noms.append(structure.get_item_name_in_language(item, 'en'))
        self.client.post('/touch/import/text/', {
            'text': '\n'.join(noms), 'confirm': '1',
            'char_class': 'Iop', 'level': '200'})
        return Char.objects.order_by('-id').first()

    def test_the_german_reader_is_told_and_the_french_one_is_not(self):
        char = self._char()
        allemand = self.client.get('/de/touch/spells/%d/' % char.id,
                                   HTTP_ACCEPT_LANGUAGE='de')
        self.assertEqual(200, allemand.status_code)
        page = allemand.content.decode('utf-8')
        self.assertIn('nicht mehr in Ihrer Sprache', page)

        francais = self.client.get('/fr/touch/spells/%d/' % char.id,
                                   HTTP_ACCEPT_LANGUAGE='fr')
        self.assertEqual(200, francais.status_code)
        self.assertNotIn('plus les noms de sorts',
                         francais.content.decode('utf-8'))
