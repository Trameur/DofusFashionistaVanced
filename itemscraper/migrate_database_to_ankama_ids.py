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

import sqlite3
import json
import os
import shutil
from datetime import datetime

current_directory = os.path.dirname(os.path.abspath(__file__))

# Load the transformed data to get ankama_id mappings
with open(f'{current_directory}/transformed_equipment.json', 'r', encoding='utf-8') as f:
    equipment_data = json.load(f)

with open(f'{current_directory}/transformed_sets.json', 'r', encoding='utf-8') as f:
    sets_data = json.load(f)

# Create mapping dictionaries: old_id -> new_id
# The old_id is the position in the JSON array (1-indexed)
# For mounts, we need to offset their IDs to avoid conflicts with equipment
# For duplicate items (same ankama_id), we add a counter offset
MOUNT_ID_OFFSET = 1000000
DUPLICATE_ID_OFFSET = 100000000  # Large offset for duplicate item variants

item_id_mapping = {}
ankama_id_counter = {}  # Track how many times we've seen each ankama_id

for i, item in enumerate(equipment_data):
    old_id = i + 1
    ankama_id = item['ankama_id']
    
    # Track duplicates
    if ankama_id not in ankama_id_counter:
        ankama_id_counter[ankama_id] = 0
    else:
        ankama_id_counter[ankama_id] += 1
    
    # Calculate new ID
    if item.get('ankama_type') == 'mounts':
        # Mounts get offset to avoid conflicts with equipment
        new_id = MOUNT_ID_OFFSET + ankama_id
        if ankama_id_counter[ankama_id] > 0:
            new_id += DUPLICATE_ID_OFFSET * ankama_id_counter[ankama_id]
    else:
        # Equipment uses ankama_id directly, with offset for duplicates
        new_id = ankama_id
        if ankama_id_counter[ankama_id] > 0:
            # For duplicate items (e.g., "Ice Daggers 1", "Ice Daggers 2")
            new_id += DUPLICATE_ID_OFFSET * ankama_id_counter[ankama_id]
    
    item_id_mapping[old_id] = new_id

set_id_mapping = {i + 1: set_item['ankama_id'] for i, set_item in enumerate(sets_data)}

