"""Centralized version metadata for Dofus Fashionista."""
from __future__ import annotations

FASHIONISTA_VERSION = "3.6.12.16"
FASHIONISTA_BETA_VERSION = "3.7.2.2"
FASHIONISTA_DOFUS2_VERSION = "2.73.3.14"
FASHIONISTA_RETRO_VERSION = "1.49.5"
FASHIONISTA_TOUCH_VERSION = "1.74.5"

# (UTC day, patch): Ankama's release day up to 2.68, the day our data went in from 2.69 on; retro and touch by hand
PATCH_TIMELINE = {
    'dofus3': [
        ('2014-02-11', '2.18'),
        ('2014-04-15', '2.19'),
        ('2014-05-13', '2.20'),
        ('2014-06-13', '2.21'),
        ('2014-08-08', '2.22'),
        ('2014-09-23', '2.23'),
        ('2014-10-10', '2.24'),
        ('2014-11-12', '2.25'),
        ('2014-12-09', '2.26'),
        ('2015-02-16', '2.27'),
        ('2015-04-21', '2.28'),
        ('2015-06-23', '2.29'),
        ('2015-08-31', '2.30'),
        ('2015-10-27', '2.31'),
        ('2015-12-08', '2.32'),
        ('2016-02-02', '2.33'),
        ('2016-04-18', '2.34'),
        ('2016-06-21', '2.35'),
        ('2016-09-20', '2.36'),
        ('2016-10-18', '2.37'),
        ('2016-12-06', '2.39'),
        ('2017-02-10', '2.40'),
        ('2017-04-04', '2.41'),
        ('2017-06-20', '2.42'),
        ('2017-09-05', '2.43'),
        ('2017-12-05', '2.45'),
        ('2018-03-27', '2.46'),
        ('2018-06-26', '2.47'),
        ('2018-09-18', '2.48'),
        ('2018-12-11', '2.49'),
        ('2019-01-29', '2.50'),
        ('2019-04-09', '2.51'),
        ('2019-07-02', '2.52'),
        ('2019-10-01', '2.53'),
        ('2019-12-11', '2.54'),
        ('2020-07-15', '2.56'),
        ('2020-09-21', '2.57'),
        ('2020-12-15', '2.58'),
        ('2021-04-20', '2.59'),
        ('2021-07-06', '2.60'),
        ('2021-09-14', '2.61'),
        ('2021-12-07', '2.62'),
        ('2022-03-22', '2.63'),
        ('2022-06-28', '2.64'),
        ('2022-09-20', '2.65'),
        ('2022-12-06', '2.66'),
        ('2023-03-28', '2.67'),
        ('2023-07-04', '2.68'),
        ('2023-09-28', '2.69'),
        ('2023-12-07', '2.70'),
        ('2024-03-30', '2.71'),
        ('2024-06-18', '2.72'),
        ('2024-11-08', '2.73'),
        ('2024-11-29', '3.0'),
        ('2025-04-22', '3.1'),
        ('2025-07-22', '3.2'),
        ('2025-10-01', '3.3'),
        ('2025-12-09', '3.4'),
        ('2026-03-05', '3.5'),
        ('2026-06-23', '3.6'),
    ],
    'beta': [
        ('2026-05-22', '3.5'),
        ('2026-06-03', '3.6'),
        ('2026-09-17', '3.7'),
    ],
    'dofus2': [
        ('2026-05-27', '2.73'),
    ],
    'retro': [
        ('2026-05-28', '1.48'),
        ('2026-08-18', '1.49'),
    ],
    'touch': [
        ('2026-06-07', '1.72'),
        ('2026-07-05', '1.73'),
        ('2026-08-09', '1.74'),
    ],
}

# What the version watch compares for versions whose public number is not the
# release signal. Touch keeps its public number in the footer while its asset
# bundle moves, so the bundle is watched here. Retro's build is kept as
# last-seen diagnostics; its item-data gate is WATCHED_RETRO_LANG below.
#
# A Touch bundle that moves does not have to mean new gear either. 3.2.13
# changed two item descriptions out of the French fallback and added one item,
# out of 13517, and all three are ornaments: their typeId sits at 182 to 185,
# where every entry is level 1 with at most two effects, against the varied
# levels and up to six effects of the real cloaks and shields. The database
# came out identical, 39 tables compared by content.
#
# 3.3.5 moved even less: the same two records out of 13679 in each of the four
# languages Touch still serves, a spell book's criteria (24057) and an
# ornament's look (23923, typeId 185). Retro 1.49.3 moved its build with all
# seven lang categories and all 9428 rendered clips standing still. Both were
# re-scraped on 2026-09-15 and both databases came out identical, every table
# compared as a set of rows.
WATCHED_RETRO_BUILD = "1.49.5.5656.445-401e092"
WATCHED_TOUCH_ASSETS = "3.3.6_6AvTTrLJHOzoovPXExeiipZDAI90KDp."

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
WATCHED_RETRO_ASSET_DIGEST = "157fe4018312a20cda74b5d3f26002569de619cf"
WATCHED_RETRO_ASSET_COUNT = 9447


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
