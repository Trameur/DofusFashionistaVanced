# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""La fiche d'un objet mene au solveur, l'objet verrouille dans le build.

Mesure du 11 septembre 2026: les fiches d'encyclopedie sont les pages les
plus visitees du site (section 16: 49 % des vues en temps reel), et aucune
ne menait vers le solveur, seulement vers l'accueil, l'encyclopedie, les
autres versions et les builds qui portent l'objet. Un lecteur qui trouvait
son objet devait repartir de zero. La fiche envoie maintenant son objet au
demarrage rapide de la meme version, qui le verrouille dans son emplacement
et laisse le solveur remplir le reste.
"""

import re

from django.test import SimpleTestCase, TestCase

from chardata.coaching_view import DEFAULT_LEVELS, included_item_for
from chardata.encyclopedia_view import LOCALIZED_UI
from chardata.lock_forbid import get_inclusions_dict
from chardata.models import Char

PHRASE = ('This build will keep %(item)s (level %(level)s): the solver fills '
          'the other slots around it.')


def _objet(version, type_name='Hat', niveau_max=200):
    """Un objet porte, non retire, avec un identifiant Ankama (les
    representants de groupes <<ou>> n'en ont pas et n'ont pas de fiche)."""
    from fashionistapulp.structure import get_structure
    structure = get_structure(version)
    for item in structure.get_items_list():
        if (structure.get_type_name_by_id(item.type) == type_name
                and not getattr(item, 'removed', False)
                and getattr(item, 'ankama_id', None)
                and item.level <= niveau_max):
            return structure, item
    raise AssertionError('no %s to test with on %s' % (type_name, version))


def _fiche(client, version, structure, item):
    from chardata.official_site import get_item_link
    lien = get_item_link(item.ankama_type, item.ankama_id,
                         structure.get_item_name_in_language(item, 'en'),
                         game_version=version)
    lien = re.sub(r'^https?://[^/]+', '', lien)
    reponse = client.get(lien, HTTP_ACCEPT_LANGUAGE='en', follow=True)
    assert reponse.status_code == 200, (lien, reponse.status_code)
    return reponse.content.decode('utf-8')


def _ancre(page):
    debut = page.find('encyclopedia-build-around')
    assert debut != -1, 'no build-around link on the fiche'
    return page[page.rfind('<a', 0, debut):page.find('</a>', debut)]


class TheFicheLinksToTheQuickStartTests(TestCase):

    def test_the_link_carries_the_item_to_the_same_version(self):
        structure, item = _objet('dofus3')
        ancre = _ancre(_fiche(self.client, 'dofus3', structure, item))
        self.assertIn('href="/quickstart/?item=%d"' % item.id, ancre)
        self.assertIn(LOCALIZED_UI['en']['build_around_label'], ancre)

    def test_a_touch_fiche_keeps_the_reader_on_touch(self):
        structure, item = _objet('touch')
        ancre = _ancre(_fiche(self.client, 'touch', structure, item))
        self.assertIn('href="/touch/quickstart/?item=%d"' % item.id, ancre)

    def test_the_label_exists_in_five_languages(self):
        phrases = {LOCALIZED_UI[l]['build_around_label']
                   for l in ('en', 'fr', 'es', 'pt', 'de')}
        self.assertEqual(5, len(phrases))


class TheQuickStartKeepsTheItemTests(TestCase):

    def test_the_form_names_the_item_and_starts_the_levels_at_its_own(self):
        structure, item = _objet('dofus3', niveau_max=200)
        page = self.client.get('/quickstart/', {'item': item.id},
                               HTTP_ACCEPT_LANGUAGE='en').content.decode('utf-8')
        self.assertIn('coaching-included-item', page)
        self.assertIn(structure.get_item_name_in_language(item, 'en'), page)
        self.assertRegex(page, r'<input[^>]*name="?item"?[^>]*value="?%d"?'
                         % item.id)
        niveaux = [int(v) for v in re.findall(
            r'<option[^>]*value="?(\d+)"?[^>]*>\d+</option>', page)]
        self.assertTrue(niveaux, 'no level options')
        self.assertTrue(all(lvl >= item.level for lvl in niveaux), niveaux)
        self.assertIn(200, niveaux)

    def test_an_item_above_the_highest_default_level_brings_its_own(self):
        """Aucune version ne porte aujourd'hui d'objet au-dessus de 200 (le
        plafond des objets, pas celui des personnages): la branche est
        verifiee sur le calcul, et la mesure qui la rend inatteignable est
        affirmee plutot que sautee, pour qu'une donnee qui change la rende
        rouge et non silencieuse."""
        from fashionistapulp.game_versions import dofus_versions
        from fashionistapulp.structure import get_structure
        plus_haut = 0
        for version in dofus_versions():
            for item in get_structure(version).get_items_list():
                if not getattr(item, 'removed', False):
                    plus_haut = max(plus_haut, item.level)
        self.assertLessEqual(plus_haut, max(DEFAULT_LEVELS))
        # Le calcul que suivrait un tel objet, par la fonction de la vue.
        from chardata.coaching_view import level_options_for
        self.assertEqual(([230], 230), level_options_for(230))
        self.assertEqual(([50, 100, 150, 180, 200], 200), level_options_for(50))
        # L'objet apporte toujours son propre niveau, le plus bas qui le
        # porte, puis les defauts au-dessus.
        self.assertEqual(([160, 180, 200], 200), level_options_for(160))
        self.assertEqual((DEFAULT_LEVELS, 200), level_options_for(None))

    def test_a_bogus_item_changes_nothing(self):
        for valeur in ('abc', '999999999', ''):
            page = self.client.get('/quickstart/', {'item': valeur},
                                   HTTP_ACCEPT_LANGUAGE='en').content.decode('utf-8')
            self.assertNotIn('coaching-included-item', page, valeur)
            niveaux = [int(v) for v in re.findall(
                r'<option[^>]*value="?(\d+)"?[^>]*>\d+</option>', page)]
            self.assertEqual(DEFAULT_LEVELS, niveaux, valeur)

    def test_submitting_locks_the_item_in_its_slot(self):
        structure, item = _objet('dofus3', type_name='Ring')
        reponse = self.client.post('/quickstart/', {
            'char_class': 'Cra', 'char_level': '200',
            'play_style': 'solo_pvm', 'item': str(item.id)})
        self.assertEqual(302, reponse.status_code)
        char = Char.objects.order_by('-id').first()
        self.assertEqual({'ring1': item.id}, get_inclusions_dict(char))
        self.assertEqual('dofus3', char.game_version)
        self.assertEqual(200, char.level)

    def test_an_item_above_the_chosen_level_is_not_locked(self):
        from fashionistapulp.structure import get_structure
        structure = get_structure('dofus3')
        haut = next(i for i in structure.get_items_list()
                    if i.level > 150 and not getattr(i, 'removed', False)
                    and structure.get_type_name_by_id(i.type) == 'Hat')
        self.client.post('/quickstart/', {
            'char_class': 'Cra', 'char_level': '150',
            'play_style': 'solo_pvm', 'item': str(haut.id)})
        char = Char.objects.order_by('-id').first()
        self.assertEqual({}, get_inclusions_dict(char))

    def test_a_default_hidden_item_asked_for_is_unhidden(self):
        """create_build seme les exclusions par defaut; un objet que le
        lecteur demande gagne sur un defaut qui le cacherait."""
        from chardata.lock_forbid import get_default_exclusions
        from fashionistapulp.structure import get_structure
        structure = get_structure('dofus3')
        char_temoin = Char(char_class='Cra', level=200, game_version='dofus3')
        defauts = set(get_default_exclusions(char_temoin))
        cache = next((i for i in structure.get_items_list()
                      if i.id in defauts and not getattr(i, 'removed', False)
                      and i.level <= 200
                      and structure.get_type_name_by_id(i.type) in
                      ('Hat', 'Cloak', 'Belt', 'Boots', 'Amulet')), None)
        if cache is None:
            self.skipTest('no default-hidden item to ask for')
        self.client.post('/quickstart/', {
            'char_class': 'Cra', 'char_level': '200',
            'play_style': 'solo_pvm', 'item': str(cache.id)})
        char = Char.objects.order_by('-id').first()
        self.assertIn(cache.id, get_inclusions_dict(char).values())
        # Lu par le chemin garde du depot (read_char_blob), pas a nu: une
        # colonne illisible doit etre un echec de test, pas une exception.
        from chardata.lock_forbid import read_char_blob
        exclusions = read_char_blob(char.exclusions, None, 'exclusions', char)
        self.assertIsNotNone(exclusions, 'the exclusions column is unreadable')
        self.assertNotIn(cache.id, exclusions)


class TheHelperRefusesWhatIsNotAnItemOfThisVersionTests(SimpleTestCase):

    def test_none_for_junk_and_for_the_wrong_version(self):
        self.assertIsNone(included_item_for('dofus3', None))
        self.assertIsNone(included_item_for('dofus3', 'x'))
        self.assertIsNone(included_item_for('dofus3', -1))
        structure, item = _objet('dofus3')
        trouve = included_item_for('dofus3', str(item.id), language='fr')
        self.assertEqual(item.id, trouve['id'])
        self.assertEqual('hat', trouve['slot'])
        self.assertEqual(structure.get_item_name_in_language(item, 'fr'),
                         trouve['name'])

    def test_a_ring_goes_to_the_first_ring_slot(self):
        structure, item = _objet('dofus3', type_name='Ring')
        self.assertEqual('ring1', included_item_for('dofus3', item.id)['slot'])


class TheSentenceIsInEveryCatalogueTests(SimpleTestCase):

    def test_four_native_translations(self):
        import gettext
        import os
        from django.conf import settings
        vues = set()
        for langue in ('fr', 'es', 'pt', 'de'):
            phrase = gettext.translation(
                'django', os.path.join(settings.BASE_DIR, 'locale'),
                languages=[langue]).gettext(PHRASE)
            self.assertNotEqual(PHRASE, phrase, langue)
            self.assertIn('%(item)s', phrase, langue)
            self.assertIn('%(level)s', phrase, langue)
            vues.add(phrase)
        self.assertEqual(4, len(vues))
