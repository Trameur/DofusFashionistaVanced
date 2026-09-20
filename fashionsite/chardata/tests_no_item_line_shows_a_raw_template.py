# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""No item line shows a raw Ankama template such as {{item,23408::Dorigami}} to the reader."""
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

# Two real references, one of each form, taken from the databases
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
