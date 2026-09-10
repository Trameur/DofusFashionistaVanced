# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Coller son stuff en texte et le retrouver ici.

Le lecteur de captures lit UN objet. Cette page lit un build, et sans rien
demander a personne d'autre: pas de lien a publier chez un concurrent, pas de
build public, pas d'image. Un build prive, un build recopie d'un Discord ou
d'un forum, un build qu'on a simplement sous les yeux dans le jeu.
"""

from django.test import SimpleTestCase, TestCase

from chardata.text_build_import import MAX_LIGNES, MAX_OBJETS, read_items
from fashionistapulp.structure import (get_structure, get_current_game_version,
                                       set_current_game_version)


def _noms(version, types, langue='en'):
    """Un vrai nom d'objet par type, pris dans le catalogue lui-meme."""
    structure = get_structure(version)
    trouve = []
    for type_name in types:
        for item in structure.types[200][type_name]:
            if item.removed:
                continue
            trouve.append(structure.get_item_name_in_language(item, langue))
            break
    return trouve


class PastedTextBecomesABuildTests(SimpleTestCase):

    def setUp(self):
        self.precedente = get_current_game_version()
        set_current_game_version('dofus3')
        self.addCleanup(set_current_game_version, self.precedente)

    def test_a_list_of_names_comes_back_as_those_items(self):
        noms = _noms('dofus3', ('Hat', 'Cloak', 'Belt', 'Boots'))
        self.assertEqual(4, len(noms), noms)
        lu = read_items('\n'.join(noms), 'dofus3', 'en')
        self.assertEqual([m['name'] for m in lu['matched']], noms)
        self.assertEqual([], lu['ignored'])
        self.assertEqual(4, len(lu['item_ids']))

    def test_the_order_of_the_text_is_the_order_of_the_build(self):
        noms = _noms('dofus3', ('Boots', 'Hat', 'Cloak'))
        lu = read_items('\n'.join(noms), 'dofus3', 'en')
        self.assertEqual([m['name'] for m in lu['matched']], noms)

    def test_a_whole_tooltip_can_be_pasted_and_the_stats_are_skipped(self):
        """Mesure du 10 septembre 2026: sur **7800 lignes** qui ne sont pas des
        noms d'objets (les etiquettes de stats des cinq langues, declinees en
        <<51 X>>, <<X 51>>, <<-12 X>>, plus les entetes d'infobulle usuelles),
        prises sur Dofus 3, Retro et Touch, le contrat retenu en reconnait
        **zero**. Le rappel sur 1800 vrais noms est de 98,8 %.
        """
        noms = _noms('dofus3', ('Hat', 'Cloak'))
        texte = '\n'.join([
            noms[0], '51 Vitality', '30 Strength', 'Level 200',
            noms[1], '-12 AP', 'Effects:', 'Conditions',
        ])
        lu = read_items(texte, 'dofus3', 'en')
        self.assertEqual([m['name'] for m in lu['matched']], noms)
        for parasite in ('51 Vitality', '30 Strength', 'Level 200', '-12 AP'):
            self.assertIn(parasite, lu['ignored'])

    def test_a_stat_word_never_drags_an_item_in_by_substring(self):
        """La faute que le contrat par egalite supprime.

        L'autocompletion accepte une sous-chaine, parce qu'elle repond a
        quelqu'un qui tape. Appliquee a une infobulle collee, la meme regle
        faisait entrer **269 objets sur 7800 lignes (3,4 %)**, et pas des
        objets exotiques: <<agility>> ramenait Agility Ring, <<chance>> Chance
        Belt, <<damage>> Damaged Farmer Scythe, <<weight>> Weighted Helmet. Le
        joueur se serait retrouve avec un anneau qu'il n'a jamais porte.

        Le rappel, lui, est le meme dans les deux contrats: 98,8 %. La
        sous-chaine ne rattrapait donc rien qu'on perde ici.
        """
        for mot in ('agility', 'chance', 'damage', 'weight', 'power',
                    'vitality'):
            with self.subTest(mot=mot):
                lu = read_items(mot, 'dofus3', 'en')
                self.assertEqual([], lu['item_ids'], lu['matched'])
                self.assertEqual([mot], lu['ignored'])

    def test_a_name_read_one_letter_wrong_still_lands_and_says_so(self):
        """Le rapprochement tolerant de G1 sert ici aussi, et la piece porte
        la mention: un build qui met en silence l'objet voisin est pire qu'un
        build qui dit avoir devine."""
        noms = _noms('dofus3', ('Hat',))
        original = noms[0]
        abime = original[:-1] + ('x' if original[-1] != 'x' else 'y')
        lu = read_items(abime, 'dofus3', 'en')
        self.assertEqual(1, len(lu['matched']), lu)
        self.assertEqual(original, lu['matched'][0]['name'])
        self.assertTrue(lu['matched'][0]['approximate'])

    def test_an_exact_name_is_never_flagged_as_a_guess(self):
        noms = _noms('dofus3', ('Hat',))
        lu = read_items(noms[0], 'dofus3', 'en')
        self.assertFalse(lu['matched'][0]['approximate'])

    def test_nothing_at_all_reads_as_nothing(self):
        for texte in ('', '   ', '\n\n\n'):
            with self.subTest(texte=repr(texte)):
                lu = read_items(texte, 'dofus3', 'en')
                self.assertEqual([], lu['item_ids'])
                self.assertEqual([], lu['ignored'])

    def test_a_pasted_clipboard_is_cut_and_says_it_was(self):
        lu = read_items('\n'.join(['x' * 12] * (MAX_LIGNES + 40)),
                        'dofus3', 'en')
        self.assertTrue(lu['truncated'])

    def test_the_catalogue_is_walked_once_per_paste(self):
        """Le vivier fait des milliers de noms et chaque ligne inconnue est
        comparee a chacun. Le reconstruire par ligne rendait la page
        inutilisable des la dixieme."""
        from chardata import text_build_import
        vrai = text_build_import._pool
        appels = []

        def compte(structure, language):
            appels.append(1)
            return vrai(structure, language)

        text_build_import._pool = compte
        self.addCleanup(setattr, text_build_import, '_pool', vrai)
        read_items('\n'.join(_noms('dofus3', ('Hat', 'Cloak', 'Belt'))),
                   'dofus3', 'en')
        self.assertEqual(1, len(appels))

    def test_it_reads_the_version_it_was_given(self):
        """Un nom Retro cherche dans le catalogue Dofus 3 habillerait le
        personnage avec autre chose. Le catalogue suit la version demandee,
        pas celle que le lecteur consultait."""
        noms = _noms('retro', ('Hat',))
        lu = read_items(noms[0], 'retro', 'en')
        self.assertEqual(1, len(lu['item_ids']), lu)
        self.assertEqual(noms[0], lu['matched'][0]['name'])

    def test_it_never_returns_more_items_than_a_build_can_wear(self):
        noms = _noms('dofus3', ('Ring',))
        lu = read_items('\n'.join('%s ' % noms[0] + ' ' * i
                                  for i in range(MAX_OBJETS + 10)),
                        'dofus3', 'en')
        self.assertLessEqual(len(lu['item_ids']), MAX_OBJETS)


