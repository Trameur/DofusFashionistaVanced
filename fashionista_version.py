"""Centralized version metadata for Dofus Fashionista."""
from __future__ import annotations

FASHIONISTA_VERSION = "3.6.11.12"
FASHIONISTA_BETA_VERSION = "3.6.7.7"
FASHIONISTA_DOFUS2_VERSION = "2.73.3.14"
FASHIONISTA_RETRO_VERSION = "1.48"
FASHIONISTA_TOUCH_VERSION = "1.73"

# What the version watch compares for versions whose public number is not the
# release signal. Touch stays "1.73" in the footer while its asset bundle moves,
# so the bundle is watched here. Retro's build is kept as last-seen diagnostics;
# its item-data gate is WATCHED_RETRO_LANG below.
#
# A Touch bundle that moves does not have to mean new gear either. 3.2.13
# changed two item descriptions out of the French fallback and added one item,
# out of 13517, and all three are ornaments: their typeId sits at 182 to 185,
# where every entry is level 1 with at most two effects, against the varied
# levels and up to six effects of the real cloaks and shields. The database
# came out identical, 39 tables compared by content.
WATCHED_RETRO_BUILD = "1.49.2.5639.441-0b18f88"
WATCHED_TOUCH_ASSETS = "3.3.4_JQRGJCkoJZrlHn0XElOeOU3CuELSZK4T"

# Retro item data comes from the lang CDN, not from the client build, and that
# is now measured twice rather than argued: 1.49.0 and then 1.49.1 both shipped
# with every lang version below standing still, and a full re-scrape of each
# gave a byte-identical database -- 39 tables, content compared row by row, not
# a count. So a Retro build string that moves says nothing about the items, and
# the categories the item pipeline reads are what to watch.
WATCHED_RETRO_LANG = {
    'items': '1260',
    'itemstats': '1259',
    'itemsets': '1254',
    'crafts': '1258',
    'effects': '1258',
    'classes': '1258',
    'spells': '1254',
}

# Whether the committed Retro renders need a refresh, over the WHOLE set the
# four Retro renderers read, not a sample of it. 9428 clips at 1.49.3: items
# 6862, sprites 1066, artworks 826, spell icons 674.
#
# It used to be nine hand-picked files, and they could not answer the question.
# Three of the four Retro build transitions in this repo's history moved
# rendered clips and the sample fired on 0 of 9 every time: its nine names are
# ids 1, 31, 40, 100 and 101, the oldest content in a 2004 game, byte-identical
# at every version. Worse, it looked each name UP, so an ADDED file was never a
# key and could not be seen at all, and 38 of the 48 rendered changes in
# 1.48.21 to 1.49.0 were pure additions.
#
# Reading all 9428 is the cheap option, not the expensive one: the sample
# already downloaded this entire 6.9 MB manifest and kept nine entries, and its
# nine lookups cost eight times the single pass that reads every one.
#
# NEVER type this by hand. `python itemscraper/check_game_versions.py
# --emit-snapshot` reads the live manifest and prints the two lines below.
WATCHED_RETRO_ASSET_DIGEST = "75d84aec73638cbe2010fe8d12f1c90a5f40250a"
WATCHED_RETRO_ASSET_COUNT = 9428


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
