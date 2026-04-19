import sqlite3
import os

# Get database path
script_dir = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(script_dir, '..', 'fashionistapulp', 'fashionistapulp', 'items.db')
db_path = os.path.normpath(db_path)

print(f"Checking database at: {db_path}\n")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Check sample equipment items
print("=== Sample Equipment Items (should use ankama_id directly) ===")
cursor.execute("SELECT id, ankama_id, name FROM items WHERE type = 'Amulet' LIMIT 5")
for row in cursor.fetchall():
    print(f"ID: {row[0]}, Ankama ID: {row[1]}, Name: {row[2]}")

# Check sample mounts
print("\n=== Sample Mounts (should be 1M + ankama_id) ===")
cursor.execute("SELECT id, ankama_id, name FROM items WHERE type = 'Petsmount' LIMIT 5")
for row in cursor.fetchall():
    print(f"ID: {row[0]}, Ankama ID: {row[1]}, Name: {row[2]}, Offset: {row[0] - row[1]}")

# Check duplicate items
print("\n=== Duplicate Check (Ice Daggers with ankama_id 6981) ===")
cursor.execute("SELECT id, ankama_id, name FROM items WHERE ankama_id = 6981")
rows = cursor.fetchall()
for row in rows:
    offset = row[0] - row[1]
    offset_type = "Direct" if offset == 0 else f"+{offset//100000000}*100M"
    print(f"ID: {row[0]}, Ankama ID: {row[1]}, Name: {row[2]}, Type: {offset_type}")

# Check ID ranges
print("\n=== ID Range Summary ===")
cursor.execute("SELECT MIN(id), MAX(id) FROM items WHERE type != 'Petsmount'")
min_eq, max_eq = cursor.fetchone()
print(f"Equipment IDs: {min_eq} to {max_eq}")

cursor.execute("SELECT MIN(id), MAX(id) FROM items WHERE type = 'Petsmount'")
min_mount, max_mount = cursor.fetchone()
print(f"Mount IDs: {min_mount} to {max_mount}")

# Check sets
print("\n=== Sample Sets ===")
cursor.execute("SELECT id, ankama_id, name FROM sets LIMIT 5")
for row in cursor.fetchall():
    print(f"ID: {row[0]}, Ankama ID: {row[1]}, Name: {row[2]}")

conn.close()
print("\n✅ Migration verification complete!")
