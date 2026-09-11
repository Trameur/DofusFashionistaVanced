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

    def test_a_whole_tooltip_can_be_pasted_and_its_rolls_come_with_it(self):
        """Mesure du 10 septembre 2026: sur **7800 lignes** qui ne sont pas des
        noms d'objets (les etiquettes de stats des cinq langues, declinees en
        <<51 X>>, <<X 51>>, <<-12 X>>, plus les entetes d'infobulle usuelles),
        prises sur Dofus 3, Retro et Touch, aucune n'est prise pour un objet.

        Elles ne sont pas perdues pour autant: une ligne de jet revient a la
        piece qu'elle suit. Un import qui repose le stuff <<a l'identique>> et
        jetterait les jets ne reposerait pas le meme stuff.
        """
        noms = _noms('dofus3', ('Hat', 'Cloak'))
        texte = '\n'.join([
            noms[0], '51 Vitality', 'Level 200',
            noms[1], 'Effects:', 'Conditions',
        ])
        lu = read_items(texte, 'dofus3', 'en')
        self.assertEqual([m['name'] for m in lu['matched']], noms)
        # Le jet revient a la piece qu'il suit, pas a l'autre.
        self.assertTrue(any(r['name'] == 'Vitality' and r['value'] == 51
                            for r in lu['matched'][0]['rolls']),
                        lu['matched'][0]['rolls'])
        self.assertEqual([], lu['matched'][1]['rolls'])
        # Et ce qui n'est ni un nom ni un jet reste signale.
        for parasite in ('Level 200', 'Effects:', 'Conditions'):
            self.assertIn(parasite, lu['ignored'])

    def test_a_roll_before_any_item_is_reported_not_guessed(self):
        """Coller ses stats sans le nom au-dessus n'attache rien: on ne
        devine pas a quelle piece elles appartenaient."""
        lu = read_items('51 Vitality\n30 Strength', 'dofus3', 'en')
        self.assertEqual([], lu['item_ids'])
        self.assertEqual(2, lu['orphan_rolls'])
        self.assertEqual(['51 Vitality', '30 Strength'], lu['ignored'])

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
        self.assertIn('Read this', page)

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
        'en': ('Import a build', 'Read this',
               'One item name per line, or a build link'),
        'fr': ('Importer un build', 'Lire tout ça',
               'Un nom d’objet par ligne, ou un lien de build'),
        'es': ('Importar un build', 'Leer esto',
               'Un nombre de objeto por línea, o un enlace de build'),
        'pt': ('Importar um build', 'Ler isto',
               'Um nome de item por linha, ou um link de build'),
        'de': ('Build importieren', 'Das lesen',
               'Ein Gegenstandsname pro Zeile, oder ein Build-Link'),
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
        for nom in ('text_build.html', 'inventory.html'):
            chemin = os.path.join(racine, nom)
            with open(chemin, encoding='utf-8') as f:
                yield nom, f.read()

    def test_the_sweep_reads_the_pages_it_names(self):
        # Deux pages depuis le 11 septembre 2026: la page qui ne prenait
        # qu'un lien est fondue dans la page d'import unique.
        lues = list(self._pages())
        self.assertEqual(2, len(lues))
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


