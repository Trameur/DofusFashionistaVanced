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

def main():
    parser = argparse.ArgumentParser(description="Load item dump into SQLite database")
    parser.add_argument("--game-version", default="dofus3", help="Game version (dofus3, beta, retro, touch)")
    args = parser.parse_args()

    items_db_path = get_items_db_path(args.game_version)
    dumped_db_path = get_items_dump_path(args.game_version)
    
    # Utiliser des méthodes compatibles Windows/Linux pour supprimer le fichier
    if os.path.exists(items_db_path):
        os.remove(items_db_path)
    
    # Approche pour charger les données selon le système d'exploitation
    if platform.system() == 'Windows':
        print(f"Importing database from {dumped_db_path} to {items_db_path}")
        try:
            # Executescript handles semicolons in SQL strings correctly.
            with open(dumped_db_path, 'r', encoding='utf-8') as f:
                sql_script = f.read()
            sql_script = _sanitize_dump_sql(sql_script)

            conn = sqlite3.connect(items_db_path)
            conn.executescript("PRAGMA foreign_keys = OFF;")
            conn.executescript(sql_script)
            conn.commit()
            conn.close()
            print("Database import completed successfully.")
        except Exception as e:
            print(f"Error during database import: {e}")
    else:
        # Méthode originale pour Linux/macOS
        os.system('rm %s' % items_db_path)
        os.system('sqlite3 %s < %s' % (items_db_path, dumped_db_path))
        os.system('chmod 666 %s' % items_db_path)
    
    # S'assurer que les permissions sont correctes (équivalent de chmod 666)
    # Sous Windows, nous devons nous assurer que le fichier est accessible en écriture
    try:
        if platform.system() == 'Windows':
            import stat
            os.chmod(items_db_path, stat.S_IWRITE | stat.S_IREAD)
        print(f"Permissions set on {items_db_path}")
    except Exception as e:
        print(f"Warning: Could not set permissions on database: {e}")

if __name__ == '__main__':
    main()
