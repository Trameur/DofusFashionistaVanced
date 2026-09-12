# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""La page des sorts n'offre plus un rang que le niveau refuse.

La page pose un rond cliquable par rang de sort. Elle les posait **tous**,
sans regarder le niveau du personnage. Cliquer le dernier rond d'un sort qu'on
n'a pas monte changeait la table des degats, alors que le serveur bornait le
rang du panneau: les deux se contredisaient et c'etait la table qui montrait
des degats hors de portee.

**Mesure du 12 septembre 2026**, tous les sorts de toutes les classes, part
des rangs offerts que le niveau ne permet pas:

| niveau | dofus3 | beta  | dofus2 | touch | retro |
|--------|-------:|------:|-------:|------:|------:|
| 1      | 93,6 % | 93,6 %| 93,4 % | 83,1 %| 86,6 %|
| 50     | 83,9 % | 83,9 %| 83,9 % | 60,2 %| 41,0 %|
| 100    | 62,2 % | 62,2 %| 61,6 % | 23,4 %| 16,7 %|
| 200    |    0 % |   0 % |    0 % |   0 % |   0 % |

**49620 rangs offerts sur dix niveaux, 21099 hors de portee, soit 42,5 %.** Le
zero a 200 explique que personne ne l'ait vu: les builds de test et la plupart
des builds partages sont au niveau maximum.

Demonstration avant le correctif, sur un Cra Retro de **niveau 20**: cliquer le
sixieme rang de Fleche Empoisonnee, que le jeu ouvre au niveau 101, faisait
passer la table de **187-203 a 235-252** pendant que le panneau restait a
10949.

