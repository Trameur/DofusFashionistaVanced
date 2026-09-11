# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Un lancer du meilleur tour qui n'affiche aucun degat dit pourquoi.

Mesure du 12 septembre 2026 sur la copie de production: **77 des 200 tours
proposes, soit 38,5 %, contiennent au moins un lancer a zero**, 86 lancers au
total. Le panneau affichait <<Tirs Puissants, 1 PA, 0>> et rien d'autre.

Le solveur a raison de depenser ce PA: retirer le sort de ses options fait
BAISSER le tour, verifie sur 60 builds sans une seule exception. Mais un zero
sans un mot se lit comme une panne, et le lecteur conclut que l'outil se
trompe au moment meme ou il a raison.

Deux raisons, et deux seulement, lues dans la donnee:

- le sort ne porte que des lignes de buff, donc il n'a rien a poser lui-meme
  et sa valeur est dans les lancers qui suivent;
- ses degats sont differes, donc ils sont comptes dans le bloc du dessous.

Sur les 86 lancers a zero mesures, **les 86 recoivent une note**: 84 de buff
et 2 de degats differes. Un zero qu'on ne saurait pas expliquer resterait nu
plutot que de recevoir une phrase au hasard.
"""

from django.test import SimpleTestCase, TestCase

LANGUES = ('en', 'fr', 'es', 'pt', 'de')


class _Lancable(object):
    """Un lancable reduit a ce que la note regarde."""

    def __init__(self, buffs=(), hits=()):
        self.buffs = list(buffs)
        self.hits = list(hits)


class TheReasonIsReadAndNeverGuessedTests(SimpleTestCase):

    def _note(self, castable, name='Essai', later=None, damage=0):
        from chardata.spells_view import _cast_note
        return _cast_note(castable, name, later or {}, damage)

    def test_a_buff_cast_says_it_raises_what_follows(self):
        note = self._note(_Lancable(buffs=['buff_pow']))
        self.assertIn('raises the casts', note)

    def test_a_delayed_cast_says_its_damage_is_counted_apart(self):
        note = self._note(_Lancable(hits=['air']), name='Poison',
                          later={'Poison': 120})
        self.assertIn('counted apart', note)

    def test_the_delayed_reason_wins_over_the_buff_one(self):
        """Un sort qui porte les deux: ce qu'il pose est plus concret que ce
        qu'il grossit, et le bloc du dessous le montre deja."""
        note = self._note(_Lancable(buffs=['buff_pow'], hits=['air']),
                          name='Poison', later={'Poison': 120})
        self.assertIn('counted apart', note)

    def test_a_cast_that_deals_damage_says_nothing(self):
        self.assertEqual('', self._note(_Lancable(hits=['air']), damage=412))

    def test_a_zero_nobody_can_explain_stays_bare(self):
        """Mieux vaut un zero nu qu'une phrase inventee."""
        self.assertEqual('', self._note(_Lancable()))

    def test_a_weapon_cast_is_never_called_a_buff(self):
        """Le lancable de l'arme ne porte pas d'attribut `buffs`, et la note
        ne doit pas se tromper de raison en le lisant."""
        class _Arme(object):
            is_spell = False
        self.assertEqual('', self._note(_Arme()))


class TheNoteAnswersInFiveLanguagesTests(SimpleTestCase):

    def _notes(self, langue):
        from django.utils.translation import override
        from chardata.spells_view import _CAST_NOTES
        with override(langue):
            return {cle: str(valeur) for cle, valeur in _CAST_NOTES.items()}

    def test_each_language_has_its_own_words(self):
        anglais = self._notes('en')
        for langue in LANGUES:
            with self.subTest(langue=langue):
                notes = self._notes(langue)
                for cle, texte in notes.items():
                    self.assertTrue(texte)
                    if langue != 'en':
                        self.assertNotEqual(anglais[cle], texte, cle)

    def test_the_french_reader_reads_french(self):
        notes = self._notes('fr')
        self.assertIn('aucun dégât', notes['buff'])
        self.assertIn('lancers', notes['buff'])
        self.assertIn('compté à part', notes['delayed'])


class TheLineKeepsItsShapeTests(TestCase):
    """Le nom du sort garde sa place: la note va SOUS la ligne et non dedans.
    La ligne est donc un bloc a elle, et le rafraichissement du panneau doit
    la rebatir pareil, sans quoi la note disparait au premier reglage change.
    """

    def _build(self):
        from fashionistapulp.structure import (get_structure,
                                               set_current_game_version)
        from chardata.models import Char
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

    def test_every_cast_line_is_a_block_of_its_own(self):
        import re
        char = self._build()
        page = self.client.get('/spells/%d/' % char.id).content.decode('utf-8')
        listes = re.findall(r'<ol class="best-combo-casts">(.*?)</ol>', page,
                            re.S)
        self.assertTrue(listes, 'le panneau du meilleur tour est absent')
        lignes = re.findall(r'<li>\s*(<[a-z]+[^>]*)', listes[0])
        self.assertTrue(lignes)
        for ouverture in lignes:
            self.assertIn('best-combo-cast-line', ouverture)

    def test_the_refresh_answer_carries_the_note_for_every_cast(self):
        """Le panneau est rebati depuis ce JSON: une note absente ici
        disparaitrait au premier reglage change."""
        import json
        char = self._build()
        reponse = self.client.get('/best_combo/%d/' % char.id)
        self.assertEqual(200, reponse.status_code)
        combo = json.loads(reponse.content.decode('utf-8'))['best_combo']
        self.assertTrue(combo['casts'])
        for cast in combo['casts']:
            self.assertIn('note', cast)
            if not cast['damage']:
                self.assertTrue(cast['note'], cast['name'])
