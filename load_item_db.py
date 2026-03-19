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

import os
import platform
import sqlite3

from fashionistapulp.fashionista_config import get_items_db_path, get_items_dump_path

def main():
    items_db_path = get_items_db_path()
    dumped_db_path = get_items_dump_path()
    
    # Utiliser des méthodes compatibles Windows/Linux pour supprimer le fichier
    if os.path.exists(items_db_path):
        os.remove(items_db_path)
    
    # Approche pour charger les données selon le système d'exploitation
    if platform.system() == 'Windows':
        print(f"Importing database from {dumped_db_path} to {items_db_path}")
        try:
            # Ouvrir le fichier dump et diviser les instructions SQL
            with open(dumped_db_path, 'r', encoding='utf-8') as f:
                sql_script = f.read()

            # Créer une connexion à la base de données
            conn = sqlite3.connect(items_db_path)
            cursor = conn.cursor()

            # Activer le mode continue on error
            conn.executescript("PRAGMA foreign_keys = OFF;")

            # Diviser le script en instructions individuelles et les exécuter
            # Ignorer les erreurs "table already exists"
            statements = sql_script.split(';')
            for statement in statements:
                statement = statement.strip()
                if statement:
                    try:
                        cursor.execute(statement + ';')
                    except sqlite3.Error as e:
                        # Ignorer les erreurs "table already exists"
                        if "already exists" not in str(e):
                            print(f"Error executing statement: {e}")

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
