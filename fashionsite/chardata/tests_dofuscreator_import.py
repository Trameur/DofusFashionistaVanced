# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A public DofusCreator project reads back from its link."""

from django.test import SimpleTestCase, TestCase

from chardata import build_link_import, dofuscreator_import
from chardata.dofusbook_import import ImportError_

LIEN = 'https://dofuscreator.com/projet/6e9f4'

# Real Dofus 3 item ids, not invented ones.
PAGE = '''<html><head><title> MIAAW 420 </title></head><body>
<script>var projeto = {info: { nome: " MIAAW 420", publico: "1", preco: "21.5",servidor: "mono", elemento: "Agilidade/Sorte", secundaria: "Fuga", modo: "Todos", raca: "ecaflip", descricao : "" }, level: 200, itens: {"chapeu":{"id":"18590","img":"16509","exos":[["danos_feiticos",1]]},"capa":{"id":"18591","img":"17377","exos":[["danos_feiticos",1]]},"amuleto":{"id":"17103","img":"1271","exos":[["danos_feiticos",1]]},"anel1":{"id":"22186","img":"9342","exos":[["pa",1]]},"anel2":{"id":"32234","img":"9400","exos":[["pm",1]]},"cinto":{"id":"17104","img":"10297","exos":[["critico",2]]},"bota":{"id":"22187","img":"11343","exos":[["danos_feiticos",1]]},"arma":{"id":"32235","img":"2096","exos":[["danos_criticos",8],["agua ",85]]},"escudo":{"id":"32236","img":"82561","exos":[["danos_criticos",8]]},"pet":{"id":"13465","img":"121003","exos":[]},"misc1":{"id":"694","img":"23001","exos":[]},"misc2":{"id":"7043","img":"23005","exos":[]},"misc3":{"id":"7754","img":"23012","exos":[]},"misc4":{"id":"7115","img":"23011","exos":[]},"misc5":{"id":"6980","img":"23004","exos":[]},"misc6":{"id":"739","img":"23003","exos":[]}}, distribuidos: {"vitalidade":0,"sabedoria":0,"forca":5,"inteligencia":0,"sorte":265,"agilidade":265}, pergaminhos: {"vitalidade":100,"sabedoria":100,"forca":100,"inteligencia":100,"sorte":100,"agilidade":100}, buffs: []};</script>
<div class="row"></div></body></html>'''

# an unknown project code answers 200 with an empty builder, no script
PAGE_VIDE = '<html><body><div class="row"></div></body></html>'


def _ouvreur(page=PAGE, erreur=None):
    class Reponse(object):
        def read(self, *args):
            return page.encode('utf-8')

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def ouvrir(requete, timeout=None):
        if erreur is not None:
            raise erreur
        return Reponse()
    return ouvrir


class TheLinkIsRecognisedTests(SimpleTestCase):

    def test_the_two_hosts_and_the_project_path(self):
        self.assertEqual(('dofuscreator.com', '6e9f4'),
                         dofuscreator_import.parse_link(LIEN))
        self.assertEqual(('www.dofuscreator.com', '379dd'),
                         dofuscreator_import.parse_link(
                             'https://www.dofuscreator.com/projet/379dd?lang=fr'))
        self.assertEqual(('dofuscreator.com', '6e9f4'),
                         dofuscreator_import.parse_link('dofuscreator.com/projet/6e9f4/'))

    def test_retro_projects_and_other_pages_are_not_read(self):
        """Retro projects often reference ids absent from their own catalogue, so they are not read."""
        for url in ('https://retro.dofuscreator.com/projet/1cb35',
                    'https://dofuscreator.com/projets?lang=fr',
                    'https://dofuscreator.com/', 'https://example.com/projet/6e9f4'):
            with self.subTest(url=url):
                self.assertIsNone(dofuscreator_import.parse_link(url))

    def test_the_registry_knows_both_sites(self):
        self.assertTrue(build_link_import.recognises(LIEN))
        self.assertTrue(build_link_import.recognises(
            'https://www.dofusbook.net/fr/stuff/7894460-zobal-m-200'))
        self.assertFalse(build_link_import.recognises('https://example.com/x'))
        self.assertEqual(['dofusbook.net', 'dofus-stuffer.is-great.net',
                          'dofuscreator.com'],
                         build_link_import.readable_sites())


class ThePageIsReadTests(TestCase):

    def test_the_inline_script_gives_the_project(self):
        projet = dofuscreator_import.parse_project(PAGE)
        self.assertEqual('MIAAW 420', projet['name'])
        self.assertEqual(200, projet['level'])
        self.assertEqual('ecaflip', projet['race'])
        self.assertEqual(16, len(projet['items']))
        self.assertEqual(('chapeu', 18590, [['danos_feiticos', 1]]), projet['items'][0])
        self.assertEqual({'forca': 5, 'sorte': 265, 'agilidade': 265,
                          'vitalidade': 0, 'sabedoria': 0, 'inteligencia': 0},
                         projet['points'])
        self.assertEqual(100, projet['scrolls']['agilidade'])

    def test_a_page_without_the_script_is_not_found(self):
        with self.assertRaises(ImportError_) as arret:
            dofuscreator_import.parse_project(PAGE_VIDE)
        self.assertEqual('not_found', arret.exception.reason)

    def test_the_build_comes_back_in_our_ids_with_stats_class_and_fm(self):
        from fashionistapulp.structure import get_structure
        lu = dofuscreator_import.read_build(LIEN, opener=_ouvreur())
        structure = get_structure('dofus3')
        self.assertEqual('dofus3', lu['game_version'])
        self.assertEqual('MIAAW 420', lu['name'])
        self.assertEqual(200, lu['level'])
        self.assertEqual('Ecaflip', lu['char_class'])
        self.assertFalse(lu['class_is_unknown'])
        self.assertEqual(16, len(lu['item_ids']), lu['missing'])
        self.assertEqual([], lu['missing'])
        ankama = {structure.get_item_by_id(i).ankama_id for i in lu['item_ids']}
        self.assertIn(2469 if 2469 in ankama else 18590, ankama)
        self.assertIn(694, ankama)
        self.assertEqual({'Strength': 5, 'Chance': 265, 'Agility': 265},
                         lu['base_points'])
        self.assertEqual(100, lu['base_scrolled']['Vitality'])
        # nine pieces carry named exos on their site that are not applied there
        self.assertEqual(9, len(lu['fm_not_carried']))
        self.assertTrue(set(lu['fm_not_carried']) <= set(lu['item_ids']))

    def test_errors_of_the_fetch_have_their_reason(self):
        import urllib.error
        introuvable = urllib.error.HTTPError(LIEN, 404, 'nope', {}, None)
        with self.assertRaises(ImportError_) as arret:
            dofuscreator_import.read_build(LIEN, opener=_ouvreur(erreur=introuvable))
        self.assertEqual('not_found', arret.exception.reason)
        with self.assertRaises(ImportError_) as arret:
            dofuscreator_import.read_build(LIEN, opener=_ouvreur(erreur=OSError('down')))
        self.assertEqual('unreachable', arret.exception.reason)
        with self.assertRaises(ImportError_) as arret:
            dofuscreator_import.read_build(LIEN, opener=_ouvreur(page=PAGE_VIDE))
        self.assertEqual('not_found', arret.exception.reason)

    def test_the_registry_reads_it_the_same_way(self):
        lu = build_link_import.read(LIEN, opener=_ouvreur())
        self.assertEqual('Ecaflip', lu['char_class'])
        with self.assertRaises(ImportError_) as arret:
            build_link_import.read('https://example.com/x')
        self.assertEqual('not_a_link', arret.exception.reason)
