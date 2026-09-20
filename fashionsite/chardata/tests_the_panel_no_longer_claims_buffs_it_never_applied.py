# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The best turn sentence describes the buffs in force, never buffs it did not apply."""

import json
import re

from django.test import TestCase
from django.utils.translation import gettext, override

LANGUES = ('en', 'fr', 'es', 'pt', 'de')

SANS = ('One turn on a single target: average damage and critical hit rate '
        'included. Buffs cast in the turn count; none is assumed standing '
        'before it.')
AVEC = ('One turn on a single target: average damage and critical hit rate '
        'included. Buffs cast in the turn count, on top of the ones ticked '
        'on this page.')
FAUSSE = ('One turn on a single target: average damage, self buffs and '
          'critical hit rate included.')

# The minifier sorts attributes: find the tag by its class
NOTE_SORTS = re.compile(r'<span[^>]*best-combo-buff-note[^>]*>(.*?)</span>',
                        re.S)
NOTE_COMPARE = re.compile(r'<td[^>]*compare-best-turn-note[^>]*>(.*?)</td>',
                          re.S)
LIGNE_BUILD = re.compile(r'<tr[^>]*solution-best-turn-row[^>]*>(.*?)</tr>',
                         re.S)
TITRE = re.compile(r'title="([^"]*)"')


def _texte(html):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', html)).strip()


class _AvecUnBuild(TestCase):

    def setUp(self):
        from django.contrib.auth.models import User
        self.auteur = User.objects.create_user('auteur', 'a@x.test', 'pw')
        self.client.force_login(self.auteur)

    def _build(self, char_class='Cra',
               types=('Hat', 'Cloak', 'Belt', 'Boots', 'Amulet')):
        from chardata.models import Char
        from fashionistapulp.structure import (get_structure,
                                               set_current_game_version)
        set_current_game_version('dofus3')
        structure = get_structure('dofus3')
        noms = []
        for type_name in types:
            item = next(i for i in structure.types[200][type_name]
                        if not i.removed and i.ankama_id)
            noms.append(structure.get_item_name_in_language(item, 'en'))
        self.client.post('/import/text/', {
            'text': '\n'.join(noms), 'confirm': '1',
            'char_class': char_class, 'level': '200'})
        char = Char.objects.order_by('-id').first()
        char.link_shared = True
        char.save()
        return char

    def _page(self, chemin, langue='en'):
        return self.client.get(chemin, HTTP_ACCEPT_LANGUAGE=langue,
                               follow=True).content.decode('utf-8')


class TheDefaultSentenceIsTrueTests(_AvecUnBuild):

    def test_the_panel_opens_saying_no_buff_is_standing(self):
        char = self._build()
        note = NOTE_SORTS.search(self._page('/spells/%d/' % char.id))
        self.assertIsNotNone(note, 'la phrase des buffs a disparu du panneau')
        self.assertEqual(gettext(SANS), _texte(note.group(1)))

    def test_no_page_claims_self_buffs_are_included(self):
        char = self._build()
        autre = self._build(types=('Hat',))
        pages = ('/spells/%d/' % char.id,
                 '/solution/%d/' % char.id,
                 '/compare_sets/%d/%d/' % (char.id, autre.id))
        for chemin in pages:
            with self.subTest(chemin=chemin):
                self.assertNotIn(FAUSSE, self._page(chemin))

    def test_the_source_carries_the_sentence_nowhere(self):
        import os

        import chardata
        racine = os.path.dirname(os.path.abspath(chardata.__file__))
        coupables = []
        for dossier, _sous, fichiers in os.walk(racine):
            for nom in fichiers:
                if not nom.endswith(('.html', '.py', '.js')):
                    continue
                if nom.startswith('tests_'):
                    continue
                chemin = os.path.join(dossier, nom)
                with open(chemin, encoding='utf-8') as fichier:
                    if 'self buffs and critical hit rate' in fichier.read():
                        coupables.append(chemin)
        self.assertEqual([], coupables)


