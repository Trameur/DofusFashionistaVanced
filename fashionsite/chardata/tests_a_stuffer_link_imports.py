# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A DofusBook stuffer link comes back in through the import.

On 2026-09-18 Thibaud pasted a touch.dofusbook.net link ending in
`dofus-stuffer/objets?stuff=...` and the page answered that it could not
read that site. Its reader only knew public build links, which carry an id;
a stuffer link carries the whole build in its parameter and no id. Our own
export writes that link, so the site could not read back what it hands out.
The tail of his link (ids, counts, level 200, exo byte 6, 99 wisdom and 374
chance invested) is byte for byte what our encoder writes for those values;
the builds below reuse it.
"""
import base64

from django.test import SimpleTestCase, TestCase

from chardata import build_link_import, dofusbook_export
from chardata.dofusbook_import import (ImportError_, parse_link,
                                       parse_stuffer_link)

#: The pieces of his link, in their group order.
IDS = [14085, 8699, 19943, 19947, 14086, 12113, 19941, 13344, 13783, 694,
       7043, 7754, 16035]
COUNTS = [1, 1, 1, 1, 1, 2, 5, 0, 1, 0]


def _grouped():
    grouped, at = [], 0
    for count in COUNTS:
        grouped.append(IDS[at:at + count])
        at += count
    return grouped


def _link(version='touch', **payload):
    options = dict(points={1: 99, 4: 374}, scrolls={i: 100 for i in range(6)},
                   exos=dofusbook_export.EXO_AP | dofusbook_export.EXO_MP,
                   forge={0: 1050, 2: 30, 6: 3, 20: 12})
    options.update(payload)
    stuff = dofusbook_export.payload(_grouped(), 200, **options)
    return dofusbook_export.build_url(version, 'fr', stuff)


def _raw_link(value, host='touch.dofusbook.net'):
    stuff = base64.b64encode(dofusbook_export._pack(value)).decode('ascii')
    return ('https://%s/desktop/fr/equipement/dofus-stuffer/objets?stuff=%s'
            % (host, stuff.replace('+', '%2B').replace('/', '%2F')))


class AStufferLinkReadsBackWhatTheExportWroteTests(TestCase):

    def test_the_pieces_level_points_scrolls_and_exos_come_back(self):
        from fashionistapulp.structure import get_structure
        build = build_link_import.read(_link())
        structure = get_structure('touch')
        self.assertEqual('touch', build['game_version'])
        self.assertEqual(200, build['level'])
        self.assertEqual([], build['missing'])
        self.assertEqual(IDS, [structure.get_item_by_id(i).ankama_id
                               for i in build['item_ids']])
        self.assertEqual({'Wisdom': 99, 'Chance': 374}, build['base_points'])
        self.assertEqual(6, len(build['base_scrolled']))
        self.assertEqual({'ap_exo': True, 'mp_exo': True, 'range_exo': False},
                         build['exo_options'])

    def test_its_forgemagie_comes_back_as_totals_for_no_piece(self):
        """Their `Pc` shows the totals less the naked character, and the
        exo point is the option, not forgemagie."""
        build = build_link_import.read(_link())
        self.assertEqual({'vi': 1050, 'fo': 30, 'pa': 3, 'dmg': 12},
                         build['fm_global'])
        self.assertEqual({}, build['rolls'])

    def test_the_version_is_the_host(self):
        for version in ('dofus3', 'touch'):
            with self.subTest(version=version):
                self.assertEqual(version, build_link_import.read(
                    _link(version, forge={}))['game_version'])

    def test_pieces_the_host_version_lacks_are_refused(self):
        """The same floor as a public build: most of these Touch pieces
        are not in the Retro catalogue."""
        with self.assertRaises(ImportError_) as caught:
            build_link_import.read(_link('retro'))
        self.assertEqual('wrong_version', caught.exception.reason)


class AStufferLinkIsReadLikeTheirDecoderReadsItTests(TestCase):
    """The defaults of their `Nc`, read off index-desktop-CdEmUrEc.js."""

    def test_a_group_with_no_count_holds_one_piece(self):
        link = _raw_link([[0] * 51, [0] * 6, 200, 0, [1, 1], IDS[:3]])
        build = build_link_import.read(link)
        self.assertEqual(3, len(build['item_ids']))

    def test_a_short_total_list_reads_as_zeros(self):
        link = _raw_link([[500], [0] * 6, 200, 0, [1], IDS[:1]])
        build = build_link_import.read(link)
        self.assertEqual({'Vitality': 100}, build['base_scrolled'])

    def test_a_plus_turned_into_a_space_still_reads(self):
        stuff = dofusbook_export.payload(_grouped(), 10)
        self.assertIn('+', stuff)
        spaced = stuff.replace('+', ' ')
        self.assertEqual(dofusbook_export.read_payload(stuff),
                         dofusbook_export.read_payload(spaced))


class AStufferLinkThatIsNoBuildIsRefusedTests(SimpleTestCase):
    """Refused as a damaged link, and never fetched: nothing on this path
    goes to their site."""

    def _reason(self, link):
        with self.assertRaises(ImportError_) as caught:
            build_link_import.read(link)
        return caught.exception.reason

    def test_what_is_not_base64_is_refused(self):
        self.assertEqual('bad_link', self._reason(
            'https://touch.dofusbook.net/desktop/fr/equipement/'
            'dofus-stuffer/objets?stuff=%%%%not-a-build'))

    def test_what_is_not_a_list_of_numbers_is_refused(self):
        stuff = base64.b64encode(b'\x81\x01\x02').decode('ascii')
        self.assertEqual('bad_link', self._reason(
            'https://touch.dofusbook.net/x?stuff=' + stuff))

    def test_bytes_after_the_build_are_refused(self):
        stuff = parse_stuffer_link(_link())[1]
        brut = base64.b64decode(stuff) + b'\x00'
        self.assertEqual('bad_link', self._reason(
            'https://touch.dofusbook.net/x?stuff=%s'
            % base64.b64encode(brut).decode('ascii').replace('+', '%2B')))

    def test_a_parameter_longer_than_any_build_is_refused(self):
        self.assertEqual('bad_link', self._reason(
            'https://touch.dofusbook.net/x?stuff=' + 'A' * 5000))


class AStufferLinkIsRecognisedTests(SimpleTestCase):

    def test_on_each_of_their_hosts(self):
        for host in ('www.dofusbook.net', 'retro.dofusbook.net',
                     'touch.dofusbook.net'):
            with self.subTest(host=host):
                self.assertTrue(build_link_import.recognises(
                    'https://%s/desktop/fr/equipement/dofus-stuffer/objets'
                    '?stuff=kA' % host))

    def test_not_elsewhere_nor_without_the_parameter(self):
        self.assertFalse(build_link_import.recognises(
            'https://example.com/objets?stuff=kA'))
        self.assertIsNone(parse_stuffer_link(
            'https://touch.dofusbook.net/desktop/fr/equipement/'
            'dofus-stuffer/objets'))

    def test_a_public_build_link_is_still_read_by_its_id(self):
        self.assertIsNone(parse_stuffer_link(
            'https://www.dofusbook.net/fr/equipement/7894460-zobal/objets'))
        self.assertEqual(('www.dofusbook.net', '7894460'), parse_link(
            'https://www.dofusbook.net/fr/equipement/7894460-zobal/objets'))


class TheImportPageTakesAStufferLinkTests(TestCase):

    def test_the_preview_names_the_version_and_the_exos(self):
        page = self.client.post('/import/text/', {'text': _link()})
        self.assertContains(page, 'id="import-link-read"')
        self.assertContains(page, 'Read from the link (Touch).')
        self.assertContains(page, "exo options: AP, MP.")
        self.assertContains(page, 'id="import-link-fm-global"')

    def test_a_truncated_link_is_called_damaged_not_unreadable(self):
        """Nothing was fetched, so blaming their site would be false."""
        page = self.client.post('/import/text/', {'text': _link()[:-40]})
        self.assertContains(page, 'That link is incomplete or damaged.')
        self.assertNotContains(page, 'That site answered')

    def test_confirming_creates_the_build_with_its_exo_options(self):
        from chardata.models import Char, CharBaseStats
        from chardata.options import get_options
        from chardata.solution import get_solution
        from fashionistapulp.structure import set_current_game_version
        reponse = self.client.post('/import/text/', {
            'text': _link(), 'confirm': '1', 'char_class': 'Iop',
            'level': '200'})
        self.assertEqual(302, reponse.status_code)
        char = Char.objects.order_by('-id').first()
        self.assertEqual('touch', char.game_version)
        options = get_options(char)
        self.assertEqual((True, True, False), (
            options.get('ap_exo'), options.get('mp_exo'),
            bool(options.get('range_exo'))))
        # The page reads the build under /touch/; this thread is on dofus3,
        # where four of these pieces do not exist.
        set_current_game_version('touch')
        self.addCleanup(set_current_game_version, 'dofus3')
        portes = [item for item in get_solution(char).item_list or []
                  if item.name != 'NoItem']
        self.assertEqual(len(IDS), len(portes))
        chance = CharBaseStats.objects.get(char=char, stat='Chance')
        self.assertEqual((474, 100), (chance.total_value, chance.scrolled_value))


class TheLinkIsTheWholeStatementTests(TestCase):
    """What the review of 2026-09-18 reproduced: a new level 200 build starts
    with the AP and MP exo options on and every characteristic fully
    scrolled, and a link that says otherwise used to be overruled."""

    def _created(self, link):
        from chardata.models import Char
        self.client.post('/import/text/', {
            'text': link, 'confirm': '1', 'char_class': 'Iop', 'level': '200'})
        return Char.objects.order_by('-id').first()

    def _exos(self, char):
        from chardata.options import get_options
        options = get_options(char)
        return tuple(bool(options.get(key))
                     for key in ('ap_exo', 'mp_exo', 'range_exo'))

    def test_a_link_with_no_exo_turns_the_options_off(self):
        char = self._created(_link('dofus3', exos=0, forge={}))
        self.assertEqual((False, False, False), self._exos(char))

    def test_a_range_exo_alone_is_the_only_option_on(self):
        char = self._created(_link(exos=dofusbook_export.EXO_RANGE, forge={}))
        self.assertEqual((False, False, True), self._exos(char))

    def test_an_unscrolled_characteristic_stays_unscrolled(self):
        """Their vitality field always reads scrolled from level 10 on (see
        dofusbook_export.vitality_scroll_is_forced); the other five follow
        the link."""
        from chardata.models import CharBaseStats
        char = self._created(_link(scrolls={}, points={4: 374}, forge={}))
        rows = {row.stat: (row.total_value, row.scrolled_value)
                for row in CharBaseStats.objects.filter(char=char)}
        self.assertEqual((374, 0), rows['Chance'])
        self.assertEqual((0, 0), rows['Strength'])
        self.assertEqual(100, rows['Vitality'][1])


class ADamagedStufferLinkIsNeverFetchedTests(SimpleTestCase):

    def _refused_without_a_request(self, link):
        requests = []

        def opener(request, timeout=None):
            requests.append(request.full_url)
            raise AssertionError('fetched %s' % request.full_url)

        with self.assertRaises(ImportError_) as caught:
            build_link_import.read(link, opener=opener)
        self.assertEqual([], requests)
        return caught.exception.reason

    def test_points_no_build_can_hold_are_refused(self):
        link = _raw_link([[0] * 51, [0, 10 ** 9, 0, 0, 0, 0], 200, 0,
                          COUNTS, IDS])
        self.assertEqual('bad_link', self._refused_without_a_request(link))

    def test_a_mangled_parameter_is_not_read_as_a_build_id(self):
        """Digits inside the base64 used to be taken for a public build id."""
        link = ('https://touch.dofusbook.net/desktop/fr/equipement/'
                'dofus-stuffer/objets?stuff%3DkZ/1234567AAAA')
        self.assertIsNone(parse_link(link))
        self.assertEqual('bad_link', self._refused_without_a_request(link))

    def test_a_link_pasted_without_its_scheme_keeps_its_parameter(self):
        stuff = dofusbook_export.payload(_grouped(), 200,
                                         forge={20: -1, 21: -1, 22: -1})
        self.assertIn('//', stuff)
        link = ('www.dofusbook.net/desktop/fr/equipement/dofus-stuffer/'
                'objets?stuff=' + stuff)
        host, read = parse_stuffer_link(link)
        self.assertEqual('www.dofusbook.net', host)
        # Unencoded, its '+' comes back a space, which their decoder and ours
        # turn back into '+'.
        self.assertEqual(dofusbook_export.read_payload(stuff),
                         dofusbook_export.read_payload(read))


class TheExportKeepsTheVitalityScrollReadableTests(SimpleTestCase):
    """Their decoder derives the vitality scroll from the same field as its
    forgemagie; a total that carries the field across a hundred would be read
    back as another scroll and another forgemagie."""

    def test_a_total_that_crosses_a_hundred_is_refused(self):
        self.assertEqual(({}, [0]), dofusbook_export.carriable_forge(
            {0: 5}, {}, level=9))
        self.assertEqual(({}, [0]), dofusbook_export.carriable_forge(
            {0: -400}, {0: 100}, level=50))

    def test_one_that_stays_on_its_side_travels(self):
        self.assertEqual(({0: 50}, []), dofusbook_export.carriable_forge(
            {0: 50}, {0: 100}, level=200))
        lu = dofusbook_export.read_payload(dofusbook_export.payload(
            _grouped(), 200, scrolls={0: 100}, forge={0: 50}))
        self.assertEqual({0: 50}, {k: v for k, v in
                                   dofusbook_export.global_forge(lu).items()
                                   if k == 0})
