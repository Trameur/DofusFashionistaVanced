# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Handing a build over to DofusBook by link.

Everything asserted here was measured against their live site on 2026-09-10
and is then replayed offline, so the suite describes what really happens
without touching the network.
"""

import base64
import json

from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from chardata import dofusbook_export


#: The sixteen Ankama ids of a real Dofus 3 build, in their group order.
BUILD = {
    'Cloak': [958],
    'Hat': [14063],
    'Belt': [14081],
    'Boots': [14078],
    'Amulet': [14080],
    'Ring': [14077, 14089],
    'Dofus': [21451, 21452, 21453, 21995, 21996, 21997],
    'Shield': [18670],
    'Weapon': [8098],
    'Pet': [12541],
}

#: The payload that was opened in a browser on 2026-09-10 and put those
#: sixteen items in the sixteen right slots of a DofusBook draft, named the
#: way our own catalogue names them, with their forgemagie panel EMPTY.
CHARGE_MESUREE = (
    'ltwAM80EfgAAAAAABwMAZAABAAAAAAAAAAAAAADNA+gAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAACWAAAAAAAAzMgAmgEBAQEBAgYBAQHcABDNA77NNu/NNwHNNv7NNwDNNv3NNwnNU8vN'
    'U8zNU83NVevNVezNVe3NSO7NH6LNMP0=')


def unpack(octets, position=0):
    """The msgpack subset the payload uses, read back independently.

    Written the other way round from the encoder on purpose: an encoder
    checked against itself proves only that it is consistent.
    """
    tete = octets[position]
    position += 1
    if tete <= 0x7f:
        return tete, position
    if tete == 0xcc:
        return octets[position], position + 1
    if tete == 0xcd:
        return int.from_bytes(octets[position:position + 2], 'big'), position + 2
    if tete == 0xce:
        return int.from_bytes(octets[position:position + 4], 'big'), position + 4
    if 0x90 <= tete <= 0x9f:
        taille = tete & 0x0f
    elif tete == 0xdc:
        taille = int.from_bytes(octets[position:position + 2], 'big')
        position += 2
    else:
        raise AssertionError('byte 0x%02x is not in the payload alphabet' % tete)
    valeurs = []
    for _ in range(taille):
        valeur, position = unpack(octets, position)
        valeurs.append(valeur)
    return valeurs, position


def champs(charge):
    """[fm, points, level, flags, counts, ids] out of a base64 payload."""
    valeurs, position = unpack(base64.b64decode(charge))
    assert position == len(base64.b64decode(charge)), 'trailing bytes'
    return valeurs


class ThePayloadStillMatchesTheOneThatWorkedTests(SimpleTestCase):
    """The format is undocumented and read off a minified bundle, so the only
    honest guard is a payload that was watched arriving."""

    def test_the_measured_build_encodes_byte_for_byte(self):
        groupes = dofusbook_export.group_ankama_ids(BUILD)
        self.assertEqual(CHARGE_MESUREE,
                         dofusbook_export.payload(groupes, 200))

    def test_the_ids_come_out_in_their_group_order(self):
        """Their flat list is positional: only the rank says which slot an id
        lands in, so a reordered group would dress the character wrong."""
        attendus = [958, 14063, 14081, 14078, 14080, 14077, 14089,
                    21451, 21452, 21453, 21995, 21996, 21997,
                    18670, 8098, 12541]
        _fm, _points, level, _flags, counts, ids = champs(CHARGE_MESUREE)
        self.assertEqual(attendus, ids)
        self.assertEqual([1, 1, 1, 1, 1, 2, 6, 1, 1, 1], counts)
        self.assertEqual(200, level)

    def test_a_group_never_overflows_into_the_next_slot(self):
        """from_item_id_list is not the only place a seventh dofus hurts: here
        it would push the shield's id into a dofus slot and the pet into the
        weapon's."""
        trop = dict(BUILD)
        trop['Dofus'] = BUILD['Dofus'] + [99999]
        trop['Ring'] = BUILD['Ring'] + [88888]
        groupes = dofusbook_export.group_ankama_ids(trop)
        self.assertEqual(6, len(groupes[6]))
        self.assertEqual(2, len(groupes[5]))
        self.assertNotIn(99999, [a for g in groupes for a in g])
        self.assertNotIn(88888, [a for g in groupes for a in g])


