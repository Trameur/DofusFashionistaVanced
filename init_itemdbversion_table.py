#!/usr/bin/env python

"""
Creates the missing 'chardata_itemdbversion' table by hand and inserts
its first values.
"""

import os
import sys
import platform
import django
import hashlib
import datetime
import traceback

# Django environment
if platform.system() == 'Windows':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fashionsite.settings')
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fashionsite'))
else:
    # Docker path
    sys.path.insert(0, '/app/fashionsite')
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fashionsite.settings')

def calculate_hash(file_path):
    """MD5 hash of a file."""
    if not os.path.exists(file_path):
        print(f"The file {file_path} does not exist.")
        return None
        
    md5_hash = hashlib.md5()
    with open(file_path, 'rb') as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            md5_hash.update(byte_block)
    return md5_hash.hexdigest()

def main():
    print("Initializing the chardata_itemdbversion table...")
    try:
        django.setup()

        from chardata.models import ItemDbVersion
        from django.db import connection

        # Does the table exist
        with connection.cursor() as cursor:
            try:
                cursor.execute("SELECT COUNT(*) FROM chardata_itemdbversion")
                count = cursor.fetchone()[0]
                print(f"The chardata_itemdbversion table exists and holds {count} rows.")
                return
            except Exception as e:
                print(f"The table does not exist or cannot be reached: {e}")
                
                # Try the Django migrations first
                print("Trying the Django migrations...")
                try:
                    from django.core.management import call_command
                    call_command('migrate', 'chardata')
                    print("Django migrations applied.")
                    
                    cursor.execute("SELECT COUNT(*) FROM chardata_itemdbversion")
                    count = cursor.fetchone()[0]
                    print(f"The chardata_itemdbversion table exists and holds {count} rows.")
                    
                    # An empty table gets a first row
                    if count == 0:
                        # Dump file path for this environment
                        if platform.system() == 'Windows':
                            base_path = os.path.dirname(os.path.abspath(__file__))
                            dump_path = os.path.join(base_path, 'fashionistapulp', 'fashionistapulp', 'items.db.dump')
                        else:
                            dump_path = '/app/fashionistapulp/fashionistapulp/items.db.dump'
                        
                        # The dump hash, or a default value
                        dump_hash = calculate_hash(dump_path) or "initial_hash_" + datetime.datetime.now().strftime("%Y%m%d%H%M%S")
                        
                        item_db_version = ItemDbVersion(dump_hash=dump_hash)
                        item_db_version.save()
                        print(f"First hash inserted through the Django model: {dump_hash}")
                    
                    return
                except Exception as migrate_error:
                    print(f"Error while applying the migrations: {migrate_error}")
                
                # The migrations failed: create the table by hand
                print("Creating the chardata_itemdbversion table by hand...")
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS chardata_itemdbversion (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        dump_hash VARCHAR(255) NOT NULL,
                        created_time DATE
                    )
                """)
                
                # Dump file path for this environment
                if platform.system() == 'Windows':
                    base_path = os.path.dirname(os.path.abspath(__file__))
                    dump_path = os.path.join(base_path, 'fashionistapulp', 'fashionistapulp', 'items.db.dump')
                else:
                    dump_path = '/app/fashionistapulp/fashionistapulp/items.db.dump'
                
                dump_hash = calculate_hash(dump_path)
                
                if dump_hash:
                    current_date = datetime.datetime.now().strftime("%Y-%m-%d")
                    cursor.execute("""
                        INSERT INTO chardata_itemdbversion (dump_hash, created_time) 
                        VALUES (%s, %s)
                    """, [dump_hash, current_date])
                    print(f"First hash inserted: {dump_hash}")
                else:
                    # Placeholder hash when the dump file is missing
                    current_date = datetime.datetime.now().strftime("%Y-%m-%d")
                    cursor.execute("""
                        INSERT INTO chardata_itemdbversion (dump_hash, created_time) 
                        VALUES (%s, %s)
                    """, ["initial_hash_" + datetime.datetime.now().strftime("%Y%m%d%H%M%S"), current_date])
                    print("Placeholder first hash inserted")
                
                print("chardata_itemdbversion table created and initialized.")

    except Exception as e:
        print(f"Error while initializing the table: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()
