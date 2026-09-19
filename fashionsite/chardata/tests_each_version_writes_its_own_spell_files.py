# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Chaque version ecrit ses propres fichiers de sorts.

Trouve en mettant a jour les cinq versions le 15 septembre 2026, sur le run de
la beta, le premier depuis le 12 septembre a aller jusqu'aux sorts.

**Deux etapes de `update_data_beta.py` travaillaient au nom de Dofus 3.**

- `spells/constants` ne passait pas `--game-version beta`. Depuis `4f1f2bcc9`
  (12 septembre), le generateur refuse des fichiers `_beta` sous l'etiquette
  `dofus3`: l'etape echouait en 0,1 s et `dofus_constants_beta.py` n'etait
  plus regenere.
- `spells/transform` ne passait pas `--names-output`, et ecrivait donc les
  noms de la beta dans `itemscraper/transformed_spell_names.json`, le fichier
  que `chardata/spell_localization.py` lit pour afficher les noms de sorts.
  Mesure sur ce run: un seul sort differait, *Piercing Shot*, et le run de la
  beta y avait mis `Durchdringender Schuss` et `Tiro Perforante` a la place
  des noms de Dofus 3, `Durchbohrender Schuss` et `Tiro Penetrante`.

`update_data_dofus2.py` faisait deja les deux. Le parcours tient les deux
orchestrateurs qui ne sont pas Dofus 3 a la meme regle.
"""
import os
import re

from django.test import SimpleTestCase

RACINE = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

ORCHESTRATEURS = (
    ('update_data_beta.py', 'beta'),
    ('update_data_dofus2.py', 'dofus2'),
)


def _etape(source, nom):
    """La liste d'arguments d'une etape de l'orchestrateur, en texte."""
    trouve = re.search(r'step\("%s", \[(.*?)\]' % re.escape(nom), source,
                       re.S)
    return trouve.group(1) if trouve else None


def _source(nom):
    with open(os.path.join(RACINE, nom), encoding='utf-8') as fichier:
        return fichier.read()


class EachVersionWritesItsOwnSpellFilesTests(SimpleTestCase):

    def test_the_constants_step_names_its_version(self):
        for nom, version in ORCHESTRATEURS:
            with self.subTest(orchestrateur=nom):
                bloc = _etape(_source(nom), 'spells/constants')
                self.assertIsNotNone(bloc)
                self.assertRegex(bloc, r'"--game-version",\s*"%s"' % version)

    def test_the_transform_step_keeps_its_names_out_of_the_shared_file(self):
        for nom, version in ORCHESTRATEURS:
            with self.subTest(orchestrateur=nom):
                bloc = _etape(_source(nom), 'spells/transform')
                self.assertIsNotNone(bloc)
                sortie = re.search(r'"--names-output",\s*"([^"]+)"', bloc)
                self.assertIsNotNone(
                    sortie, 'writes the names the site reads for Dofus 3')
                self.assertIn('_%s.json' % version, sortie.group(1))

    def test_the_shared_names_file_is_the_one_the_site_reads(self):
        """Ce qui fait de la regle ci-dessus plus qu'une preference."""
        from chardata import spell_localization
        self.assertEqual('transformed_spell_names.json',
                         spell_localization.SPELL_NAMES_JSON.name)
