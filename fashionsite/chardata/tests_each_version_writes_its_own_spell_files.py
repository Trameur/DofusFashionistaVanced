# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Each version's update orchestrator must write its own spell files, not Dofus 3's."""
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
    """The argument list of one orchestrator step, as text."""
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
        """Ties the rule above to the file the site actually reads."""
        from chardata import spell_localization
        self.assertEqual('transformed_spell_names.json',
                         spell_localization.SPELL_NAMES_JSON.name)
