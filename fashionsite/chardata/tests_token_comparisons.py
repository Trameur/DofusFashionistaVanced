# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Un jeton se compare en temps constant, partout ou il s'en compare un.

Le projet le savait deja : `_password_reset_token_is_valid` utilise
`constant_time_compare`, et le docstring voisin raconte meme le defaut qu'il a
fallu corriger sur ces jetons. Deux autres comparaisons du meme genre etaient
restees en `!=` -- la signature de l'identifiant de build encode, et le jeton
de confirmation d'adresse.

**Ce module ne pretend pas refermer une faille.** Ni l'une ni l'autre n'est
exploitable en pratique : la premiere porte sur quatre octets a travers le
reseau, ou le signal de temps est noye des ordres de grandeur sous le bruit ;
la seconde n'ouvre qu'une action idempotente, activer un compte. Ce qui se
garde ici est la COHERENCE : le meme fichier faisait les deux, a trois
fonctions d'intervalle.

Le test verifie le comportement, pas la forme -- une comparaison en temps
constant doit accepter le bon jeton et refuser tous les autres, y compris ceux
qui partagent un prefixe avec lui.
"""
from django.test import SimpleTestCase

from chardata.encoded_char_id import decode_char_id, encode_char_id


class TokensAreComparedInConstantTimeTests(SimpleTestCase):

    def test_a_valid_encoded_id_still_decodes(self):
        """Le plancher. Sans lui, une comparaison qui refuse TOUT passerait
        les tests suivants sans rien garder."""
        for identifiant in (1, 42, 12345, 246814):
            encode = encode_char_id(identifiant)
            self.assertEqual(
                identifiant, decode_char_id(encode),
                'a freshly encoded id no longer decodes: %r' % encode)

    def test_a_tampered_signature_is_refused(self):
        refuses = 0
        encode = encode_char_id(246814)
        import base64
        brut = base64.b64decode(encode.translate(
            str.maketrans('.-_', '+/=')))
        corps, signature = brut[:-4], brut[-4:]
        for position in range(4):
            for delta in (1, 128):
                fausse = bytearray(signature)
                fausse[position] = (fausse[position] + delta) % 256
                if bytes(fausse) == signature:
                    continue
                faux = base64.b64encode(corps + bytes(fausse)).decode(
                    'utf-8').translate(str.maketrans('+/=', '.-_'))
                self.assertIsNone(
                    decode_char_id(faux),
                    'a signature altered at byte %d was accepted' % position)
                refuses += 1
        self.assertGreaterEqual(
            refuses, 6,
            'only %d altered signatures were actually built, so this test '
            'barely exercises the comparison' % refuses)

    def test_every_token_comparison_in_the_project_is_constant_time(self):
        """L'invariant que ce module existe pour tenir.

        Il lit la source parce qu'un canal temporel ne s'observe pas dans un
        test unitaire -- et parce que ce qui se garde est justement qu'on
        n'ecrive pas `!=` la prochaine fois.
        """
        import os
        import re

        racine = os.path.dirname(os.path.abspath(__file__))
        motif = re.compile(
            r'^\s*(?:if|elif|return|assert)\s+[^\n]*?'
            r'(\w*(?:token|hmac|signature|digest)\w*)\s*(==|!=)\s*[^\n:]+',
            re.I | re.M)
        # `digest` sert aussi a comparer du CONTENU (version_content compare
        # deux empreintes de catalogue), ce qui n'est pas un secret.
        SANS_OBJET = ('version_content.py',)
        fautes, examines = [], 0
        for dossier, _sous, fichiers in os.walk(racine):
            if 'migrations' in dossier:
                continue
            for f in fichiers:
                if not f.endswith('.py') or f.startswith('test'):
                    continue
                if f in SANS_OBJET:
                    continue
                chemin = os.path.join(dossier, f)
                with open(chemin, encoding='utf-8', errors='replace') as fh:
                    texte = fh.read()
                examines += 1
                for m in motif.finditer(texte):
                    fautes.append('%s:%d %s'
                                  % (f, texte[:m.start()].count('\n') + 1,
                                     m.group(0).strip()[:70]))
        self.assertGreaterEqual(
            examines, 30,
            'only %d modules scanned; the sweep is too narrow for its zero to '
            'mean anything' % examines)
        self.assertFalse(
            fautes,
            'these compare a token with == or != instead of '
            'constant_time_compare: %s' % fautes[:4])
