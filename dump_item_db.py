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
import subprocess
import sqlite3
import sys

from fashionistapulp.fashionista_config import get_items_db_path, get_items_dump_path

def main():
    parser = argparse.ArgumentParser(description="Dump an items db to its SQL dump file")
    parser.add_argument("--game-version", default="dofus3",
                        choices=("dofus3", "beta", "dofus2", "touch", "retro"),
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


def _write_dump(items_db_path, target_path):
    """Write the SQL dump of items_db_path into target_path."""
    print(f"Dumping database from {items_db_path} to {target_path}")

    if platform.system() == 'Windows':
        # Vérifier si sqlite3.exe est disponible dans le PATH
        try:
            subprocess.run(["sqlite3", "--version"],
                           stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE,
                           check=True)
            sqlite_available = True
        except (subprocess.SubprocessError, FileNotFoundError):
            sqlite_available = False

        if sqlite_available:
            # Utiliser sqlite3 en ligne de commande si disponible
            with open(target_path, 'w', encoding='utf-8') as f:
                subprocess.run(["sqlite3", items_db_path, ".dump"],
                               stdout=f,
                               stderr=subprocess.PIPE,
                               text=True,
                               check=True)
        else:
            # Utiliser le module sqlite3 Python si l'exécutable n'est pas disponible
            conn = sqlite3.connect(items_db_path)
            with open(target_path, 'w', encoding='utf-8') as f:
                # Obtenir une liste de toutes les tables
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' "
                               "AND name <> 'sqlite_sequence';")
                tables = cursor.fetchall()

                # Exporter le schéma et les données pour chaque table
                for table in tables:
                    table_name = table[0]
                    # Exporter le schéma (CREATE TABLE)
                    cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table_name}';")
                    create_statement = cursor.fetchone()[0]
                    f.write(f"{create_statement};\n")

                    # Exporter les données (INSERT)
                    cursor.execute(f"SELECT * FROM {table_name};")
                    rows = cursor.fetchall()
                    for row in rows:
                        # Formater les valeurs pour SQL
                        values = []
                        for value in row:
                            if value is None:
                                values.append("NULL")
                            elif isinstance(value, (bytes, bytearray)):
                                # Les listes picklees d'extra_lines sont des
                                # blobs. Les passer par str() ecrivait b'...'
                                # dans le SQL et le dump ne se rechargeait pas.
                                values.append("X'%s'" % value.hex())
                            elif isinstance(value, str):
                                # Échapper les apostrophes et guillemets
                                escaped_value = value.replace("'", "''")
                                values.append(f"'{escaped_value}'")
                            else:
                                values.append(str(value))
                        # Créer la requête INSERT
                        f.write(f"INSERT INTO {table_name} VALUES ({', '.join(values)});\n")

                # Les index, sinon ce repli rend un dump plus pauvre que celui
                # du CLI: cinq index par version disparaissaient, et toute base
                # reconstruite depuis ce dump repartait sans eux. Les
                # sqlite_autoindex sont recrees par SQLite avec la table.
                cursor.execute(
                    "SELECT sql FROM sqlite_master WHERE type IN "
                    "('index', 'trigger', 'view') AND sql IS NOT NULL "
                    "AND name NOT LIKE 'sqlite_autoindex%';")
                for (statement,) in cursor.fetchall():
                    f.write(f"{statement};\n")

            conn.close()
    else:
        # Méthode originale pour Linux/macOS, dont le code de retour etait
        # ignore: sqlite3 pouvait echouer et laisser un dump vide.
        with open(target_path, 'w', encoding='utf-8') as f:
            subprocess.run(['sqlite3', items_db_path, '.dump'],
                           stdout=f, check=True)


if __name__ == '__main__':
    main()
