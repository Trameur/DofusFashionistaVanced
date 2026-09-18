# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Each notion the German reader sees uses one word: Gegenstand, Stufe, Set, Buff."""

import io
import os
import re

from django.test import SimpleTestCase
from django.utils import translation
from django.utils.translation import gettext

# Notion -> (chosen word, its minimum count, other words with their old count)
_NOTIONS = {
    'item': ('Gegenst', 87, {'Punkt': 4, 'Element': 4}),
    'level': ('Stufe', 26, {'Ebene': 1}),
    'set': ('Set', 120, {'Sätz': 3}),
    'buff': ('Buff', 11, {'poliert': 1}),
}

# Past five words a msgid is prose, where Level is the usual German word
_LONGUEUR_LIBELLE = 5

# Labels seen together: (msgid, msgid, shared word, where)
_VOISINS = (
    ('Lock Items', 'Forbid Items', 'Gegenst', 'le menu d\'un projet'),
    ('Fully Buff', 'Clean Buffs', 'Buff', 'les deux boutons des sorts'),
    ('Character Level', 'Character Name', 'Charakter', 'la page de creation'),
    ('Character Level', 'Character Class', 'Charakter', 'la page de creation'),
    ('Min Level', 'Max Level', 'Stufe', 'les filtres des builds partages'),
    ('Compare sets', 'Choose sets to compare', 'Set', 'le bandeau'),
)

# (msgid, wrong translation, what it actually means)
_MOTS_FAUX = (
    ('About', 'Um', 'une preposition: autour de, vers'),
    ('Item A', 'Punkt A', 'un point, comme un point de score'),
    ('Item B', 'Punkt B', 'un point, comme un point de score'),
    ('Lock Items', 'Elemente sperren', 'element, pas objet'),
    ('Character Level', 'Charakterebene', 'ebene: un plan, une couche'),
    ('Min Level', 'Min. Level', 'la meme page dit Stufe sur chaque carte'),
    ('Max Level', 'Max. Level', 'la meme page dit Stufe sur chaque carte'),
    ('Compare sets', 'Sätze vergleichen', 'satz: une phrase, un jeu'),
    ('Compare Sets', 'Sätze vergleichen', 'satz: une phrase, un jeu'),
    ('Change Sets', 'Änderungssätze', 'un nom compose sur un bouton'),
    ('Fully Buff', 'Vollständig poliert', 'poliert: poli, lustre'),
)

# Only the verb goes in the link (freischalten is a separable verb)
_PHRASE_DU_LIEN = '<a href=%(lock_link)s>Unlock</a> some items'

_ENTREE = re.compile(r'(?m)^msgid ((?:"[^\n]*"\n)+)msgstr ((?:"[^\n]*"\n?)+)')


def _catalogue(langue):
    """[(msgid, msgstr)] from the .po."""
    chemin = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'locale', langue, 'LC_MESSAGES', 'django.po')
    with io.open(chemin, encoding='utf-8') as fichier:
        contenu = fichier.read()
    entrees = []
    for bloc in _ENTREE.finditer(contenu):
        msgid = ''.join(re.findall(r'"([^\n]*)"', bloc.group(1)))
        msgstr = ''.join(re.findall(r'"([^\n]*)"', bloc.group(2)))
        if msgid and msgstr:
            entrees.append((msgid, msgstr))
    return entrees


def _traduit(msgid):
    """German text from the compiled catalogue."""
    with translation.override('de'):
        return gettext(msgid)


