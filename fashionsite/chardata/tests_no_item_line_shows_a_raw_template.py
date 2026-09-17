# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Aucune ligne d'objet ne montre un modele brut au lecteur.

Ankama ecrit ses renvois avec le nom dedans:
`{{spell,8395,1::Pourpre Profond}}`, `{{item,23408::Dorigami}}`. Le client les
resout, notre archive les stocke tels quels, et `fold_spell_blocks` les rendait
verbatim: le lecteur voyait les accolades.

**Mesure du 17 septembre 2026**, en depliant `extra_lines` des cinq bases:

| version | lignes | objets | langues |
|---------|--------|--------|---------|
| dofus3  | 13  | 2 (Black-Spotted Dofus 7112, Nightmare Dofus 26066) | les cinq pour 7112, de/es/pt pour 26066 |
| beta    | 306 | 74 (Dofus Pourpre, Emeraude, Turquoise...) | de, es, fr, pt |
| dofus2  | 0 | | |
| touch   | 0 | | |
| retro   | 0 | | |

L'anglais etait propre parce que sa ligne porte deja le nom en clair: c'est
exactement ce que la resolution rend aux quatre autres langues. Ce n'est donc
pas un defaut de la beta: il etait deja sur la version par defaut, sur deux
objets de niveau 180, et la beta 3.7.0.0 l'a multiplie par vingt.

`resolve_templates` garde le nom et jette le modele. Sur la beta, la ligne
`{{spell,8395,1::Pourpre Profond}} :` redevient un titre, donc l'objet retrouve
le nom et son infobulle, la forme que l'anglais avait deja.
"""
import os
import pickle
import sqlite3
import unittest

from django.test import SimpleTestCase

from fashionistapulp.spell_text import fold_spell_blocks, resolve_templates

PULP = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), 'fashionistapulp', 'fashionistapulp')

BASES = {
    'dofus3': 'items.db',
    'beta': 'items_beta.db',
    'dofus2': 'items_dofus2.db',
    'touch': 'items_touch.db',
    'retro': 'items_retro.db',
}

#: Deux vrais renvois, un de chaque forme, pris dans les bases le 17 septembre.
TEMOINS = (
    ('{{spell,8395,1::Pourpre Profond}} :', 'Pourpre Profond :'),
    ('quand le porteur inflige des dommages, lui et ses allies portant le '
     '{{item,23408::Dorigami}} gagnent 1 PA',
     'quand le porteur inflige des dommages, lui et ses allies portant le '
     'Dorigami gagnent 1 PA'),
)


def _stored_lines(chemin):
    connexion = sqlite3.connect('file:%s?mode=ro' % chemin, uri=True)
    try:
        table = connexion.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' "
            "AND name = 'extra_lines'").fetchone()
        if not table:
            return []
        stockees = []
        for item, langue, blob in connexion.execute(
                'SELECT item, language, line FROM extra_lines'):
            lignes = pickle.loads(blob) if isinstance(
                blob, (bytes, bytearray)) else [blob]
            if not isinstance(lignes, (list, tuple)):
                lignes = [lignes]
            stockees.append((item, langue, list(lignes)))
        return stockees
    finally:
        connexion.close()


class NoItemLineShowsARawTemplateTests(SimpleTestCase):

    def test_the_name_inside_the_template_is_what_is_shown(self):
        for brut, attendu in TEMOINS:
            with self.subTest(brut=brut):
                self.assertEqual(attendu, resolve_templates(brut))

    def test_no_kept_line_or_tooltip_shows_a_template(self):
        fautifs = []
        lus = 0
        for version, fichier in sorted(BASES.items()):
            chemin = os.path.join(PULP, fichier)
            if not os.path.exists(chemin):
                raise unittest.SkipTest('%s is absent' % fichier)
            for item, langue, lignes in _stored_lines(chemin):
                lus += 1
                gardees, infobulles = fold_spell_blocks(lignes)
                for texte in list(gardees) + list(infobulles) + list(
                        infobulles.values()):
                    if '{{' in str(texte):
                        fautifs.append('%s item %s [%s]: %s'
                                       % (version, item, langue,
                                          str(texte)[:80]))
        self.assertGreater(lus, 2000, 'the stored lines were not read')
        self.assertEqual([], fautifs[:20])