def migrate_database(db_path):
    """Migrate an existing database to use ankama_ids instead of sequential IDs"""
    
    # Create backup
    backup_path = f"{db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    print(f"Creating backup: {backup_path}")
    shutil.copy2(db_path, backup_path)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if migration is needed
        cursor.execute("SELECT id, ankama_id FROM items LIMIT 1")
        row = cursor.fetchone()
        if row and row[0] == row[1]:
            print("Database already uses ankama_ids. No migration needed.")
            return
        
        print("Starting migration...")
        
        # Step 1: Create temporary mapping tables
        print("Creating ID mapping tables...")
        cursor.execute("""
            CREATE TEMPORARY TABLE item_id_mapping (
                old_id INTEGER PRIMARY KEY,
                new_id INTEGER
            )
        """)
        
        cursor.execute("""
            CREATE TEMPORARY TABLE set_id_mapping (
                old_id INTEGER PRIMARY KEY,
                new_id INTEGER
            )
        """)
        
        # Insert mappings
        cursor.executemany(
            "INSERT INTO item_id_mapping VALUES (?, ?)",
            item_id_mapping.items()
        )
        
        cursor.executemany(
            "INSERT INTO set_id_mapping VALUES (?, ?)",
            set_id_mapping.items()
        )
        
        # Step 2: Update all tables that reference items or sets
        print("Migrating items table...")
        
        # Create new items table with ankama_id as primary key
        cursor.execute("""
            CREATE TABLE items_new (
                id INTEGER PRIMARY KEY,
                name text,
                level INTEGER,
                type INTEGER,
                item_set INTEGER,
                ankama_id INTEGER,
                ankama_type text,
                removed INTEGER,
                dofustouch INTEGER,
                FOREIGN KEY(type) REFERENCES item_types (id),
                FOREIGN KEY(item_set) REFERENCES sets (id)
            )
        """)
        
        # Copy data with new IDs
        cursor.execute("""
            INSERT INTO items_new
            SELECT 
                COALESCE(m.new_id, i.id) as id,
                i.name,
                i.level,
                i.type,
                CASE 
                    WHEN i.item_set IS NOT NULL AND s.new_id IS NOT NULL 
                    THEN s.new_id 
                    ELSE i.item_set 
                END as item_set,
                i.ankama_id,
                i.ankama_type,
                i.removed,
                i.dofustouch
            FROM items i
            LEFT JOIN item_id_mapping m ON i.id = m.old_id
            LEFT JOIN set_id_mapping s ON i.item_set = s.old_id
        """)
        
        # Drop old table and rename new one
        cursor.execute("DROP TABLE items")
        cursor.execute("ALTER TABLE items_new RENAME TO items")
        
        print("Migrating sets table...")
        
        # Create new sets table
        cursor.execute("""
            CREATE TABLE sets_new (
                id INTEGER PRIMARY KEY,
                name text,
                ankama_id INTEGER,
                dofustouch INTEGER
            )
        """)
        
        cursor.execute("""
            INSERT INTO sets_new
            SELECT 
                COALESCE(m.new_id, s.id) as id,
                s.name,
                s.ankama_id,
                s.dofustouch
            FROM sets s
            LEFT JOIN set_id_mapping m ON s.id = m.old_id
        """)
        
        cursor.execute("DROP TABLE sets")
        cursor.execute("ALTER TABLE sets_new RENAME TO sets")
        
        # Step 3: Update all foreign key references
        tables_to_update = [
            'stats_of_item',
            'min_stat_to_equip',
            'max_stat_to_equip',
            'min_rank_to_equip',
            'min_align_level_to_equip',
            'min_prof_level_to_equip',
            'weapon_is_onehanded',
            'weapon_crit_hits',
            'weapon_crit_bonus',
            'weapon_ap',
            'weapon_weapontype',
            'weapon_hits',
            'extra_lines',
            'item_names',
            'item_weird_conditions'
        ]
        
        for table in tables_to_update:
            # Check if table exists
            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
            if cursor.fetchone():
                print(f"Migrating {table}...")
                
                # Get table structure
                cursor.execute(f"PRAGMA table_info({table})")
                columns = cursor.fetchall()
                
                # Create new table
                cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table}'")
                create_sql = cursor.fetchone()[0]
                create_sql_new = create_sql.replace(f'"{table}"', f'"{table}_new"').replace(f'{table}', f'{table}_new')
                cursor.execute(create_sql_new)
                
                # Build column list and update statement
                col_names = [col[1] for col in columns]
                col_list = ', '.join(col_names)
                
                # Update based on whether 'item' or 'item_set' column exists
                if 'item' in col_names:
                    select_cols = []
                    for col in col_names:
                        if col == 'item':
                            select_cols.append('COALESCE(m.new_id, t.item) as item')
                        else:
                            select_cols.append(f't.{col}')
                    
                    cursor.execute(f"""
                        INSERT INTO {table}_new
                        SELECT {', '.join(select_cols)}
                        FROM {table} t
                        LEFT JOIN item_id_mapping m ON t.item = m.old_id
                    """)
                elif 'item_set' in col_names:
                    select_cols = []
                    for col in col_names:
                        if col == 'item_set':
                            select_cols.append('COALESCE(m.new_id, t.item_set) as item_set')
                        else:
                            select_cols.append(f't.{col}')
                    
                    cursor.execute(f"""
                        INSERT INTO {table}_new
                        SELECT {', '.join(select_cols)}
                        FROM {table} t
                        LEFT JOIN set_id_mapping m ON t.item_set = m.old_id
                    """)
                else:
                    # No item or item_set column, just copy
                    cursor.execute(f"INSERT INTO {table}_new SELECT * FROM {table}")
                
                # Drop old and rename new
                cursor.execute(f"DROP TABLE {table}")
                cursor.execute(f"ALTER TABLE {table}_new RENAME TO {table}")
        
        # Handle set_bonus table (references item_set)
        if cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='set_bonus'").fetchone():
            print("Migrating set_bonus...")
            cursor.execute("""
                CREATE TABLE set_bonus_new (
                    item_set INTEGER,
                    num_pieces_used INTEGER,
                    stat INTEGER,
                    value INTEGER,
                    FOREIGN KEY(item_set) REFERENCES sets(id),
                    FOREIGN KEY(stat) REFERENCES stats(id)
                )
            """)
            
            cursor.execute("""
                INSERT INTO set_bonus_new
                SELECT 
                    COALESCE(m.new_id, sb.item_set) as item_set,
                    sb.num_pieces_used,
                    sb.stat,
                    sb.value
                FROM set_bonus sb
                LEFT JOIN set_id_mapping m ON sb.item_set = m.old_id
            """)
            
            cursor.execute("DROP TABLE set_bonus")
            cursor.execute("ALTER TABLE set_bonus_new RENAME TO set_bonus")
        
        # Handle set_names table
        if cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='set_names'").fetchone():
            print("Migrating set_names...")
            cursor.execute("""
                CREATE TABLE set_names_new (
                    item_set INTEGER,
                    language text,
                    name text,
                    FOREIGN KEY(item_set) REFERENCES sets(id)
                )
            """)
            
            cursor.execute("""
                INSERT INTO set_names_new
                SELECT 
                    COALESCE(m.new_id, sn.item_set) as item_set,
                    sn.language,
                    sn.name
                FROM set_names sn
                LEFT JOIN set_id_mapping m ON sn.item_set = m.old_id
            """)
            
            cursor.execute("DROP TABLE set_names")
            cursor.execute("ALTER TABLE set_names_new RENAME TO set_names")
        
        # Commit changes
        conn.commit()
        print("Migration completed successfully!")
        print(f"Backup saved at: {backup_path}")
        
    except Exception as e:
        conn.rollback()
        print(f"Error during migration: {e}")
        print(f"Database has been rolled back. Backup is still available at: {backup_path}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    # Get the database path - check for both items.db and item_db.db
    project_root = os.path.dirname(current_directory)
    db_path = os.path.join(project_root, 'fashionistapulp', 'fashionistapulp', 'items.db')
    
    # Fallback to item_db.db if items.db doesn't exist
    if not os.path.exists(db_path):
        db_path = os.path.join(project_root, 'fashionistapulp', 'fashionistapulp', 'item_db.db')
    
    if not os.path.exists(db_path):
        print(f"Database not found at: {db_path}")
        print("Please provide the correct path to your database file")
    else:
        print(f"Database found at: {db_path}")
        response = input("Do you want to proceed with the migration? (yes/no): ")
        if response.lower() == 'yes':
            migrate_database(db_path)
        else:
            print("Migration cancelled")
