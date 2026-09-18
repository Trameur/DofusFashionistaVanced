# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""German stat labels use the words the game uses."""
import io
import json
import os
import re
import unicodedata
import unittest

from django.test import SimpleTestCase
from django.utils import translation
from django.utils.translation import gettext

RACINE = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
BRUT = os.path.join(RACINE, 'itemscraper', 'raw', '3.6.11.12')
PO = os.path.join(RACINE, 'fashionsite', 'locale', 'de', 'LC_MESSAGES',
                  'django.po')

# msgid -> (game's word, the word it replaced)
MOTS_DU_JEU = {
    'Pods': ('Pods', 'Schoten'),
    'HP': ('LP', 'PS'),
    'Power': ('Schlagkraft', 'Leistung'),
    'Fire Damage': ('Feuerschaden', 'Brandschaden'),
    'Pushback Damage': ('Schubsschaden', 'Pushback-Schaden'),
    'Heals': ('Heilung', 'Heilt'),
    'Lock': ('Blocken', 'Sperren'),
    'AP Reduction': ('AP-Entzug', 'AP-Reduktion'),
    'MP Reduction': ('BP-Entzug', 'MP-Reduzierung'),
    'Resists': ('Resistenzen', 'Widersteht'),
    'Summons': ('Beschwörungen', 'Ladung'),
    'Leeching': ('Leveln', 'Blutegel'),
}

# Our msgid -> Ankama's English term, when it differs
CHEZ_ANKAMA = {
    'Resists': 'Resistance',
    'Summons': 'Summons',
    'Lock': 'Lock',
}

# Kept although Ankama writes otherwise: (ours, Ankama's, uses on the site)
GARDES = {
    'Prospecting': ('Prospektion', 'Filzwert', 16),
    'Critical Failure': ('Kritischer Fehlschlag', 'Kritischer Patzer', 2),
}

# Umlauts once spelled as ae/oe/ue
TREMAS_RENDUS = {
    'Hide invalid or outdated builds': 'Ungültige',
    'Conditions not met': 'erfüllt',
    'Add to inventory': 'hinzufügen',
}

_DIGRAPHES = (('ae', 'ä'), ('oe', 'ö'), ('ue', 'ü'),
              ('Ae', 'Ä'), ('Oe', 'Ö'), ('Ue', 'Ü'))
_MOT = re.compile(r'[^\W\d_]+', re.UNICODE)
_MSGSTR = re.compile(r'^msgstr(?:\[\d\])? "(.*)"$')
_SUITE = re.compile(r'^"(.*)"$')


def _sans_accent(mot):
    return ''.join(lettre for lettre
                   in unicodedata.normalize('NFD', mot)
                   if unicodedata.category(lettre) != 'Mn')


def _msgstrs():
    lignes = io.open(PO, encoding='utf-8').read().split('\n')
    index = 0
    while index < len(lignes):
        trouve = _MSGSTR.match(lignes[index])
        if not trouve:
            index += 1
            continue
        texte = trouve.group(1)
        index += 1
        while index < len(lignes):
            suite = _SUITE.match(lignes[index])
            if not suite:
                break
            texte += suite.group(1)
            index += 1
        if texte:
            yield texte


def _ankama():
    """{English term: {German terms}}, paired by id."""
    anglais = json.load(io.open(os.path.join(BRUT, 'en.json'),
                                encoding='utf-8'))['entries']
    allemand = json.load(io.open(os.path.join(BRUT, 'de.json'),
                                 encoding='utf-8'))['entries']
    par_terme = {}
    for identifiant, terme in anglais.items():
        mot = allemand.get(identifiant)
        if mot:
            par_terme.setdefault(terme, set()).add(mot)
    return par_terme


