# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Chaque caracteristique porte, en allemand, le mot du jeu.

Trouve en parcourant la galerie en allemand, sur Touch, depuis les propres
liens du site. La liste des options se lisait:

    Widersteht  Blutegel  Prospektion  Schoten  Fallen  Ladung

**Quatre de ces six mots disent autre chose en allemand.** <<Widersteht>> est
un verbe conjugue (<<il resiste>>), <<Blutegel>> sont les sangsues,
<<Schoten>> sont les cosses de petits pois, et <<Ladung>> est une cargaison.
Ailleurs sur le site, la meme page ecrivait <<PS>>, qui est l'abreviation
allemande du cheval-vapeur, pour les points de vie.

**Le mot retenu n'est pas une preference: il est appuye deux fois.**

1. Le fichier de langue allemand du client Dofus 3 (3.6.11.12), lu au **meme
   identifiant** que l'anglais. C'est Ankama qui apparie les deux, pas nous.
2. Le catalogue du site lui-meme, qui emploie deja l'autre mot ailleurs.

Mesure du 14 septembre 2026 sur les 64 noms de caracteristiques du catalogue:
Ankama en nomme 30 en allemand, le site et lui en ecrivent **18 pareil** et
**12 differemment**. Sur ces douze, onze sont corrigees ici, et la douzieme
est nommee plus bas.

| caracteristique | ecrit | corrige en | le site ecrivait deja |
|-----------------|-------|------------|------------------------|
| Pods | Schoten | Pods | (fr, es et pt gardent Pods) |
| HP | PS | LP | Lebenspunkte, 2 fois |
| Power | Leistung | Schlagkraft | Schlagkraft, 2 fois |
| Fire Damage | Brandschaden | Feuerschaden | Feuerschaden, 1 fois |
| Pushback Damage | Pushback-Schaden | Schubsschaden | Schubsschaden, 1 fois |
| Heals | Heilt | Heilung | (verbe contre nom) |
| Lock | Sperren | Blocken | Sperren nomme deja le bouton verrouiller |
| AP Reduction | AP-Reduktion | AP-Entzug | <<entzieht AP>> |
| MP Reduction | MP-Reduzierung | BP-Entzug | BP, 19 fois contre MP, 5 fois |
| Resists | Widersteht | Resistenzen | Resistenzen, 17 fois |
| Summons | Ladung | Beschwoerungen | Beschwoerungen, 4 fois |

**Ce qui n'est pas touche, et pourquoi.** `Prospecting` reste
<<Prospektion>> la ou Ankama ecrit <<Filzwert>>: le mot est du bon allemand,
le site l'emploie **seize fois** de suite, guides compris, et <<Filzwert>>
n'apparait nulle part. C'est un choix de vocabulaire, pas une faute, et le
corriger d'un cote seulement ferait exactement le defaut que ce lot corrige.
Meme raison pour `Critical Failure` (<<Kritischer Fehlschlag>>, quand Ankama
ecrit <<Kritischer Patzer>>) et pour `Summon` au singulier, dont Ankama n'a
que l'abreviation <<Beschw.>>.

`Leeching` n'est nomme par aucun fichier d'Ankama: c'est un type de build, pas
une caracteristique. <<Blutegel>> etait quand meme faux, et il devient
<<Leveln>>, le mot que le catalogue allemand emploie deja
(<<Farmen / Leveln>>), comme le francais dit <<Mulage>> et le portugais
<<UP>>.

**Six mots ecrivaient leurs tremas en deux lettres** -- <<Ungueltige>>,
<<Waehle>>, <<fuege>>, <<Loesungs>>, <<erfuellt>>, <<hinzufuegen>> -- alors
que le meme mot porte son trema ailleurs dans le meme catalogue
(<<Ungueltige Aktion>> voisine <<Ungueltige ... ausblenden>>). Ils sont
ecrits en allemand.

Les traductions sont lues par `gettext`, donc dans le catalogue **compile**:
un `.po` corrige mais non recompile ne passe pas plus qu'un `.po` fautif.

