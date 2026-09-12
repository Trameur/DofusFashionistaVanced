# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Le panneau nomme les deux stats qu'il ne compte pas.

`calculate_damage` multiplie par le % degats de sort et par le % degats
d'arme, et **jamais** par le % degats de melee ni par le % degats a distance.
Le site les affiche pourtant dans le resume du build, laisse leur donner un
poids sur la page des caracteristiques, les optimise (`smart_build` leur donne
un poids selon une probabilite d'attaque de melee interpolee de 0,1 pour un
Cra a 0,7 pour un Sacrieur) et les compte 35 dans le score public.

**Pourquoi on ne les applique pas, et pourquoi ce test defend cette omission.**
La reference de sorts porte la portee de chaque rang. Mesure du 12 septembre
2026: sur Dofus 3, **86,0 % des sorts ont une fenetre de portee allant de 1 a
N**, donc c'est le lanceur qui decide s'il frappe au contact ou a distance.
Seuls 4,9 % sont a distance seulement et 9,2 % au contact seulement. Meme sur
Retro, la version la plus tranchee, 63,2 % restent au choix. Appliquer l'une
des deux stats demanderait donc d'inventer la portee de 86 % des lancers, ce
qui serait faux plus souvent que de les taire.

**Ce que l'omission coute, mesure.** Sur les builds de la base locale, 6 sur
63, soit 9,5 %, portent du % degats a distance, et il y vaut **-12** (deux
objets a -6 chacun). Le panneau **surestimait** donc leurs degats, et rien ne
le disait.

