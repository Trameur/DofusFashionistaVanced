# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""La page d'un build annonce son meilleur tour, et y mene.

Le nombre existait sur la page des sorts et, depuis la section 55, dans la
comparaison. Il manquait sur **la page la plus lue des trois**: celle ou l'on
arrive depuis la galerie, depuis un lien partage ou depuis `/random/`.

Il est a cote du score du build, qui pese des stats; celui-ci dit ce que le
stuff fait en un tour. Le nombre est un lien vers la page des sorts, la seule
ou le lecteur peut changer les hypotheses, et l'infobulle porte ces
hypotheses mot pour mot, les memes que les deux autres pages.

**Pourquoi pas dans la galerie.** C'etait la premiere idee, et la mesure l'a
ecartee: le filtre <<cacher les builds invalides>> construit la metadonnee de
TOUS les builds correspondants et non des 24 de la page. Mesure du 12
septembre 2026: 1980 builds partages, 37 ms le tour, **73 secondes sur un
cache froid**. Ici c'est un seul calcul par page affichee.

Un tour qui ne se calcule pas fait disparaitre la ligne et rien d'autre: le
texte a copier et le score sont construits avant, dans leur propre bloc.
"""

import re

from django.test import TestCase
from django.utils.translation import gettext, override

LANGUES = ('en', 'fr', 'es', 'pt', 'de')

#: Le minifieur trie les attributs: on trouve la ligne par sa classe.
LIGNE = re.compile(r'<tr[^>]*solution-best-turn-row[^>]*>(.*?)</tr>', re.S)
LIEN = re.compile(r'href="([^"]+)"')
TITRE = re.compile(r'title="([^"]*)"')


def _texte(html):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', html)).strip()


class _AvecUnBuild(TestCase):

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
            'char_class': 'Cra', 'level': '200'})
        char = Char.objects.order_by('-id').first()
        char.link_shared = True
        char.save()
        return char

    def _ligne(self, chemin, langue='en', client=None):
        page = (client or self.client).get(
            chemin, HTTP_ACCEPT_LANGUAGE=langue,
            follow=True).content.decode('utf-8')
        trouve = LIGNE.search(page)
        self.assertIsNotNone(trouve, 'ligne absente sur %s' % chemin)
        return trouve.group(1)


class TheOwnerSeesItTests(_AvecUnBuild):

    def test_the_row_carries_a_number(self):
        char = self._build()
        ligne = self._ligne('/solution/%d/' % char.id)
        texte = _texte(ligne)
        self.assertIn(gettext('Best turn'), texte)
        chiffres = re.findall(r'\d+', texte)
        self.assertTrue(chiffres, texte)
        self.assertGreater(int(chiffres[-1]), 0)

    def test_the_number_is_the_one_the_spells_page_shows(self):
        """Deux pages, un seul nombre: si elles divergent, l'une des deux
        ment."""
        from chardata.solution import get_solution
        from chardata.spells_view import _best_combo
        from fashionistapulp.structure import set_current_game_version
        char = self._build()
        set_current_game_version('dofus3')
        attendu = _best_combo(char, get_solution(char), 'dofus3')['total']
        ligne = self._ligne('/solution/%d/' % char.id)
        self.assertIn(str(attendu), _texte(ligne))

    def test_it_leads_to_the_spells_page(self):
        char = self._build()
        ligne = self._ligne('/solution/%d/' % char.id)
        lien = LIEN.search(ligne)
        self.assertIsNotNone(lien, 'le nombre ne mene nulle part')
        self.assertEqual(200, self.client.get(lien.group(1),
                                              follow=True).status_code)


class TheVisitorSeesItTooTests(_AvecUnBuild):

    def _adresse_partagee(self, char):
        from chardata.encoded_char_id import encode_char_id
        return '/s/%s/%s/' % (char.char_name or 'shared',
                              encode_char_id(char.id))

    def test_the_shared_page_carries_it(self):
        from django.test import Client
        char = self._build()
        ligne = self._ligne(self._adresse_partagee(char), client=Client())
        self.assertIn(gettext('Best turn'), _texte(ligne))

    def test_the_visitor_link_points_at_the_public_spells_page(self):
        """Un visiteur ne peut pas ouvrir `/spells/<id>/`: ce chemin est celui
        de l'auteur, et le lui offrir serait la porte fermee de la section
        51."""
        from django.test import Client
        visiteur = Client()
        char = self._build()
        ligne = self._ligne(self._adresse_partagee(char), client=visiteur)
        lien = LIEN.search(ligne)
        self.assertIsNotNone(lien)
        self.assertIn('/spells_linked/', lien.group(1))
        self.assertEqual(200, visiteur.get(lien.group(1),
                                           follow=True).status_code)


class ItSaysWhatItAssumedTests(_AvecUnBuild):

    def test_the_tooltip_repeats_the_other_pages_word_for_word(self):
        char = self._build()
        ligne = self._ligne('/solution/%d/' % char.id)
        titre = TITRE.search(ligne)
        self.assertIsNotNone(titre, 'aucune hypothese annoncee')
        for phrase in ('One turn on a single target: average damage, self '
                       'buffs and critical hit rate included.',
                       'Spells at the highest level the character reaches.'):
            self.assertIn(gettext(phrase), titre.group(1))

    def test_the_label_answers_in_five_languages(self):
        char = self._build()
        vus = {}
        for langue in LANGUES:
            with self.subTest(langue=langue):
                with override(langue):
                    attendu = gettext('Best turn')
                vus[langue] = attendu
                self.assertIn(attendu,
                              _texte(self._ligne('/solution/%d/' % char.id,
                                                 langue)))
        for langue, mot in vus.items():
            if langue != 'en':
                self.assertNotEqual(vus['en'], mot, langue)
