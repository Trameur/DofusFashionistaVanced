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
import subprocess
import sqlite3

from fashionistapulp.fashionista_config import get_items_db_path, get_items_dump_path

def main():
    items_db_path = get_items_db_path()
    dump_path = get_items_dump_path()
    
    if platform.system() == 'Windows':
        try:
            print(f"Dumping database from {items_db_path} to {dump_path}")
            
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
                with open(dump_path, 'w', encoding='utf-8') as f:
                    subprocess.run(["sqlite3", items_db_path, ".dump"], 
                                  stdout=f, 
                                  stderr=subprocess.PIPE, 
                                  text=True, 
                                  check=True)
            else:
                # Utiliser le module sqlite3 Python si l'exécutable n'est pas disponible
                conn = sqlite3.connect(items_db_path)
                with open(dump_path, 'w', encoding='utf-8') as f:
                    # Obtenir une liste de toutes les tables
                    cursor = conn.cursor()
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
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
                                elif isinstance(value, str):
                                    # Échapper les apostrophes et guillemets
                                    escaped_value = value.replace("'", "''")
                                    values.append(f"'{escaped_value}'")
                                else:
                                    values.append(str(value))
                            # Créer la requête INSERT
                            f.write(f"INSERT INTO {table_name} VALUES ({', '.join(values)});\n")
                
                conn.close()
            
            print("Database dump completed successfully.")
        except Exception as e:
            print(f"Error during database dump: {e}")
    else:
        # Méthode originale pour Linux/macOS
        os.system('sqlite3 %s .dump > %s' % (items_db_path, dump_path))
    
if __name__ == '__main__':
    main()
