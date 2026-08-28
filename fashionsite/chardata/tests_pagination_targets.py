# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Un numero de page se touche au doigt.

Mesure dans un navigateur a 375 px, le 28 aout 2026 : les elements de
`.encyclopedia-pagination` faisaient **10 x 22 px**, `padding: 0`. Sur un
telephone, viser « 5 » plutot que « 6 » est un tirage au sort -- et
l'encyclopedie est justement la surface ou le trafic mobile arrive depuis
Google.

Le minimum publie est 24 x 24 px (WCAG 2.5.8). Le site le respectait deja
ailleurs sans le savoir : la pagination de `/sharedbuilds/` porte
`padding: 8px 12px` et mesure **51 x 78**. Deux traitements pour la meme
fonction, sur le meme site.

Ce module ne teste pas des pixels -- aucun navigateur ne tourne ici. Il garde
les deux choses qu'un test sans rendu peut garder honnetement :

  1. la regle existe et declare un minimum d'au moins 24 px ;
  2. **chaque page paginee passe bien par le conteneur que la regle vise.**

La seconde est la vraie : une quatrieme page paginee qui inventerait sa propre
classe echapperait a la regle en silence, et personne ne le verrait avant de
sortir un telephone.
"""
import os
import re

from django.test import SimpleTestCase

_ICI = os.path.dirname(os.path.abspath(__file__))
CSS = os.path.join(_ICI, 'static', 'chardata', 'encyclopedia.css')
GABARITS = os.path.join(_ICI, 'templates', 'chardata')

#: Le minimum publie, en pixels CSS.
_MINIMUM = 24

#: Le marqueur qu'un gabarit affiche une rangee de numeros de page.
_SIGNE_DE_PAGINATION = re.compile(r'page_links|has_previous|has_next')


class EveryPageNumberIsBigEnoughToTapTests(SimpleTestCase):

    @staticmethod
    def _regle_du_conteneur():
        with open(CSS, encoding='utf-8') as f:
            texte = f.read()
        m = re.search(r'\.encyclopedia-pagination\s*>\s*\*\s*\{([^}]*)\}', texte)
        return m.group(1) if m else None

    def test_the_stylesheet_is_readable(self):
        """Le plancher du temoin.

        Un chemin faux rendrait une feuille vide, donc aucune regle trouvee,
        donc un echec franc plutot qu'un vert trompeur -- mais autant le dire
        explicitement.
        """
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
        """`encyclopedia-page-link` sert aussi aux liens du corps de page.

        Une regle posee sur la CLASSE gonflerait les liens « Ouvrir les
        details » de chaque carte. Elle doit viser les enfants du conteneur.
        """
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
        # Sans plancher, un motif casse rendrait zero gabarit et zero echappee.
        self.assertGreaterEqual(
            vus, 3,
            'only %d paginated template(s) found; the scan is too narrow to '
            'be guarding anything' % vus)
        self.assertFalse(
            echappees,
            'these paginate through a container no sizing rule reaches: %s'
            % echappees)
