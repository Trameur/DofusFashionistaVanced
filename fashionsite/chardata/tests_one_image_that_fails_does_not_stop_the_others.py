# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""One icon that fails to download does not stop the others."""
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

# The Mister Penguin Chain shape: the size asked is missing, the other exists
OBJET_AVEC_REPLI = [
    {'name_en': 'Mister Penguin Chain', 'w_type': 'Amulet',
     'image_url': 'https://x/1332-128.png',
     'image_url_fallback': 'https://x/1332-64.png'},
]


# Dofus 2 comes from the dofusdude mirror, whose urls carry Ankama's icon id
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
        # A few of the mirror's icons answer 403
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
