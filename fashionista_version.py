"""Centralized version metadata for Dofus Fashionista."""
from __future__ import annotations

FASHIONISTA_VERSION = "3.6.10.11"
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
WATCHED_TOUCH_ASSETS = "3.2.13_miqAldppdZIIl0c_i,HlUFqPb44FCiSO"

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

# If Retro moves its client build while the lang data above stays fixed, these
# representative visual assets tell us whether the committed Retro renders
# need a refresh even though the item database does not.
WATCHED_RETRO_ASSET_SAMPLE = {
    'resources/app/retroclient/clips/items/1/1.swf': {
        'hash': 'dd03c8a425ac1d3cd185955288ca5d82ff96ade3',
        'size': 1651,
    },
    'resources/app/retroclient/clips/items/1/100.swf': {
        'hash': '89cd4af75da7670df327259e78a4889373661890',
        'size': 550,
    },
    'resources/app/retroclient/clips/items/16/1.swf': {
        'hash': 'f5d1d94af51c2f8fbdedc232171dd06ae86c6294',
        'size': 412,
    },
    'resources/app/retroclient/clips/items/22/1.swf': {
        'hash': '28711c4f28507cc3bb4b2b52e2c05e2e83cf0b83',
        'size': 1277,
    },
    'resources/app/retroclient/clips/spells/icons/up/1.swf': {
        'hash': '6fee82b3c0bde91eadf0d48a930262eaed20ec3c',
        'size': 748,
    },
    'resources/app/retroclient/clips/spells/icons/up/101.swf': {
        'hash': '5f624431a12ff02e5e6424aa19cdcdea0ee20f2d',
        'size': 884,
    },
    'resources/app/retroclient/clips/artworks/big/31.swf': {
        'hash': 'd9f03880309cf9d30f264e9c1e68d83ddd14210b',
        'size': 16967,
    },
    'resources/app/retroclient/clips/artworks/big/40.swf': {
        'hash': '787815dcba9829f93cd5b7592e4401c7d3f4c743',
        'size': 24051,
    },
    'resources/app/retroclient/clips/sprites/31.swf': {
        'hash': '6c8debc9d76dadb88cc9e63eb607d9cc6e3ba18a',
        'size': 191437,
    },
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