class ThePythonRollParserAgreesWithTheBrowserOneTests(TestCase):
    """Deux implementations de la meme lecture, tenues a la meme table.

    `parseStatLine` vit dans un gabarit et tourne chez le lecteur; son jumeau
    Python sert l'import par texte. Porter une regle sans ce test, c'est se
    garantir deux comportements dans six mois: la regle des groupes de
    chiffres, qui a deja fabrique 476 et 4560 une fois, serait corrigee d'un
    cote et pas de l'autre.

    Les lignes ci-dessous ne sont pas decoratives. Chacune est un cas qui a
    reellement casse: le separateur de fourchette mal lu, l'icone de stat lue
    comme un chiffre, les groupes de milliers, le pourcentage, le signe.
    """

    LEXIQUE = {'force': 'str', 'vitalite': 'vit', 'critique': 'ch',
               '% critique': 'ch'}

    LIGNES = [
        '38 Force',
        '-20 Force',
        '+15 Force',
        '4 50 Force',
        '1 000 Vitalite',
        '1 234 567 Vitalite',
        '57 \u00e0 76 Force',
        '57 a 76 Force',
        '57 to 76 Force',
        '57 bis 76 Force',
        '57 4 76 Force',
        '3 4 5 60 Force',
        '0 Force',
        '10 % Critique',
        '10% Critique',
        'Force',
        '',
        '   ',
        '12 Sagesse',
        '1.000 Vitalite',
        '-1 000 Vitalite',
    ]

    def _js(self):
        """Le meme harnais que les tests du lecteur de captures.

        Il est importe et non recopie: si l'extraction par comptage
        d'accolades cesse de marcher, les deux familles de tests doivent
        rougir ensemble, pas l'une sans l'autre.
        """
        import json
        from chardata.tests import InventoryScriptHarness
        # GABARIT est un attribut de CLASSE du harnais, donc on lie
        # _source au harnais et seul _node a self, dont il utilise les
        # assertions et skipTest.
        source = InventoryScriptHarness._source(InventoryScriptHarness)
        morceaux = [InventoryScriptHarness._extract(source, 'ocrNormalize'),
                    InventoryScriptHarness._extract(source, 'parseStatLine')]
        script = '\n'.join(morceaux) + (
            '\nconst lexicon = %s;\n'
            'console.log(JSON.stringify(%s.map('
            'l => parseStatLine(l, lexicon))));\n'
            % (json.dumps(self.LEXIQUE), json.dumps(self.LIGNES)))
        return json.loads(InventoryScriptHarness._node(self, script))

    def _python(self):
        from chardata.text_build_import import _lit_ligne_de_stat
        return [_lit_ligne_de_stat(ligne, self.LEXIQUE)
                for ligne in self.LIGNES]

    def test_both_readers_answer_the_same_thing_on_every_line(self):
        cote_js = self._js()
        cote_python = self._python()
        self.assertEqual(len(self.LIGNES), len(cote_js))
        divergences = []
        for ligne, js, py in zip(self.LIGNES, cote_js, cote_python):
            if js != py:
                divergences.append((ligne, js, py))
        self.assertFalse(
            divergences,
            'the browser reader and the server one disagree, so the same '
            'paste gives two builds: %s' % divergences)

    def test_the_table_still_covers_the_cases_that_broke(self):
        """Un test d'accord qui ne compare que des lignes faciles est vert et
        ne garde rien."""
        lu = dict(zip(self.LIGNES, self._python()))
        self.assertIsNone(lu['57 4 76 Force'], 'the 476 case came back')
        self.assertIsNone(lu['3 4 5 60 Force'], 'the 4560 case came back')
        self.assertIsNone(lu['57 \u00e0 76 Force'])
        self.assertEqual({'key': 'str', 'value': 50}, lu['4 50 Force'])
        self.assertEqual({'key': 'vit', 'value': 1000}, lu['1 000 Vitalite'])
        self.assertEqual({'key': 'vit', 'value': 1234567},
                         lu['1 234 567 Vitalite'])
        self.assertEqual({'key': 'str', 'value': -20}, lu['-20 Force'])
        self.assertIsNone(lu['0 Force'], 'a zero roll is not a roll')
        self.assertIsNone(lu['Force'], 'a bare label is not a roll')


