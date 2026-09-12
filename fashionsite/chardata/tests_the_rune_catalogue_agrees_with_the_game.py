# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Le catalogue des runes de transcendance, confronte aux donnees du jeu.

Ce catalogue vient de DofusDB, une source communautaire, et la politique du
site est de ne s'en servir qu'a defaut de premiere main. Or Ankama repond a
la meme question: le client Dofus 2.73 embarque sa propre table de textes, et
elle nomme ces runes une par une.

**Mesure du 13 septembre 2026, deux sources independantes.**

| rang | catalogue DofusDB | client 2.73 d'Ankama |
|------|------------------:|---------------------:|
| Ta   |                36 |               **36** |
| Pata |                25 |               **25** |
| Rata |                20 |               **20** |

Elles disent exactement la meme chose, rang par rang. Ce n'est donc plus une
donnee communautaire qu'on croit sur parole, c'est une donnee corroboree par
le jeu lui-meme, et ces tests le maintiennent: un re-scrape qui ramenerait
autre chose serait dementi par Ankama avant d'atteindre le site.

**La regle de version, verifiee sur chaque jeu.** Le site n'offre ces runes
qu'a Dofus 3, la Beta et Dofus 2. Les deux autres versions ont ete lues dans
leurs propres fichiers le 13 septembre 2026:

- Touch: 309 occurrences du mot <<rune>> dans `Items_fr.json`, **aucune
  transcendance**;
- Retro: 325 dans `items_fr.json` du client 1.29, **aucune transcendance**.

Les deux comptent bien des runes de forgemagie, donc ce zero est une absence
et pas une recherche qui aurait rate son fichier. Retro n'est pas garde ici:
le depot n'embarque aucun fichier brut de Retro, et un test ne peut pas
mesurer ce qui n'est pas la. Sa moitie du constat reste ce paragraphe, avec
sa date.

**Et les noms.** `solution_result.py` portait la phrase <<Ankama names its
runes in French in every client>>, et le code la suivait: les cinq langues
recevaient le nom francais. Les cinq tables du client 2.73 la demontent, sur
les 81 runes et sans une exception:

| fr | en | es | pt | de |
|----|----|----|----|----|
| Rune Ta Ine | Tra Int Rune | Runa Ta Inte | Runa Ta Int | Tra-Int-Rune |
| Rune Pata Fo | Pa Tra Str Rune | Runa Buta Fu | Runa Pata For | Pa-Tra-Kra-Rune |

Un lecteur anglais qui cherchait <<Rune Ta Ine>> dans son propre client ne
trouvait rien. Les **405 noms** (81 runes, cinq langues) ont ete confrontes
aux deux sources le 13 septembre 2026: **zero desaccord**.

Noter que l'espagnol renomme jusqu'au rang, Ta/Buta/Suta la ou le francais dit
Ta/Pata/Rata. Le rang reste donc lu sur le nom francais, qui est une cle et
non une etiquette; un test plus bas le fixe.
"""

import io
import json
import os
import re

from django.test import SimpleTestCase, TestCase
from django.utils.translation import override

#: Ce que les deux sources doivent dire, rang par rang. Un total ne suffirait
#: pas: 81 se repartit de beaucoup de facons, et c'est la repartition qui dit
#: que les deux tables parlent des memes objets.
_RANGS_ATTENDUS = {'Ta': 36, 'Pata': 25, 'Rata': 20}

#: Ce que le client Touch porterait s'il connaissait la mecanique.
_MARQUEURS = ('Rune Ta ', 'Rune Pata', 'Rune Rata')

#: Les cinq langues que le site sert, et dans lesquelles Ankama nomme
#: chacune de ces runes differemment.
LANGUES_JEU = ('fr', 'en', 'es', 'pt', 'de')

#: Le bloc de configuration que la page remet a son JavaScript.
_CONFIG = re.compile(
    r'<script[^>]*\bid="fm-config"[^>]*>(.*?)</script>', re.S)


def _racine_depot():
    return os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))


def _catalogue():
    chemin = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          'forgemagie_transcendance.json')
    with io.open(chemin, encoding='utf-8') as f:
        return json.load(f)


def _source_du_scraper():
    chemin = os.path.join(_racine_depot(), 'scripts',
                          'scrape_transcendance_runes.py')
    with io.open(chemin, encoding='utf-8') as f:
        return f.read()


def _rangs_du_catalogue():
    rangs = {}
    for rune in _catalogue()['runes']:
        rangs[rune['rank_label']] = rangs.get(rune['rank_label'], 0) + 1
    return rangs


def _rangs_du_client_dofus2():
    """Ce qu'Ankama nomme, dans la table de textes du client 2.73.

    Le fichier fait 31 Mo et se lit en 0,29 s; le comptage prend 0,027 s.
    """
    chemin = os.path.join(_racine_depot(), 'itemscraper', 'raw', '2.73.3.14',
                          'fr.json')
    with io.open(chemin, encoding='utf-8') as f:
        textes = json.load(f)['texts']
    rangs = {}
    for valeur in textes.values():
        if not isinstance(valeur, str) or not valeur.startswith('Rune '):
            continue
        morceaux = valeur.split()
        if len(morceaux) > 1 and morceaux[1] in _RANGS_ATTENDUS:
            rangs[morceaux[1]] = rangs.get(morceaux[1], 0) + 1
    return rangs


class TheCatalogueAgreesWithAnkamasOwnClientTests(SimpleTestCase):

    def test_the_catalogue_splits_the_ranks_the_way_it_was_measured(self):
        self.assertEqual(_RANGS_ATTENDUS, _rangs_du_catalogue())
        self.assertEqual(81, len(_catalogue()['runes']))

    def test_ankamas_own_client_names_exactly_the_same_runes(self):
        """La corroboration elle-meme.

        Si un re-scrape ramene un autre compte, c'est le jeu qui le dement,
        pas une valeur qu'on aurait recopiee a cote.
        """
        self.assertEqual(_RANGS_ATTENDUS, _rangs_du_client_dofus2())

    def test_the_two_sources_are_really_two(self):
        """Sans ce garde, les deux tests ci-dessus pourraient lire le meme
        fichier et s'accorder avec eux-memes."""
        chemin = os.path.join(_racine_depot(), 'itemscraper', 'raw',
                              '2.73.3.14', 'fr.json')
        self.assertTrue(os.path.exists(chemin), 'the 2.73 text table is gone')
        self.assertIn('DofusDB', _catalogue()['source'])


