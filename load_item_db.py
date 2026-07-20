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
import platform
import sqlite3
import importlib

try:
    fashionista_config = importlib.import_module('fashionistapulp.fashionista_config')
except ModuleNotFoundError:
    fashionista_config = importlib.import_module('fashionistapulp.fashionistapulp.fashionista_config')

get_items_db_path = fashionista_config.get_items_db_path
get_items_dump_path = fashionista_config.get_items_dump_path


def _sanitize_dump_sql(sql_script):
    sanitized_lines = []
    for line in sql_script.splitlines():
        if 'sqlite_sequence' in line.lower():
            continue
        sanitized_lines.append(line)
    return '\n'.join(sanitized_lines)

def _build_db_file(target_path, dumped_db_path):
    """Create a fresh SQLite DB at target_path from the SQL dump."""
    if platform.system() == 'Windows':
        # Executescript handles semicolons in SQL strings correctly.
        with open(dumped_db_path, 'r', encoding='utf-8') as f:
            sql_script = _sanitize_dump_sql(f.read())
        conn = sqlite3.connect(target_path)
        conn.executescript("PRAGMA foreign_keys = OFF;")
        conn.executescript(sql_script)
        conn.commit()
        conn.close()
    else:
        # One big transaction with fsync disabled while building the private
        # temp file. The dump carries no BEGIN/COMMIT, so the bare CLI used
        # to run every INSERT in its own autocommit with an fsync each
        # (~76k fsyncs once the monster grades landed): minutes of boot on
        # VPS disks, which kept production in maintenance on 2026-07-20.
        # Crash-safety is not needed here: the temp file is discarded on
        # failure and os.replace provides the atomicity.
        return_code = os.system(
            '{ echo "PRAGMA synchronous=OFF; PRAGMA journal_mode=MEMORY; '
            'BEGIN TRANSACTION;"; cat %s; echo "COMMIT;"; } | sqlite3 %s'
            % (dumped_db_path, target_path))
        if return_code != 0:
            raise RuntimeError('sqlite3 import failed (exit %d)' % return_code)
        os.system('chmod 666 %s' % target_path)


def main():
    parser = argparse.ArgumentParser(description="Load item dump into SQLite database")
    parser.add_argument("--game-version", default="dofus3", help="Game version (dofus3, beta, retro, touch)")
    args = parser.parse_args()

    items_db_path = get_items_db_path(args.game_version)
    dumped_db_path = get_items_dump_path(args.game_version)

    # Build into a private temp file, then atomically move it into place.
    # structure.py rebuilds this DB on import, so every Gunicorn worker rebuilds
    # it on startup. The old "rm then sqlite3 < dump" deleted the live file
    # mid-write, so one worker could wipe another's half-written DB -> SQLite
    # "disk I/O error" and a corrupt items DB (empty/garbage builds). A unique
    # temp + os.replace makes each rebuild atomic: readers and concurrent
    # rebuilders always see a complete database.
    tmp_db_path = '%s.tmp.%d' % (items_db_path, os.getpid())
    if os.path.exists(tmp_db_path):
        os.remove(tmp_db_path)

    print(f"Importing database from {dumped_db_path} to {items_db_path}")
    try:
        _build_db_file(tmp_db_path, dumped_db_path)
        os.replace(tmp_db_path, items_db_path)  # atomic on the same filesystem
        print("Database import completed successfully.")
    except Exception as e:
        print(f"Error during database import: {e}")
        if os.path.exists(tmp_db_path):
            try:
                os.remove(tmp_db_path)
            except OSError:
                pass
        return

    # Ensure the file is writable (equivalent of chmod 666 on Windows).
    try:
        if platform.system() == 'Windows':
            import stat
            os.chmod(items_db_path, stat.S_IWRITE | stat.S_IREAD)
        print(f"Permissions set on {items_db_path}")
    except Exception as e:
        print(f"Warning: Could not set permissions on database: {e}")

if __name__ == '__main__':
    main()
