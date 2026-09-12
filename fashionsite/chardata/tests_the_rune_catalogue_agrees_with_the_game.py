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
"""

import io
import json
import os

from django.test import SimpleTestCase

#: Ce que les deux sources doivent dire, rang par rang. Un total ne suffirait
#: pas: 81 se repartit de beaucoup de facons, et c'est la repartition qui dit
#: que les deux tables parlent des memes objets.
_RANGS_ATTENDUS = {'Ta': 36, 'Pata': 25, 'Rata': 20}

#: Ce que le client Touch porterait s'il connaissait la mecanique.
_MARQUEURS = ('Rune Ta ', 'Rune Pata', 'Rune Rata')


def _racine_depot():
    return os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))


def _catalogue():
    chemin = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          'forgemagie_transcendance.json')
    with io.open(chemin, encoding='utf-8') as f:
        return json.load(f)


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