C'est le **serveur** qui decide desormais, et la page ne le recalcule plus. Elle
en portait une copie en JavaScript, `decideLevel`, qui refaisait
`_decide_spell_level`: deux copies d'une meme regle finissent par s'ecarter, et
celle-la avait deja une troisieme soeur sur la page de comparaison.
"""

import os
import re

from django.test import SimpleTestCase, TestCase
from django.utils.translation import gettext, override

LANGUES = ('en', 'fr', 'es', 'pt', 'de')

ETIQUETTE = re.compile(r'data-out-of-reach="([^"]*)"')

GABARIT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       'templates', 'chardata', 'spells.html')


class TheServerDecidesTests(SimpleTestCase):

    def test_it_says_the_highest_rank_the_level_reaches(self):
        from chardata.spells_view import _reach
        cas = (
            # (niveaux du jeu, niveau du personnage, dispo, rang le plus haut)
            ([1, 1, 1, 1, 1, 101], 20, True, 4),
            ([1, 1, 1, 1, 1, 101], 150, True, 5),
            ([70, 70, 70, 70, 70, 170], 20, False, 0),
            ([70, 70, 70, 70, 70, 170], 100, True, 4),
            ([1, 66, 132], 1, True, 0),
            ([1, 66, 132], 70, True, 1),
            ([1, 66, 132], 200, True, 2),
            ([200], 199, False, 0),
        )
        for niveaux, niveau, dispo, rang in cas:
            with self.subTest(niveaux=niveaux, niveau=niveau):
                self.assertEqual({'available': dispo, 'highest_level': rang},
                                 _reach(niveaux, niveau))

    def test_a_caller_with_no_level_gets_every_rank(self):
        """La page de comparaison decide par colonne, chaque build ayant son
        propre niveau: elle ne passe pas de niveau et garde tous les rangs."""
        from chardata.spells_view import _reach
        self.assertEqual({'available': True, 'highest_level': 2},
                         _reach([1, 66, 132], None))

    def test_it_never_disagrees_with_the_rank_the_panel_uses(self):
        """Le panneau borne le rang demande avec `_decide_spell_level`. Si les
        deux divergeaient, la table et le panneau se contrediraient a nouveau,
        ce qui est exactement le defaut corrige ici."""
        from chardata.spell_buffs import (_decide_spell_level,
                                          get_damage_spells_for_version)
        from chardata.spells_view import _reach
        from chardata.version_compat import filter_classes_for_version
        from fashionistapulp.dofus_constants import CHARACTER_CLASSES
        from fashionistapulp.game_versions import version_keys

        vus = 0
        for version in version_keys():
            par_classe = get_damage_spells_for_version(version)
            for classe in filter_classes_for_version(CHARACTER_CLASSES,
                                                     version):
                for spell in par_classe.get(classe, []):
                    req = list(spell.level_req or [])
                    if not req:
                        continue
                    for niveau in (1, 20, 50, 100, 150, 200):
                        atteint = _reach(req, niveau)
                        vus += 1
                        if not atteint['available']:
                            self.assertLess(niveau, req[0])
                            continue
                        self.assertEqual(_decide_spell_level(req, niveau),
                                         atteint['highest_level'])
        self.assertGreater(vus, 5000, 'trop peu de cas mesures')


class TheRuleLivesInOnePlaceTests(SimpleTestCase):

    def test_the_page_no_longer_carries_its_own_copy_of_the_rank_rule(self):
        """`decideLevel` refaisait `_decide_spell_level` en JavaScript. La
        boucle qui comparait les niveaux deux a deux a disparu; ce qui reste
        lit la reponse du serveur."""
        with open(GABARIT, encoding='utf-8') as fichier:
            source = fichier.read()
        self.assertNotIn('char_level }} < spell.level[0] || numLevels',
                         source.replace('{{char_level}}', 'char_level }}'))
        self.assertIn('spell.highest_level', source)
        self.assertIn('isOutOfReach', source)


class TheDigestCarriesItTests(TestCase):

    def setUp(self):
        from django.contrib.auth.models import User
        self.auteur = User.objects.create_user('auteur', 'a@x.test', 'pw')
        self.client.force_login(self.auteur)

    def _build(self, niveau, char_class='Cra'):
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
            'char_class': char_class, 'level': str(niveau)})
        char = Char.objects.order_by('-id').first()
        if char.level != niveau:
            char.level = niveau
            char.save()
        return char

    def _digests(self, char):
        import json
        page = self.client.get('/spells/%d/' % char.id,
                               follow=True).content.decode('utf-8')
        brut = re.search(r'var\s+spellDigests\s*=\s*(\[.*?\])\s*;', page, re.S)
        self.assertIsNotNone(brut, 'la page ne porte pas ses sorts')
        return json.loads(brut.group(1))

    def test_every_spell_says_how_far_the_level_goes(self):
        char = self._build(200)
        sorts = [d for d in self._digests(char) if d.get('type') == 'spell']
        self.assertGreater(len(sorts), 5)
        for digest in sorts:
            with self.subTest(sort=digest['name']):
                self.assertIn('highest_level', digest)
                self.assertIn('available', digest)
                self.assertLess(digest['highest_level'],
                                len(digest['level']))

    def test_a_low_level_build_is_offered_fewer_ranks(self):
        """Mesure du 12 septembre 2026: 93,6 % des rangs sont hors de portee
        au niveau 1 en Dofus 3, et 0 % au niveau 200. Sans cet ecart le
        correctif ne changerait rien."""
        def hors_de_portee(niveau):
            sorts = [d for d in self._digests(self._build(niveau))
                     if d.get('type') == 'spell' and d.get('level')]
            offerts = sum(len(d['level']) for d in sorts)
            atteints = sum(0 if not d['available']
                           else d['highest_level'] + 1 for d in sorts)
            return offerts - atteints, offerts

        bas, offerts_bas = hors_de_portee(1)
        haut, offerts_haut = hors_de_portee(200)
        self.assertEqual(0, haut, 'un niveau 200 atteint tout')
        self.assertGreater(bas, offerts_bas * 0.5,
                           'plus de la moitie des rangs sont hors de portee '
                           'au niveau 1')

    def test_a_spell_the_character_does_not_have_is_marked_unavailable(self):
        char = self._build(1)
        sorts = [d for d in self._digests(char)
                 if d.get('type') == 'spell' and d.get('level')]
        indisponibles = [d for d in sorts if not d['available']]
        self.assertTrue(indisponibles, 'aucun sort hors de portee au niveau 1')
        for digest in indisponibles:
            with self.subTest(sort=digest['name']):
                self.assertLess(1, digest['level'][0])
                self.assertEqual(0, digest['highest_level'])


class TheLabelSaysWhichLevelTests(TestCase):

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
        item = next(i for i in structure.types[200]['Hat']
                    if not i.removed and i.ankama_id)
        self.client.post('/import/text/', {
            'text': structure.get_item_name_in_language(item, 'en'),
            'confirm': '1', 'char_class': 'Cra', 'level': '50'})
        return Char.objects.order_by('-id').first()

    def test_the_five_languages_say_which_level_the_rank_needs(self):
        """L'etiquette ne passe par aucun texte de page: elle voyage dans un
        attribut que le JavaScript remplit, donc oubliee elle sortirait en
        anglais partout."""
        char = self._build()
        vus = {}
        for langue in LANGUES:
            with self.subTest(langue=langue):
                page = self.client.get(
                    '/spells/%d/' % char.id, HTTP_ACCEPT_LANGUAGE=langue,
                    follow=True).content.decode('utf-8')
                trouve = ETIQUETTE.search(page)
                self.assertIsNotNone(trouve, 'etiquette absente')
                with override(langue):
                    attendu = gettext('Needs level %(level)s') % {
                        'level': '__level__'}
                self.assertEqual(attendu, trouve.group(1))
                vus[langue] = trouve.group(1)
        for langue, texte in vus.items():
            if langue != 'en':
                self.assertNotEqual(vus['en'], texte, langue)

    def test_the_label_keeps_a_place_for_the_number(self):
        """Sans la marque, l'infobulle dirait <<Demande le niveau>> sans
        niveau."""
        char = self._build()
        page = self.client.get('/spells/%d/' % char.id,
                               follow=True).content.decode('utf-8')
        self.assertIn('__level__', ETIQUETTE.search(page).group(1))
