# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A page number can be tapped: every paginated page goes through the container the rule sizes."""
import os
import re

from django.test import SimpleTestCase

_ICI = os.path.dirname(os.path.abspath(__file__))
CSS = os.path.join(_ICI, 'static', 'chardata', 'encyclopedia.css')
GABARITS = os.path.join(_ICI, 'templates', 'chardata')

# The published minimum, in CSS pixels (WCAG 2.5.8)
_MINIMUM = 24

# The marker that a template shows a row of page numbers
_SIGNE_DE_PAGINATION = re.compile(r'page_links|has_previous|has_next')


class EveryPageNumberIsBigEnoughToTapTests(SimpleTestCase):

    @staticmethod
    def _regle_du_conteneur():
        with open(CSS, encoding='utf-8') as f:
            texte = f.read()
        m = re.search(r'\.encyclopedia-pagination\s*>\s*\*\s*\{([^}]*)\}', texte)
        return m.group(1) if m else None

    def test_the_stylesheet_is_readable(self):
        self.assertTrue(os.path.exists(CSS), CSS)
        with open(CSS, encoding='utf-8') as f:
            self.assertGreater(len(f.read()), 2000,
                               'encyclopedia.css looks truncated')

    def test_the_pagination_row_declares_a_tappable_minimum(self):
        corps = self._regle_du_conteneur()
        self.assertIsNotNone(
            corps,
            'no rule targets the children of .encyclopedia-pagination, so the '
            'page numbers are back to whatever the text line box gives them')
        for propriete in ('min-width', 'min-height'):
            m = re.search(r'%s\s*:\s*(\d+)px' % propriete, corps)
            self.assertIsNotNone(m, '%s is not declared: %r'
                                 % (propriete, corps.strip()))
            self.assertGreaterEqual(
                int(m.group(1)), _MINIMUM,
                '%s is %spx, under the published %dpx minimum'
                % (propriete, m.group(1), _MINIMUM))

    def test_the_rule_is_scoped_to_the_pagination(self):
        with open(CSS, encoding='utf-8') as f:
            texte = f.read()
        for bloc in re.findall(r'([^{}]+)\{([^}]*)\}', texte):
            selecteur, corps = bloc[0].strip(), bloc[1]
            if 'min-height' not in corps and 'min-width' not in corps:
                continue
            if 'encyclopedia-page-link' in selecteur and \
                    'encyclopedia-pagination' not in selecteur:
                self.fail('%r sizes the class itself, which is also used by '
                          'body links' % selecteur)

    def test_every_paginated_template_uses_that_container(self):
        echappees = []
        vus = 0
        for nom in sorted(os.listdir(GABARITS)):
            if not nom.endswith('.html'):
                continue
            with open(os.path.join(GABARITS, nom), encoding='utf-8',
                      errors='replace') as f:
                texte = f.read()
            if not _SIGNE_DE_PAGINATION.search(texte):
                continue
            vus += 1
            if 'encyclopedia-pagination' not in texte and \
                    'class="pagination"' not in texte:
                echappees.append(nom)
        # Without a floor a broken pattern would find zero templates and zero escapes
        self.assertGreaterEqual(
            vus, 3,
            'only %d paginated template(s) found; the scan is too narrow to '
            'be guarding anything' % vus)
        self.assertFalse(
            echappees,
            'these paginate through a container no sizing rule reaches: %s'
            % echappees)