class OnlyTheVersionsWithTheMechanicOfferItTests(SimpleTestCase):

    def test_the_touch_client_knows_no_transcendence_rune(self):
        chemin = os.path.join(_racine_depot(), 'itemscraper', 'touch_raw',
                              'Items_fr.json')
        with io.open(chemin, encoding='utf-8', errors='replace') as f:
            texte = f.read()
        # Le plancher du temoin: Touch a bien des runes de forgemagie, donc
        # un zero sur les marqueurs est une absence et non un fichier rate.
        self.assertGreater(texte.lower().count('rune'), 100,
                           'this file carries no rune at all, so the zero '
                           'below would prove nothing')
        presents = [m for m in _MARQUEURS if m in texte]
        self.assertFalse(presents,
                         'Touch turns out to name these after all: %s'
                         % presents)

    def test_the_site_offers_them_on_three_versions_and_no_other(self):
        from chardata.forgemagie_transcendance import get_transcendence_runes
        offertes = {}
        for version in ('dofus3', 'beta', 'dofus2', 'touch', 'retro'):
            offertes[version] = len(get_transcendence_runes(version))
        self.assertEqual({'dofus3': 81, 'beta': 81, 'dofus2': 81,
                          'touch': 0, 'retro': 0}, offertes)


class TheRunesTakeTheNameTheReadersClientGivesThemTests(SimpleTestCase):
    """La phrase <<Ankama names its runes in French in every client>> etait
    fausse, et c'est elle qui avait produit l'affichage."""

    def _noms_ankama(self):
        """{nom francais: {langue: nom}} depuis le client 2.73."""
        tables = {}
        for langue in LANGUES_JEU:
            chemin = os.path.join(_racine_depot(), 'itemscraper', 'raw',
                                  '2.73.3.14', '%s.json' % langue)
            with io.open(chemin, encoding='utf-8') as f:
                tables[langue] = json.load(f)['texts']
        sortie = {}
        for identifiant, valeur in tables['fr'].items():
            if not isinstance(valeur, str) or not valeur.startswith('Rune '):
                continue
            morceaux = valeur.split()
            if len(morceaux) > 1 and morceaux[1] in _RANGS_ATTENDUS:
                sortie[valeur] = dict(
                    (l, tables[l].get(identifiant)) for l in LANGUES_JEU)
        return sortie

    def test_the_catalogue_carries_a_name_in_every_language(self):
        vides = [(rune['id'], langue)
                 for rune in _catalogue()['runes']
                 for langue in LANGUES_JEU
                 if not (rune.get('name') or {}).get(langue)]
        self.assertFalse(vides, 'runes with a missing name: %s' % vides[:6])

    def test_ankamas_own_client_confirms_all_four_hundred_and_five(self):
        """La corroboration, nom par nom et langue par langue."""
        ankama = self._noms_ankama()
        self.assertEqual(81, len(ankama))
        desaccords, verifies = [], 0
        for rune in _catalogue()['runes']:
            noms = rune['name']
            chez_ankama = ankama.get(noms['fr'])
            self.assertIsNotNone(
                chez_ankama, 'Ankama does not name %s' % noms['fr'])
            for langue in LANGUES_JEU:
                verifies += 1
                if noms[langue] != chez_ankama[langue]:
                    desaccords.append((noms['fr'], langue, noms[langue],
                                       chez_ankama[langue]))
        self.assertEqual(405, verifies)
        self.assertFalse(desaccords,
                         'the catalogue and the game disagree: %s'
                         % desaccords[:4])

    def test_every_rune_is_renamed_by_the_game_in_every_language(self):
        """Le fait qui justifie tout le lot. S'il cessait d'etre vrai, cette
        traduction deviendrait du bruit et il faudrait le savoir."""
        pareils = [rune['name']['fr'] for rune in _catalogue()['runes']
                   if len(set(rune['name'][l] for l in LANGUES_JEU)) == 1]
        self.assertFalse(
            pareils,
            'these runes carry one name in all five languages, so translating '
            'them changes nothing: %s' % pareils[:4])

    def test_the_rank_is_read_in_french_because_it_is_a_key(self):
        """L'espagnol dit Ta/Buta/Suta. Lire le rang dans la langue du lecteur
        laisserait toutes les runes espagnoles sans rang."""
        source = _source_du_scraper()
        self.assertIn('.get("fr")', source)
        espagnols = set()
        for rune in _catalogue()['runes']:
            morceaux = rune['name']['es'].split()
            if len(morceaux) > 1:
                espagnols.add(morceaux[1])
        self.assertTrue(
            espagnols - set(_RANGS_ATTENDUS),
            'Spanish now uses the French rank words, so this reason is stale')