class TheTextImportPageTests(TestCase):

    def _url(self, version='dofus3'):
        return ('/import/text/' if version == 'dofus3'
                else '/%s/import/text/' % version)

    def _texte(self, version='dofus3'):
        return '\n'.join(_noms(version, ('Hat', 'Cloak', 'Belt')))

    def test_the_page_offers_one_text_area(self):
        reponse = self.client.get(self._url())
        self.assertEqual(200, reponse.status_code)
        page = reponse.content.decode('utf-8')
        self.assertIn('name="text"', page)
        self.assertIn('Read this text', page)

    def test_the_route_answers_under_a_version_prefix_too(self):
        """Le site a deux tables d'URL. Une route posee dans une seule rend
        404 dans l'autre, et le lecteur qui joue a Retro est justement celui
        qui a un prefixe."""
        for version in ('dofus3', 'retro', 'touch', 'beta', 'dofus2'):
            with self.subTest(version=version):
                self.assertEqual(
                    200, self.client.get(self._url(version)).status_code)

    def test_reading_the_text_creates_nothing_yet(self):
        from chardata.models import Char
        avant = Char.objects.count()
        page = self.client.post(self._url(), {'text': self._texte()})
        self.assertContains(page, 'Bring this build in')
        self.assertEqual(avant, Char.objects.count())

    def test_the_class_and_the_level_are_asked_for(self):
        """Une infobulle porte le niveau de l'OBJET, jamais celui du
        personnage, et rien dans une liste de noms ne nomme une classe."""
        page = self.client.post(self._url(), {'text': self._texte()})
        self.assertContains(page, 'name="char_class"')
        self.assertContains(page, 'name="level"')

    def test_text_with_no_item_in_it_says_so_and_creates_nothing(self):
        from chardata.models import Char
        avant = Char.objects.count()
        page = self.client.post(self._url(), {'text': '51 Vitality\nLevel 200'})
        self.assertContains(page, 'matched our catalogue')
        self.assertEqual(avant, Char.objects.count())

    def test_confirming_brings_the_gear_in_without_solving(self):
        from chardata.models import Char
        from chardata.solution import get_solution
        texte = self._texte()
        reponse = self.client.post(self._url(), {
            'text': texte, 'confirm': '1', 'char_class': 'Iop', 'level': '200'})
        self.assertEqual(302, reponse.status_code)
        char = Char.objects.order_by('-id').first()
        self.assertIsNotNone(char)
        self.assertEqual('Iop', char.char_class)
        solution = get_solution(char)
        # item_list rend un emplacement par slot du build; les seize qui n'ont
        # rien recu portent le nom 'NoItem'. Ce sont des vides, pas des objets.
        portes = sorted(item.name for item in (solution.item_list or [])
                        if item.name != 'NoItem')
        attendus = sorted(l.strip() for l in texte.split('\n'))
        self.assertEqual(attendus, portes)

    def test_the_build_is_not_presented_as_something_the_solver_found(self):
        """`origin` decide de `is_generated`. Un build colle n'a jamais ete
        calcule, et la page ne doit pas laisser croire le contraire."""
        from chardata.models import Char
        from chardata.solution import get_solution
        self.client.post(self._url(), {
            'text': self._texte(), 'confirm': '1', 'char_class': 'Iop',
            'level': '200'})
        char = Char.objects.order_by('-id').first()
        origine = get_solution(char).input.get('origin')
        self.assertEqual('pasted_text', origine)
        self.assertNotEqual('generated', origine)

    def test_the_level_the_reader_typed_is_the_level_of_the_build(self):
        from chardata.models import Char
        self.client.post(self._url(), {
            'text': self._texte(), 'confirm': '1', 'char_class': 'Cra',
            'level': '150'})
        char = Char.objects.order_by('-id').first()
        self.assertEqual(150, char.level)
        self.assertEqual('Cra', char.char_class)


