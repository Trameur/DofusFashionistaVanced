# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Handing a build over to DofusBook by link.

Everything asserted here was measured against their live site on 2026-09-10
and is then replayed offline, so the suite describes what really happens
without touching the network.
"""

import base64
import io
import json
import os
import re

from django.conf import settings
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
    # A forgemagie takes a line below its catalogue minimum as often as above
    # its maximum, so the payload carries negatives too. Their decoder is the
    # whole msgpack; these four shapes are the ones ours writes.
    if tete >= 0xe0:
        # A negative fixint carries no payload byte: the head IS the value.
        return tete - 0x100, position
    if tete == 0xd0:
        return int.from_bytes(octets[position:position + 1], 'big',
                              signed=True), position + 1
    if tete == 0xd1:
        return int.from_bytes(octets[position:position + 2], 'big',
                              signed=True), position + 2
    if tete == 0xd2:
        return int.from_bytes(octets[position:position + 4], 'big',
                              signed=True), position + 4
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

    def test_a_build_with_no_forgemagie_writes_none(self):
        """The forgemagie travels since 2026-09-11, so the guard is no longer
        that the field is always empty but that nothing fills it on its own:
        a build with no rolls leaves every position at the character's own
        base, which is what makes their panel show nothing."""
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

    #: The reasons never reach the template as literals, so they are named
    #: here; everything the reader actually sees is READ OFF the template.
    RAISONS = (
        'DofusBook has no site for this version of the game.',
        'This build has no gear to send.',
    )

    #: The gettext of a template, `{% trans "..." %}` only. A hand written
    #: copy of the page's strings answers the question of the day it was
    #: written and goes stale silently: this list stayed behind on
    #: 2026-09-11 when a sentence was replaced, and the suite blamed the new
    #: page for a string it no longer carries.
    MOTIF = re.compile(r'{%\s*trans\s+"((?:[^"\\]|\\.)*)"\s*%}')
    GABARIT = ('fashionsite/chardata/templates/chardata/'
               'dofusbook_export.html')

    def chaines(self):
        chemin = os.path.join(settings.BASE_DIR, '..', self.GABARIT)
        texte = io.open(os.path.normpath(chemin), encoding='utf-8').read()
        vues = []
        for brut in self.MOTIF.findall(texte):
            msgid = brut.replace('\\"', '"')
            if msgid not in vues:
                vues.append(msgid)
        return vues

    def test_the_template_is_read_and_not_a_copy_of_it(self):
        """The scan is only worth something if it finds the page."""
        vues = self.chaines()
        self.assertGreaterEqual(len(vues), 12)
        self.assertIn('Open on DofusBook', vues)

    def test_every_string_is_translated_in_the_four_other_languages(self):
        from django.utils.translation import gettext, override
        muettes = []
        for langue in ('fr', 'es', 'pt', 'de'):
            with override(langue):
                for chaine in list(self.chaines()) + list(self.RAISONS):
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


class TheirOwnNumbersAreTheBaselineTests(SimpleTestCase):
    """A forgemagie total is a difference, so it is only as true as the
    number it is measured against. That number has to be THEIRS: the two
    catalogues do not always agree, and ours would print a forgemagie the
    player never forged."""

    #: Their own answer for two pieces of build 23227661, copied from
    #: /api/items/x/stuffer/ on 2026-09-11.
    LEURS = [
        {'official': 14094, 'name': 'Amulette du Strigide', 'effects': [
            {'id': 130, 'name': 'vi', 'type': 'E', 'min': 351, 'max': 400},
            {'id': 200, 'name': 'cc', 'type': 'E', 'min': 4, 'max': 6},
            {'id': 210, 'name': 'pa', 'type': 'E', 'min': 1, 'max': 1},
            {'id': 430, 'name': 'rc', 'type': 'E', 'min': -16, 'max': -20},
        ]},
        {'official': 32235, 'name': 'Arc de Culbutoeuf', 'effects': [
            {'id': 10, 'name': 'dn', 'type': 'D', 'min': 34, 'max': 41},
            {'id': 130, 'name': 'vi', 'type': 'E', 'min': 351, 'max': 400},
            {'id': 320, 'name': 'pp', 'type': 'E', 'min': 11, 'max': 15},
        ]},
        {'official': 7112, 'name': 'Dofus Tachete', 'effects': [
            {'id': 430, 'name': 'rc', 'type': 'E', 'min': 30, 'max': 30},
            {'id': 705, 'name': 'sp', 'type': 'O', 'min': 18888, 'max': 1},
        ]},
    ]

    def test_a_line_counts_for_what_their_own_sheet_counts(self):
        """Their `Pc` sums `c.max > 0 ? c.max : c.min` over the effects of
        type E. The Strigide amulet is the case that matters: its critical
        resistance runs from -16 to -20, so their sheet counts -16 while our
        catalogue holds -20."""
        valeurs = dofusbook_export.their_line_values(self.LEURS)
        self.assertEqual(400, valeurs[14094]['vi'])
        self.assertEqual(6, valeurs[14094]['cc'])
        self.assertEqual(-16, valeurs[14094]['rc'])
        self.assertEqual(30, valeurs[7112]['rc'])

    def test_a_weapon_damage_line_and_a_spell_are_not_characteristics(self):
        """Their D lines are the weapon's own damage and their O lines a
        spell; neither lands on a characteristic, and reading one as a
        baseline would make every total on that piece wrong."""
        valeurs = dofusbook_export.their_line_values(self.LEURS)
        self.assertNotIn('dn', valeurs[32235])
        self.assertNotIn('sp', valeurs[7112])
        self.assertEqual({'vi': 400, 'pp': 15}, valeurs[32235])

    def test_the_ids_and_the_values_come_from_one_answer(self):
        """Two calls would be two answers, and a piece known by the first and
        missing from the second would export with no baseline at all."""
        self.assertEqual({14094, 32235, 7112},
                         dofusbook_export.ids_of(self.LEURS))


class TheForgemagieTravelsAsOneTotalTests(SimpleTestCase):
    """Thibaud, 2026-09-11: "l'export ne met pas bien les FM". Their `fm` is
    one number per characteristic, and which number goes where is decided by
    their `ve` array alone."""

    def test_their_positions_are_the_ones_read_off_their_bundle(self):
        """`ve` was copied from index-desktop-CIlE29DC.js on 2026-09-11, and
        the positions their own decoder treats specially are the proof it is
        not shifted: their `Nc` bumps 6, 7 and 10 from the flag byte and
        their `Pc` subtracts the character's own base at 0, 6, 7, 9, 11 and
        23."""
        ve = dofusbook_export.VE
        self.assertEqual(52, len(ve))
        self.assertEqual(('pa', 'pm', 'po'), (ve[6], ve[7], ve[10]))
        self.assertEqual(('vi', 'pp', 'ic', 'pd'),
                         (ve[0], ve[9], ve[11], ve[23]))
        self.assertEqual((6, 7, 10), dofusbook_export.EXO_INDEXES)
        # Their loop is `p < 51`, so the last code is never read from a link.
        self.assertEqual('rw', ve[dofusbook_export.FM_LENGTH])

    def test_every_position_they_read_has_one_of_our_characteristics(self):
        table = dofusbook_export.index_by_stat_key()
        self.assertEqual(set(range(dofusbook_export.FM_LENGTH)),
                         set(table.values()))
        self.assertEqual(dofusbook_export.FM_LENGTH, len(table))
        self.assertEqual(16, table['ch'])
        self.assertEqual(22, table['cridam'])
        self.assertEqual(20, table['dam'])

    def test_what_their_array_cannot_name_is_left_without_a_position(self):
        """Critical failure has no code in their `ve` at all, and the weapon
        resistance percentage sits at the position their loop stops before.
        Neither may borrow a neighbour."""
        table = dofusbook_export.index_by_stat_key()
        self.assertNotIn('cf', table)
        self.assertNotIn('resperwea', table)

    def _fm(self, forge, scrolls=None, level=200):
        groupes = dofusbook_export.group_ankama_ids(BUILD)
        charge = dofusbook_export.payload(groupes, level, scrolls=scrolls,
                                          forge=forge)
        return champs(charge)[0]

    def test_a_total_lands_on_its_own_position_and_nowhere_else(self):
        fm = self._fm({22: 8, 20: 20})
        self.assertEqual(8, fm[22])
        self.assertEqual(20, fm[20])
        self.assertEqual(0, fm[21])
        self.assertEqual(0, fm[19])

    def test_a_total_is_added_to_the_base_their_decoder_takes_back(self):
        """Their `Pc` subtracts the character's own value at six positions,
        so a total written raw there would come out short by exactly that
        base: 1000 pods less, 100 prospecting less."""
        fm = self._fm({23: 50, 9: 7})
        self.assertEqual(1050, fm[23])
        self.assertEqual(107, fm[9])

    def test_a_total_shares_the_field_with_the_scroll(self):
        """For the six base characteristics their field is scroll plus
        forgemagie, split at a hundred by their own decoder."""
        fm = self._fm({1: 12}, scrolls={1: 100})
        self.assertEqual(112, fm[1])
        self.assertEqual(12, self._fm({1: 12})[1])

    def test_a_negative_total_survives_the_round_trip(self):
        """A forgemagie takes a line below its minimum as readily as above
        its maximum, and their decoder is the whole msgpack."""
        for valeur in (-1, -32, -33, -200, -40000):
            with self.subTest(valeur=valeur):
                self.assertEqual(valeur, self._fm({20: valeur})[20])

    def test_the_vitality_field_still_hides_its_scroll_and_its_base(self):
        fm = self._fm({0: 30}, scrolls={0: 100})
        # 1050 of base HP at level 200, the 100 their decoder reads as the
        # scroll, and the forgemagie on top.
        self.assertEqual(1050 + 100 + 30, fm[0])

    def test_a_base_characteristic_refuses_what_their_field_cannot_hold(self):
        """Their decoder reads the scroll as `value >= 100 ? 100 : 0` and
        keeps the rest. So under a full scroll a negative total would read as
        NO scroll, and with no scroll a total of a hundred would invent one.
        Both are refused and named rather than sent wrong."""
        garde, refuses = dofusbook_export.carriable_forge(
            {1: -12, 2: 120, 3: 40}, scrolls={1: 100, 2: 0, 3: 0})
        self.assertEqual({3: 40}, garde)
        self.assertEqual([1, 2], refuses)

    def test_a_negative_total_is_fine_once_it_is_past_their_six(self):
        garde, refuses = dofusbook_export.carriable_forge({20: -40})
        self.assertEqual({20: -40}, garde)
        self.assertEqual([], refuses)

    def test_an_exo_never_travels_as_a_total(self):
        """The game gives one exo point per characteristic for the whole
        build and their format carries that as a single bit. Summing two
        pieces into the field would print two points."""
        garde, refuses = dofusbook_export.carriable_forge({6: 1, 7: 1, 10: 1})
        self.assertEqual({}, garde)
        self.assertEqual([], refuses)
        self.assertEqual({6: dofusbook_export.EXO_AP,
                          7: dofusbook_export.EXO_MP,
                          10: dofusbook_export.EXO_RANGE},
                         dofusbook_export.EXO_BIT_BY_INDEX)


class ThePageSendsTheForgemagieItShowsTests(TestCase):
    """From the build to the query string, with their own answer in the
    middle. The unit tests above fix the arithmetic; this one checks that the
    page actually asks for it and puts the result in the link."""

    def _char(self):
        from chardata.models import Char
        from fashionistapulp.structure import (get_structure,
                                               set_current_game_version)
        set_current_game_version('dofus3')
        structure = get_structure('dofus3')
        item = next(i for i in structure.types[200]['Hat']
                    if not i.removed and i.ankama_id)
        self.client.post('/import/text/', {
            'text': structure.get_item_name_in_language(item, 'en'),
            'confirm': '1', 'char_class': 'Cra', 'level': '200'})
        return Char.objects.order_by('-id').first(), item

    def _page(self, char, entrees, langue='en'):
        from unittest import mock

        class Reponse(object):
            def read(self, *args):
                return json.dumps({'data': entrees}).encode('utf-8')

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        with mock.patch('chardata.dofusbook_export.urllib.request.urlopen',
                        return_value=Reponse()):
            return self.client.get('/export/dofusbook/%d/' % char.id,
                                   HTTP_ACCEPT_LANGUAGE=langue)

    def _charge(self, page):
        import urllib.parse
        trouve = re.search(r'stuff=([^"&\'<> ]+)', page)
        self.assertTrue(trouve, 'no link on the page')
        return champs(urllib.parse.unquote(trouve.group(1)))

    def test_a_roll_leaves_as_the_difference_with_their_own_number(self):
        """The player's value minus what THEIR catalogue gives the same
        piece, at the position their `ve` names. Their number is deliberately
        one point off ours here: the total has to follow theirs, because
        their page adds their own."""
        from chardata.lock_forbid import set_stat_overrides
        from fashionistapulp.structure import get_structure
        char, item = self._char()
        structure = get_structure('dofus3')
        vitalite = structure.get_stat_by_key('vit')
        critiques = structure.get_stat_by_key('cridam')
        notre_max = dict(item.stats)[vitalite.id]
        set_stat_overrides(char, {item.id: {vitalite.id: notre_max + 9,
                                            critiques.id: 8}})
        entrees = [{'official': item.ankama_id, 'effects': [
            {'name': 'vi', 'type': 'E', 'min': 1, 'max': notre_max - 1}]}]
        page = self._page(char, entrees).content.decode('utf-8')
        fm, _points, _level, _flags, _counts, _ids = self._charge(page)
        table = dofusbook_export.index_by_stat_key()
        # Their number is one below ours, so the player's nine points of
        # forgemagie read as ten from where their sheet starts.
        self.assertEqual(1050 + 100 + 10, fm[table['vit']])
        # A line their piece does not carry at all: the whole value travels.
        self.assertEqual(8, fm[table['cridam']])
        self.assertIn('one total per characteristic', page)

    def test_a_roll_read_as_an_exo_travels_as_their_bit(self):
        """One exo point per characteristic for the whole build is the game's
        rule and their flag byte is how their format holds it. Two pieces
        carrying the same exo must not arrive as two points."""
        from chardata.lock_forbid import set_stat_overrides
        from fashionistapulp.structure import get_structure
        char, item = self._char()
        structure = get_structure('dofus3')
        pm = structure.get_stat_by_key('mp')
        self.assertNotIn(pm.id, dict(item.stats))
        set_stat_overrides(char, {item.id: {pm.id: 1}})
        entrees = [{'official': item.ankama_id, 'effects': []}]
        page = self._page(char, entrees).content.decode('utf-8')
        fm, _points, _level, flags, _counts, _ids = self._charge(page)
        self.assertEqual(dofusbook_export.EXO_MP,
                         flags & dofusbook_export.EXO_MP)
        # Their `Nc` adds the point itself; the field keeps the character's
        # own three MP and nothing more.
        self.assertEqual(3, fm[dofusbook_export.index_by_stat_key()['mp']])

    def test_a_characteristic_their_field_cannot_hold_is_named(self):
        """Critical failure has no position in their `ve` at all. The page
        says so before the player leaves, in their language."""
        from chardata.lock_forbid import set_stat_overrides
        from fashionistapulp.structure import get_structure
        char, item = self._char()
        structure = get_structure('dofus3')
        echec = structure.get_stat_by_key('cf')
        set_stat_overrides(char, {item.id: {echec.id: 3}})
        entrees = [{'official': item.ankama_id, 'effects': []}]
        page = self._page(char, entrees).content.decode('utf-8')
        self.assertIn('export-forge-staying', page)
        self.assertIn('cannot hold these', page)
        francaise = self._page(char, entrees, langue='fr').content.decode('utf-8')
        self.assertIn('ne peut pas porter', francaise)

    def test_a_build_with_no_roll_says_nothing_about_forgemagie(self):
        char, item = self._char()
        entrees = [{'official': item.ankama_id, 'effects': []}]
        page = self._page(char, entrees).content.decode('utf-8')
        self.assertNotIn('export-forge', page)
        self.assertIn('The build name and the class do not travel', page)
