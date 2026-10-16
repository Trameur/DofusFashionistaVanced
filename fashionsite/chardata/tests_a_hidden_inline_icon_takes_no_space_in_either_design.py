# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""An inline icon the workshop script hides with the hidden attribute is not drawn as a plain square, and a shown one keeps its inline box, in both designs and both themes."""
from django.test import SimpleTestCase

from chardata.tests_the_setup_stylesheet_support import DESIGNS, chain_of, stylesheet, winning

SHEETS = [('workshop.css', stylesheet('workshop.css')), ('modern.css', stylesheet('modern.css'))]
STATUS = (('html', {}), ('body', {}), ('div', {'class': 'workshop-wrapper'}), ('div', {'class': 'ws-card brown-box'}),
          ('span', {'class': 'ws-status'}))


def icon_chain(design, **attrs):
    return chain_of(STATUS, 'span', dict({'class': 'fm-ico'}, **attrs), DESIGNS[design])


class AHiddenInlineIconTests(SimpleTestCase):

    def test_a_hidden_status_icon_is_not_displayed(self):
        for design in DESIGNS:
            for width in (375, 1920):
                with self.subTest(design=design, width=width):
                    self.assertEqual('none', winning(SHEETS, icon_chain(design, hidden=''), 'display', width)[0])

    def test_a_shown_status_icon_keeps_its_inline_box(self):
        for design in DESIGNS:
            for width in (375, 1920):
                with self.subTest(design=design, width=width):
                    self.assertEqual('inline-block', winning(SHEETS, icon_chain(design), 'display', width)[0])
