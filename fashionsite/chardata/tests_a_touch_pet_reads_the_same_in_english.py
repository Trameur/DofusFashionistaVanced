# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A Touch pet's English encyclopedia page gives the lines of its French one.

On 2026-09-18 the French pages of Blue Piwin, Mastostroke, Pink Dragoone and
Tarantulino answered 404, and every Touch rebuild ended with
pets/scrape-bonuses FAILED (the steps after it ran on the old file). Their
English pages answered, so the scraper reads those when the French one is gone.
Read that way, the English pages gave the French reader's lines on all 172 pets
that had both, and the file's lines on the four.

Both readers stop at the diet. Until the same day the French one never did:
its stop words kept their accents and were compared with a line that had lost
them, so it kept the gain per meal of the soul-fed pets, "1 Intelligence", as a
second cap. The Mastostroke pages below follow the layout of its live English
page and of the live French pages of Mosk and Bilby; the other two list every
line shape the live pages had on 2026-09-18.
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
                        '110 Chance', '75 Puissance', '2 PA', '1 PM',
                        '55 Fuite', '55 Tacle', '54 Esquive PA', '54 Esquive PM',
                        '44 Dommages Critiques', '65 Résistance Critiques',
                        '66 Dommages Poussée', '65 Résistance Poussée',
                        '-10 Vitalité'])
EVERY_SHAPE_EN = _page(['Max effects with hormone', '150 Vitality',
                        '5% Earth Resistance', '6% Fire Resistance',
                        '44 Air Resistance', '3 Neutral Resistance',
                        '22 Water Damage', '7 Neutral Damage', '17 Damage',
                        '12% Damage', '55 Heals', '1100 pods', '1 pod',
                        '2100 Initiative', '90 Prospecting', '220 Wisdom',
                        '110 Strength', '110 Intelligence', '110 Agility',
                        '110 Chance', '75 Power', '2 AP', '1 MP', '55 Dodge',
                        '55 Lock', '54 AP Parry', '54 MP Parry',
                        '44 Critical Damage', '65 Critical Resistance',
                        '66 Pushback Damage', '65 Pushback Resistance',
                        '-10 Vitality'])


class ATouchPetReadsTheSameInEnglishTests(SimpleTestCase):

    def setUp(self):
        self.scraper = itemscraper_module('scrape_touch_pet_bonuses')

    def test_the_english_page_gives_the_french_lines_up_to_the_diet(self):
        french = self.scraper.parse_bonuses(MASTOSTROKE_FR, 'fr')
        self.assertEqual([['Intelligence', 110]], french)
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
             ['Chance', 110], ['Power', 75], ['AP', 2], ['MP', 1],
             ['Dodge', 55], ['Lock', 55], ['AP Loss Resist', 54],
             ['MP Loss Resist', 54], ['Critical Damage', 44],
             ['Critical Resist', 65], ['Pushback Damage', 66],
             ['Pushback Resist', 65]],
            french)
        self.assertEqual(french,
                         self.scraper.parse_bonuses(EVERY_SHAPE_EN, 'en'))

    def test_a_page_without_the_block_gives_nothing(self):
        self.assertEqual([], self.scraper.parse_bonuses(_page(['Diet']), 'en'))


class TheScrapeNeverLosesAVariantInSilenceTests(SimpleTestCase):
    """A variant's id comes from its pet and its stat, so a pet or a line that
    comes in, a line that moves and a cap that changes leave every id where it
    was. What still needs a human is a variant that goes: a build wearing it
    would fall back to the bare pet."""

    PREVIOUS = {'Bilby': [['Prospecting', 90], ['Prospecting', 1]],
                'Icky Tofu': [['Strength', 110], ['Intelligence', 110]],
                'Mastostroke': [['Intelligence', 110], ['Intelligence', 1]],
                'Mosk': [['Agility', 110], ['Agility', 1]]}

    def setUp(self):
        self.scraper = itemscraper_module('scrape_touch_pet_bonuses')

    def _lost(self, current, pets=None):
        return self.scraper.lost_variants(self.PREVIOUS, current, pets)

    def test_the_same_lines_lose_nothing(self):
        self.assertEqual([], self._lost(dict(self.PREVIOUS)))

    def test_dropping_the_gain_per_meal_loses_nothing(self):
        current = {name: lines if name == 'Icky Tofu' else lines[:1]
                   for name, lines in self.PREVIOUS.items()}
        self.assertEqual([], self._lost(current))
        self.assertEqual([], self.scraper.changed_values(self.PREVIOUS, current))

    def test_a_new_cap_keeps_its_variant_and_is_reported(self):
        current = dict(self.PREVIOUS, Mastostroke=[['Intelligence', 120]])
        self.assertEqual([], self._lost(current))
        self.assertEqual([('Mastostroke', 'Intelligence', 110, 120)],
                         self.scraper.changed_values(self.PREVIOUS, current))

    def test_a_new_pet_or_line_loses_nothing(self):
        current = dict(self.PREVIOUS, Brulay=[['Intelligence', 160]],
                       Mosk=[['Agility', 110], ['Power', 75]])
        self.assertEqual([], self._lost(current))

    def test_reordered_lines_lose_nothing(self):
        current = dict(self.PREVIOUS, **{
            'Icky Tofu': [['Intelligence', 110], ['Strength', 110]]})
        self.assertEqual([], self._lost(current))

    def test_a_lost_line_is_named(self):
        current = dict(self.PREVIOUS, **{'Icky Tofu': [['Strength', 110]]})
        self.assertEqual([('Icky Tofu', 'Intelligence')], self._lost(current))

    def test_a_lost_pet_is_named(self):
        current = {name: lines for name, lines in self.PREVIOUS.items()
                   if name != 'Bilby'}
        self.assertEqual([('Bilby', 'Prospecting')], self._lost(current))

    def test_a_cap_moving_onto_a_carried_stat_loses_its_variant(self):
        # Sirocco carries 160 Agility in the game data, so its 160 line is no
        # variant.
        pets = {name: [set()] for name in self.PREVIOUS}
        pets['Icky Tofu'] = [{('Strength', 120)}]
        current = dict(self.PREVIOUS, **{
            'Icky Tofu': [['Strength', 120], ['Intelligence', 110]]})
        self.assertEqual([('Icky Tofu', 'Strength')],
                         self._lost(current, pets))

    def test_a_pet_whose_lines_are_all_carried_may_go(self):
        pets = {name: [set()] for name in self.PREVIOUS}
        pets['Icky Tofu'] = [{('Strength', 110), ('Intelligence', 110)}]
        current = {name: lines for name, lines in self.PREVIOUS.items()
                   if name != 'Icky Tofu'}
        self.assertEqual([], self._lost(current, pets))


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
        self.assertIn('variants that would disappear: Bow Meow (Chance)',
                      printed)
        self.assertIn('nothing written', printed)

    def test_a_new_line_is_written(self):
        code, written, printed = self._run(
            {self.scraper.ENGLISH_URL % 1728: _page(
                ['Max effects with hormone', '110 Agility', '110 Strength',
                 '27% Neutral Resistance', '110 Intelligence', '110 Vitality',
                 '110 Chance', '75 Power'])})
        self.assertEqual(0, code)
        self.assertEqual({'Bow Meow': self.BOW_MEOW + [['Power', 75]]}, written)
        self.assertIn('new variants: 1', printed)
