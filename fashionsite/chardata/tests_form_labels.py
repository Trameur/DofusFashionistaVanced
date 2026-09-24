# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A form field must announce its name through an aria-label, a for label, or a wrapping label."""
import re

from django.test import TestCase

PAGES = ('/', '/encyclopedia/', '/encyclopedia/sets/',
         '/encyclopedia/monsters/', '/sharedbuilds/', '/setup/',
         '/login_page/', '/contact/', '/forgemagie/', '/smartbuild/')
NAVIGATEUR = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36')
# these types are named differently: a button by its value, a checkbox by trailing text, a hidden field by nobody
SANS_OBJET = "type=['\"](hidden|submit|button|checkbox|radio|image|reset)['\"]"
# avoids \b on purpose: through a heredoc it becomes a backspace and the pattern silently matches nothing
CHAMP = '<(?:input|select|textarea)[ >][^>]*>?'


def _enveloppes(html):
    """(start, end) of each <label>...</label>, for implicit labelling."""
    spans = []
    for ouvre in re.finditer('<label[ >]', html):
        ferme = html.find('</label>', ouvre.start())
        if ferme != -1:
            spans.append((ouvre.start(), ferme))
    return spans


def champs_sans_nom(html):
    """Fields none of the three ways name, and the total examined."""
    pour = set(re.findall('<label[^>]*for="([^"]+)"', html))
    spans = _enveloppes(html)
    nus, examines = [], 0
    for trouve in re.finditer(CHAMP, html):
        balise = trouve.group(0)
        if re.search(SANS_OBJET, balise):
            continue
        examines += 1
        if 'aria-label' in balise or 'title=' in balise:
            continue
        identifiant = re.search('id="([^"]+)"', balise)
        if identifiant and identifiant.group(1) in pour:
            continue
        if any(debut < trouve.start() < fin for debut, fin in spans):
            continue
        nus.append(balise)
    return nus, examines


class EveryFormFieldSaysWhatItIsTests(TestCase):
    """The labels were there. They just did not name the field."""

    def _html(self, chemin):
        reponse = self.client.get(chemin, HTTP_ACCEPT_LANGUAGE='en',
                                  HTTP_USER_AGENT=NAVIGATEUR)
        self.assertEqual(reponse.status_code, 200,
                         '%s answered %s' % (chemin, reponse.status_code))
        return reponse.content.decode('utf-8', 'replace')

    def test_no_field_is_announced_as_an_unnamed_box(self):
        nus, examines = [], 0
        pages_avec_champ = 0
        for chemin in PAGES:
            manquants, combien = champs_sans_nom(self._html(chemin))
            examines += combien
            if combien:
                pages_avec_champ += 1
            for balise in manquants:
                nom = re.search("name=['\"]([^'\"]+)", balise)
                nus.append((chemin, nom.group(1) if nom else balise[:40]))
        self.assertFalse(
            nus, 'these fields have no accessible name (page, field): %s' % nus)
        # counted per page: a broken pattern finds zero fields everywhere, and zero missing out of zero would pass
        self.assertGreaterEqual(
            examines, 20, 'only %d fields examined over %d pages'
            % (examines, len(PAGES)))
        self.assertGreaterEqual(
            pages_avec_champ, 4,
            'only %d of the %d pages carried a form field'
            % (pages_avec_champ, len(PAGES)))

    def test_the_entry_form_names_all_four_of_its_fields(self):
        """/setup/ is the page everyone enters through; kept separate so a regression there is reported on its own."""
        html = self._html('/setup/')
        pour = set(re.findall('<label[^>]*for="([^"]+)"', html))
        for identifiant in ('input-char-name', 'input-char-level',
                            'select-char-class', 'input-proj-name'):
            with self.subTest(champ=identifiant):
                self.assertIn(identifiant, pour,
                              'no label names %s' % identifiant)
                self.assertIn('id="%s"' % identifiant, html,
                              '%s is named by a label but does not exist'
                              % identifiant)