`itemscraper/raw` est hors du depot (.gitignore): le parcours qui relit le
fichier d'Ankama se met de cote quand il est absent, les autres non.
"""
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

#: msgid -> le mot du jeu, et le mot qu'il remplace.
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

#: Notre msgid -> le terme sous lequel Ankama nomme la meme notion, quand ce
#: n'est pas le meme mot. `Leeching` n'y est pas: c'est un type de build, pas
#: une caracteristique, et Ankama ne le nomme nulle part.
CHEZ_ANKAMA = {
    'Resists': 'Resistance',
    'Summons': 'Summons',
    'Lock': 'Lock',
}

#: Ce que le site garde alors qu'Ankama ecrit autre chose, et pourquoi. La
#: mesure est ce qui autorise l'exception: la retirer doit se voir.
GARDES = {
    'Prospecting': ('Prospektion', 'Filzwert', 16),
    'Critical Failure': ('Kritischer Fehlschlag', 'Kritischer Patzer', 2),
}

#: Les mots dont le trema etait ecrit en deux lettres.
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
    """{terme anglais: {termes allemands}}, au meme identifiant."""
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
        """Lu par gettext, donc dans le catalogue compile."""
        with translation.override('de'):
            for cle, (attendu, remplace) in sorted(MOTS_DU_JEU.items()):
                with self.subTest(cle=cle):
                    rendu = gettext(cle)
                    self.assertEqual(attendu, rendu)
                    self.assertNotEqual(remplace, rendu)

    def test_the_word_it_replaced_is_gone_from_the_whole_catalogue(self):
        """Un mot corrige sur l'etiquette et laisse dans une phrase ferait
        exactement le defaut que ce lot corrige."""
        textes = list(_msgstrs())
        self.assertGreater(len(textes), 1000, len(textes))
        for cle, (_attendu, remplace) in sorted(MOTS_DU_JEU.items()):
            if cle in ('Lock', 'HP'):
                # <<Sperren>> nomme encore le bouton verrouiller un objet, et
                # <<PS>> ne se lit plus nulle part; les deux sont verifies a
                # part, plus bas.
                continue
            reste = [texte for texte in textes
                     if re.search(r'\b%s\b' % re.escape(remplace), texte)]
            with self.subTest(cle=cle):
                self.assertEqual([], reste)

    def test_one_word_still_names_the_button_it_always_named(self):
        """<<Sperren>> reste le verrou d'un objet: c'est la notion voisine,
        et lui prendre son mot serait le meme defaut a l'envers."""
        textes = list(_msgstrs())
        verrous = [texte for texte in textes if re.search(r'\bSperren\b', texte)]
        self.assertGreaterEqual(len(verrous), 3, verrous)
        with translation.override('de'):
            self.assertEqual('Blocken', gettext('Lock'))
        chevaux = [texte for texte in textes if re.search(r'\bPS\b', texte)]
        self.assertEqual([], chevaux, 'PS is horsepower, not health')

    def test_no_umlaut_is_spelled_with_two_letters(self):
        """Le catalogue est son propre temoin: un mot qui porte son trema
        quelque part ne peut pas le perdre ailleurs."""
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
        """Une exception sans son nombre redevient une preference."""
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
        """La regle elle-meme, relue chez Ankama. Se met de cote quand
        itemscraper/raw est absent, ce qui est le cas sur un depot propre."""
        if not os.path.exists(os.path.join(BRUT, 'de.json')):
            raise unittest.SkipTest(
                'itemscraper/raw is gitignored; download the Dofus 3 lang '
                'files to read Ankama"s own German')
        par_terme = _ankama()
        self.assertGreater(len(par_terme), 10000, len(par_terme))
        for cle, (attendu, _remplace) in sorted(MOTS_DU_JEU.items()):
            if cle == 'Leeching':
                # Pas une caracteristique: Ankama ne la nomme nulle part, et
                # c'est ce qui la range dans les exceptions.
                self.assertNotIn(cle, par_terme)
                continue
            chez_ankama = par_terme.get(CHEZ_ANKAMA.get(cle, cle))
            with self.subTest(cle=cle):
                self.assertTrue(chez_ankama, cle)
                # Le pluriel allemand est le notre: Ankama n'ecrit que
                # <<Resistenz>>, le libelle est une liste, et les autres
                # langues le mettent aussi au pluriel.
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
