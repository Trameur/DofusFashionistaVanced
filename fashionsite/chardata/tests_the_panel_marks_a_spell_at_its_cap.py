# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Le panneau marque un sort arrive au plafond que le tour permet.

Un sort porte trois plafonds dans la donnee du jeu: lancers par tour, lancers
par cible, et temps de relance (qui vaut 1 dans le tour). `Castable.limit` en
prend le minimum, donc il est exactement <<le plus que ce tour-la permet sur
une cible>>, ce que le panneau annonce deja comme cadre. Une seule phrase
couvre les trois sans preciser a faux laquelle a joue.

**Mesure du 12 septembre 2026**, un panneau par classe sur les cinq versions,
83 panneaux: **79, soit 95,2 %, sont faconnes par une limite** sans que rien
ne le dise. Par version: 100 % sur Dofus 3, la beta, Dofus 2 et Touch, 66,7 %
sur Retro. Et **97,5 % des sorts jouables portent une limite** (1789 sur
1835), donc un lecteur qui voit un sort une seule fois ne peut pas deviner si
le solveur a choisi ou si le jeu refuse.

**La mesure a decide la forme.** 174 des 331 lignes de panneau porteraient la
mention, soit une ligne sur deux. Une phrase sous une ligne sur deux est du
bruit, donc c'est un marqueur <<2/2>> dans la ligne, sans ligne ajoutee, et la
phrase passe en infobulle.

Le marqueur n'est pose que quand la limite a **faconne** le tour: le sort est
lance autant de fois que permis ALORS QUE les PA payaient un lancer de plus.
Sinon il n'explique rien.

