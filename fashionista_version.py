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
#
# A Touch bundle that moves does not have to mean new gear either. 3.2.13
# changed two item descriptions out of the French fallback and added one item,
# out of 13517, and all three are ornaments: their typeId sits at 182 to 185,
# where every entry is level 1 with at most two effects, against the varied
# levels and up to six effects of the real cloaks and shields. The database
# came out identical, 39 tables compared by content.
WATCHED_RETRO_BUILD = "1.49.1.5632.439-348db46"
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