class TheSentenceFollowsTheTickedBuffsTests(_AvecUnBuild):

    def _combo(self, char, buff_state=None):
        from chardata.solution import get_solution
        from chardata.spells_view import _best_combo
        from fashionistapulp.structure import set_current_game_version
        set_current_game_version('dofus3')
        return _best_combo(char, get_solution(char), 'dofus3',
                           buff_state=buff_state)

    def _un_buff(self, char):
        from chardata.spell_combo import (Castable, _decide_spell_level,
                                          get_damage_spells_for_version)
        for spell in get_damage_spells_for_version('dofus3').get('Cra', []):
            if not spell.casting or char.level < spell.level_req[0]:
                continue
            castable = Castable(
                spell, _decide_spell_level(spell.level_req, char.level), False)
            if castable.buffs:
                return spell.name
        self.fail('aucun sort de buff pour ce personnage')

    def test_ticking_a_buff_changes_the_sentence(self):
        char = self._build()
        nom = self._un_buff(char)
        self.assertEqual(gettext(SANS), self._combo(char)['buff_note'])
        self.assertEqual(gettext(AVEC),
                         self._combo(char, {nom: 'n1'})['buff_note'])

    def test_a_buff_that_never_applies_leaves_the_sentence_alone(self):
        char = self._build()
        combo = self._combo(char, {'Sort qui n existe pas': 'n1'})
        self.assertEqual(gettext(SANS), combo['buff_note'])

    def test_the_ajax_answer_carries_it_so_the_page_can_follow(self):
        char = self._build()
        nom = self._un_buff(char)
        reponse = self.client.post(
            '/best_combo/%d/' % char.id,
            {'buff_state': json.dumps({nom: 'n1'}),
             'spell_levels': json.dumps({}), 'pushback': 'false'})
        self.assertEqual(200, reponse.status_code)
        combo = json.loads(reponse.content.decode('utf-8'))['best_combo']
        self.assertEqual(gettext(AVEC), combo['buff_note'])


class TheThreePagesAgreeTests(_AvecUnBuild):

    def test_the_three_pages_say_the_same_sentence(self):
        char = self._build()
        autre = self._build(types=('Hat',))
        attendu = gettext(SANS)
        panneau = NOTE_SORTS.search(self._page('/spells/%d/' % char.id))
        self.assertIsNotNone(panneau)
        self.assertEqual(attendu, _texte(panneau.group(1)))

        compare = NOTE_COMPARE.search(
            self._page('/compare_sets/%d/%d/' % (char.id, autre.id)))
        self.assertIsNotNone(compare)
        self.assertIn(attendu, _texte(compare.group(1)))

        ligne = LIGNE_BUILD.search(self._page('/solution/%d/' % char.id))
        self.assertIsNotNone(ligne)
        titre = TITRE.search(ligne.group(1))
        self.assertIsNotNone(titre)
        self.assertIn(attendu, titre.group(1))

    def test_the_rank_sentence_still_follows_it(self):
        char = self._build()
        page = self._page('/solution/%d/' % char.id)
        titre = TITRE.search(LIGNE_BUILD.search(page).group(1))
        self.assertIn(gettext('Spells at the highest level the character '
                              'reaches.'), titre.group(1))


class TheFiveLanguagesAnswerTests(_AvecUnBuild):

    def test_each_language_reads_its_own_sentence(self):
        char = self._build()
        vus = {}
        for langue in LANGUES:
            with self.subTest(langue=langue):
                with override(langue):
                    attendu = gettext(SANS)
                vus[langue] = attendu
                note = NOTE_SORTS.search(
                    self._page('/spells/%d/' % char.id, langue))
                self.assertIsNotNone(note)
                self.assertEqual(attendu, _texte(note.group(1)))
        for langue, phrase in vus.items():
            if langue != 'en':
                self.assertNotEqual(vus['en'], phrase, langue)

    def test_the_ticked_sentence_is_translated_too(self):
        with override('en'):
            anglais = gettext(AVEC)
        self.assertEqual(AVEC, anglais)
        for langue in LANGUES:
            if langue == 'en':
                continue
            with self.subTest(langue=langue):
                with override(langue):
                    self.assertNotEqual(anglais, gettext(AVEC))