Premiere mesure a jeter, notee pour la methode: une version anterieure de la
sonde appariait les noms canoniques de `castable_spells` aux noms AFFICHES des
lancers. Sur Retro et Touch les deux diffèrent, donc leurs limites etaient
lues comme absentes et ces versions comptaient zero: la part sortait a 73,5 %
au lieu de 95,2 %.
"""

import json
import re

from django.test import SimpleTestCase, TestCase
from django.utils.translation import gettext, override

LANGUES = ('en', 'fr', 'es', 'pt', 'de')

PHRASE = 'at the most one turn on one target allows'

#: Le minifieur trie les attributs: on cherche la classe ou qu'elle soit.
MARQUE = re.compile(
    r'<span[^>]*best-combo-limit-mark[^>]*>\s*(\d+/\d+)\s*</span>')
LIGNE = re.compile(r'<li>(.*?)</li>', re.S)
TITRE = re.compile(r'title="([^"]*)"')


class _Faux(object):
    """Un lancable reduit a ce que `_limit_notes` lit."""

    is_spell = True

    def __init__(self, nom, cout, limite):
        self.spell = type('S', (), {'name': nom})()
        self.cost = cout
        self.limit = limite


class TheMarkFollowsTheRuleTests(SimpleTestCase):

    def _notes(self, spells, order, ap):
        from chardata.spells_view import _limit_notes
        times = {}
        for nom, _d in order:
            times[nom] = times.get(nom, 0) + 1
        return _limit_notes(spells, order, times, ap)

    def test_it_marks_the_last_cast_of_a_capped_spell(self):
        """Le dernier, celui ou la depense s'arrete: le marquer trois fois
        serait du bruit."""
        sort = _Faux('Concentration', 2, 3)
        order = [('Concentration', 100.0)] * 3
        notes = self._notes([sort], order, 12)
        self.assertEqual({2}, set(notes.keys()))
        self.assertEqual('3/3', notes[2][0])
        self.assertEqual(gettext(PHRASE), notes[2][1])

    def test_it_says_nothing_when_the_ap_stopped_the_spending(self):
        """Sans cette condition le marqueur n'expliquerait rien: c'est le
        budget qui a arrete le tour, pas le plafond."""
        sort = _Faux('Big', 5, 2)
        order = [('Big', 100.0)] * 2
        # 3 lancers couteraient 15 PA, le budget est 12: le plafond n'a rien
        # faconne.
        self.assertEqual({}, self._notes([sort], order, 12))

    def test_it_says_nothing_below_the_cap(self):
        sort = _Faux('Small', 2, 4)
        order = [('Small', 100.0)] * 2
        self.assertEqual({}, self._notes([sort], order, 12))

    def test_it_says_nothing_when_the_spell_has_no_cap(self):
        sort = _Faux('Free', 2, None)
        order = [('Free', 100.0)] * 3
        self.assertEqual({}, self._notes([sort], order, 12))

    def test_the_mark_counts_the_casts_and_the_cap(self):
        sort = _Faux('Twice', 3, 2)
        order = [('Twice', 100.0)] * 2
        notes = self._notes([sort], order, 12)
        self.assertEqual('2/2', notes[1][0])


class ItFiresOnRealBuildsTests(TestCase):

    def setUp(self):
        from django.contrib.auth.models import User
        self.auteur = User.objects.create_user('auteur', 'a@x.test', 'pw')
        self.client.force_login(self.auteur)

    def _build(self, char_class='Iop'):
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
            'char_class': char_class, 'level': '200'})
        return Char.objects.order_by('-id').first()

    def _combo(self, char, char_class=None):
        from chardata.solution import get_solution
        from chardata.spells_view import _best_combo
        from fashionistapulp.structure import set_current_game_version
        set_current_game_version('dofus3')

        class _Char(object):
            id = char.id
            level = char.level
            game_version = 'dofus3'

        _Char.char_class = char_class or char.char_class
        return _best_combo(_Char(), get_solution(char), 'dofus3')

    def test_most_classes_hit_a_cap_in_their_best_turn(self):
        """Mesure du 12 septembre 2026: 95,2 % des panneaux. Sans cette part,
        le marqueur serait une decoration qui ne sort jamais."""
        from chardata.version_compat import filter_classes_for_version
        from fashionistapulp.dofus_constants import CHARACTER_CLASSES
        char = self._build()
        vus = 0
        marques = 0
        for classe in filter_classes_for_version(CHARACTER_CLASSES, 'dofus3'):
            combo = self._combo(char, classe)
            if not combo or not combo['casts']:
                continue
            vus += 1
            if any(c['limit_mark'] for c in combo['casts']):
                marques += 1
        self.assertGreater(vus, 10, 'trop peu de classes mesurees')
        part = 100.0 * marques / vus
        self.assertGreater(part, 60.0,
                           'seulement %.1f %% des panneaux portent un '
                           'marqueur' % part)

    def test_no_mark_repeats_on_an_earlier_cast_of_the_same_spell(self):
        from collections import Counter
        from chardata.version_compat import filter_classes_for_version
        from fashionistapulp.dofus_constants import CHARACTER_CLASSES
        char = self._build()
        for classe in filter_classes_for_version(CHARACTER_CLASSES, 'dofus3'):
            combo = self._combo(char, classe)
            if not combo or not combo['casts']:
                continue
            marques = Counter(c['name'] for c in combo['casts']
                              if c['limit_mark'])
            for nom, combien in marques.items():
                with self.subTest(classe=classe, sort=nom):
                    self.assertEqual(1, combien,
                                     '%s marque %d fois' % (nom, combien))

    def test_the_mark_matches_the_number_of_casts_shown(self):
        """Le lecteur compte les lignes: le marqueur doit dire le meme
        nombre."""
        from collections import Counter
        from chardata.version_compat import filter_classes_for_version
        from fashionistapulp.dofus_constants import CHARACTER_CLASSES
        char = self._build()
        vus = 0
        for classe in filter_classes_for_version(CHARACTER_CLASSES, 'dofus3'):
            combo = self._combo(char, classe)
            if not combo or not combo['casts']:
                continue
            comptes = Counter(c['name'] for c in combo['casts'])
            for cast in combo['casts']:
                if not cast['limit_mark']:
                    continue
                vus += 1
                lances, limite = cast['limit_mark'].split('/')
                with self.subTest(classe=classe, sort=cast['name']):
                    self.assertEqual(comptes[cast['name']], int(lances))
                    self.assertGreaterEqual(int(lances), int(limite))
        self.assertGreater(vus, 5, 'aucun marqueur mesure')


class ThePageShowsItTests(TestCase):

    def setUp(self):
        from django.contrib.auth.models import User
        self.auteur = User.objects.create_user('auteur', 'a@x.test', 'pw')
        self.client.force_login(self.auteur)

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
            'char_class': 'Iop', 'level': '200'})
        return Char.objects.order_by('-id').first()

    def test_the_rendered_page_carries_the_mark_and_its_tooltip(self):
        char = self._build()
        page = self.client.get('/spells/%d/' % char.id,
                               follow=True).content.decode('utf-8')
        marques = MARQUE.findall(page)
        self.assertTrue(marques, 'aucun marqueur sur la page')
        # L'infobulle voyage avec: le marqueur seul serait cryptique.
        ligne_marquee = [l for l in LIGNE.findall(page) if MARQUE.search(l)]
        self.assertTrue(ligne_marquee)
        titre = TITRE.search(ligne_marquee[0])
        self.assertIsNotNone(titre, 'le marqueur n a pas d infobulle')
        self.assertEqual(gettext(PHRASE), titre.group(1))

    def test_the_ajax_answer_carries_both_fields(self):
        """Le panneau se rafraichit sans recharger; sans ces deux champs le
        marqueur disparait au premier clic."""
        char = self._build()
        reponse = self.client.post('/best_combo/%d/' % char.id, {
            'buff_state': json.dumps({}), 'spell_levels': json.dumps({}),
            'pushback': 'false'})
        self.assertEqual(200, reponse.status_code)
        combo = json.loads(reponse.content.decode('utf-8'))['best_combo']
        marques = [c for c in combo['casts'] if c['limit_mark']]
        self.assertTrue(marques, 'la reponse AJAX ne porte aucun marqueur')
        for cast in marques:
            with self.subTest(sort=cast['name']):
                self.assertRegex(cast['limit_mark'], r'^\d+/\d+$')
                self.assertEqual(gettext(PHRASE), cast['limit_title'])

    def test_the_tooltip_answers_in_five_languages(self):
        char = self._build()
        vus = {}
        for langue in LANGUES:
            with self.subTest(langue=langue):
                page = self.client.get(
                    '/spells/%d/' % char.id, HTTP_ACCEPT_LANGUAGE=langue,
                    follow=True).content.decode('utf-8')
                ligne = [l for l in LIGNE.findall(page) if MARQUE.search(l)]
                self.assertTrue(ligne)
                titre = TITRE.search(ligne[0])
                self.assertIsNotNone(titre)
                with override(langue):
                    attendu = gettext(PHRASE)
                self.assertEqual(attendu, titre.group(1))
                vus[langue] = attendu
        for langue, phrase in vus.items():
            if langue != 'en':
                self.assertNotEqual(vus['en'], phrase, langue)
