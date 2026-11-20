# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A card says what is worn in its slot, the Dofus row is captioned from what the version holds, and the card actions are legible in both themes."""

import os
import re
from types import SimpleNamespace

from django.test import SimpleTestCase
from django.utils import translation

from chardata.solution_result import dofus_row_title, piece_label_type

STATIC = os.path.join(os.path.dirname(__file__), 'static', 'chardata')


def _read(name):
    with open(os.path.join(STATIC, name), encoding='utf-8') as handle:
        return handle.read()


def _luminance(hex_color):
    channels = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(first, second):
    high, low = sorted((_luminance(first), _luminance(second)), reverse=True)
    return (high + 0.05) / (low + 0.05)


class ThePetSlotIsLabelledByWhatIsWornTests(SimpleTestCase):

    def test_a_mount_in_the_pet_slot_is_labelled_mount(self):
        item = SimpleNamespace(slot='pet', item_added=True, ankama_type='mounts')
        self.assertEqual('Mount', piece_label_type(item))

    def test_a_pet_in_the_pet_slot_stays_a_pet(self):
        item = SimpleNamespace(slot='pet', item_added=True, ankama_type='equipment')
        self.assertEqual('Pet', piece_label_type(item))

    def test_a_piece_with_no_recorded_origin_stays_a_pet(self):
        item = SimpleNamespace(slot='pet', item_added=True)
        self.assertEqual('Pet', piece_label_type(item))

    def test_an_empty_pet_slot_stays_a_pet(self):
        item = SimpleNamespace(slot='pet', item_added=False, ankama_type='mounts')
        self.assertEqual('Pet', piece_label_type(item))

    def test_other_slots_keep_their_type(self):
        item = SimpleNamespace(slot='ring2', item_added=True, ankama_type='mounts')
        self.assertEqual('Ring', piece_label_type(item))

    def test_the_card_template_prints_the_label_it_is_given(self):
        with open(os.path.join(os.path.dirname(__file__), 'templates', 'chardata',
                               'solution_item.html'), encoding='utf-8') as handle:
            template = handle.read()
        self.assertIn('{% trans item.slot_type %}', template)


class TheDofusRowCaptionFollowsTheVersionTests(SimpleTestCase):

    def _title(self, version):
        with translation.override('en'):
            return str(dofus_row_title(version))

    def test_versions_with_dofus_and_trophies_say_both(self):
        for version in ('dofus3', 'beta', 'touch'):
            self.assertEqual('Dofus and trophies', self._title(version), version)

    def test_retro_has_no_trophies_and_does_not_mention_them(self):
        self.assertEqual('Dofus', self._title('retro'))


class TheCardActionsAreLegibleTests(SimpleTestCase):

    def setUp(self):
        self.sheet = _read('modern-solution-parts.css')
        self.core = _read('modern-core.css')

    def _glyph_colors(self, selector):
        block = re.search(re.escape(selector) + r'\{(.*?)\n\}', self.sheet, re.S).group(1)
        found = {}
        for name, value in re.findall(r'--fm-ico-([a-z-]+):(url\(.*?\));', block):
            colors = re.findall(r"stroke='%23([0-9a-f]{6})'", value)
            fills = re.findall(r"fill='%23([0-9a-f]{6})'", value)
            found[name] = ['#' + c for c in colors + fills]
        return found

    def test_every_glyph_has_three_to_one_on_its_card_in_both_themes(self):
        surfaces = {'html.fm-modern:not(.fm-dark)': '#f6efde', 'html.fm-modern.fm-dark': '#231b10'}
        self.assertIn('--fm-surface:#f6efde', self.core)
        self.assertIn('--fm-surface:#231b10', self.core)
        for selector, surface in surfaces.items():
            glyphs = self._glyph_colors(selector)
            self.assertEqual(8, len(glyphs), selector)
            for name, colors in glyphs.items():
                self.assertTrue(colors, name)
                for color in colors:
                    if name == 'forbid-on' and color not in glyphs['forbid-off']:
                        continue
                    self.assertGreaterEqual(_contrast('#' + color.lstrip('#'), surface), 3, (selector, name, color))

    def test_the_pressed_glyph_differs_in_shape_from_the_resting_one(self):
        for selector in ('html.fm-modern:not(.fm-dark)', 'html.fm-modern.fm-dark'):
            block = re.search(re.escape(selector) + r'\{(.*?)\n\}', self.sheet, re.S).group(1)
            icons = dict(re.findall(r'--fm-ico-([a-z-]+):(url\(.*?\));', block))
            self.assertNotEqual(icons['lock-on'], icons['lock-off'])
            self.assertNotEqual(icons['forbid-on'], icons['forbid-off'])

    def test_the_inline_dimming_no_longer_hides_a_resting_button(self):
        self.assertIn('.solution-item-button[aria-pressed]{ opacity:1 !important; }', self.sheet)

    def test_a_pressed_button_carries_a_ring(self):
        self.assertRegex(self.sheet, r'\[aria-pressed="true"\]\{ box-shadow:inset 0 0 0 1\.5px')

    def test_every_action_keeps_a_visible_focus_ring(self):
        self.assertIn('.solution-item-button:focus-visible{ outline:none; box-shadow:var(--fm-ring)', self.sheet)
