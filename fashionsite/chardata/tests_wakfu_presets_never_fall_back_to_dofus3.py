# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""A version outside Dofus never gets the presets of Dofus 3."""
from django.test import SimpleTestCase

from chardata.presets import VERSION_PRESETS, version_presets
from fashionistapulp.game_versions import GAME_VERSIONS


class WakfuPresetsNeverFallBackToDofus3Tests(SimpleTestCase):
    def test_wakfu_has_its_own_entry_or_raises(self):
        try:
            found = version_presets('wakfu')
        except KeyError:
            return
        self.assertIsNot(found, VERSION_PRESETS['dofus3'])

    def test_every_version_outside_dofus_is_refused_without_an_entry(self):
        for key, known in GAME_VERSIONS.items():
            if known.dofus or key in VERSION_PRESETS:
                continue
            with self.assertRaises(KeyError, msg=key):
                version_presets(key)

    def test_a_dofus_version_returns_its_own_entry(self):
        for key, known in GAME_VERSIONS.items():
            if known.dofus and key in VERSION_PRESETS:
                self.assertIs(VERSION_PRESETS[key], version_presets(key), key)

    def test_an_unknown_key_still_returns_the_default(self):
        self.assertIs(VERSION_PRESETS['dofus3'], version_presets('no-such-version'))