class PastedRollsReachTheBuildTests(TestCase):
    """Coller une infobulle doit rendre le stuff TEL QU'IL EST, jets compris.

    Un import qui ramene les bons objets avec leurs valeurs de catalogue
    rend un autre stuff que celui du joueur, et le solveur repartirait ensuite
    de chiffres qui ne sont pas les siens.
    """

    def _objet_avec_stats(self, type_name='Hat'):
        structure = get_structure('dofus3')
        for item in structure.types[200][type_name]:
            if not item.removed and item.stats:
                return structure, item
        raise AssertionError('no item with stats in %s' % type_name)

    def _texte_infobulle(self, structure, item, valeur=None):
        nom = structure.get_item_name_in_language(item, 'en')
        stat_id, catalogue = item.stats[0]
        stat = structure.get_stat_by_id(stat_id)
        lu = catalogue if valeur is None else valeur
        return nom, stat, lu, '%s\n%d %s' % (nom, lu, stat.name)

    def test_the_rolls_are_written_on_the_build(self):
        structure, item = self._objet_avec_stats()
        _nom, stat, valeur, texte = self._texte_infobulle(structure, item, 7)
        from chardata.models import Char
        from chardata.lock_forbid import get_stat_overrides
        self.client.post('/import/text/', {
            'text': texte, 'confirm': '1', 'char_class': 'Iop',
            'level': '200'})
        char = Char.objects.order_by('-id').first()
        overrides = get_stat_overrides(char)
        self.assertIn(item.id, overrides, overrides)
        self.assertEqual(valeur, overrides[item.id][stat.id])

    def test_a_build_with_no_rolls_pasted_carries_no_overrides(self):
        """Le garde de l'autre cote: coller une simple liste de noms ne doit
        pas inventer d'overrides."""
        from chardata.models import Char
        from chardata.lock_forbid import get_stat_overrides
        self.client.post('/import/text/', {
            'text': '\n'.join(_noms('dofus3', ('Hat', 'Cloak'))),
            'confirm': '1', 'char_class': 'Iop', 'level': '200'})
        char = Char.objects.order_by('-id').first()
        self.assertEqual({}, get_stat_overrides(char))

    def test_a_roll_on_a_stat_the_item_lacks_is_never_written(self):
        """`Model._apply_stat_overrides` AJOUTE la caracteristique a la piece
        quand elle n'y figure pas. Ecrire un tel jet ferait naitre sur l'objet
        une stat qu'il n'a jamais eue, et le solveur optimiserait autour."""
        structure, item = self._objet_avec_stats()
        portees = set(sid for sid, _v in item.stats)
        absente = next(s for s in structure.get_stats_list()
                       if s.id not in portees and s.name
                       # Les PA, PM et portee sont maintenant appliques comme
                       # des EXOS quand la piece ne les porte pas: le modele ne
                       # les ajoute pas a l'objet. Le cas <<stat inventee>> se
                       # teste donc sur une stat qui n'est pas de ceux-la.
                       and s.key not in ('ap', 'mp', 'range'))
        nom = structure.get_item_name_in_language(item, 'en')
        from chardata.models import Char
        from chardata.lock_forbid import get_stat_overrides
        self.client.post('/import/text/', {
            'text': '%s\n40 %s' % (nom, absente.name),
            'confirm': '1', 'char_class': 'Iop', 'level': '200'})
        char = Char.objects.order_by('-id').first()
        overrides = get_stat_overrides(char)
        self.assertNotIn(absente.id, overrides.get(item.id, {}), overrides)

    def test_the_preview_shows_the_rolls_and_what_it_left_out(self):
        structure, item = self._objet_avec_stats()
        portees = set(sid for sid, _v in item.stats)
        absente = next(s for s in structure.get_stats_list()
                       if s.id not in portees and s.name
                       # Les PA, PM et portee sont maintenant appliques comme
                       # des EXOS quand la piece ne les porte pas: le modele ne
                       # les ajoute pas a l'objet. Le cas <<stat inventee>> se
                       # teste donc sur une stat qui n'est pas de ceux-la.
                       and s.key not in ('ap', 'mp', 'range'))
        nom = structure.get_item_name_in_language(item, 'en')
        stat_id, catalogue = item.stats[0]
        stat = structure.get_stat_by_id(stat_id)
        page = self.client.post('/import/text/', {
            'text': '%s\n%d %s\n40 %s' % (nom, catalogue, stat.name,
                                          absente.name)})
        corps = page.content.decode('utf-8')
        self.assertIn(stat.name, corps)
        self.assertIn('does not carry that stat', corps)
        self.assertIn(absente.name, corps)

    def test_an_out_of_range_roll_is_kept_and_flagged(self):
        """La forgemagie pousse legitimement un jet au-dessus de son maximum
        et peut en sacrifier un sous son minimum. Seul le joueur sait, donc on
        applique et on signale, jamais on refuse."""
        from chardata.stat_range import get_stat_range
        structure = get_structure('dofus3')
        cible = None
        for item in structure.types[200]['Hat']:
            if item.removed or not item.stats:
                continue
            for stat_id, _v in item.stats:
                if get_stat_range(item, stat_id):
                    cible = (item, stat_id)
                    break
            if cible:
                break
        self.assertIsNotNone(cible, 'no Dofus 3 hat carries a roll range')
        item, stat_id = cible
        bas, _haut = get_stat_range(item, stat_id)
        stat = structure.get_stat_by_id(stat_id)
        nom = structure.get_item_name_in_language(item, 'en')
        lu = read_items('%s\n%d %s' % (nom, bas - 1, stat.name),
                        'dofus3', 'en')
        jet = next(r for r in lu['matched'][0]['rolls']
                   if r['name'] == stat.name)
        self.assertTrue(jet['applied'], jet)
        self.assertTrue(jet['out_of_range'], jet)
        self.assertEqual(bas - 1, lu['overrides'][item.id][stat_id])

    def test_the_pasted_roll_actually_changes_the_build_totals(self):
        """La preuve que les jets servent a quelque chose.

        Les ecrire dans `stat_overrides` ne prouve rien tout seul: la solution
        est construite AVANT eux, par `_place_items`. Ce qui les fait compter,
        c'est que `get_solution` repasse par `get_effective_stat_overrides` a
        chaque lecture. Si ce chemin disparaissait, le build afficherait les
        valeurs de catalogue et le dictionnaire dormirait sans que rien ne
        rougisse.
        """
        from chardata.models import Char
        from chardata.solution import get_solution
        structure, item = self._objet_avec_stats()
        stat_id, catalogue = item.stats[0]
        stat = structure.get_stat_by_id(stat_id)
        nom = structure.get_item_name_in_language(item, 'en')
        vise = max(1, catalogue - 25)

        self.client.post('/import/text/', {
            'text': '%s\n%d %s' % (nom, vise, stat.name),
            'confirm': '1', 'char_class': 'Iop', 'level': '200'})
        char = Char.objects.order_by('-id').first()
        porte = next(i for i in get_solution(char).item_list
                     if i.name != 'NoItem')
        # ModelResultItem.stats est indexe par la CLE de la stat, pas par
        # son id, et c'est la que l'override atterrit.
        self.assertEqual(vise, porte.stats[stat.key],
                         'the build shows the catalogue roll, not the pasted '
                         'one')
        self.assertNotEqual(catalogue, vise, 'the case proves nothing')


