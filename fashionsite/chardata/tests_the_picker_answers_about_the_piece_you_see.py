# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""La fenetre de changement d'objet repond sur la piece qu'on regarde.

Trouve en exercant la fenetre sur un build Touch. Elle renvoie trois cartes
au navigateur, les conditions, l'ecart de caracteristiques et le profil
d'arme, et **elles etaient indexees par le nom de l'objet**. Ankama donne le
meme nom a deux pieces differentes, donc la seconde ecrasait la premiere et
le lecteur lisait les chiffres d'un autre objet sous celui qu'il regardait.

Mesure du 13 septembre 2026, en ne comptant que les homonymes du **meme
type**, les seuls qui se rencontrent dans une fenetre:

| version | noms partages | valeurs distinctes | conditions distinctes |
|---------|---------------|--------------------|-----------------------|
| dofus3  | 0             | 0                  | 0                     |
| beta    | 0             | 0                  | 0                     |
| dofus2  | 0             | 0                  | 0                     |
| touch   | 17            | 14                 | 0                     |
| retro   | 40            | 1                  | 0                     |

Les conditions pour equiper, elles, coincident partout: c'est l'ecart de
caracteristiques que le lecteur lisait faux.

Preuve au niveau du lecteur: deux capes Touch s'appellent <<Caracape>>, l'une
de niveau 60 et l'autre de niveau 150. Avant, les deux lignes affichaient
<<-370 PV>>. Apres, la premiere dit <<-150 PV>> et la seconde <<-370 PV>>.

