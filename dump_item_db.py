#!/usr/bin/env python

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

import argparse
import os
import subprocess
import sqlite3
import sys

from fashionistapulp.fashionista_config import get_items_db_path, get_items_dump_path
from fashionistapulp.game_versions import version_keys

def main():
    parser = argparse.ArgumentParser(description="Dump an items db to its SQL dump file")
    # From the registry, so a version added there needs no edit here. The list
    # used to be written out by hand and had gone stale: Wakfu was refused by a
    # script that dumps whatever tables it is given.
    parser.add_argument("--game-version", default="dofus3",
                        choices=version_keys(include_experimental=True),
                        help="Which version's db/dump pair to use (default dofus3; "
                             "the argument used to be silently ignored)")
    args = parser.parse_args()

    items_db_path = get_items_db_path(args.game_version)
    dump_path = get_items_dump_path(args.game_version)

    # The dump is the tracked source of truth: load_item_db.py rebuilds every
    # version's database from it. Writing straight into it meant a failure
    # halfway through left a truncated dump on disk, and on Linux the shell
    # redirect emptied the file before sqlite3 even ran. Build a private temp
    # file and move it into place, the way load_item_db.py already does.
    tmp_dump_path = '%s.tmp.%d' % (dump_path, os.getpid())
    if os.path.exists(tmp_dump_path):
        os.remove(tmp_dump_path)

    try:
        _write_dump(items_db_path, tmp_dump_path)
        os.replace(tmp_dump_path, dump_path)
        print("Database dump completed successfully.")
    except Exception as e:
        print(f"Error during database dump: {e}")
        if os.path.exists(tmp_dump_path):
            try:
                os.remove(tmp_dump_path)
            except OSError:
                pass
        sys.exit(1)


def _iterdump_to(items_db_path, target_path):
    """The dump sqlite3 itself would write, from the standard library.

    This replaced a hand-rolled serializer that wrote no index at all and
    pushed blobs through str(), so its dump could not be read back. The rest
    of the project already dumps through iterdump (store_item_obtainment), and
    it handles both.
    """
    conn = sqlite3.connect(items_db_path)
    try:
        with open(target_path, 'w', encoding='utf-8') as out_file:
            for statement in conn.iterdump():
                out_file.write(statement)
                out_file.write('\n')
    finally:
        conn.close()


def _write_dump(items_db_path, target_path):
    """Write the SQL dump of items_db_path into target_path."""
    print(f"Dumping database from {items_db_path} to {target_path}")

    # The command line tool when it is there, the standard library when it is
    # not. Only Windows had the fallback, and the machine the pipelines run on
    # is the one with no sqlite3 on its PATH: there the dump raised
    # FileNotFoundError and the whole update stopped.
    try:
        with open(target_path, 'w', encoding='utf-8') as f:
            subprocess.run(['sqlite3', items_db_path, '.dump'],
                           stdout=f, stderr=subprocess.PIPE, check=True)
    except (OSError, subprocess.SubprocessError):
        _iterdump_to(items_db_path, target_path)


if __name__ == '__main__':
    main()