class TheTextIsReadInItsOwnLanguageTests(SimpleTestCase):
    """Le lecteur peut jouer en francais et lire le site en anglais.

    La langue se deduit des JETS, qui sont un signal fiable: le lexique de
    stats d'une langue reconnait ses propres lignes et pas celles des autres.
    Le vivier de noms est ensuite construit dans cette langue-la. Sans jet
    dans le texte il n'y a aucun signal, et la langue de l'interface gagne.
    """

    def setUp(self):
        self.precedente = get_current_game_version()
        set_current_game_version('dofus3')
        self.addCleanup(set_current_game_version, self.precedente)

    def _objet(self):
        structure = get_structure('dofus3')
        for item in structure.types[200]['Hat']:
            if not item.removed and item.stats:
                return structure, item
        raise AssertionError('no hat with stats')

    def test_a_french_paste_is_understood_by_an_english_reader(self):
        structure, item = self._objet()
        nom_fr = structure.get_item_name_in_language(item, 'fr')
        nom_en = structure.get_item_name_in_language(item, 'en')
        self.assertNotEqual(nom_fr, nom_en, 'the case proves nothing')
        lu = read_items('%s\n400 Vitalite\n50 Sagesse' % nom_fr,
                        'dofus3', 'en')
        self.assertEqual('fr', lu['stat_language'])
        self.assertEqual([nom_fr], [m['name'] for m in lu['matched']])
        self.assertTrue(lu['matched'][0]['rolls'])

    def test_without_any_roll_the_reader_language_still_decides(self):
        """Le comportement d'avant, qui doit survivre: une liste de noms
        anglais lue par un lecteur anglais."""
        structure, item = self._objet()
        nom_en = structure.get_item_name_in_language(item, 'en')
        lu = read_items(nom_en, 'dofus3', 'en')
        self.assertEqual('en', lu['stat_language'])
        self.assertEqual([nom_en], [m['name'] for m in lu['matched']])