class TheTextImportPageSpeaksEveryLanguageTests(TestCase):
    """Le gabarit est en anglais; quatre lecteurs sur cinq lisent autre chose.

    Un temoin par langue, pris dans la traduction et pas dans une marque: un
    mot qui survit tel quel a la traduction ne prouverait que lui-meme.
    """

    TEMOINS = {
        'en': ('Import a build from text', 'Read this text',
               'One item name per line'),
        'fr': ('Importer un build depuis du texte', 'Lire ce texte',
               'Un nom d\u2019objet par ligne'),
        'es': ('Importar un build desde texto', 'Leer este texto',
               'Un nombre de objeto por l\u00ednea'),
        'pt': ('Importar um build a partir de texto', 'Ler este texto',
               'Um nome de item por linha'),
        'de': ('Einen Build aus Text importieren', 'Diesen Text lesen',
               'Ein Item-Name pro Zeile'),
    }

    def test_every_language_gets_the_page_in_its_own_words(self):
        manquants = []
        for langue, temoins in sorted(self.TEMOINS.items()):
            reponse = self.client.get(
                '/import/text/', headers={'accept-language': langue})
            self.assertEqual(200, reponse.status_code, langue)
            corps = reponse.content.decode('utf-8')
            for temoin in temoins:
                if temoin not in corps:
                    manquants.append((langue, temoin))
        self.assertFalse(
            manquants,
            'the catalogue compiled but these never reached the page: %s'
            % manquants)


