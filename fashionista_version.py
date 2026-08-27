"""Centralized version metadata for Dofus Fashionista."""
from __future__ import annotations

FASHIONISTA_VERSION = "3.6.10.11"
FASHIONISTA_BETA_VERSION = "3.6.7.7"
FASHIONISTA_DOFUS2_VERSION = "2.73.3.14"
FASHIONISTA_RETRO_VERSION = "1.48"
FASHIONISTA_TOUCH_VERSION = "1.73"

# What the version watch compares for the two versions whose public number
# never moves. Retro stays "1.48" and Touch "1.73" in the footer while their
# real build changes with every content patch, so those two are watched here
# instead. Update them when the matching pipeline is re-run.
WATCHED_RETRO_BUILD = "1.49.0.5616.438-085f62d"
WATCHED_TOUCH_ASSETS = "3.2.12_cLlB,151J4Vd.fZX3eoz-xHi7Tx6Mw*3"

# Retro item data comes from the lang CDN, not from the client build: 1.49.0
# shipped with these lang versions unchanged, and a full re-scrape gave a
# byte-identical dump. The categories the item pipeline reads are watched here
# so a lang publish is caught even when the build string stands still.
WATCHED_RETRO_LANG = {
    'items': '1260',
    'itemstats': '1259',
    'itemsets': '1254',
    'crafts': '1258',
    'effects': '1258',
    'classes': '1258',
    'spells': '1254',
}


def get_version() -> str:
    """Return the current site/game version string."""
    return FASHIONISTA_VERSION


def get_beta_version() -> str:
    return FASHIONISTA_BETA_VERSION


def get_dofus2_version() -> str:
    return FASHIONISTA_DOFUS2_VERSION


def get_retro_version() -> str:
    return FASHIONISTA_RETRO_VERSION


def get_touch_version() -> str:
    return FASHIONISTA_TOUCH_VERSION


if __name__ == "__main__":
    print(get_version())