class TheGermanStatsUseTheWordsTheGameUsesTests(SimpleTestCase):

    def test_each_label_reads_the_word_the_game_uses(self):
        """Reads the compiled catalogue."""
        with translation.override('de'):
            for cle, (attendu, remplace) in sorted(MOTS_DU_JEU.items()):
                with self.subTest(cle=cle):
                    rendu = gettext(cle)
                    self.assertEqual(attendu, rendu)
                    self.assertNotEqual(remplace, rendu)

    def test_the_word_it_replaced_is_gone_from_the_whole_catalogue(self):
        textes = list(_msgstrs())
        self.assertGreater(len(textes), 1000, len(textes))
        for cle, (_attendu, remplace) in sorted(MOTS_DU_JEU.items()):
            if cle in ('Lock', 'HP'):
                # Checked in the next test
                continue
            reste = [texte for texte in textes
                     if re.search(r'\b%s\b' % re.escape(remplace), texte)]
            with self.subTest(cle=cle):
                self.assertEqual([], reste)

    def test_one_word_still_names_the_button_it_always_named(self):
        """Sperren is still the item lock button."""
        textes = list(_msgstrs())
        verrous = [texte for texte in textes if re.search(r'\bSperren\b', texte)]
        self.assertGreaterEqual(len(verrous), 3, verrous)
        with translation.override('de'):
            self.assertEqual('Blocken', gettext('Lock'))
        chevaux = [texte for texte in textes if re.search(r'\bPS\b', texte)]
        self.assertEqual([], chevaux, 'PS is horsepower, not health')

    def test_no_umlaut_is_spelled_with_two_letters(self):
        """A word with an umlaut somewhere has it everywhere."""
        textes = list(_msgstrs())
        avec_accent = set()
        for texte in textes:
            for mot in _MOT.findall(texte):
                if _sans_accent(mot) != mot:
                    avec_accent.add(_sans_accent(mot).lower())
        fautifs = []
        for texte in textes:
            for mot in _MOT.findall(texte):
                if _sans_accent(mot) != mot:
                    continue
                for digraphe, lettre in _DIGRAPHES:
                    if digraphe not in mot:
                        continue
                    candidat = _sans_accent(
                        mot.replace(digraphe, lettre)).lower()
                    if candidat in avec_accent and candidat != mot.lower():
                        fautifs.append(mot)
                        break
        self.assertEqual([], sorted(set(fautifs)))

        with translation.override('de'):
            for cle, mot in sorted(TREMAS_RENDUS.items()):
                with self.subTest(cle=cle):
                    self.assertIn(mot, gettext(cle))

    def test_what_the_site_keeps_carries_its_measurement(self):
        textes = list(_msgstrs())
        for cle, (garde, chez_ankama, combien) in sorted(GARDES.items()):
            with self.subTest(cle=cle):
                with translation.override('de'):
                    self.assertEqual(garde, gettext(cle))
                ailleurs = sum(
                    1 for texte in textes
                    if re.search(r'\b%s\w*' % re.escape(garde), texte))
                self.assertGreaterEqual(ailleurs, 1, garde)
                self.assertEqual(
                    [], [texte for texte in textes
                         if re.search(r'\b%s\b' % re.escape(chez_ankama),
                                      texte)],
                    '%s now appears too, so the site says both' % chez_ankama)
                self.assertGreater(combien, 1)

    def test_ankamas_own_german_is_where_these_words_come_from(self):
        """Skipped without itemscraper/raw, which is gitignored."""
        if not os.path.exists(os.path.join(BRUT, 'de.json')):
            raise unittest.SkipTest(
                'itemscraper/raw is gitignored; download the Dofus 3 lang '
                'files to read Ankama"s own German')
        par_terme = _ankama()
        self.assertGreater(len(par_terme), 10000, len(par_terme))
        for cle, (attendu, _remplace) in sorted(MOTS_DU_JEU.items()):
            if cle == 'Leeching':
                # A build type, not a stat: Ankama never names it
                self.assertNotIn(cle, par_terme)
                continue
            chez_ankama = par_terme.get(CHEZ_ANKAMA.get(cle, cle))
            with self.subTest(cle=cle):
                self.assertTrue(chez_ankama, cle)
                # Ankama only writes Resistenz, our label is plural
                self.assertTrue(
                    any(attendu == mot or attendu == mot + 'en'
                        for mot in chez_ankama),
                    '%s: %r vs %r' % (cle, attendu, sorted(chez_ankama)))
        for cle, (garde, chez_ankama, _combien) in sorted(GARDES.items()):
            with self.subTest(cle=cle):
                mots = par_terme.get(cle) or set()
                self.assertIn(chez_ankama, mots)
                self.assertNotIn(garde, mots,
                                 'Ankama now writes it the way we do, so the '
                                 'exception has no reason left')
