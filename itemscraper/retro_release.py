# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Which Retro client release a step reads, and the version key that names its folders."""
from pathlib import Path

ITEMSCRAPER = Path(__file__).resolve().parent
ROOT = ITEMSCRAPER.parent
STATIC = ROOT / 'fashionsite' / 'chardata' / 'static' / 'chardata'
STATICFILES = ROOT / 'fashionsite' / 'staticfiles' / 'chardata'

MAIN = 'main'
BETA = 'beta'
RELEASES = (MAIN, BETA)
VERSION_KEYS = {MAIN: 'retro', BETA: 'retrobeta'}
NOTICE = '[%s]' % VERSION_KEYS[BETA]


def add_release_argument(parser):
    """The --release option every Retro step takes."""
    parser.add_argument('--release', choices=RELEASES, default=MAIN,
                        help='Retro client release to read: main (default) or beta')


def version_key(release=MAIN):
    """The registry key of a release, which is also its cytrus_cdn.RELEASES key."""
    return VERSION_KEYS[release]


def is_beta(release):
    """True for the beta release."""
    return release == BETA


def raw_dir(release=MAIN):
    """Where the lang files and client clips of a release are kept."""
    return ITEMSCRAPER / ('%s_raw' % version_key(release))


def work_dir(release=MAIN):
    """Where the transformed files of a release are written."""
    return ITEMSCRAPER / version_key(release)


def dump_path(release=MAIN):
    """The SQL dump of a release: main's committed one, the beta's in its work folder."""
    if is_beta(release):
        return work_dir(release) / ('item_db_dumped_%s.dump' % version_key(release))
    return ROOT / 'fashionistapulp' / 'fashionistapulp' / 'item_db_dumped_retro.dump'


def static_dir(kind, release=MAIN):
    """The static folder of one asset kind (items, pets, spells, monsters) for a release."""
    return STATIC / kind / version_key(release)


def notice(text):
    """One line the pipeline copies into its beta report."""
    print('%s %s' % (NOTICE, text), flush=True)