class TheSiteCanReadBackItsOwnExportTests(TestCase):
    """Le bouton <<Copier en texte>> et la page d'import doivent se parler.

    Mesure du 10 septembre 2026, avant ce lot: colle tel quel, un build
    exporte par le site rendait **zero objet reconnu**, les six lignes toutes
    ignorees. L'export prefixe chaque piece de son emplacement (<<Hat: ...>>)
    et l'import comparait la ligne entiere a un nom d'objet; le rapprochement
    tolerant ne pouvait rien, retirer <<Hat: >> coute cinq corrections quand le
    plafond est a trois.

    Le tour complet est ce qui compte, pas chaque moitie: on exporte un vrai
    build par la vraie fonction, on colle le resultat dans la vraie page, et
    on compare ce qui revient.
    """

    def _build_exporte(self, avec_caracteristiques=True):
        """Un build cree par la vraie page, puis exporte par la vraie fonction.

        Le build passe par `/import/text/` plutot que par `create_build`
        directement: cette derniere veut une session, et emprunter le chemin
        du site evite d'en fabriquer une pour les besoins du test.
        """
        from chardata.models import Char, CharBaseStats
        from chardata.solution import get_solution
        from chardata.solution_view import _build_share_text
        from django.test import RequestFactory

        structure = get_structure('dofus3')
        noms = [structure.get_item_name_in_language(
                    next(i for i in structure.types[200][t] if not i.removed),
                    'en')
                for t in ('Hat', 'Cloak', 'Belt')]
        self.client.post('/import/text/', {'text': '\n'.join(noms),
                                           'confirm': '1',
                                           'char_class': 'Cra',
                                           'level': '187'})
        char = Char.objects.order_by('-id').first()
        char.char_name = 'Mon Cra'
        char.save()
        if avec_caracteristiques:
            for nom, points, parchos in (('Vitality', 101, 100),
                                         ('Strength', 50, 0)):
                ligne, _n = CharBaseStats.objects.get_or_create(
                    char=char, stat=nom,
                    defaults={'total_value': 0, 'scrolled_value': 0})
                ligne.total_value = points + parchos
                ligne.scrolled_value = parchos
                ligne.save()
        texte = _build_share_text(RequestFactory().get('/'), char,
                                  get_solution(char))
        return char, texte, noms

    def test_the_export_is_read_back_as_the_same_gear(self):
        _char, texte, noms = self._build_exporte()
        lu = read_items(texte, 'dofus3', 'en')
        self.assertEqual(sorted(noms),
                         sorted(m['name'] for m in lu['matched']),
                         'the site cannot read its own export: %s' % texte)

    def test_a_french_reader_reads_the_same_export(self):
        """L'export ecrit les noms INTERNES quelle que soit la langue. Sans le
        nom interne au vivier, un lecteur francais ne relisait pas un texte
        que le site venait de lui donner."""
        _char, texte, noms = self._build_exporte()
        lu = read_items(texte, 'dofus3', 'fr')
        self.assertEqual(len(noms), len(lu['matched']), lu['ignored'])

    def test_the_export_carries_the_class_and_the_level(self):
        _char, texte, _noms = self._build_exporte()
        lu = read_items(texte, 'dofus3', 'en')
        self.assertEqual('Cra', lu['char_class'])
        self.assertEqual(187, lu['char_level'])

    def test_the_export_carries_the_base_characteristics(self):
        _char, texte, _noms = self._build_exporte()
        self.assertIn('Points:', texte)
        lu = read_items(texte, 'dofus3', 'en')
        self.assertEqual({'Vitality': 101, 'Strength': 50}, lu['base_points'])
        # Strength a ete mis a zero parchotage, les quatre autres gardent le
        # plein que create_build pose. La ligne sort donc, et en entier.
        self.assertIn('Scrolls:', texte)
        self.assertEqual(0, lu['base_scrolled']['Strength'])
        self.assertEqual(100, lu['base_scrolled']['Vitality'])

    def test_a_default_build_carries_neither_line(self):
        """`create_build` cree TOUT build entierement parchote.

        Sortir les parchotages systematiquement collerait six valeurs
        identiques a la fin de chaque message Discord sans rien apprendre a
        personne. La ligne ne sort donc que si elle s'ecarte du defaut, et le
        tour reste exact: absente, elle veut dire <<le defaut>>, qui est
        precisement ce que la creation repose.
        """
        _char, texte, _noms = self._build_exporte(avec_caracteristiques=False)
        self.assertNotIn('Points:', texte)
        self.assertNotIn('Scrolls:', texte)

    def test_a_default_build_still_comes_back_fully_scrolled(self):
        """L'autre moitie: si la ligne absente ne voulait pas dire le defaut,
        le tour perdrait cent points de parchotage sur six stats."""
        from chardata.models import Char
        from chardata.util import get_stats_and_scrolled
        _char, texte, _noms = self._build_exporte(avec_caracteristiques=False)
        self.client.post('/import/text/', {'text': texte, 'confirm': '1',
                                           'char_class': 'Cra',
                                           'level': '187'})
        revenu = Char.objects.order_by('-id').first()
        _spent, scrolled = get_stats_and_scrolled(revenu)
        self.assertEqual(100, scrolled['Vitality'])
        self.assertEqual(100, scrolled['Agility'])

    def test_the_whole_trip_gives_back_the_same_character(self):
        """Le tour complet, par la vraie page."""
        from chardata.models import Char
        from chardata.util import get_stats_and_scrolled
        _char, texte, noms = self._build_exporte()
        avant = Char.objects.count()
        self.client.post('/import/text/', {'text': texte, 'confirm': '1',
                                           'char_class': 'Cra',
                                           'level': '187'})
        self.assertEqual(avant + 1, Char.objects.count())
        revenu = Char.objects.order_by('-id').first()
        self.assertEqual('Cra', revenu.char_class)
        self.assertEqual(187, revenu.level)
        spent, scrolled = get_stats_and_scrolled(revenu)
        self.assertEqual(101, spent['Vitality'])
        self.assertEqual(100, scrolled['Vitality'])
        self.assertEqual(50, spent['Strength'])
        self.assertEqual(0, scrolled['Strength'])

    def test_the_class_is_offered_preselected_when_the_text_names_it(self):
        """Sans jamais comparer deux attributs dans l'ordre: le gabarit est
        minifie et les attributs y sont tries.

        Le balayage porte sur la LISTE DES CLASSES et non sur la page: la page
        en porte une seconde depuis que le lecteur de captures demande la
        langue du jeu, et son option preselectionnee n'est pas une classe de
        plus. Un garde qui lit la page entiere garde la page, pas la liste
        qu'il croit surveiller.
        """
        import re
        _char, texte, _noms = self._build_exporte()
        corps = self.client.post(
            '/import/text/', {'text': texte}).content.decode('utf-8')
        liste = re.search(r'<select[^>]*name="char_class"[^>]*>(.*?)</select>',
                          corps, re.S)
        self.assertIsNotNone(liste, 'the class list is gone from the page')
        options = re.findall(r'<option[^>]*>', liste.group(1))
        cra = [o for o in options if 'Cra' in o]
        self.assertTrue(cra, options[:3])
        self.assertTrue(any('selected' in o for o in cra), cra)
        autres = [o for o in options
                  if 'selected' in o and 'Cra' not in o]
        self.assertEqual([], autres, 'two classes are preselected')


