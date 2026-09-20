# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A token is compared in constant time wherever one is compared."""
from django.test import SimpleTestCase

from chardata.encoded_char_id import decode_char_id, encode_char_id


class TokensAreComparedInConstantTimeTests(SimpleTestCase):

    def test_a_valid_encoded_id_still_decodes(self):
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
        import os
        import re

        racine = os.path.dirname(os.path.abspath(__file__))
        motif = re.compile(
            r'^\s*(?:if|elif|return|assert)\s+[^\n]*?'
            r'(\w*(?:token|hmac|signature|digest)\w*)\s*(==|!=)\s*[^\n:]+',
            re.I | re.M)
        # digest also compares content (version_content compares two catalogue digests), which is no secret
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
