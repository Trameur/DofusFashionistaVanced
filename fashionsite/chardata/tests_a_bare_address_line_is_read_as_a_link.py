# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A pasted line with no scheme still counts as a link when it is a bare address."""

import json

from django.test import SimpleTestCase, TestCase

from chardata import build_link_import, text_build_view


def _dofusbook_opener(charge):
    class Reponse(object):
        def read(self, *args):
            return json.dumps(charge).encode('utf-8')

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def ouvrir(request, timeout=None):
        return Reponse()

    return ouvrir


def _dofuscreator_opener(page):
    class Reponse(object):
        def read(self, *args):
            return page.encode('utf-8')

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def ouvrir(request, timeout=None):
        return Reponse()

    return ouvrir


def _dofuscreator_page(ankama_id):
    return ('<html><body><script>var projeto = {info: {nome: "Bare link", '
           'raca: "iop"}, level: 200, itens: {"chapeu": {"id": "%d", '
           '"img": "1", "exos": []}}, distribuidos: {}, pergaminhos: {}, '
           'buffs: []};</script></body></html>' % ankama_id)


class AKnownHostMatchesWithOrWithoutAPathTests(SimpleTestCase):

    def test_each_is_read_as_a_link(self):
        for ligne in ('retro.dofusbook.net/fr/stuff/2558915-bas-level',
                     'touch.dofusbook.net/desktop/fr/equipement/'
                     'dofus-stuffer/objets?stuff=kA',
                     'dofuscreator.com/projet/6e9f4',
                     'd-bk.net/abcdef', 'dofusbook.net'):
            with self.subTest(ligne=ligne):
                self.assertTrue(text_build_view._ligne_est_un_lien(ligne))

    def test_a_bare_host_inside_a_sentence_is_still_text(self):
        self.assertFalse(text_build_view._ligne_est_un_lien(
            'go see dofuscreator.com/projet/6e9f4 please'))


class MixedCaseAndUppercaseBareHostsAreRecognisedTests(SimpleTestCase):

    LIGNES = (
        'DofusBook.net/fr/stuff/7894460-zobal-m-200',
        'WWW.DOFUSBOOK.NET/fr/stuff/7894460-zobal-m-200',
        'Retro.DofusBook.net/fr/stuff/2558915-bas-level',
        'RETRO.DOFUSBOOK.NET/fr/stuff/2558915-bas-level',
        'Touch.DofusBook.net/fr/stuff/2558915-bas-level',
        'TOUCH.DOFUSBOOK.NET/fr/stuff/2558915-bas-level',
        'Dofus-Stuffer.Is-Great.net?stuff=kA',
        'DOFUS-STUFFER.IS-GREAT.NET?stuff=kA',
        'DofusCreator.com/projet/6e9f4',
        'DOFUSCREATOR.COM/projet/6e9f4',
        'D-Bk.net/abcdef',
        'D-BK.NET/abcdef',
    )

    def test_each_is_read_as_a_link(self):
        for ligne in self.LIGNES:
            with self.subTest(ligne=ligne):
                self.assertTrue(text_build_view._ligne_est_un_lien(ligne))

    def test_each_is_recognised_by_a_reader(self):
        for ligne in self.LIGNES:
            with self.subTest(ligne=ligne):
                self.assertTrue(build_link_import.recognises(ligne))


class ADomainShapedItemNameStaysTextTests(SimpleTestCase):
    """Domains match by structure, not by case; R.I.Pala stays text."""

    def test_none_of_these_dotted_words_is_read_as_a_link(self):
        for candidat in ('R.I.Pala', 'final.build', 'level.up', 'sac.a.dos',
                         'Tank.Force'):
            with self.subTest(candidat=candidat):
                self.assertFalse(text_build_view._ligne_est_un_lien(candidat))


class AnUnknownDomainNeedsAPathToReadAsALinkTests(SimpleTestCase):

    def test_a_path_after_an_unknown_domain_reads_as_a_link(self):
        self.assertTrue(text_build_view._ligne_est_un_lien('example.com/build/42'))

    def test_an_unknown_domain_alone_stays_text(self):
        self.assertFalse(text_build_view._ligne_est_un_lien('example.com'))


class ABareRetroDofusbookLinkReadsAsARetroLinkTests(SimpleTestCase):

    LIEN = 'retro.dofusbook.net/fr/stuff/2558915-bas-level'

    def test_it_is_recognised_without_a_scheme(self):
        self.assertTrue(build_link_import.recognises(self.LIEN))

    def test_it_reads_as_a_retro_build_with_no_network(self):
        from fashionistapulp.structure import get_structure
        item = next(iter(get_structure('retro').items_dict.values()))
        charge = {'stuff': {'name': 'Bas Level', 'character_level': 21},
                 'items': [{'official': item.ankama_id, 'name': item.name}]}
        build = build_link_import.read(self.LIEN,
                                       opener=_dofusbook_opener(charge))
        self.assertEqual('retro', build['game_version'])