La phrase reprend les libelles que le resume du build affiche, dans la langue
du lecteur, pour qu'il relie la phrase a la ligne qu'il voit. Elle n'apparait
que quand le build porte une des deux stats: neuf builds sur dix ne sont pas
concernes et n'ont pas besoin du bruit.
"""

import json
import re

from django.test import TestCase
from django.utils.translation import gettext, override

LANGUES = ('en', 'fr', 'es', 'pt', 'de')

NOTE = re.compile(r'<span[^>]*best-combo-melee-note[^>]*>(.*?)</span>', re.S)
LIGNE_BUILD = re.compile(r'<tr[^>]*solution-best-turn-row[^>]*>(.*?)</tr>',
                         re.S)
NOTE_COMPARE = re.compile(r'<td[^>]*compare-best-turn-note[^>]*>(.*?)</td>',
                          re.S)
TITRE = re.compile(r'title="([^"]*)"')

PHRASE = ('%(melee)s and %(ranged)s are not counted here: on most casts the '
          'caster chooses the range.')


def _texte(html):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', html)).strip()


def _attendu(langue):
    with override(langue):
        return gettext(PHRASE) % {'melee': gettext('% Melee Damage'),
                                  'ranged': gettext('% Ranged Damage')}


class _AvecDesBuilds(TestCase):

    def setUp(self):
        from django.contrib.auth.models import User
        self.auteur = User.objects.create_user('auteur', 'a@x.test', 'pw')
        self.client.force_login(self.auteur)

    def _pieces_avec_la_stat(self):
        """Les pieces du catalogue qui portent une des deux stats, cherchees
        dans la donnee et non nommees ici: les objets changent de nom entre
        les versions et entre les mises a jour."""
        from fashionistapulp.structure import (get_structure,
                                               set_current_game_version)
        set_current_game_version('dofus3')
        structure = get_structure('dofus3')
        ids = {structure.stat_dict_key[cle].id
               for cle in ('permedam', 'perrandam')
               if cle in structure.stat_dict_key}
        self.assertTrue(ids, 'les deux stats sont absentes du catalogue')
        trouvees = []
        for type_name, items in structure.types[200].items():
            for item in items:
                if item.removed or not item.ankama_id:
                    continue
                if any(sid in ids and valeur
                       for sid, valeur in (item.stats or [])):
                    trouvees.append(
                        structure.get_item_name_in_language(item, 'en'))
        return trouvees

    def _build(self, noms):
        from chardata.models import Char
        self.client.post('/import/text/', {
            'text': '\n'.join(noms), 'confirm': '1',
            'char_class': 'Cra', 'level': '200'})
        char = Char.objects.order_by('-id').first()
        char.link_shared = True
        char.save()
        return char

    def _build_concerne(self):
        noms = self._pieces_avec_la_stat()
        self.assertTrue(noms, 'aucune piece ne porte ces stats en Dofus 3')
        return self._build(noms[:2]), noms[:2]

    def _build_ordinaire(self):
        from fashionistapulp.structure import (get_structure,
                                               set_current_game_version)
        set_current_game_version('dofus3')
        structure = get_structure('dofus3')
        ids = {structure.stat_dict_key[cle].id
               for cle in ('permedam', 'perrandam')
               if cle in structure.stat_dict_key}
        for item in structure.types[200]['Hat']:
            if item.removed or not item.ankama_id:
                continue
            if not any(sid in ids and valeur
                       for sid, valeur in (item.stats or [])):
                return self._build(
                    [structure.get_item_name_in_language(item, 'en')])
        self.fail('aucun chapeau sans ces stats')

    def _stats(self, char):
        from chardata.solution import get_solution
        from fashionistapulp.structure import set_current_game_version
        set_current_game_version(char.game_version)
        return dict(get_solution(char).get_stats_total())


class TheStatsAreReallyLeftOutTests(_AvecDesBuilds):

    def test_the_formula_applies_neither_of_them(self):
        """La condition du defaut. Si un jour la formule les applique, ce test
        tombe et fait relire le raisonnement: 86 % des sorts ont une portee au
        choix du lanceur, donc appliquer l'une des deux demanderait d'inventer
        la portee de la plupart des lancers."""
        import copy

        from fashionistapulp.dofus_constants import (BaseDamage,
                                                     calculate_damage)
        socle = {'agi': 0, 'str': 0, 'int': 0, 'cha': 0, 'pow': 0, 'dam': 0,
                 'cridam': 0, 'heals': 0, 'perspedam': 0, 'perweadam': 0,
                 'permedam': 0, 'perrandam': 0, 'earthdam': 0, 'firedam': 0,
                 'waterdam': 0, 'airdam': 0, 'neutdam': 0}
        ligne = BaseDamage(min_dam=100, max_dam=100, element='fire',
                           steals=False, heals=False)
        nu = calculate_damage([copy.copy(ligne)], dict(socle), False, True)
        for cle in ('permedam', 'perrandam'):
            with self.subTest(stat=cle):
                stats = dict(socle, **{cle: 50})
                avec = calculate_damage([copy.copy(ligne)], stats, False, True)
                self.assertEqual(int(nu[0].max_dam), int(avec[0].max_dam),
                                 '%s change le resultat' % cle)
        # Et pour montrer que le test sait distinguer: le % de sort, lui, agit.
        avec_sort = calculate_damage([copy.copy(ligne)],
                                     dict(socle, perspedam=50), False, True)
        self.assertGreater(int(avec_sort[0].max_dam), int(nu[0].max_dam))

    def test_most_spells_leave_the_range_to_the_caster(self):
        """La raison chiffree de ne pas les appliquer. Sans cette part, la
        decision serait une preference."""
        from chardata.spell_buffs import (_decide_spell_level,
                                          get_damage_spells_for_version)
        from chardata.spell_reference import reference_by_spell_id
        from chardata.version_compat import filter_classes_for_version
        from fashionistapulp.dofus_constants import CHARACTER_CLASSES
        from fashionistapulp.structure import set_current_game_version

        set_current_game_version('dofus3')
        par_classe = get_damage_spells_for_version('dofus3')
        au_choix = 0
        total = 0
        for classe in filter_classes_for_version(CHARACTER_CLASSES, 'dofus3'):
            reference = reference_by_spell_id('dofus3', classe)
            for spell in par_classe.get(classe, []):
                if not spell.get_effects_digest().non_crit_dams:
                    continue
                entree = reference.get(getattr(spell, 'spell_id', None))
                portees = (entree or {}).get('range')
                if not portees:
                    continue
                total += 1
                rang = min(_decide_spell_level(spell.level_req, 200),
                           len(portees) - 1)
                fenetre = portees[rang]
                if (isinstance(fenetre, (list, tuple)) and len(fenetre) == 2
                        and fenetre[0] <= 1 < fenetre[1] + 1
                        and fenetre[1] > 1):
                    au_choix += 1
        self.assertGreater(total, 300, 'trop peu de sorts avec une portee')
        part = 100.0 * au_choix / total
        self.assertGreater(part, 70.0,
                           'seulement %.1f %% des sorts laissent la portee au '
                           'choix du lanceur' % part)


class TheNoteAppearsOnlyWhenItAppliesTests(_AvecDesBuilds):

    def test_a_build_carrying_the_stat_is_told(self):
        char, noms = self._build_concerne()
        stats = self._stats(char)
        self.assertTrue(stats.get('permedam') or stats.get('perrandam'),
                        'le build temoin ne porte pas la stat: %s' % noms)
        page = self.client.get('/spells/%d/' % char.id,
                               follow=True).content.decode('utf-8')
        trouve = NOTE.search(page)
        self.assertIsNotNone(trouve, 'le panneau ne dit rien')
        self.assertEqual(_attendu('en'), _texte(trouve.group(1)))

    def test_a_build_without_it_is_not_bothered(self):
        """Neuf builds sur dix ne sont pas concernes."""
        char = self._build_ordinaire()
        stats = self._stats(char)
        self.assertFalse(stats.get('permedam') or stats.get('perrandam'))
        page = self.client.get('/spells/%d/' % char.id,
                               follow=True).content.decode('utf-8')
        trouve = NOTE.search(page)
        self.assertEqual('', _texte(trouve.group(1)) if trouve else '')

    def test_the_ajax_answer_carries_it(self):
        """Le panneau se rafraichit sans recharger et doit porter la phrase
        par ce chemin aussi.

        Mesure du 13 septembre 2026: aucun sort des cinq versions n'accorde de
        % melee ni de % distance, donc aujourd'hui un buff coche ne peut pas
        la faire apparaitre. Elle voyage quand meme avec les deux autres pour
        que le panneau n'ait qu'un seul chemin de rafraichissement.
        """
        char, _noms = self._build_concerne()
        reponse = self.client.post('/best_combo/%d/' % char.id, {
            'buff_state': json.dumps({}), 'spell_levels': json.dumps({}),
            'pushback': 'false'})
        self.assertEqual(200, reponse.status_code)
        combo = json.loads(reponse.content.decode('utf-8'))['best_combo']
        self.assertEqual(_attendu('en'), combo['melee_note'])


class ItNamesTheStatsTheSummaryShowsTests(_AvecDesBuilds):

    def test_it_uses_the_labels_of_the_stat_lines(self):
        """Le lecteur doit relier la phrase a la ligne qu'il voit dans le
        resume du build, pas a un vocabulaire nouveau."""
        char, _noms = self._build_concerne()
        page = self.client.get('/spells/%d/' % char.id,
                               follow=True).content.decode('utf-8')
        texte = _texte(NOTE.search(page).group(1))
        self.assertIn(gettext('% Melee Damage'), texte)
        self.assertIn(gettext('% Ranged Damage'), texte)

    def test_the_five_languages_answer(self):
        char, _noms = self._build_concerne()
        vus = {}
        for langue in LANGUES:
            with self.subTest(langue=langue):
                page = self.client.get(
                    '/spells/%d/' % char.id, HTTP_ACCEPT_LANGUAGE=langue,
                    follow=True).content.decode('utf-8')
                trouve = NOTE.search(page)
                self.assertIsNotNone(trouve)
                self.assertEqual(_attendu(langue), _texte(trouve.group(1)))
                vus[langue] = _attendu(langue)
        for langue, phrase in vus.items():
            if langue != 'en':
                self.assertNotEqual(vus['en'], phrase, langue)


class TheThreePagesSayTheSameTests(_AvecDesBuilds):

    def test_the_build_page_and_the_comparison_repeat_it(self):
        """Trois pages qui annoncent le meme nombre doivent annoncer les memes
        hypotheses."""
        char, _noms = self._build_concerne()
        autre = self._build_ordinaire()
        attendu = _attendu('en')

        build = self.client.get('/solution/%d/' % char.id,
                                follow=True).content.decode('utf-8')
        ligne = LIGNE_BUILD.search(build)
        self.assertIsNotNone(ligne)
        titre = TITRE.search(ligne.group(1))
        self.assertIsNotNone(titre)
        self.assertIn(attendu, titre.group(1))

        compare = self.client.get(
            '/compare_sets/%d/%d/' % (char.id, autre.id),
            follow=True).content.decode('utf-8')
        note = NOTE_COMPARE.search(compare)
        self.assertIsNotNone(note)
        self.assertIn(attendu, _texte(note.group(1)))