class AScrollNeverBecomesForgemagieTests(SimpleTestCase):
    """Their decoder reads `t[0][p] >= 100 ? 100 : 0` as the scroll and keeps
    THE REMAINDER as forgemagie. So a raw value in that field is not merely
    lost, it is printed on their page as a bonus the player never had."""

    def _fm(self, scrolls, level=200):
        """Their `t[0]`, the 51 values that carry scroll plus forgemagie."""
        groupes = dofusbook_export.group_ankama_ids(BUILD)
        fm = champs(dofusbook_export.payload(groupes, level,
                                             scrolls=scrolls))[0]
        self.assertEqual(dofusbook_export.FM_LENGTH, len(fm))
        return fm

    def test_a_full_scroll_travels_as_a_hundred(self):
        self.assertEqual(100, self._fm({1: 100})[1])

    def test_a_partial_scroll_travels_as_nothing(self):
        """50 sent as is would read back as +50 forgemagie on wisdom."""
        self.assertEqual(0, self._fm({1: 50})[1])

    def test_touch_hundred_and_fifty_is_cut_to_a_hundred(self):
        """Touch scrolls to 150 and Retro to 101. Sending either whole would
        show up as +50 and +1 of invented forgemagie."""
        fm = self._fm({1: 150, 2: 101})
        self.assertEqual([100, 100], list(fm[1:3]))
        self.assertNotIn(150, list(fm))
        self.assertNotIn(101, list(fm))

    def test_forgemagie_is_never_written(self):
        """Our jets are per item and theirs is one total per characteristic;
        turning one into the other would invent a number. Every index that is
        not one of their six character bases stays at zero."""
        fm = self._fm({})
        for index in range(dofusbook_export.FM_LENGTH):
            if index in dofusbook_export.BASE_INDEXES:
                continue
            self.assertEqual(0, fm[index],
                             'index %d should carry nothing' % index)


class NoInventedForgemagieIsPrintedTests(SimpleTestCase):
    """The failure the plan named in advance: their `Pc` subtracts the naked
    character's own value from six of the fields, so a zero there prints
    "-1050 Vitalite" of forgemagie under the player's name and takes it off
    the totals. Measured on their page at levels 1, 100 and 200 before and
    after: writing their `Gt` values empties the panel."""

    def test_their_character_base_is_reproduced_exactly(self):
        for level, attendu in (
                (1, {0: 55, 6: 6, 7: 3, 9: 100, 11: 1, 23: 1000}),
                (99, {0: 545, 6: 6, 7: 3, 9: 100, 11: 1, 23: 1000}),
                (100, {0: 550, 6: 7, 7: 3, 9: 100, 11: 1, 23: 1000}),
                (200, {0: 1050, 6: 7, 7: 3, 9: 100, 11: 1, 23: 1000})):
            self.assertEqual(attendu, dofusbook_export.character_base(level))

    def test_every_subtracted_field_is_filled(self):
        groupes = dofusbook_export.group_ankama_ids(BUILD)
        fm = champs(dofusbook_export.payload(groupes, 200))[0]
        self.assertEqual(1150, fm[0])  # 1050 plus the forced vitality scroll
        self.assertEqual(7, fm[6])
        self.assertEqual(3, fm[7])
        self.assertEqual(100, fm[9])
        self.assertEqual(0, fm[10])
        self.assertEqual(1, fm[11])
        self.assertEqual(1000, fm[23])

    def test_an_exo_reads_as_one_point_and_not_as_a_hole(self):
        """Their flag adds one to the same field, so the base has to be there
        underneath or the exo prints as minus seven."""
        groupes = dofusbook_export.group_ankama_ids(BUILD)
        fm, _points, level, flags, _counts, _ids = champs(
            dofusbook_export.payload(groupes, 200, exos=7))
        self.assertEqual(7, fm[6])
        self.assertEqual(3, fm[7])
        self.assertEqual(200, level)
        self.assertEqual(7, flags)

    def test_the_vitality_scroll_is_forced_from_level_ten(self):
        """Index 0 has to be the base HP and the scroll at once, and their
        decoder reads any value of 100 or more as a full scroll. Under level
        10 the base HP is small enough for both to be true."""
        self.assertFalse(dofusbook_export.vitality_scroll_is_forced(9))
        self.assertTrue(dofusbook_export.vitality_scroll_is_forced(10))
        self.assertTrue(dofusbook_export.vitality_scroll_is_forced(200))

    def test_a_low_level_without_the_scroll_keeps_the_truth(self):
        groupes = dofusbook_export.group_ankama_ids(BUILD)
        fm = champs(dofusbook_export.payload(groupes, 5))[0]
        # (5 - 1) * 5 + 55 = 75, under their 100 threshold, so no scroll is
        # claimed and the forgemagie still cancels.
        self.assertEqual(75, fm[0])
        fm = champs(dofusbook_export.payload(groupes, 5,
                                             scrolls={0: 100}))[0]
        self.assertEqual(175, fm[0])