**Le second defaut, sur la meme surface.** La liste est mise en cache cinq
minutes, et sa cle ne portait pas la langue alors que la recherche filtre sur
le nom **traduit**. Une recherche <<Caracape>> trouve les deux capes en
anglais et une seule en francais, ou l'autre s'appelle <<Caparak>>: le
premier lecteur servi donnait sa liste au suivant, dans l'orthographe de sa
propre langue. Verifie a l'ecran dans les deux sens.
"""

import collections
import json

from django.core.cache import cache
from django.test import TestCase, SimpleTestCase
from django.utils import translation

from chardata.models import Char
from chardata.util import get_picker_cache_key
from fashionistapulp.structure import get_structure, set_current_game_version

#: (noms partages, dont les valeurs different, dont les conditions different)
#: dans le catalogue lui-meme, sans porteur. Un plancher: sans homonymes, les
#: tests ci-dessous ne prouveraient rien.
_HOMONYMES = {'dofus3': (0, 0, 0), 'beta': (0, 0, 0), 'dofus2': (0, 0, 0),
              'touch': (17, 14, 0), 'retro': (40, 1, 0)}

#: Les deux capes Touch qui portent le meme nom anglais.
_CARACAPE = (2532, 19624)



class TwoPiecesShareANameTests(SimpleTestCase):
    """Le plancher, et la raison d'etre du lot. Mesure sur le catalogue seul,
    donc independante de tout build."""

    def tearDown(self):
        set_current_game_version('dofus3')

    @staticmethod
    def _valeurs(objet):
        return (tuple(sorted(objet.stats or ())),
                tuple(sorted((cle, repr(valeur)) for cle, valeur
                             in (objet.stat_ranges or {}).items())))

    @staticmethod
    def _conditions(objet):
        return (tuple(sorted(objet.min_stats_to_equip or ())),
                tuple(sorted(objet.max_stats_to_equip or ())))

    def _lots(self, version):
        set_current_game_version(version)
        structure = get_structure(version)
        par_nom = collections.defaultdict(list)
        for objet in structure.get_available_items_list():
            par_nom[(objet.name, objet.type)].append(objet)
        return [lot for lot in par_nom.values() if len(lot) > 1]

    def test_each_version_shares_the_names_it_shares(self):
        for version, (noms, valeurs, conditions) in _HOMONYMES.items():
            with self.subTest(version=version):
                lots = self._lots(version)
                self.assertEqual(noms, len(lots))
                self.assertEqual(
                    valeurs,
                    sum(1 for lot in lots
                        if len({self._valeurs(objet) for objet in lot}) > 1))
                self.assertEqual(
                    conditions,
                    sum(1 for lot in lots
                        if len({self._conditions(objet)
                                for objet in lot}) > 1))

    def test_the_two_touch_cloaks_really_differ(self):
        """Sans cela, le test de la fenetre passerait sur deux pieces
        identiques et ne prouverait rien."""
        set_current_game_version('touch')
        structure = get_structure('touch')
        pieces = [structure.get_item_by_id(numero) for numero in _CARACAPE]
        self.assertEqual({'Caracape'}, {piece.name for piece in pieces})
        self.assertEqual(2, len({piece.level for piece in pieces}))
        self.assertEqual(2, len({self._valeurs(piece) for piece in pieces}))


class ThePickerAnswersByPieceTests(TestCase):
    """La fenetre est interrogee pour de vrai, comme la page le fait."""

    def setUp(self):
        self.client.post('/touch/createproject/', {
            'project': 'p', 'charname': 'P', 'level': '200',
            'class': 'Iop', 'where_to_go': 'wizard'})
        self.char = Char.objects.order_by('-id').first()
        # The build has to wear a cloak: the difference the window shows is
        # the one between the offered piece and the one already in the slot.
        self.assertEqual(200, self.client.get('/touch/solution/%d/'
                                              % self.char.id,
                                              follow=True).status_code)
        self.porte = self._cloak_worn()

    def _cloak_worn(self):
        from chardata.solution import get_solution
        self.char.refresh_from_db()
        resultat = get_solution(self.char)
        self.assertIsNotNone(resultat, 'the build has no solution')
        for item in resultat.item_list:
            if item.slot == 'cloak' and item.item_added:
                return item.name
        return ''

    def tearDown(self):
        set_current_game_version('dofus3')

    def _fenetre(self, terme, langue='en', slot='cloak', vider=True):
        if vider:
            cache.clear()
        with translation.override(langue):
            reponse = self.client.post(
                '/touch/itemexchange/%d/' % self.char.id,
                {'slot': slot, 'equip': self.porte, 'page': '1',
                 'search_term': terme, 'order_by_stat': 'false',
                 'stat_filters_json': '[]'},
                HTTP_ACCEPT_LANGUAGE=langue)
        self.assertEqual(200, reponse.status_code)
        return json.loads(reponse.content.decode('utf-8'))

    def test_every_map_is_keyed_by_the_pieces_number(self):
        donnees = self._fenetre('Caracape')
        numeros = {str(item['id']) for item in donnees['items']}
        self.assertTrue(numeros)
        for carte in ('violations', 'differences'):
            with self.subTest(carte=carte):
                self.assertEqual(numeros, set(donnees[carte] or {}))

    def test_two_cloaks_of_the_same_name_get_two_answers(self):
        """Le test qui aurait attrape le defaut."""
        donnees = self._fenetre('Caracape')
        rendus = [item for item in donnees['items']
                  if item['name'] == 'Caracape']
        self.assertEqual(2, len(rendus),
                         'the pair was not offered, this proves nothing')
        lignes = {_texte_json(donnees['differences'][str(item['id'])])
                  for item in rendus}
        self.assertEqual(2, len(lignes), lignes)

    def test_a_search_made_in_one_language_does_not_answer_another(self):
        """La liste est filtree sur le nom traduit et gardee cinq minutes.
        <<Caracape>> trouve les deux capes en anglais et une seule en
        francais, ou l'autre s'appelle <<Caparak>>: sans la langue dans la
        cle, le premier lecteur servi donnait sa liste au suivant."""
        anglais = self._fenetre('Caracape', 'en')
        self.assertEqual(2, len([item for item in anglais['items']
                                 if item['name'] == 'Caracape']),
                         'English no longer finds both, this proves nothing')
        francais = self._fenetre('Caracape', 'fr', vider=False)
        self.assertEqual([2532], [item['id'] for item in francais['items']
                                  if item['name'] == 'Caracape'])


def _texte_json(lignes):
    return ' / '.join(ligne['text'] for ligne in lignes or ())


class TheCachedListKnowsItsLanguageTests(SimpleTestCase):
    """La recherche filtre sur le nom traduit, donc la liste mise en cache
    appartient a une langue."""

    def test_the_key_changes_with_the_language(self):
        cles = set()
        for langue in ('en', 'fr', 'es', 'pt', 'de'):
            with translation.override(langue):
                cles.add(get_picker_cache_key(7, 4, 'Caracape', 'false', '[]'))
        self.assertEqual(5, len(cles))

    def test_the_key_still_changes_with_everything_it_changed_with(self):
        """Le plancher: ajouter la langue ne doit rien avoir efface."""
        with translation.override('en'):
            base = get_picker_cache_key(7, 4, 'Caracape', 'false', '[]')
            autres = {
                'projet': get_picker_cache_key(8, 4, 'Caracape', 'false',
                                               '[]'),
                'type': get_picker_cache_key(7, 5, 'Caracape', 'false', '[]'),
                'recherche': get_picker_cache_key(7, 4, 'Caparak', 'false',
                                                  '[]'),
                'ordre': get_picker_cache_key(7, 4, 'Caracape', 'true', '[]'),
                'filtres': get_picker_cache_key(7, 4, 'Caracape', 'false',
                                                '[{"stat": 1}]'),
            }
        for quoi, cle in autres.items():
            with self.subTest(quoi=quoi):
                self.assertNotEqual(base, cle)