class EveryGermanLabelUsesTheWordTheSiteAlreadyUsesTests(SimpleTestCase):

    def test_no_short_label_names_a_thing_the_site_names_otherwise(self):
        ecarts = []
        for msgid, _ in _catalogue('de'):
            if len(msgid.split()) > _LONGUEUR_LIBELLE:
                continue
            for notion, (retenu, _n, ecartes) in _NOTIONS.items():
                if notion not in msgid.lower():
                    continue
                rendu = _traduit(msgid)
                if retenu.lower() in rendu.lower():
                    continue
                for mauvais in ecartes:
                    if mauvais.lower() in rendu.lower():
                        ecarts.append((msgid, rendu, notion, retenu))
                        break
        self.assertEqual(
            [], ecarts,
            'these German labels name a thing with a word the site does not '
            'use for it: %s' % ecarts)

    def test_the_chosen_word_dominates_the_ones_set_aside(self):
        entrees = _catalogue('de')
        for notion, (retenu, _stamp, ecartes) in _NOTIONS.items():
            with self.subTest(notion=notion):
                compte = len([1 for msgid, msgstr in entrees
                              if notion in msgid.lower()
                              and retenu.lower() in msgstr.lower()])
                for mauvais in ecartes:
                    reste = len([1 for msgid, msgstr in entrees
                                 if notion in msgid.lower()
                                 and retenu.lower() not in msgstr.lower()
                                 and mauvais.lower() in msgstr.lower()])
                    self.assertGreater(
                        compte, reste * 5,
                        '%r no longer clearly dominates %r for %r (%d against '
                        '%d)' % (retenu, mauvais, notion, compte, reste))

    def test_the_recorded_counts_are_the_ones_measured(self):
        entrees = _catalogue('de')
        for notion, (retenu, attendu, _ecartes) in _NOTIONS.items():
            with self.subTest(notion=notion):
                compte = len([1 for msgid, msgstr in entrees
                              if notion in msgid.lower()
                              and retenu.lower() in msgstr.lower()])
                self.assertGreaterEqual(
                    compte, attendu,
                    '%r was measured %d times for %r and is now used %d '
                    'times' % (retenu, attendu, notion, compte))

    def test_the_rule_covers_enough_labels_to_prove_something(self):
        entrees = _catalogue('de')
        sous_la_frontiere = [
            msgid for msgid, _ in entrees
            if len(msgid.split()) <= _LONGUEUR_LIBELLE
            and any(n in msgid.lower() for n in _NOTIONS)]
        self.assertGreaterEqual(
            len(sous_la_frontiere), 30,
            'the rule now covers almost nothing, so it proves nothing: %d '
            'labels' % len(sous_la_frontiere))

    def test_the_prose_that_keeps_Level_is_prose_and_is_counted(self):
        prose =[msgid for msgid, msgstr in _catalogue('de')
                 if 'level' in msgid.lower()
                 and 'Stufe' not in msgstr and 'Level' in msgstr]
        self.assertTrue(prose, 'the idiomatic exception vanished entirely')
        courts = [m for m in prose if len(m.split()) <= _LONGUEUR_LIBELLE]
        self.assertEqual(
            [], courts,
            'these are control labels, not prose, so they may not claim the '
            'idiomatic exception: %s' % courts)
        self.assertLessEqual(
            len(prose), 9,
            'the idiomatic exception was 9 entries and is now %d; the rule '
            'is being worked around' % len(prose))


class NoLabelKeepsAWordThatMeansSomethingElseTests(SimpleTestCase):

    def test_the_wrong_words_are_gone_and_stay_gone(self):
        revenus = [(msgid, faux, sens) for msgid, faux, sens in _MOTS_FAUX
                   if _traduit(msgid) == faux]
        self.assertEqual(
            [], revenus,
            'these labels are back to a word that says something else: %s'
            % revenus)

    def test_the_faq_never_calls_an_item_a_score_point(self):
        """The FAQ says Punkte for score points: match Punkt A, not Punkt."""
        fautifs = []
        for msgid, _ in _catalogue('de'):
            rendu = _traduit(msgid)
            if re.search(r'\b(Punkt|Element) [AB]\b', rendu):
                fautifs.append((msgid[:60], rendu[:80]))
        self.assertEqual(
            [], fautifs,
            'these say Punkt A or Element A where the table says Gegenstand '
            'A: %s' % fautifs)


class TwoThingsSeenTogetherUseTheSameWordTests(SimpleTestCase):

    def test_neighbouring_labels_agree_on_the_word(self):
        desaccords = []
        for gauche, droite, mot, ou in _VOISINS:
            rg, rd = _traduit(gauche), _traduit(droite)
            if mot.lower() not in rg.lower() or mot.lower() not in rd.lower():
                desaccords.append((ou, gauche, rg, droite, rd, mot))
        self.assertEqual(
            [], desaccords,
            'these labels sit side by side and name the same thing with two '
            'words: %s' % desaccords)

    def test_the_neighbours_really_are_translated_apart(self):
        identiques = [(g, d) for g, d, _mot, _ou in _VOISINS
                      if _traduit(g) == _traduit(d)]
        self.assertEqual(
            [], identiques,
            'these pairs render the same string, so agreeing proves nothing: '
            '%s' % identiques)


class TheLinkCoversTheVerbOnlyTests(SimpleTestCase):

    def test_every_language_links_the_verb_and_not_the_sentence(self):
        trop_larges = []
        for langue in ('en', 'fr', 'es', 'pt', 'de'):
            with translation.override(langue):
                rendu = gettext(_PHRASE_DU_LIEN)
            lien = re.search(r'<a href=[^>]*>(.*?)</a>(.*)', rendu)
            self.assertIsNotNone(
                lien, '%s lost the link entirely: %r' % (langue, rendu))
            if not lien.group(2).strip():
                trop_larges.append((langue, rendu))
        self.assertEqual(
            [], trop_larges,
            'these languages put the whole sentence inside the link, so the '
            'reader cannot tell what the link does: %s' % trop_larges)