class TheExosTravelAsTheirThreeBitsTests(SimpleTestCase):
    """Their `t[3]` adds one AP, MP or range to the forgemagie array, which is
    exactly what an exo is. The bits are read off their own `Nc`."""

    def test_each_exo_sets_its_own_bit(self):
        self.assertEqual(4, dofusbook_export.EXO_AP)
        self.assertEqual(2, dofusbook_export.EXO_MP)
        self.assertEqual(1, dofusbook_export.EXO_RANGE)
        groupes = dofusbook_export.group_ankama_ids(BUILD)
        sans = base64.b64decode(dofusbook_export.payload(groupes, 200))
        avec = base64.b64decode(
            dofusbook_export.payload(groupes, 200, exos=7))
        self.assertNotEqual(sans, avec)
        self.assertIn(b'\xcc\xc8\x07', avec)


class TheLinkPointsAtTheirOwnCatalogueTests(SimpleTestCase):
    """A build lives in one version, and so does the site that must read it."""

    def test_each_version_gets_its_own_host(self):
        for version, hote in (('dofus3', 'www.dofusbook.net'),
                              ('touch', 'touch.dofusbook.net'),
                              ('retro', 'retro.dofusbook.net')):
            url = dofusbook_export.build_url(version, 'fr', 'x')
            self.assertTrue(url.startswith('https://%s/' % hote), url)

    def test_a_version_they_do_not_have_gets_no_link(self):
        """dofus2 and beta have no DofusBook site. Pointing them at www would
        hand the player a catalogue that is not theirs."""
        for version in ('dofus2', 'beta', 'wakfu'):
            self.assertFalse(dofusbook_export.supports(version))
            with self.assertRaises(dofusbook_export.ExportError):
                dofusbook_export.build_url(version, 'fr', 'x')

    def test_a_language_they_do_not_have_falls_back_to_english(self):
        """Their router is `path:"/:lang(fr|es|en)/"`. A German reader sent to
        /de/ gets their catch-all redirect, not the draft."""
        self.assertEqual('fr', dofusbook_export.language_for('fr'))
        self.assertEqual('es', dofusbook_export.language_for('es'))
        for code in ('de', 'pt', 'it', '', None):
            self.assertEqual('en', dofusbook_export.language_for(code))

    def test_the_payload_is_escaped_into_the_query(self):
        """base64 carries +, / and =, and a bare + in a query string is a
        space."""
        url = dofusbook_export.build_url('dofus3', 'fr', 'a+b/c=')
        self.assertIn('stuff=a%2Bb%2Fc%3D', url)


