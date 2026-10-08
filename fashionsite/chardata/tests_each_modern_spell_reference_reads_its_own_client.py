# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Dofus 3 and its beta each build their spell reference from their own client and spell dump."""
import inspect
import os
from unittest import mock

from django.test import SimpleTestCase


def _reader():
    from chardata.tests import itemscraper_module
    return itemscraper_module('store_spell_reference')


class EachModernVersionReadsItsOwnClientTests(SimpleTestCase):

    def _read_for(self, game_version):
        reader = _reader()
        signature = inspect.signature(reader.read_modern)
        calls = []

        def record(*args, **kwargs):
            bound = signature.bind(*args, **kwargs)
            bound.apply_defaults()
            calls.append(dict(bound.arguments))
            return {}

        with mock.patch.object(reader, 'read_modern', side_effect=record):
            reader.build(game_version)
        self.assertEqual(1, len(calls))
        return (os.path.basename(calls[0]['path']), calls[0]['tag'],
                calls[0]['dump_name'])

    def test_each_version_reads_its_class_dump_its_client_tag_and_its_spell_dump(self):
        import fashionista_version as ours
        expected = {
            'dofus3': ('transformed_class_spells.json', ours.FASHIONISTA_VERSION,
                       'transformed_spells.json'),
            'beta': ('transformed_class_spells_beta.json', ours.FASHIONISTA_BETA_VERSION,
                     'transformed_spells_beta.json'),
        }
        for game_version, read in expected.items():
            with self.subTest(game_version=game_version):
                self.assertEqual(read, self._read_for(game_version))