class AnExportNamesItsGameAndTheImportRefusesAnotherTests(TestCase):
    """Un meme nom n'est pas un meme objet d'un jeu a l'autre.

    Mesure du 10 septembre 2026, sur les catalogues livres:

      depuis Retro, colles sur Dofus 3 : 1594 des 6269 noms existent aussi,
      et **482 d'entre eux y designent un objet d'un AUTRE NIVEAU**
      (<<Amulet of the Valiant Heart>> passe de 41 a 200,
       <<Arachnamu>> de 20 a 40).
      depuis Touch  : 818 sur 2618 reconnus changent de niveau.
      depuis Dofus 2: 210 sur 3306.

    L'export ne disait pas de quel jeu il venait, et l'import cherchait donc
    dans le catalogue de la page. Le lecteur recevait un build plausible qui
    n'etait pas le sien, ce qui est le pire resultat possible: rien ne lui
    aurait signale l'erreur.
    """

    def _texte_exporte(self, version):
        from chardata.models import Char
        from chardata.solution import get_solution
        from chardata.solution_view import _build_share_text
        from django.test import RequestFactory

        structure = get_structure(version)
        noms = [structure.get_item_name_in_language(
                    next(i for i in structure.types[200][t] if not i.removed),
                    'en')
                for t in ('Hat', 'Cloak')]
        prefixe = '' if version == 'dofus3' else '/' + version
        self.client.post('%s/import/text/' % prefixe,
                         {'text': '\n'.join(noms), 'confirm': '1',
                          'char_class': 'Cra', 'level': '200'})
        char = Char.objects.order_by('-id').first()
        return _build_share_text(RequestFactory().get('/'), char,
                                 get_solution(char)), noms

    def test_the_export_says_which_game_it_belongs_to(self):
        for version, libelle in (('dofus3', 'Dofus 3'), ('retro', 'Retro'),
                                 ('touch', 'Touch')):
            with self.subTest(version=version):
                texte, _noms = self._texte_exporte(version)
                self.assertIn(libelle, texte.split('\n')[0], texte)

    def test_the_reader_gets_the_version_back(self):
        texte, _noms = self._texte_exporte('retro')
        lu = read_items(texte, 'retro', 'en')
        self.assertEqual('retro', lu['stated_version'])

    def test_a_retro_build_is_refused_on_the_dofus3_page(self):
        texte, _noms = self._texte_exporte('retro')
        page = self.client.post('/import/text/', {'text': texte})
        self.assertContains(page, 'a different item in each game')
        self.assertNotContains(page, 'Bring this build in')

    def test_the_refusal_points_at_the_right_page(self):
        texte, _noms = self._texte_exporte('retro')
        page = self.client.post('/import/text/', {'text': texte})
        self.assertContains(page, '/retro/import/text/')

    def test_nothing_is_created_when_the_game_does_not_match(self):
        from chardata.models import Char
        texte, _noms = self._texte_exporte('retro')
        avant = Char.objects.count()
        self.client.post('/import/text/', {'text': texte, 'confirm': '1',
                                           'char_class': 'Cra',
                                           'level': '200'})
        self.assertEqual(avant, Char.objects.count())

    def test_the_same_game_is_read_normally(self):
        texte, noms = self._texte_exporte('retro')
        page = self.client.post('/retro/import/text/', {'text': texte})
        self.assertContains(page, 'Bring this build in')
        for nom in noms:
            self.assertContains(page, nom)

    def test_a_text_with_no_version_still_works(self):
        """Tous les textes exportes avant ce lot n'en ont pas, et une liste
        de noms tapee a la main non plus. Absente, la version veut dire
        <<celle de la page>>, ce qui etait le comportement d'avant."""
        noms = _noms('dofus3', ('Hat', 'Cloak'))
        lu = read_items('\n'.join(noms), 'dofus3', 'en')
        self.assertIsNone(lu['stated_version'])
        page = self.client.post('/import/text/', {'text': '\n'.join(noms)})
        self.assertContains(page, 'Bring this build in')

    def test_an_old_export_without_its_version_still_works(self):
        """La forme exacte que le site ecrivait avant ce lot."""
        noms = _noms('dofus3', ('Hat', 'Cloak'))
        ancien = 'Mon Cra - Cra lvl 187\n\nHat: %s\nCloak: %s' % tuple(noms)
        lu = read_items(ancien, 'dofus3', 'en')
        self.assertIsNone(lu['stated_version'])
        self.assertEqual('Cra', lu['char_class'])
        self.assertEqual(187, lu['char_level'])
        self.assertEqual(2, len(lu['matched']))


