#!/usr/bin/env python

"""
Script pour créer manuellement la table manquante 'chardata_itemdbversion'
et y insérer les valeurs de base.
"""

import os
import sys
import platform
import django
import hashlib
import datetime
import traceback

# Configurer l'environnement Django
if platform.system() == 'Windows':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fashionsite.settings')
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fashionsite'))
else:
    # Chemin pour Docker
    sys.path.insert(0, '/app/fashionsite')
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fashionsite.settings')

def calculate_hash(file_path):
    """Calcule le hash MD5 d'un fichier."""
    if not os.path.exists(file_path):
        print(f"Le fichier {file_path} n'existe pas!")
        return None
        
    md5_hash = hashlib.md5()
    with open(file_path, 'rb') as f:
        # Lire par blocs de 4096 octets pour optimiser la mémoire
        for byte_block in iter(lambda: f.read(4096), b""):
            md5_hash.update(byte_block)
    return md5_hash.hexdigest()

def main():
    print("Initialisation de la table chardata_itemdbversion...")
    try:
        # Initialiser Django
        django.setup()

        # Importer le modèle ItemDbVersion
        from chardata.models import ItemDbVersion
        from django.db import connection

        # Vérifier si la table existe
        with connection.cursor() as cursor:
            try:
                cursor.execute("SELECT COUNT(*) FROM chardata_itemdbversion")
                count = cursor.fetchone()[0]
                print(f"La table chardata_itemdbversion existe et contient {count} enregistrements.")
                return  # La table existe déjà, on arrête
            except Exception as e:
                print(f"La table n'existe pas ou est inaccessible : {e}")
                
                # Tenter d'appliquer les migrations Django
                print("Tentative d'application des migrations Django...")
                try:
                    from django.core.management import call_command
                    call_command('migrate', 'chardata')
                    print("Migrations Django appliquées avec succès.")
                    
                    # Vérifier que la table existe après la migration
                    cursor.execute("SELECT COUNT(*) FROM chardata_itemdbversion")
                    count = cursor.fetchone()[0]
                    print(f"La table chardata_itemdbversion existe et contient {count} enregistrements.")
                    
                    # Si la table est vide, nous insérons une valeur initiale
                    if count == 0:
                        # Déterminer le chemin du fichier de dump selon l'environnement
                        if platform.system() == 'Windows':
                            base_path = os.path.dirname(os.path.abspath(__file__))
                            dump_path = os.path.join(base_path, 'fashionistapulp', 'fashionistapulp', 'items.db.dump')
                        else:
                            dump_path = '/app/fashionistapulp/fashionistapulp/items.db.dump'
                        
                        # Calculer le hash ou utiliser une valeur par défaut
                        dump_hash = calculate_hash(dump_path) or "initial_hash_" + datetime.datetime.now().strftime("%Y%m%d%H%M%S")
                        
                        # Créer un nouvel enregistrement dans ItemDbVersion
                        item_db_version = ItemDbVersion(dump_hash=dump_hash)
                        item_db_version.save()
                        print(f"Hash initial inséré via modèle Django: {dump_hash}")
                    
                    return
                except Exception as migrate_error:
                    print(f"Erreur lors de l'application des migrations : {migrate_error}")
                
                # Si les migrations échouent, créer la table manuellement
                print("Création manuelle de la table chardata_itemdbversion...")
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS chardata_itemdbversion (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        dump_hash VARCHAR(255) NOT NULL,
                        created_time DATE
                    )
                """)
                
                # Déterminer le chemin du fichier de dump selon l'environnement
                if platform.system() == 'Windows':
                    base_path = os.path.dirname(os.path.abspath(__file__))
                    dump_path = os.path.join(base_path, 'fashionistapulp', 'fashionistapulp', 'items.db.dump')
                else:
                    dump_path = '/app/fashionistapulp/fashionistapulp/items.db.dump'
                
                # Calculer le hash du fichier de dump actuel
                dump_hash = calculate_hash(dump_path)
                
                if dump_hash:
                    # Insérer une valeur initiale avec la date actuelle
                    current_date = datetime.datetime.now().strftime("%Y-%m-%d")
                    cursor.execute("""
                        INSERT INTO chardata_itemdbversion (dump_hash, created_time) 
                        VALUES (%s, %s)
                    """, [dump_hash, current_date])
                    print(f"Hash initial inséré : {dump_hash}")
                else:
                    # Utiliser un hash fictif si le fichier n'existe pas
                    current_date = datetime.datetime.now().strftime("%Y-%m-%d")
                    cursor.execute("""
                        INSERT INTO chardata_itemdbversion (dump_hash, created_time) 
                        VALUES (%s, %s)
                    """, ["initial_hash_" + datetime.datetime.now().strftime("%Y%m%d%H%M%S"), current_date])
                    print("Hash initial fictif inséré")
                
                print("Table chardata_itemdbversion créée et initialisée avec succès.")

    except Exception as e:
        print(f"Erreur lors de l'initialisation de la table : {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()