class WhatTheyCannotCarryIsCheckedBeforeTheLinkTests(SimpleTestCase):
    """The measurement this whole page exists for. On retro.dofusbook.net,
    three of the sixteen Ankama ids of a real build are absent from their
    catalogue and their page drops them without a word."""

    RETRO = [11542, 6741, 11545, 8861, 9347, 8877, 11543,
             694, 737, 739, 972, 6980, 7112, 8855, 7753, 6978]
    ABSENTS = (6741, 9347, 7753)

    def _opener(self, connus, erreur=None, vu=None):
        essai = self

        class Reponse(object):
            def __init__(self, contenu):
                self.contenu = contenu

            def read(self, *args):
                return json.dumps(self.contenu).encode('utf-8')

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        def ouvrir(request, timeout=None):
            if vu is not None:
                vu.append(request.full_url)
            # Their site answers 403 to a request that does not look like it
            # came from their own pages.
            essai.assertTrue(request.get_header('Referer', '')
                             .startswith('https://'))
            essai.assertIn('Mozilla', request.get_header('User-agent', ''))
            if erreur is not None:
                raise erreur
            return Reponse({'source': 'database',
                            'data': [{'official': a} for a in connus]})

        return ouvrir

    def _groupes(self):
        plat = list(self.RETRO)
        return dofusbook_export.group_ankama_ids({
            'Cloak': plat[0:1], 'Hat': plat[1:2], 'Belt': plat[2:3],
            'Boots': plat[3:4], 'Amulet': plat[4:5], 'Ring': plat[5:7],
            'Dofus': plat[7:13], 'Shield': plat[13:14],
            'Weapon': plat[14:15], 'Pet': plat[15:16]})

    def test_the_three_they_do_not_have_are_named(self):
        groupes = self._groupes()
        connus = dofusbook_export.known_ankama_ids(
            'retro', groupes,
            opener=self._opener([a for a in self.RETRO
                                 if a not in self.ABSENTS]))
        self.assertEqual(13, len(connus))
        for absent in self.ABSENTS:
            self.assertNotIn(absent, connus)

    def test_what_they_do_not_have_is_left_out_of_the_payload(self):
        """Leaving them in would not break their page, it would silently give
        the player a build with three holes."""
        groupes = self._groupes()
        connus = set(a for a in self.RETRO if a not in self.ABSENTS)
        gardes = dofusbook_export.keep_known(groupes, connus)
        restants = [a for groupe in gardes for a in groupe]
        self.assertEqual(13, len(restants))
        for absent in self.ABSENTS:
            self.assertNotIn(absent, restants)
        self.assertEqual([], gardes[1])
        self.assertEqual([], gardes[4])
        self.assertEqual([], gardes[8])

    def test_the_question_is_asked_with_their_slot_codes(self):
        vu = []
        dofusbook_export.known_ankama_ids(
            'retro', self._groupes(),
            opener=self._opener(self.RETRO, vu=vu))
        self.assertEqual(1, len(vu))
        self.assertIn('retro.dofusbook.net/api/items/', vu[0])
        for code, ankama in (('ca', 11542), ('ch', 6741), ('a2', 11543),
                             ('d6', 7112), ('br', 8855), ('ar', 7753),
                             ('fa', 6978)):
            self.assertIn('%s-%d' % (code, ankama), vu[0])

    def test_a_site_we_cannot_reach_gives_a_reason_and_no_link(self):
        import urllib.error
        for erreur, raison in (
                (urllib.error.HTTPError('u', 403, 'no', None, None), 'refused'),
                (OSError('down'), 'unreachable')):
            with self.assertRaises(dofusbook_export.ExportError) as pris:
                dofusbook_export.known_ankama_ids(
                    'retro', self._groupes(),
                    opener=self._opener(self.RETRO, erreur=erreur))
            self.assertEqual(raison, pris.exception.reason)