class ABareTouchDofusbookLinkReadsAsATouchLinkTests(SimpleTestCase):

    LIEN = 'touch.dofusbook.net/fr/stuff/2558915-bas-level'

    def test_it_is_recognised_without_a_scheme(self):
        self.assertTrue(build_link_import.recognises(self.LIEN))

    def test_it_reads_as_a_touch_build_with_no_network(self):
        from fashionistapulp.structure import get_structure
        item = next(iter(get_structure('touch').items_dict.values()))
        charge = {'stuff': {'name': 'Bas Level', 'character_level': 21},
                 'items': [{'official': item.ankama_id, 'name': item.name}]}
        build = build_link_import.read(self.LIEN,
                                       opener=_dofusbook_opener(charge))
        self.assertEqual('touch', build['game_version'])


class ABareStufferHostLinkReadsAsADofus3LinkTests(SimpleTestCase):
    """Their site writes the same stuff parameter as DofusBook; decoded
    with no request at all, so no fake opener is needed here."""

    LIEN = ('www.dofus-stuffer.is-great.net?stuff=hqEwi6EwzQR+oTFkoTJk'
           'oTNkoTRkoTVkoTYHoTcDoTlkojExAaIyM80D6KExlgDNASxfAAAAoTLMyKEzGKE0'
           'iaE1AqE2BqIxMACiMTEAojEyAKIxMwCiMTQAojE1AKIxNgChNdwAEM1Mh81LNM02'
           '9c1LM81igc0vRM028801vM1WBc07g800IM0bg80DzM1Mjs1ig80eIg==')

    def test_it_is_recognised_without_a_scheme(self):
        self.assertTrue(build_link_import.recognises(self.LIEN))

    def test_it_reads_as_a_dofus3_build_with_no_network(self):
        build = build_link_import.read(self.LIEN)
        self.assertEqual('dofus3', build['game_version'])


class ABareDofuscreatorLinkReadsAsADofuscreatorLinkTests(SimpleTestCase):

    LIEN = 'dofuscreator.com/projet/6e9f4'

    def test_it_is_recognised_without_a_scheme(self):
        self.assertTrue(build_link_import.recognises(self.LIEN))

    def test_it_reads_as_a_dofus3_build_with_no_network(self):
        from fashionistapulp.structure import get_structure
        item = next(iter(get_structure('dofus3').items_dict.values()))
        page = _dofuscreator_page(item.ankama_id)
        build = build_link_import.read(self.LIEN,
                                       opener=_dofuscreator_opener(page))
        self.assertEqual('dofus3', build['game_version'])
        self.assertEqual('Iop', build['char_class'])


class NoItemNameIsEverReadAsABareLinkTests(SimpleTestCase):
    """The bare-address rule must never swallow a pasted item name."""

    def test_no_item_name_in_any_version_or_language_matches_the_rule(self):
        from fashionistapulp.game_versions import version_keys
        from fashionistapulp.structure import get_structure
        from fashionistapulp.translation import SUPPORTED_LANGUAGES
        fautifs = []
        checked = 0
        for version in version_keys():
            structure = get_structure(version)
            for item in structure.items_dict.values():
                noms = {item.name or ''}
                for lang in SUPPORTED_LANGUAGES:
                    nom = structure.get_item_name_in_language(item, lang)
                    if nom:
                        noms.add(nom)
                for nom in noms:
                    candidat = nom.strip()
                    if not candidat:
                        continue
                    checked += 1
                    if text_build_view._ligne_est_un_lien(candidat):
                        fautifs.append((version, candidat))
        self.assertGreater(checked, 1000, checked)
        self.assertEqual([], fautifs, fautifs[:10])


class AnUnknownBareAddressIsNamedAsSuchTests(TestCase):

    def test_an_unrecognised_bare_host_gets_the_not_a_link_message(self):
        page = self.client.post('/import/text/', {'text': 'example.com/build/42'})
        self.assertContains(page, 'cannot read links from that site yet')

    def test_an_unreadable_link_is_listed_once_not_also_as_an_unmatched_line(self):
        page = self.client.post(
            '/import/text/', {'text': 'example.com/build/42\nCoiffe du Bouftou'})
        self.assertEqual(['example.com/build/42'], page.context['unreadable_links'])
        self.assertNotIn('example.com/build/42', page.context['ignored'])
