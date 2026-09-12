# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""L'atelier nomme chaque rune comme le client du lecteur la nomme.

Les noms de runes sont **construits en code**, en francais, a partir
d'abreviations (`Rune %s %s`), et c'est ce qui etait montre aux cinq langues.
Or chaque jeu les renomme:

    Rune de Terre | Earth Rune | Runa de Tierra | Runa de Terra | Rune der Erde

**Mesure du 13 septembre 2026**, chaque version lue dans SA propre table et
jamais dans celle d'une autre:

| version | runes nommees | introuvables | renommees selon la langue |
|---------|--------------:|-------------:|--------------------------:|
| Dofus 3 |           103 |            0 |                       103 |
| Beta    |           103 |            0 |                       103 |
| Dofus 2 |            96 |            0 |                        96 |
| Touch   |            82 |            0 |                        82 |
| Retro   |            52 |            0 |                        52 |

Les jeux ne se repondent pas pareil: en anglais, la rune de Vitalite est
<<Vit Rune>> sur les clients modernes et <<Vi Rune>> sur Retro.

**La clef reste francaise.** Le nom construit est ce que la session enregistre
dans le navigateur du lecteur: ses compteurs de runes lancees et les prix
qu'il a saisis y sont indexes dessus. Le traduire ferait perdre les deux au
premier changement de langue, et perdrait aussi les sessions deja
enregistrees. La page sert donc `key` (francais, stable) et `name` (traduit),
et c'est `key` que la session ecrit.
"""

import io
import json
import os
import re

from django.test import SimpleTestCase, TestCase

LANGUES = ('fr', 'en', 'es', 'pt', 'de')

VERSIONS = ('dofus3', 'beta', 'dofus2', 'touch', 'retro')

PREFIXE = {'dofus3': '', 'beta': 'beta/', 'dofus2': 'dofus2/',
           'touch': 'touch/', 'retro': 'retro/'}

#: Ce que chaque table du jeu porte, mesure le 13 septembre 2026. Le
#: catalogue embarque toutes les runes de la version, pas seulement celles que
#: la page nomme aujourd'hui, pour qu'une rune ajoutee plus tard a
#: `forgemagie_data.py` soit deja couverte.
_RUNES_PAR_VERSION = {'dofus3': 105, 'beta': 105, 'dofus2': 98,
                      'touch': 86, 'retro': 57}

#: La seule rune qu'un jeu ne renomme pas: la table portugaise de Retro porte
#: <<Rune Vi>>, l'orthographe francaise. Ce n'est pas un trou, l'entree
#: existe et l'espagnol dit bien <<Runa Vi>>; c'est Ankama qui l'a laissee
#: ainsi. Nommee ici pour que personne ne la <<corrige>>.
_NON_TRADUITE = {('retro', 'pt', 'Rune Vi')}

_CONFIG = re.compile(
    r'<script[^>]*\bid="fm-config"[^>]*>(.*?)</script>', re.S)


def _racine_depot():
    return os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))


def _catalogue():
    chemin = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          'forgemagie_rune_names.json')
    with io.open(chemin, encoding='utf-8') as f:
        return json.load(f)


def _noms_construits(version):
    """Les noms francais que la page batit, qui sont ses clefs."""
    from chardata.forgemagie_data import get_fm_stats
    noms = set()
    for stat in get_fm_stats(version).values():
        for tier, _bonus in stat['tiers']:
            noms.add(' '.join(p for p in ('Rune', tier, stat['rune']) if p))
    return noms


class EachVersionIsReadInItsOwnTableTests(SimpleTestCase):

    def test_the_catalogue_holds_every_version(self):
        catalogue = _catalogue()
        self.assertEqual(sorted(VERSIONS), sorted(catalogue))
        compte = dict((v, len(catalogue[v])) for v in VERSIONS)
        self.assertEqual(_RUNES_PAR_VERSION, compte)

    def test_the_versions_do_not_share_one_table(self):
        """Sans ce garde, lire une version dans la table d'une autre passerait
        inapercu tant que les noms se ressemblent."""
        catalogue = _catalogue()
        self.assertNotEqual(set(catalogue['dofus3']), set(catalogue['retro']))
        # Meme rune, deux jeux, deux noms anglais.
        self.assertEqual('Vit Rune', catalogue['dofus3']['Rune Vi']['en'])
        self.assertEqual('Vi Rune', catalogue['retro']['Rune Vi']['en'])

    def test_every_rune_the_page_names_is_in_its_version_table(self):
        catalogue = _catalogue()
        manquantes = []
        vues = 0
        for version in VERSIONS:
            connues = catalogue[version]
            for nom in _noms_construits(version):
                vues += 1
                if nom not in connues:
                    manquantes.append((version, nom))
        self.assertGreater(vues, 400, 'trop peu de runes examinees')
        self.assertFalse(
            manquantes,
            'the page names these and its own game table does not: %s'
            % manquantes[:6])

    def test_no_name_is_empty_in_any_language(self):
        vides = [(version, nom, langue)
                 for version, runes in _catalogue().items()
                 for nom, noms in runes.items()
                 for langue in LANGUES if not noms.get(langue)]
        self.assertFalse(vides, 'empty rune names: %s' % vides[:6])

    def test_the_game_really_does_rename_them(self):
        """Le fait qui justifie le lot. S'il cessait d'etre vrai, tout ce
        travail deviendrait du bruit et il faudrait le savoir."""
        pareils = []
        for version, runes in _catalogue().items():
            for nom, noms in runes.items():
                for langue in LANGUES:
                    if langue == 'fr' or noms[langue] != nom:
                        continue
                    if (version, langue, nom) not in _NON_TRADUITE:
                        pareils.append((version, langue, nom))
        self.assertFalse(
            pareils,
            'these keep the French spelling in another language, which is '
            'either a new fact or a hole: %s' % pareils[:6])


class TheWorkshopServesTheReadersLanguageTests(TestCase):

    def _config(self, version, langue):
        reponse = self.client.get('/%sforgemagie/' % PREFIXE[version],
                                  headers={'accept-language': langue},
                                  follow=True)
        self.assertEqual(200, reponse.status_code, version)
        corps = reponse.content.decode('utf-8')
        bloc = _CONFIG.search(corps)
        self.assertIsNotNone(bloc, version)
        return json.loads(bloc.group(1))

    def _tiers(self, config):
        return [tier for stat in config['stats'].values()
                for tier in (stat.get('tiers') or [])]

    def test_the_page_shows_the_name_the_readers_game_uses(self):
        catalogue = _catalogue()
        for version in VERSIONS:
            for langue in LANGUES:
                with self.subTest(version=version, langue=langue):
                    tiers = self._tiers(self._config(version, langue))
                    self.assertTrue(tiers, version)
                    for tier in tiers:
                        attendu = catalogue[version][tier['key']][langue]
                        self.assertEqual(attendu, tier['name'],
                                         '%s %s' % (version, tier['key']))

    def test_the_key_stays_french_whatever_the_reader_reads(self):
        """Ce que la session enregistre. Si la clef suivait la langue, un
        lecteur qui en change perdrait ses compteurs et ses prix saisis, et
        toutes les sessions deja enregistrees deviendraient illisibles."""
        for version in VERSIONS:
            with self.subTest(version=version):
                attendu = None
                for langue in LANGUES:
                    cles = sorted(t['key']
                                  for t in self._tiers(self._config(version,
                                                                    langue)))
                    if attendu is None:
                        attendu = cles
                    self.assertEqual(attendu, cles, langue)
                self.assertEqual(sorted(_noms_construits(version)), attendu)

    def test_the_reference_table_is_translated_too(self):
        """Le tableau rendu par le serveur, pas seulement la charge JS."""
        for version in ('dofus3', 'retro'):
            with self.subTest(version=version):
                vus = {}
                for langue in ('fr', 'en'):
                    reponse = self.client.get(
                        '/%sforgemagie/' % PREFIXE[version],
                        headers={'accept-language': langue}, follow=True)
                    corps = reponse.content.decode('utf-8')
                    vus[langue] = re.findall(
                        r'<span class="fm-ref-tier">([^<]*)</span>', corps)
                    self.assertTrue(vus[langue], langue)
                self.assertNotEqual(vus['fr'], vus['en'],
                                    'the reference table still serves French')
                anglais = ' '.join(vus['en'])
                self.assertIn('Rune', anglais)
                self.assertNotIn('Rune Vi:', anglais)


class TheFallbackAndTheGeneratorTests(SimpleTestCase):

    def test_an_unknown_rune_keeps_its_french_key(self):
        """Le repli coute la traduction, jamais l'etiquette: la clef est
        elle-meme un nom que le jeu emploie."""
        from chardata.forgemagie_rune_names import rune_display_name
        self.assertEqual('Rune Inconnue',
                         rune_display_name('dofus3', 'Rune Inconnue', 'en'))
        self.assertEqual('Rune Vi',
                         rune_display_name('pas_une_version', 'Rune Vi', 'en'))
        self.assertEqual('Vit Rune',
                         rune_display_name('dofus3', 'Rune Vi', 'it'))

    def test_the_generator_cannot_silently_drop_a_version(self):
        """Les tables brutes de Retro ne sont pas dans le depot. Un generateur
        qui ecraserait le fichier sans elles retirerait 57 runes sans un mot.
        """
        chemin = os.path.join(_racine_depot(), 'scripts',
                              'generate_rune_names.py')
        with io.open(chemin, encoding='utf-8') as f:
            source = f.read()
        self.assertIn('existing = _load(OUT) or {}', source)
        self.assertIn('result = dict(existing)', source)
        self.assertIn('kept.append(version)', source)
