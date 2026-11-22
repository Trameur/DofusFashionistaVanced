# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""What the tip and the solver share about transcendence runes."""

from .exo_options import forgeable_type

TRANSCENDENCE_VERSIONS = ('dofus3', 'beta', 'dofus2')


def takes_transcendence_rune(type_name, weapon_key):
    """True when a piece of this type and weapon key can take a transcendence rune."""
    return forgeable_type(type_name, weapon_key)
