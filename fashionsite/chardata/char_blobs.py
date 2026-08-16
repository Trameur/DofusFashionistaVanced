# Copyright (C) 2020 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

"""Reading the pickled columns of a Char without taking the page down.

Its own module, and deliberately importing nothing from the project: every
reader of these columns lives lower in the import graph than chardata.util.
"""

import logging
import pickle

logger = logging.getLogger(__name__)


def read_char_blob(blob, default, field, char=None):
    """A pickled char column, or the default when it no longer reads back.

    These columns hold pickles of objects that have been renamed and moved
    over the years, and one that fails used to raise straight out of whatever
    page read it: the public gallery answered 500 for every visitor because a
    single shared build had an unreadable minimum_stats. A build that lost its
    minimums is worth more to its owner than a page nobody can open.
    """
    if not blob:
        return default
    try:
        return pickle.loads(blob)
    except Exception:
        logger.warning('char %s has an unreadable %s',
                       getattr(char, 'id', '?'), field, exc_info=True)
        return default