class APastedExoIsKeptAndCountedOnceTests(TestCase):
    """Les PA, les PM et la portee ne sont pas des jets comme les autres.

    Pour ces trois-la, `Model._apply_stat_overrides` n'ajoute RIEN a la piece:
    il la note porteuse d'exo, et `create_exo_constraints` ecrit
    `exo <= option + pieces porteuses portees`. Un jet de PA sur une piece qui
    n'en porte pas est donc un exo parfaitement legitime, pas une stat
    inventee.

    L'import les refusait avec toutes les autres, et perdait donc en silence
    l'exo que le joueur avait colle. Mesure du 10 septembre 2026, sur un build
    dont l'option est a False: la piece seule fait passer le total de PA de
    **0 a 1**.
    """

    def _piece_sans(self, cle):
        structure = get_structure('dofus3')
        for item in structure.types[200]['Hat']:
            if item.removed or not item.stats:
                continue
            cles = {structure.get_stat_by_id(sid).key for sid, _v in item.stats}
            if cle not in cles:
                return structure, item
        raise AssertionError('every hat carries %s' % cle)

    def _total(self, texte, niveau):
        from chardata.models import Char
        from chardata.solution import get_solution
        self.client.post('/import/text/', {'text': texte, 'confirm': '1',
                                           'char_class': 'Iop',
                                           'level': str(niveau)})
        char = Char.objects.order_by('-id').first()
        return char, get_solution(char).get_stats_total()

    def test_an_exo_on_a_piece_that_lacks_the_stat_is_applied(self):
        structure, item = self._piece_sans('ap')
        nom = structure.get_item_name_in_language(item, 'en')
        lu = read_items('%s\n1 AP' % nom, 'dofus3', 'en')
        jet = lu['matched'][0]['rolls'][0]
        self.assertTrue(jet['applied'], jet)
        self.assertTrue(jet['exo'], jet)
        self.assertEqual([], lu['refused_rolls'])

    def test_the_exo_actually_reaches_the_build_total(self):
        """Ecrire l'override ne prouve rien; le total affiche, oui.

        Le niveau est 199 et non 200 parce que `create_build` allume
        l'option `ap_exo` des 200: au-dessus de ce seuil, l'option donne deja
        le point et la piece ne changerait rien. Le cas qui prouve quelque
        chose est celui ou l'option est eteinte.
        """
        from chardata.options import get_options
        structure, item = self._piece_sans('ap')
        nom = structure.get_item_name_in_language(item, 'en')
        char_sans, sans = self._total(nom, 199)
        self.assertFalse(get_options(char_sans)['ap_exo'],
                         'the option is on, the case proves nothing')
        _char_avec, avec = self._total('%s\n1 AP' % nom, 199)
        # L'ecart, et non la valeur absolue: depuis le 11 septembre 2026 le
        # total porte aussi les PA que le personnage a de son propre chef
        # (section 41), sept a partir du niveau 100 donc sept ici. Ecrire
        # <<0>> mesurait en fait l'absence de cette base-la, pas la presence
        # de l'exo.
        self.assertEqual(7, sans.get('ap', 0), sans)
        self.assertEqual(sans.get('ap', 0) + 1, avec.get('ap', 0), avec)

    def test_the_option_and_the_piece_never_stack(self):
        """Un point par stat pour tout le build. A 200 l'option est allumee,
        donc la piece porteuse ne doit rien ajouter par-dessus."""
        structure, item = self._piece_sans('ap')
        nom = structure.get_item_name_in_language(item, 'en')
        _c1, sans = self._total(nom, 200)
        _c2, avec = self._total('%s\n1 AP' % nom, 200)
        # Sept PA au personnage a ce niveau, plus le point de l'option: la
        # piece porteuse ne doit rien ajouter par-dessus.
        self.assertEqual(8, sans.get('ap', 0), sans)
        self.assertEqual(sans.get('ap', 0), avec.get('ap', 0),
                         'the option and the piece stacked to two')

    def test_a_stat_that_is_not_an_exo_is_still_refused(self):
        """L'exception vaut pour trois cles, pas pour le reste: ailleurs le
        modele AJOUTERAIT la caracteristique a la piece."""
        structure, item = self._piece_sans('ap')
        portees = set(sid for sid, _v in item.stats)
        absente = next(s for s in structure.get_stats_list()
                       if s.id not in portees and s.name
                       and s.key not in ('ap', 'mp', 'range'))
        nom = structure.get_item_name_in_language(item, 'en')
        lu = read_items('%s\n40 %s' % (nom, absente.name), 'dofus3', 'en')
        jet = lu['matched'][0]['rolls'][0]
        self.assertFalse(jet['applied'], jet)
        self.assertFalse(jet['exo'], jet)
        self.assertEqual(1, len(lu['refused_rolls']), lu['refused_rolls'])

    def test_the_three_exo_keys_come_from_the_model(self):
        """Recopier la liste ici, c'est se garantir de perdre des exos le jour
        ou le modele en ajoute ou en retire une."""
        from fashionistapulp.model import Model
        from chardata.text_build_import import EXO_STAT_KEYS
        self.assertIs(EXO_STAT_KEYS, Model._EXO_STAT_KEYS)
        self.assertEqual({'ap', 'mp', 'range'}, set(EXO_STAT_KEYS))


