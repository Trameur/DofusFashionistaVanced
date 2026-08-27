# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""File names Windows will not let a checkout create.

Windows still reserves the old device names, and it reserves them whatever the
extension: CON.png is as unwritable as CON. A repository holding one cannot be
cloned on Windows, which is why `Con.png`, the icon of the Sram spell Con, was
added to .gitignore four separate times rather than fixed. Ignored, it never
reached a deploy, so the spell showed a broken icon in all five versions while
the file sat on the disk of whoever last ran the scraper -- and the guard that
watches for missing icons was green, because it asks the local disk.

Both ends have to agree on the escaped name or the page asks for one file and
the scraper writes another, so the rule lives here rather than in either.
"""

#: The device names Win32 reserves. It matches on the stem, so "con.txt",
#: "CON." and "Con" are all refused, and it is case-insensitive.
WINDOWS_DEVICE_NAMES = frozenset(
    ['con', 'prn', 'aux', 'nul']
    + ['com%d' % n for n in range(1, 10)]
    + ['lpt%d' % n for n in range(1, 10)])

#: Appended to a reserved stem. A trailing underscore cannot collide with a
#: real spell or item name, and it keeps the name readable in a directory.
ESCAPE = '_'


def safe_asset_stem(stem):
    """The stem under which a file may be stored, escaped only if it has to be.

    Everything that is not a reserved device name comes back untouched, so this
    is safe to apply to every name rather than only the ones known to break.
    """
    if not stem:
        return stem
    return stem + ESCAPE if stem.lower() in WINDOWS_DEVICE_NAMES else stem


def is_reserved(stem):
    return bool(stem) and stem.lower() in WINDOWS_DEVICE_NAMES
