# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Une icone qui echoue n'arrete pas les autres.

Trouve en mettant a jour les cinq versions le 15 septembre 2026.
`itemscraper/get_equipments4.py` telechargeait chaque icone d'objet avec un
`requests.get` nu, deux fois par objet (une fois par repertoire), sans delai
maximal.

**Ce que ca coutait, mesure sur 40 vraies icones de Dofus 3:**

| methode | par objet, horloge | par objet, CPU |
|---------|--------------------|----------------|
| un `requests.get` par telechargement, deux par objet | 0.581 s | 0.402 s |
| une session, un telechargement | 0.034 s | 0.009 s |

Pour les 3833 objets de Beta, l'ancienne facon donne 2227 s d'horloge et
1540 s de CPU. Le run reel a ete coupe par son plafond apres 2370 s d'icones
et 1600 s de CPU, avant les drops, les monstres et les sorts: sa base est
restee sans onze tables. Apres le changement, la meme etape a pris 111 s.
Sur Dofus 3, une seule poignee de main TLS interrompue par l'hote
(WinError 10053) avait fait tomber toute l'etape, et avec elle chaque icone
qui venait apres.

**Trois sortes d'absence, trois verdicts.** Une connexion qui tombe est un
echec du run. Une source qui repond sans image n'en est pas un. Et une source
qui n'a pas rendu LA TAILLE demandee n'est pas une source sans image: le
141e objet de Dofus 3, `32204` (Mister Penguin Chain), porte le skin `1332`,
dont `1332-128.png` repond 404 et `1332-64.png` repond 200 avec un PNG de
8087 octets. C'est notre transformation qui ne lisait que la cle `sd`; cette
icone-la avait fini par etre commitee a la main (`a9c6eb918`). Le transform
garde maintenant l'adresse 64 px sous `image_url_fallback` et cette etape la
tente.