class ThePageSaysWhatDoesNotTravelTests(TestCase):
    """The page is worth more than a plain link only if it tells the player
    what will be missing on the other side."""

    def _char(self, noms):
        from chardata.models import Char
        from fashionistapulp.structure import (get_structure,
                                               set_current_game_version)
        set_current_game_version('dofus3')
        structure = get_structure('dofus3')
        textes = []
        for type_name in noms:
            item = next(i for i in structure.types[200][type_name]
                        if not i.removed and i.ankama_id)
            textes.append(structure.get_item_name_in_language(item, 'en'))
        self.client.post('/import/text/', {
            'text': '\n'.join(textes),
            'confirm': '1', 'char_class': 'Cra', 'level': '200'})
        return Char.objects.order_by('-id').first()

    def _page(self, char, connus):
        from unittest import mock

        class Reponse(object):
            def read(self, *args):
                return json.dumps(
                    {'data': [{'official': a} for a in connus]}).encode('utf-8')

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        with mock.patch('chardata.dofusbook_export.urllib.request.urlopen',
                        return_value=Reponse()):
            reponse = self.client.get('/export/dofusbook/%d/' % char.id)
        return reponse

    def test_an_item_they_do_not_carry_is_named_and_left_out(self):
        char = self._char(['Hat', 'Cloak'])
        from chardata.solution import get_solution
        porte = get_solution(char).items
        chapeau = porte['Hat'][0]
        cape = porte['Cloak'][0]
        reponse = self._page(char, [cape.ankama_id])
        self.assertEqual(200, reponse.status_code)
        page = reponse.content.decode('utf-8')
        # The one they know travels, the one they do not is named as staying.
        self.assertIn(cape.localized_name or cape.name, page)
        self.assertIn(chapeau.localized_name or chapeau.name, page)
        self.assertIn('stay here', page)
        # And it really is out of the link, not merely mentioned.
        lien = [l for l in page.split('"') if 'dofus-stuffer' in l][0]
        charge = base64.b64decode(
            lien.split('stuff=')[1].replace('%2B', '+').replace('%2F', '/')
            .replace('%3D', '='))
        self.assertIn(b'\xcd' + cape.ankama_id.to_bytes(2, 'big'), charge)
        self.assertNotIn(b'\xcd' + chapeau.ankama_id.to_bytes(2, 'big'),
                         charge)

    def test_a_site_that_refuses_gives_no_link_at_all(self):
        """Without their answer we cannot say which pieces would survive, and
        a link handed over blind is exactly the failure this page prevents."""
        from unittest import mock
        char = self._char(['Hat'])
        with mock.patch('chardata.dofusbook_export.urllib.request.urlopen',
                        side_effect=OSError('down')):
            page = self.client.get(
                '/export/dofusbook/%d/' % char.id).content.decode('utf-8')
        self.assertNotIn('dofus-stuffer', page)
        self.assertIn('could not be reached', page)

    def test_the_button_is_absent_from_a_version_they_do_not_have(self):
        self.assertFalse(dofusbook_export.supports('dofus2'))
        self.assertFalse(dofusbook_export.supports('beta'))


class TheExportPageSpeaksEveryLanguageTests(SimpleTestCase):
    """A page shipped in English only is a page half the readers cannot use,
    and the .mo is what serves them: an entry marked fuzzy reads fine in the
    .po and is silently ignored here."""

    CHAINES = (
        'Open this build on DofusBook',
        'These pieces travel:',
        'DofusBook does not have these in its catalogue, so they stay here:',
        'DofusBook stores a scroll as 100 or nothing, so these do not travel '
        'in full:',
        'The build name, the class and your rolls do not travel: their link '
        'format has no room for them.',
        'Open on DofusBook',
        'Your build stays here, untouched. The link only fills a draft on '
        'their site.',
        'Back to the build',
        'DofusBook has no site for this version of the game.',
        'This build has no gear to send.',
        'DofusBook will show a full Vitality scroll: for a character of this '
        'level its link format cannot say anything else.',
    )

    def test_every_string_is_translated_in_the_four_other_languages(self):
        from django.utils.translation import gettext, override
        muettes = []
        for langue in ('fr', 'es', 'pt', 'de'):
            with override(langue):
                for chaine in self.CHAINES:
                    if gettext(chaine) == chaine:
                        muettes.append((langue, chaine))
        self.assertEqual([], muettes)


class TheExportPageAnswersUnderBothUrlTablesTests(TestCase):
    """The site has two url tables, `game_urls.py` for the version prefixes
    and `urls.py` for the bare paths. The DofusBook import page shipped in
    only one of them and answered 404 under `/`."""

    def test_the_route_exists_with_and_without_a_version_prefix(self):
        self.assertEqual('/export/dofusbook/42/',
                         reverse('dofusbook_export', args=[42]))
        self.assertEqual('/retro/export/dofusbook/42/',
                         reverse('retro:dofusbook_export', args=[42]))
        self.assertEqual('/touch/export/dofusbook/42/',
                         reverse('touch:dofusbook_export', args=[42]))