class ThePagesNameTheRuneInTheReadersLanguageTests(TestCase):

    def _config(self, langue):
        reponse = self.client.get('/forgemagie/',
                                  headers={'accept-language': langue})
        self.assertEqual(200, reponse.status_code, langue)
        corps = reponse.content.decode('utf-8')
        bloc = _CONFIG.search(corps)
        self.assertIsNotNone(bloc, langue)
        return json.loads(bloc.group(1))

    def test_the_workshop_serves_each_language_its_own_names(self):
        attendus = {}
        for rune in _catalogue()['runes']:
            attendus[rune['id']] = rune['name']
        vus = {}
        for langue in LANGUES_JEU:
            config = self._config(langue)
            runes = [r for entree in config['transcendence'].values()
                     for r in entree['runes']]
            self.assertEqual(81, len(runes), langue)
            for rune in runes:
                self.assertEqual(attendus[rune['id']][langue], rune['name'],
                                 '%s, rune %s' % (langue, rune['id']))
            vus[langue] = sorted(r['name'] for r in runes)
        for langue in LANGUES_JEU:
            if langue != 'fr':
                self.assertNotEqual(
                    vus['fr'], vus[langue],
                    'the page still serves the French names to %s' % langue)

    def test_the_chip_says_the_stat_in_the_readers_language_too(self):
        """La pastille est une phrase: <<nom (+bonus stat, poids)>>.

        Le catalogue porte le libelle francais de la stat, et la pastille
        l'affichait tel quel: un lecteur allemand lisait <<Tra-Vi-Rune (+50
        Vitalite - Gewicht 40)>>, deux langues en six mots. Traduire le nom
        sans l'etiquette aurait laisse la phrase a moitie faite.
        """
        vus = {}
        for langue in LANGUES_JEU:
            config = self._config(langue)
            entree = config['transcendence'].get('vit')
            self.assertIsNotNone(entree, langue)
            vus[langue] = entree['label']
        self.assertEqual(
            len(LANGUES_JEU), len(set(vus.values())),
            'the stat label does not follow the reader: %s' % vus)

    def test_the_build_page_names_the_suggested_rune_in_the_readers_language(
            self):
        """La page du build annonce une rune conseillee par piece."""
        from chardata.solution_result import attach_transcendence
        from fashionistapulp.structure import set_current_game_version

        class Piece(object):
            item_added = True
            type = 'Amulet'
            stats = {}

        set_current_game_version('dofus3')
        vus = {}
        for langue in LANGUES_JEU:
            piece = Piece()
            with override(langue):
                attach_transcendence(piece, {'int': 10})
            self.assertTrue(piece.transcendence, langue)
            vus[langue] = piece.transcendence
        for langue in LANGUES_JEU:
            if langue != 'fr':
                self.assertNotEqual(
                    vus['fr'], vus[langue],
                    'the build page still says %s to a %s reader'
                    % (vus['fr'], langue))

    def test_an_unknown_language_falls_back_instead_of_showing_nothing(self):
        from chardata.forgemagie_transcendance import rune_name
        rune = _catalogue()['runes'][0]
        self.assertEqual(rune['name']['en'], rune_name(rune, 'it'))
        self.assertEqual(rune['name']['fr'], rune_name({'name': {
            'fr': rune['name']['fr']}}, 'it'))
        self.assertEqual('', rune_name({}, 'en'))