class NoImportPageClaimsTheGameCanBeCopiedTests(SimpleTestCase):
    """Une infobulle Dofus n'est pas connue pour etre selectionnable.

    Ce garde existait deja et ne lisait qu'une chaine: le `text_hint` du
    dictionnaire de l'inventaire. Il aurait donc laisse passer exactement la
    meme affirmation sur cette page-ci, ecrite dans un gabarit et non dans un
    dictionnaire. Un garde qui surveille une chaine surveille une chaine.

    Ce qui est interdit, c'est de dire d'ou vient le texte, pas d'accepter le
    texte: le lecteur colle ce qu'il veut, et le site n'a pas a affirmer
    qu'il peut le copier d'un endroit ou personne n'a verifie qu'il le peut.
    """

    INTERDITS = ('in-game', 'in game', 'depuis le jeu', 'dans le jeu',
                 'del juego', 'en el juego', 'do jogo', 'no jogo',
                 'aus dem spiel', 'im spiel')

    def _pages(self):
        import os
        racine = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              'templates', 'chardata')
        for nom in ('text_build.html', 'dofusbook.html', 'inventory.html'):
            chemin = os.path.join(racine, nom)
            with open(chemin, encoding='utf-8') as f:
                yield nom, f.read()

    def test_the_sweep_reads_the_pages_it_names(self):
        lues = list(self._pages())
        self.assertEqual(3, len(lues))
        for _nom, corps in lues:
            self.assertGreater(len(corps), 500)

    def test_no_import_page_says_the_text_comes_from_the_game(self):
        coupables = []
        for nom, corps in self._pages():
            bas = corps.lower()
            for interdit in self.INTERDITS:
                if interdit in bas:
                    coupables.append((nom, interdit))
        self.assertFalse(
            coupables,
            'nothing establishes that a Dofus tooltip can be selected, so '
            'these send the reader looking for something that may not '
            'exist: %s' % coupables)

    def test_the_translations_do_not_say_it_either(self):
        from django.utils import translation
        msgids = (
            'Paste the names of your gear, one per line. Anything that is '
            'not an item name is skipped, so you can paste more than just '
            'the names.',
            'Paste the names of your gear and get the same build here, piece '
            'for piece. Nothing is re-optimized unless you ask for it.',
        )
        coupables = []
        for langue in ('en', 'fr', 'es', 'pt', 'de'):
            for msgid in msgids:
                with translation.override(langue):
                    rendu = translation.gettext(msgid).lower()
                for interdit in self.INTERDITS:
                    if interdit in rendu:
                        coupables.append((langue, interdit))
        self.assertFalse(coupables, coupables)


class AnImportedBuildIsNotCalledEmptyTests(TestCase):
    """La page de solution n'avait que deux cas: suggere par le solveur, ou
    vide. Un build importe n'est ni l'un ni l'autre, et il tombait dans
    <<vide>>: la page annoncait <<This set starts empty. Click the add buttons
    to choose the items yourself>> juste au-dessus des pieces qu'on venait de
    rapatrier. Les deux imports, DofusBook et texte, passaient par la.
    """

    def _importe(self):
        from chardata.models import Char
        texte = '\n'.join(_noms('dofus3', ('Hat', 'Cloak', 'Belt')))
        self.client.post('/import/text/', {
            'text': texte, 'confirm': '1', 'char_class': 'Iop',
            'level': '200'})
        return Char.objects.order_by('-id').first(), texte

    def test_the_page_says_the_gear_was_brought_in(self):
        char, texte = self._importe()
        page = self.client.get('/solution/%d/' % char.id)
        self.assertEqual(200, page.status_code)
        corps = page.content.decode('utf-8')
        self.assertIn('gear you brought in', corps)
        self.assertNotIn('This set starts empty', corps)
        # Et les pieces sont bien la, sinon la phrase serait vraie.
        for nom in texte.split('\n'):
            self.assertIn(nom, corps)

    def test_the_page_does_not_present_it_as_a_suggestion_either(self):
        """L'autre moitie: ne pas dire <<voici le set que nous suggerons>>
        d'un stuff que le solveur n'a jamais vu."""
        char, _texte = self._importe()
        corps = self.client.get('/solution/%d/' % char.id).content.decode(
            'utf-8')
        self.assertNotIn('the set that we suggest', corps)
        self.assertIn('Nothing here was chosen by the solver', corps)

    def test_a_build_that_really_is_empty_still_says_so(self):
        """Le garde de l'autre cote: en corrigeant l'import, on ne doit pas
        avoir fait disparaitre la phrase pour les builds vraiment vides."""
        from chardata.solution_result import IMPORT_ORIGINS
        self.assertNotIn('generated', IMPORT_ORIGINS)
        source = self._gabarit()
        self.assertIn('This set starts empty', source)
        self.assertIn('{% elif is_imported %}', source)

    def _gabarit(self):
        import os
        chemin = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              'templates', 'chardata', 'solution.html')
        with open(chemin, encoding='utf-8') as f:
            return f.read()