**Ce que le lot fait.** Une session pour tout le run, avec reprises; un delai
maximal sur chaque requete; un telechargement par objet pour les deux
repertoires; l'autre taille tentee quand la premiere manque; une connexion qui
echoue est comptee, l'objet suivant est tente, et le code de sortie le dit.
"""
import contextlib
import io
import json
import os
import sys
import tempfile
from unittest import mock

import requests
from django.test import SimpleTestCase

RACINE = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
SCRAPER = os.path.join(RACINE, 'itemscraper')

OBJETS = [
    {'name_en': 'Gelano', 'w_type': 'Ring', 'image_url': 'https://x/1.png'},
    {'name_en': 'Kaonashi Mask', 'w_type': 'Hat',
     'image_url': 'https://x/2.png'},
    {'name_en': 'Bow Meow', 'w_type': 'Pet', 'image_url': 'https://x/3.png'},
]

#: La forme de Mister Penguin Chain: la taille demandee manque, l'autre existe.
OBJET_AVEC_REPLI = [
    {'name_en': 'Mister Penguin Chain', 'w_type': 'Amulet',
     'image_url': 'https://x/1332-128.png',
     'image_url_fallback': 'https://x/1332-64.png'},
]


#: Dofus 2 comes from the dofusdude mirror, whose urls carry Ankama's icon id.
OBJET_DOFUS2 = [
    {'name_en': 'Twiggy Sword', 'w_type': 'Sword',
     'image_url': 'https://api.dofusdu.de/dofus2/img/item/6007-200.png',
     'image_url_fallback': 'https://api.dofusdu.de/dofus2/img/item/6007.png'},
]
ANKAMA_6007 = 'https://static.ankama.com/dofus/www/game/items/200/6007.png'


def _scraper():
    if SCRAPER not in sys.path:
        sys.path.insert(0, SCRAPER)
    import get_equipments4
    return get_equipments4


class _Reponse:

    def __init__(self, status_code):
        self.status_code = status_code
        self.content = b'png' if status_code == 200 else b''


class _Session:
    """Compte les requetes; fait tomber les unes, repond 404 aux autres."""

    def __init__(self, en_panne=(), absentes=()):
        self.appels = []
        self.en_panne = set(en_panne)
        self.absentes = set(absentes)

    def get(self, url, **options):
        self.appels.append((url, options))
        if url in self.en_panne:
            raise requests.ConnectionError('WinError 10053')
        return _Reponse(404 if url in self.absentes else 200)


class OneImageThatFailsDoesNotStopTheOthersTests(SimpleTestCase):

    def _lancer(self, session, objets=None, version='beta'):
        scraper = _scraper()
        stockees = []
        objets = OBJETS if objets is None else objets
        with tempfile.TemporaryDirectory() as dossier:
            entree = os.path.join(dossier, 'transformed_equipment.json')
            with open(entree, 'w', encoding='utf-8') as fichier:
                json.dump(objets, fichier)
            with (mock.patch.object(scraper, 'make_session',
                                    return_value=session) as fabrique,
                  mock.patch.object(scraper, 'store_image',
                                    side_effect=lambda contenu, chemin:
                                    stockees.append(chemin)),
                  mock.patch.object(sys, 'argv',
                                    ['get_equipments4.py',
                                     '--game-version', version,
                                     '--input-file', entree]),
                  contextlib.redirect_stdout(io.StringIO())):
                code = scraper.main()
        return code, fabrique.call_count, stockees

    def test_each_item_is_fetched_once_on_one_connection(self):
        session = _Session()
        code, sessions, stockees = self._lancer(session)
        self.assertEqual(0, code)
        self.assertEqual(1, sessions)
        self.assertEqual(len(OBJETS), len(session.appels))
        self.assertEqual(2 * len(OBJETS), len(stockees))

    def test_a_dropped_connection_fails_the_run_and_the_next_item_is_tried(
            self):
        session = _Session(en_panne={'https://x/1.png'})
        code, _, stockees = self._lancer(session)
        self.assertEqual(1, code)
        self.assertEqual(len(OBJETS), len(session.appels))
        self.assertEqual(2 * (len(OBJETS) - 1), len(stockees))
        self.assertFalse([c for c in stockees if 'Gelano' in c])

    def test_an_image_the_source_does_not_have_does_not_fail_the_run(self):
        session = _Session(absentes={'https://x/1.png'})
        code, _, stockees = self._lancer(session)
        self.assertEqual(0, code)
        self.assertEqual(len(OBJETS), len(session.appels))
        self.assertEqual(2 * (len(OBJETS) - 1), len(stockees))

    def test_a_size_the_source_lacks_falls_back_to_the_one_it_renders(self):
        session = _Session(absentes={'https://x/1332-128.png'})
        code, _, stockees = self._lancer(session, OBJET_AVEC_REPLI)
        self.assertEqual(0, code)
        self.assertEqual(['https://x/1332-128.png', 'https://x/1332-64.png'],
                         [url for url, _options in session.appels])
        self.assertEqual(2, len(stockees))

    def test_a_dropped_connection_does_not_burn_the_fallback(self):
        """Un repli n'a de sens que si la source a repondu."""
        session = _Session(en_panne={'https://x/1332-128.png'})
        code, _, stockees = self._lancer(session, OBJET_AVEC_REPLI)
        self.assertEqual(1, code)
        self.assertEqual(['https://x/1332-128.png'],
                         [url for url, _options in session.appels])
        self.assertEqual([], stockees)

    def test_dofus2_takes_its_picture_from_ankama_first(self):
        session = _Session()
        code, _, stockees = self._lancer(session, OBJET_DOFUS2, 'dofus2')
        self.assertEqual(0, code)
        self.assertEqual([ANKAMA_6007],
                         [url for url, _options in session.appels])
        self.assertEqual(2, len(stockees))

    def test_dofus2_falls_back_to_the_mirror_where_ankama_has_none(self):
        # 26 of the 3388 answered 403 on 2026-09-18.
        session = _Session(absentes={ANKAMA_6007})
        code, _, stockees = self._lancer(session, OBJET_DOFUS2, 'dofus2')
        self.assertEqual(0, code)
        self.assertEqual([ANKAMA_6007, OBJET_DOFUS2[0]['image_url']],
                         [url for url, _options in session.appels])
        self.assertEqual(2, len(stockees))

    def test_the_other_versions_keep_their_own_source(self):
        session = _Session()
        self._lancer(session, OBJET_DOFUS2, 'dofus3')
        self.assertEqual([OBJET_DOFUS2[0]['image_url']],
                         [url for url, _options in session.appels])

    def test_every_request_has_a_deadline(self):
        session = _Session()
        self._lancer(session)
        for url, options in session.appels:
            with self.subTest(url=url):
                self.assertGreater(options.get('timeout') or 0, 0)
