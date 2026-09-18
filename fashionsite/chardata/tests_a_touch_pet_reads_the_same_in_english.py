# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A Touch pet's English encyclopedia page gives the lines of its French one.

On 2026-09-18 the French pages of Blue Piwin, Mastostroke, Pink Dragoone and
Tarantulino answered 404, and every Touch rebuild ended with
pets/scrape-bonuses FAILED (the steps after it ran on the old file). Their
English pages answered, so the scraper reads those when the French one is gone.
Read that way, the English pages gave the French reader's lines on all 172 pets
that had both, and the file's lines on the four.

The French reader runs to the end of the page (its stop words never match) and
keeps the gain per meal of the soul-fed pets, "1 Intelligence", as a second
line. The English reader reads the diet the same way on purpose: each line is a
variant numbered in file order, and a saved build keeps the number, so a pet
read in the other language must keep every line. The Mastostroke pages below
follow the layout of its live English page and of the live French pages of
Mosk and Bilby; the other two list every line shape the readers know.
"""
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
from unittest import mock

from django.test import SimpleTestCase

from chardata.tests import itemscraper_module


def _page(lines):
    return ('<html><body><h3>Description</h3><p>A pet.</p>'
            + ''.join('<div>%s</div>' % line for line in lines)
            + '</body></html>')


MASTOSTROKE_FR = _page(['Effets maximum sous hormone', "Drop de l'hormone", ':',
                        'Gourlo le Terrible', '110 Intelligence',
                        'Régime alimentaire', 'Âmes de monstres',
                        '1 Intelligence', '40 x', 'Sparo'])
MASTOSTROKE_EN = _page(['Max effects with hormone', 'Hormone dropped by', ':',
                        'Gourlo the Terrible', '110 Intelligence', 'Diet',
                        'Monster souls', '1 Intelligence', '40 x', 'Sparo'])

EVERY_SHAPE_FR = _page(['Effets maximum sous hormone', '150 Vitalité',
                        '5 % Résistance Terre', '6 % Résistance Feu',
                        '44 Résistance Air', '3 Résistance Neutre',
                        '22 Dommages Eau', '7 Dommages Neutre', '17 Dommages',
                        '12 % Dommages', '55 Soins', '1100 Pods', '1 Pod',
                        '2100 Initiative', '90 Prospection', '220 Sagesse',
                        '110 Force', '110 Intelligence', '110 Agilité',
                        '110 Chance', '75 Puissance', '2 PA', '-10 Vitalité'])
EVERY_SHAPE_EN = _page(['Max effects with hormone', '150 Vitality',
                        '5% Earth Resistance', '6% Fire Resistance',
                        '44 Air Resistance', '3 Neutral Resistance',
                        '22 Water Damage', '7 Neutral Damage', '17 Damage',
                        '12% Damage', '55 Heals', '1100 pods', '1 pod',
                        '2100 Initiative', '90 Prospecting', '220 Wisdom',
                        '110 Strength', '110 Intelligence', '110 Agility',
                        '110 Chance', '75 Power', '2 AP', '-10 Vitality'])


class ATouchPetReadsTheSameInEnglishTests(SimpleTestCase):

    def setUp(self):
        self.scraper = itemscraper_module('scrape_touch_pet_bonuses')

    def test_the_english_page_gives_the_french_lines_diet_included(self):
        french = self.scraper.parse_bonuses(MASTOSTROKE_FR, 'fr')
        self.assertEqual([['Intelligence', 110], ['Intelligence', 1]], french)
        self.assertEqual(french,
                         self.scraper.parse_bonuses(MASTOSTROKE_EN, 'en'))

    def test_every_line_shape_reads_the_same_in_both_languages(self):
        french = self.scraper.parse_bonuses(EVERY_SHAPE_FR, 'fr')
        self.assertEqual(
            [['Vitality', 150], ['% Earth Resist', 5], ['% Fire Resist', 6],
             ['Air Resist', 44], ['Neutral Resist', 3], ['Water Damage', 22],
             ['Neutral Damage', 7], ['Damage', 17], ['Power', 12],
             ['Heals', 55], ['Pods', 1100], ['Pods', 1],
             ['Initiative', 2100], ['Prospecting', 90], ['Wisdom', 220],
             ['Strength', 110], ['Intelligence', 110], ['Agility', 110],
             ['Chance', 110]],
            french)
        self.assertEqual(french,
                         self.scraper.parse_bonuses(EVERY_SHAPE_EN, 'en'))

    def test_a_page_without_the_block_gives_nothing(self):
        self.assertEqual([], self.scraper.parse_bonuses(_page(['Diet']), 'en'))


class TheScrapeNeverRenumbersTheVariantsTests(SimpleTestCase):
    """store_touch_pet_bonuses writes one variant per line of the file, in its
    sorted order, from 200000000, except a line the pet already carries as a
    stat of its own. A cap may change under its id; anything that adds or
    removes a variant before others may not, and one more variant even at the
    very end would take 200000228, which old Touch builds keep for the Gelano."""

    PREVIOUS = {'Bilby': [['Prospecting', 90], ['Prospecting', 1]],
                'Icky Tofu': [['Strength', 110], ['Intelligence', 110]],
                'Mastostroke': [['Intelligence', 110], ['Intelligence', 1]],
                'Mosk': [['Agility', 110], ['Agility', 1]]}

    def setUp(self):
        self.scraper = itemscraper_module('scrape_touch_pet_bonuses')

    def _moved(self, current, pets=None):
        return self.scraper.first_moved_line(self.PREVIOUS, current, pets)

    def test_the_same_lines_move_nothing(self):
        self.assertIsNone(self._moved(dict(self.PREVIOUS)))

    def test_a_new_cap_moves_nothing_and_is_reported(self):
        current = dict(self.PREVIOUS,
                       Mastostroke=[['Intelligence', 120], ['Intelligence', 1]])
        self.assertIsNone(self._moved(current))
        self.assertEqual([('Mastostroke', 'Intelligence', 110, 120)],
                         self.scraper.changed_values(self.PREVIOUS, current))

    def test_a_lost_line_moves_the_variants_from_there(self):
        current = dict(self.PREVIOUS, Mastostroke=[['Intelligence', 110]])
        self.assertEqual(('Mastostroke', 'Intelligence'), self._moved(current))

    def test_a_lost_pet_moves_the_variants_from_there(self):
        current = {name: lines for name, lines in self.PREVIOUS.items()
                   if name != 'Bilby'}
        self.assertEqual(('Bilby', 'Prospecting'), self._moved(current))

    def test_a_new_pet_moves_the_variants_after_it(self):
        current = dict(self.PREVIOUS, Brulay=[['Intelligence', 160]])
        self.assertEqual(('Icky Tofu', 'Strength'), self._moved(current))

    def test_a_new_pet_at_the_end_is_refused_too(self):
        current = dict(self.PREVIOUS, **{'Yellow Piwin': [['Agility', 110]]})
        self.assertEqual(('Yellow Piwin', 'Agility'), self._moved(current))

    def test_reordered_lines_change_what_an_id_means(self):
        current = dict(self.PREVIOUS, **{
            'Icky Tofu': [['Intelligence', 110], ['Strength', 110]]})
        self.assertEqual(('Icky Tofu', 'Strength'), self._moved(current))

    def test_a_cap_leaving_a_carried_stat_adds_a_variant(self):
        # Sirocco carries 160 Agility in the game data, so its 160 line is no
        # variant; at 170 it becomes one and every variant after it moves.
        pets = {name: [set()] for name in self.PREVIOUS}
        pets['Icky Tofu'] = [{('Strength', 110)}]
        self.assertIsNone(self._moved(dict(self.PREVIOUS), pets))
        current = dict(self.PREVIOUS, **{
            'Icky Tofu': [['Strength', 120], ['Intelligence', 110]]})
        self.assertEqual(('Icky Tofu', 'Intelligence'),
                         self._moved(current, pets))

    def test_a_pet_whose_lines_are_all_carried_may_go(self):
        pets = {name: [set()] for name in self.PREVIOUS}
        pets['Icky Tofu'] = [{('Strength', 110), ('Intelligence', 110)}]
        current = {name: lines for name, lines in self.PREVIOUS.items()
                   if name != 'Icky Tofu'}
        self.assertIsNone(self._moved(current, pets))


class TheScrapeRunTests(SimpleTestCase):
    """main() on the first two pets it reads from items_touch.db, Bow Wow
    (nothing to scrape) and Bow Meow, with the network stubbed."""

    BOW_MEOW = [['Agility', 110], ['Strength', 110], ['% Neutral Resist', 27],
                ['Intelligence', 110], ['Vitality', 110], ['Chance', 110]]
    BOW_MEOW_EN = _page(['Max effects with hormone', '110 Agility',
                         '110 Strength', '27% Neutral Resistance',
                         '110 Intelligence', '110 Vitality', '110 Chance'])
    BOW_MEOW_FR_SHORT = _page(['Effets maximum sous hormone', '110 Agilité',
                               '110 Force', '27 % Résistance Neutre',
                               '110 Intelligence', '110 Vitalité'])

    def setUp(self):
        self.scraper = itemscraper_module('scrape_touch_pet_bonuses')
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder)
        self.out = os.path.join(folder, 'touch_pet_bonuses.json')
        with open(self.out, 'w', encoding='utf-8') as handle:
            json.dump({'Bow Meow': self.BOW_MEOW}, handle)

    def _run(self, pages):
        def fetch(opener, url, **kwargs):
            return pages.get(url)
        printed = io.StringIO()
        argv = ['scrape', '--limit', '2', '--delay', '0', '--out', self.out]
        with mock.patch.object(self.scraper, 'fetch', side_effect=fetch), \
                mock.patch.object(sys, 'argv', argv), \
                contextlib.redirect_stdout(printed):
            code = self.scraper.main()
        with open(self.out, encoding='utf-8') as handle:
            return code, json.load(handle), printed.getvalue()

    def test_a_pet_with_only_an_english_page_keeps_its_lines(self):
        code, written, printed = self._run(
            {self.scraper.ENGLISH_URL % 1728: self.BOW_MEOW_EN})
        self.assertEqual(0, code)
        self.assertEqual({'Bow Meow': self.BOW_MEOW}, written)
        self.assertIn('read from the English page', printed)

    def test_a_lost_line_writes_nothing_and_says_where(self):
        code, written, printed = self._run(
            {self.scraper.BASE_URL % 1728: self.BOW_MEOW_FR_SHORT})
        self.assertEqual(1, code)
        self.assertEqual({'Bow Meow': self.BOW_MEOW}, written)
        self.assertIn('lines added, removed or reordered on: Bow Meow', printed)
        self.assertIn('nothing written', printed)
