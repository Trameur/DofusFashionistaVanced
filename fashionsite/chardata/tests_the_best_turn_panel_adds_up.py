# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Le panneau du meilleur tour s'additionne.

Chaque lancer affiche ses degats et le cumul a cet instant, et le total est
annonce en tete. Un lecteur qui additionne la colonne des degats doit retomber
sur le dernier cumul, et le dernier cumul doit etre le total. C'est la
verification la plus evidente qu'on puisse faire d'un panneau de calcul, et
elle ne tombait pas juste.

**Mesure du 12 septembre 2026**, un panneau par classe sur les cinq versions,
83 panneaux: **46 dont la colonne des degats ne retombait pas sur celle du
cumul**, jusqu'a 2 d'ecart. Et deux d'entre eux, le Iop de Dofus 3 et celui de
la beta, annoncaient **3956 en tete pour un dernier cumul de 3955**.

La cause n'etait pas le calcul mais l'affichage: les degats du lancer et le
cumul etaient arrondis chacun de son cote, a partir de flottants. Deux
arrondis honnetes du meme nombre ne s'additionnent pas. Le cumul est
maintenant arrondi une seule fois et les degats du lancer sont sa difference
avec le precedent, donc la colonne s'additionne par construction.

Le total change d'au plus 1 par rapport a l'ancien, et c'est celui de la
liste: le total en tete doit etre le nombre que les lignes en dessous
atteignent.
"""

import re

from django.test import TestCase

#: Le minifieur trie les attributs et compacte les espaces: on cherche la
#: classe ou qu'elle soit dans la balise.
CASTS = re.compile(r'<ol[^>]*best-combo-casts[^>]*>(.*?)</ol>', re.S)
LIGNE = re.compile(r'<li.*?</li>', re.S)
DEGATS = re.compile(r'<span[^>]*best-combo-damage[^>]*>(-?\d+)</span>')
CUMUL = re.compile(r'<span[^>]*best-combo-running[^>]*>(-?\d+)</span>')
TOTAL = re.compile(r'<span[^>]*best-combo-total[^>]*>\s*(-?\d+)')


class _FauxChar(object):
    """Le personnage tel que le panneau le lit: une classe et un niveau. On
    promene la meme solution sur toutes les classes de la version, ce qui est
    exactement ce qui a fait sortir les 46 panneaux faux."""

    def __init__(self, char_class, level, game_version):
        self.id = 'audit-%s' % char_class
        self.char_class = char_class
        self.level = level
        self.game_version = game_version


class _AvecUneSolution(TestCase):

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
        for type_name in ('Hat', 'Cloak', 'Belt', 'Boots', 'Amulet', 'Weapon'):
            item = next(i for i in structure.types[200][type_name]
                        if not i.removed and i.ankama_id)
            noms.append(structure.get_item_name_in_language(item, 'en'))
        self.client.post('/import/text/', {
            'text': '\n'.join(noms), 'confirm': '1',
            'char_class': char_class, 'level': '200'})
        return Char.objects.order_by('-id').first()

    def _panneaux(self, char):
        """Un panneau par classe de Dofus 3, sur la solution de ce build."""
        from chardata.solution import get_solution
        from chardata.spells_view import _best_combo
        from chardata.version_compat import filter_classes_for_version
        from fashionistapulp.dofus_constants import CHARACTER_CLASSES
        from fashionistapulp.structure import set_current_game_version

        solution = get_solution(char)
        self.assertIsNotNone(solution, 'le build importe n a pas de solution')
        panneaux = []
        for char_class in filter_classes_for_version(CHARACTER_CLASSES,
                                                     'dofus3'):
            set_current_game_version('dofus3')
            combo = _best_combo(_FauxChar(char_class, 200, 'dofus3'),
                                solution, 'dofus3')
            if combo and combo['casts']:
                panneaux.append((char_class, combo))
        self.assertGreater(len(panneaux), 10, 'trop peu de panneaux mesures')
        return panneaux


class TheColumnsAgreeTests(_AvecUneSolution):

    def test_the_damage_column_sums_to_the_last_running_total(self):
        char = self._build()
        for char_class, combo in self._panneaux(char):
            with self.subTest(classe=char_class):
                self.assertEqual(combo['casts'][-1]['running'],
                                 sum(c['damage'] for c in combo['casts']))

    def test_every_running_total_is_the_sum_so_far(self):
        """Pas seulement la derniere ligne: chaque cumul doit etre la somme
        des degats affiches au-dessus de lui."""
        char = self._build()
        for char_class, combo in self._panneaux(char):
            with self.subTest(classe=char_class):
                cumul = 0
                for index, cast in enumerate(combo['casts']):
                    cumul += cast['damage']
                    self.assertEqual(cumul, cast['running'],
                                     'lancer %d' % (index + 1))

    def test_the_headline_total_is_the_last_running_total(self):
        """Le Iop de Dofus 3 annoncait 3956 pour un dernier cumul de 3955."""
        char = self._build()
        for char_class, combo in self._panneaux(char):
            with self.subTest(classe=char_class):
                self.assertEqual(combo['casts'][-1]['running'],
                                 combo['total'])


class TheRenderedPageAddsUpTests(_AvecUneSolution):

    def _panneau_html(self, char):
        page = self.client.get('/spells/%d/' % char.id,
                               follow=True).content.decode('utf-8')
        casts = CASTS.search(page)
        self.assertIsNotNone(casts, 'la liste des lancers est absente')
        total = TOTAL.search(page)
        self.assertIsNotNone(total, 'le total en tete est absent')
        lignes = []
        for ligne in LIGNE.findall(casts.group(1)):
            degats = DEGATS.search(ligne)
            cumul = CUMUL.search(ligne)
            self.assertIsNotNone(degats, ligne)
            self.assertIsNotNone(cumul, ligne)
            lignes.append((int(degats.group(1)), int(cumul.group(1))))
        self.assertTrue(lignes, 'aucun lancer sur la page')
        return lignes, int(total.group(1))

    def test_the_page_the_reader_sees_adds_up(self):
        """Le dict peut etre juste et le gabarit lire la mauvaise cle: c'est
        la page rendue qui compte."""
        char = self._build()
        lignes, total = self._panneau_html(char)
        cumul = 0
        for index, (degats, affiche) in enumerate(lignes):
            cumul += degats
            self.assertEqual(cumul, affiche, 'lancer %d' % (index + 1))
        self.assertEqual(total, cumul)
        self.assertEqual(total, lignes[-1][1])

    def test_no_cast_shows_a_bare_zero(self):
        """Les degats affiches sont maintenant une difference d'arrondis, donc
        un lancer peut tomber a zero la ou le flottant ne l'etait pas. La
        raison doit suivre l'affichage, sinon le zero redevient muet."""
        from chardata.solution import get_solution
        from chardata.spells_view import _best_combo
        from fashionistapulp.structure import set_current_game_version

        char = self._build()
        set_current_game_version('dofus3')
        vus = 0
        for cast in _best_combo(char, get_solution(char), 'dofus3')['casts']:
            vus += 1
            if not cast['damage']:
                self.assertTrue(cast['note'], cast['name'])
        self.assertGreater(vus, 0)
