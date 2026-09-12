# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Le panneau du meilleur tour dit a quel niveau il lit les sorts.

Il disait deja un seul tour sur une cible et des degats moyens. Il taisait
l'hypothese qui pese le plus: **chaque sort est lu au niveau le plus haut que
le personnage atteint**, donc entierement monte. L'autre phrase du panneau,
celle qui parle des buffs, a ete corrigee plus tard: voir
`tests_the_panel_no_longer_claims_buffs_it_never_applied`.

Mesure du 12 septembre 2026 sur un Cra de niveau 200 de la copie de
production: **1728 degats annonces au niveau le plus haut, 1292 au niveau 1**,
un quart d'ecart. Un joueur dont les sorts ne sont pas montes lisait donc un
total qu'il ne peut pas faire, sans rien pour le lui dire.

La page laisse deja choisir le niveau de chaque sort, et le panneau suit ce
choix. La phrase suit les deux cas: le niveau le plus haut tant que rien n'a
ete touche, les niveaux choisis des qu'un seul l'a ete.
"""

import json
import re

from django.test import TestCase
from django.utils.translation import gettext, override

LANGUES = ('en', 'fr', 'es', 'pt', 'de')

HAUT = 'Spells at the highest level the character reaches.'
CHOISI = 'Spells at the levels picked above.'

#: Le minifieur trie les attributs: on ne s'ancre sur aucun ordre.
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
        """La mesure qui justifie la phrase. Sans ecart, elle ne servirait a
        rien et il vaudrait mieux ne rien dire."""
        char = self._build()
        haut = self._combo(char)
        bas = self._combo(char, levels=self._tous_au_plus_bas(char))
        self.assertTrue(haut['casts'], 'le tour est vide, le test ne mesure rien')
        self.assertGreater(haut['total'], bas['total'])


class TheNoteFollowsWhatWasReadTests(_AvecUnBuild):

    def test_it_says_the_highest_level_when_nothing_was_touched(self):
        char = self._build()
        self.assertEqual(gettext(HAUT), self._combo(char)['rank_note'])

    def test_it_says_the_picked_levels_as_soon_as_one_is_lowered(self):
        """Un seul suffit: la phrase ne doit pas attendre que tous baissent."""
        from chardata.spell_combo import castable_spells
        char = self._build()
        premier = castable_spells(char.char_class, char.level, 'dofus3')
        self.assertTrue(premier)
        for castable in premier:
            if len(castable.spell.level_req) > 1:
                baisse = {castable.name: 0}
                break
        else:
            self.skipTest('aucun sort de cette classe ne porte deux niveaux')
        self.assertEqual(gettext(CHOISI),
                         self._combo(char, levels=baisse)['rank_note'])

    def test_a_weapon_is_never_taken_for_a_lowered_spell(self):
        """L'arme n'a pas de niveau que le lecteur puisse baisser, et elle ne
        doit pas faire basculer la phrase."""
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
        self.assertIsNotNone(trouve, 'la note est absente de la page')
        self.assertEqual(gettext(HAUT), trouve.group(1).strip())

    def test_the_refresh_answer_carries_it(self):
        """Le panneau est rebati depuis ce JSON quand le lecteur change un
        niveau: sans la phrase ici, elle resterait figee sur l'ancienne."""
        char = self._build()
        reponse = self.client.post('/best_combo/%d/' % char.id,
                                   {'spell_levels': json.dumps({})})
        self.assertEqual(200, reponse.status_code)
        combo = json.loads(reponse.content.decode('utf-8'))['best_combo']
        self.assertEqual(gettext(HAUT), combo['rank_note'])
