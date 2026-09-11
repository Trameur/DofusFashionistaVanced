# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Le pied de page marque le changelog tant que sa derniere entree n'a pas
ete ouverte.

Mesure du 11 septembre 2026: quatre entrees de septembre, seize
fonctionnalites, derriere un lien <<Changelog>> du pied de page qui avait
la meme tete qu'un lien vers rien de neuf. Le lien porte maintenant la cle
de l'entree la plus recente (le msgid de son titre, le meme dans les cinq
langues), le navigateur garde la cle sur laquelle il a ouvert le changelog
pour la derniere fois, et une marque <<(nouveautes)>> s'affiche tant que
les deux different.
"""

import io
import os
import re
import shutil
import subprocess

from django.conf import settings
from django.test import SimpleTestCase, TestCase

from chardata import changelog_state

MARQUE = 'new entries'


def _lien(page):
    debut = page.find('changelog-link')
    assert debut != -1, 'no changelog link in the footer'
    return page[page.rfind('<a', 0, debut):page.find('</a>', debut) + 4]


class TheKeyIsTheNewestTitleTests(SimpleTestCase):

    def test_the_key_is_the_first_title_of_the_changelog_source(self):
        source = io.open(changelog_state.changelog_template_path(),
                         encoding='utf-8').read()
        titres = re.findall(r'class="cl-title">\{% trans "([^"]+)" %\}', source)
        self.assertTrue(titres)
        self.assertEqual(titres[0], changelog_state.newest_entry_key())

    def test_the_key_is_read_once(self):
        changelog_state.newest_entry_key()
        self.assertIn('key', changelog_state._cache)


class TheFooterCarriesTheKeyAndTheMarkTests(TestCase):

    def test_every_page_hands_the_key_to_the_script(self):
        cle = changelog_state.newest_entry_key()
        for chemin in ('/', '/faq/', '/touch/', '/import/text/'):
            page = self.client.get(chemin, HTTP_ACCEPT_LANGUAGE='en'
                                   ).content.decode('utf-8')
            lien = _lien(page)
            self.assertIn('data-changelog-latest="%s"' % cle, lien, chemin)
            self.assertIn('changelog-new', lien, chemin)
            # Cachee au chargement: c'est le script qui la montre, pour que
            # le lecteur qui a deja tout vu ne la voie pas clignoter.
            self.assertIn('hidden', lien, chemin)
            self.assertIn(MARQUE, lien, chemin)

    def test_the_mark_speaks_the_language_of_the_reader(self):
        page = self.client.get('/', HTTP_ACCEPT_LANGUAGE='fr'
                               ).content.decode('utf-8')
        lien = _lien(page)
        self.assertIn('nouveautés', lien)
        self.assertNotIn(MARQUE, lien)

    def test_the_processor_is_declared(self):
        declares = settings.TEMPLATES[0]['OPTIONS']['context_processors']
        self.assertIn('chardata.context_processors.changelog', declares)

    def test_the_dev_settings_declare_the_same_processors_as_production(self):
        """settings_dev.py garde sa propre liste: le serveur de developpement
        rendait `data-changelog-latest=""` et la marque ne s'affichait
        jamais, pendant que les tests, sur settings.py, etaient verts.
        Les deux listes doivent etre les memes."""
        def liste(nom):
            source = io.open(os.path.join(settings.BASE_DIR, 'fashionsite',
                                          nom), encoding='utf-8').read()
            bloc = source.split("'context_processors': [", 1)[1].split(']', 1)[0]
            return re.findall(r"'([\w.]+)'", bloc)
        self.assertEqual(liste('settings.py'), liste('settings_dev.py'))
        self.assertIn('chardata.context_processors.changelog',
                      liste('settings_dev.py'))


class TheScriptKeepsWhatWasSeenTests(SimpleTestCase):

    def _script(self):
        return io.open(os.path.join(settings.BASE_DIR, 'chardata', 'static',
                                    'chardata', 'changelog.js'),
                       encoding='utf-8').read()

    def test_it_reads_the_key_stores_it_on_open_and_survives_no_storage(self):
        script = self._script()
        self.assertIn("'changelog_seen'", script)
        self.assertIn('data-changelog-latest', script)
        self.assertIn('rememberChangelogSeen();', script.split('function openChangelog')[1])
        self.assertIn('markChangelogIfUnseen();', script)
        self.assertIn('try { seen = localStorage.getItem', script)
        self.assertIn('try { localStorage.setItem', script)

    def test_the_script_is_valid_javascript(self):
        node = shutil.which('node')
        if node is None:
            self.skipTest('node not installed')
        chemin = os.path.join(settings.BASE_DIR, 'chardata', 'static',
                              'chardata', 'changelog.js')
        verdict = subprocess.run([node, '--check', chemin],
                                 capture_output=True, text=True)
        self.assertEqual(0, verdict.returncode, verdict.stderr)


class TheMarkIsInEveryCatalogueTests(SimpleTestCase):

    def test_four_native_translations(self):
        import gettext
        vues = set()
        for langue in ('fr', 'es', 'pt', 'de'):
            phrase = gettext.translation(
                'django', os.path.join(settings.BASE_DIR, 'locale'),
                languages=[langue]).gettext(MARQUE)
            self.assertNotEqual(MARQUE, phrase, langue)
            vues.add(phrase)
        self.assertEqual(4, len(vues))