class TheSharedTextSpeaksTheReaderLanguageTests(TestCase):
    """Un joueur francais qui copiait son build obtenait des noms anglais.

    L'export ecrivait `item.name`, le nom interne, quelle que soit la langue.
    Colle sur un Discord francais, ca donnait <<Creaking Tree Hat>> la ou le
    joueur attendait <<Coiffe Ranshi>>.

    Le corriger demande que l'import sache relire un nom dans n'importe
    laquelle des cinq langues, parce qu'un texte partage voyage.
    """

    def _exporte(self, langue):
        from chardata.models import Char
        from chardata.solution import get_solution
        from chardata.solution_view import _build_share_text
        from django.test import RequestFactory
        from django.utils import translation

        structure = get_structure('dofus3')
        item = next(i for i in structure.types[200]['Hat'] if not i.removed)
        nom_en = structure.get_item_name_in_language(item, 'en')
        self.client.post('/import/text/', {'text': nom_en, 'confirm': '1',
                                           'char_class': 'Cra',
                                           'level': '200'})
        char = Char.objects.order_by('-id').first()
        with translation.override(langue):
            texte = _build_share_text(RequestFactory().get('/'), char,
                                      get_solution(char))
        return texte, structure.get_item_name_in_language(item, langue)

    def test_the_export_writes_the_name_in_the_reader_language(self):
        texte, nom_fr = self._exporte('fr')
        self.assertIn(nom_fr, texte, texte)

    def test_a_french_export_is_read_on_the_german_site(self):
        """Le cas qui justifie l'index multilingue: un texte partage voyage
        d'un joueur a l'autre, et rien ne dit qu'ils lisent la meme langue."""
        texte, nom_fr = self._exporte('fr')
        lu = read_items(texte, 'dofus3', 'de')
        self.assertEqual(1, len(lu['matched']), lu['ignored'])
        # Rendu dans la langue du LECTEUR, pas dans celle du texte.
        structure = get_structure('dofus3')
        item = next(i for i in structure.types[200]['Hat'] if not i.removed)
        self.assertEqual(structure.get_item_name_in_language(item, 'de'),
                         lu['matched'][0]['name'])
        self.assertNotEqual(nom_fr, lu['matched'][0]['name'])

    def test_a_text_shared_before_this_change_still_reads(self):
        """Tous les textes deja partages portent le nom INTERNE. L'index le
        garde, sinon corriger l'export aurait casse ce qui circule deja."""
        structure = get_structure('dofus3')
        item = next(i for i in structure.types[200]['Hat'] if not i.removed)
        ancien = 'Hat: %s' % item.name
        for langue in ('fr', 'de', 'en'):
            with self.subTest(langue=langue):
                lu = read_items(ancien, 'dofus3', langue)
                self.assertEqual(1, len(lu['matched']), lu['ignored'])


class TwoLanguagesThatDisagreeMakeTheReaderChooseTests(SimpleTestCase):
    """Un meme nom normalise designe deux objets DIFFERENTS d'une langue a
    l'autre: 443 fois sur Retro, 215 sur Touch, et sur Dofus 3 <<robotas>>
    est Bedazzling Boots dans une langue et Roboots dans une autre.

    Un index a plat aurait rendu l'un pour l'autre, en silence. La langue du
    lecteur tranche quand elle connait le nom; sinon, un desaccord entre les
    autres langues fait taire l'import.
    """

    def setUp(self):
        self.precedente = get_current_game_version()
        set_current_game_version('dofus3')
        self.addCleanup(set_current_game_version, self.precedente)

    def _un_desaccord(self, version='dofus3'):
        """(nom, langue absente) pour un nom que deux langues se disputent."""
        from chardata.forgemagie_view import _normalized_text
        from chardata.text_build_import import LANGUES, _pool
        structure = get_structure(version)
        _pool_lecteur, index = _pool(structure, 'en')
        for langue in LANGUES:
            for nom, entree in index[langue].items():
                autres = [index[a].get(nom) for a in LANGUES if a != langue]
                autres = [a for a in autres if a is not None]
                if any(a[1].id != entree[1].id for a in autres):
                    # Une langue qui ne connait PAS ce nom du tout.
                    for candidate in LANGUES:
                        if nom not in index[candidate]:
                            return nom, candidate
        return None, None

    def test_such_a_disagreement_really_exists(self):
        """Le plancher du temoin: sans desaccord reel, le test suivant
        garderait une regle que rien ne declenche."""
        nom, langue = self._un_desaccord()
        self.assertIsNotNone(nom, 'no cross-language collision found')
        self.assertIsNotNone(langue)

    def test_the_import_refuses_rather_than_picking_one(self):
        nom, langue = self._un_desaccord()
        if nom is None:
            self.skipTest('no cross-language collision to try')
        lu = read_items(nom, 'dofus3', langue)
        self.assertEqual([], lu['item_ids'],
                         'the import picked one of two items that share this '
                         'name across languages: %s' % lu['matched'])

    def test_the_reader_own_language_still_decides(self):
        """La regle ne doit pas rendre muet un nom que la langue du lecteur
        connait parfaitement."""
        structure = get_structure('dofus3')
        item = next(i for i in structure.types[200]['Hat'] if not i.removed)
        for langue in ('en', 'fr', 'de'):
            with self.subTest(langue=langue):
                nom = structure.get_item_name_in_language(item, langue)
                lu = read_items(nom, 'dofus3', langue)
                self.assertEqual(1, len(lu['matched']), lu['ignored'])
