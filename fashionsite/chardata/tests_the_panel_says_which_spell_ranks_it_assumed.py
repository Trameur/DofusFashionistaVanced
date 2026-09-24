# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The best-turn panel says at what level it reads the spells."""

import json
import re

from django.test import TestCase
from django.utils.translation import gettext, override

LANGUES = ('en', 'fr', 'es', 'pt', 'de')

HAUT = 'Spells at the highest level the character reaches.'
CHOISI = 'Spells at the levels picked above.'

# the minifier sorts attributes; do not anchor on their order
NOTE = re.compile(
    r'<span[^>]*\bclass=[\'"]?best-combo-rank-note[\'"]?[^>]*>([^<]*)</span>')


class _AvecUnBuild(TestCase):

    def _build(self):
        from chardata.models import Char
        from fashionistapulp.structure import (get_structure,
                                               set_current_game_version)
        set_current_game_version('dofus3')
        structure = get_structure('dofus3')
        noms = []
        for type_name in ('Hat', 'Cloak', 'Belt', 'Boots', 'Amulet'):
            item = next(i for i in structure.types[200][type_name]
                        if not i.removed and i.ankama_id)
            noms.append(structure.get_item_name_in_language(item, 'en'))
        self.client.post('/import/text/', {
            'text': '\n'.join(noms), 'confirm': '1',
            'char_class': 'Cra', 'level': '200'})
        return Char.objects.order_by('-id').first()

    def _combo(self, char, levels=None):
        from chardata.solution import get_solution
        from chardata.spells_view import _best_combo
        from fashionistapulp.structure import set_current_game_version
        set_current_game_version('dofus3')
        return _best_combo(char, get_solution(char), 'dofus3', levels=levels)

    def _tous_au_plus_bas(self, char):
        from chardata.spell_combo import castable_spells
        return {castable.name: 0
                for castable in castable_spells(char.char_class, char.level,
                                                'dofus3')}


class TheAssumptionIsWorthSayingTests(_AvecUnBuild):

    def test_the_rank_really_changes_the_total(self):
        """Without a real gap between ranks, the note would have nothing to say."""
        char = self._build()
        haut = self._combo(char)
        bas = self._combo(char, levels=self._tous_au_plus_bas(char))
        self.assertTrue(haut['casts'], 'the turn is empty, the test measures nothing')
        self.assertGreater(haut['total'], bas['total'])


class TheNoteFollowsWhatWasReadTests(_AvecUnBuild):

    def test_it_says_the_highest_level_when_nothing_was_touched(self):
        char = self._build()
        self.assertEqual(gettext(HAUT), self._combo(char)['rank_note'])

    def test_it_says_the_picked_levels_as_soon_as_one_is_lowered(self):
        """One lowered spell is enough to flip the note."""
        from chardata.spell_combo import castable_spells
        char = self._build()
        premier = castable_spells(char.char_class, char.level, 'dofus3')
        self.assertTrue(premier)
        for castable in premier:
            if len(castable.spell.level_req) > 1:
                baisse = {castable.name: 0}
                break
        else:
            self.skipTest('no spell of this class carries two levels')
        self.assertEqual(gettext(CHOISI),
                         self._combo(char, levels=baisse)['rank_note'])

    def test_a_weapon_is_never_taken_for_a_lowered_spell(self):
        """The weapon has no level to lower, so it must never flip the note."""
        from chardata.spell_combo import WeaponCastable
        self.assertTrue(WeaponCastable.at_highest_rank)


class TheNoteSpeaksTheReaderLanguageTests(_AvecUnBuild):

    def test_the_five_languages_answer(self):
        char = self._build()
        vus = {}
        for langue in LANGUES:
            with self.subTest(langue=langue):
                with override(langue):
                    vus[langue] = self._combo(char)['rank_note']
                self.assertTrue(vus[langue])
                if langue != 'en':
                    self.assertNotEqual(vus['en'], vus[langue])

    def test_the_french_reader_reads_french(self):
        char = self._build()
        with override('fr'):
            note = self._combo(char)['rank_note']
        self.assertIn('niveau le plus haut', note)


class ThePageAndTheRefreshBothCarryItTests(_AvecUnBuild):

    def test_the_page_shows_it(self):
        char = self._build()
        page = self.client.get('/spells/%d/' % char.id,
                               follow=True).content.decode('utf-8')
        trouve = NOTE.search(page)
        self.assertIsNotNone(trouve, 'the note is missing from the page')
        self.assertEqual(gettext(HAUT), trouve.group(1).strip())

    def test_the_refresh_answer_carries_it(self):
        """The panel rebuilds from this JSON when a level changes; the note must refresh too."""
        char = self._build()
        reponse = self.client.post('/best_combo/%d/' % char.id,
                                   {'spell_levels': json.dumps({})})
        self.assertEqual(200, reponse.status_code)
        combo = json.loads(reponse.content.decode('utf-8'))['best_combo']
        self.assertEqual(gettext(HAUT), combo['rank_note'])
