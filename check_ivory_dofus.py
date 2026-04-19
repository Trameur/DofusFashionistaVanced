import json
import re

# Load mapping
mapping = json.load(open('id_mapping.json'))
old_to_new = {int(k): int(v) for k, v in mapping.items()}

print("Looking for Ivory Dofus...")
print()

# Check old dump
old_dump = open('fashionistapulp/fashionistapulp/item_db_dumped.dump.bak', 'r', encoding='utf-8').read()
old_ivory = re.search(r"INSERT INTO items VALUES\((\d+),'Ivory Dofus'", old_dump)

# Check new dump  
new_dump = open('fashionistapulp/fashionistapulp/item_db_dumped copy 4.dump', 'r', encoding='utf-8').read()
new_ivory = re.search(r"INSERT INTO items VALUES\((\d+),'Ivory Dofus'", new_dump)

if old_ivory:
    old_id = int(old_ivory.group(1))
    print(f"Old dump: Ivory Dofus = ID {old_id}")
    if old_id in old_to_new:
        print(f"  → Mapped to: {old_to_new[old_id]}")
    else:
        print(f"  → NOT IN MAPPING!")
else:
    print("Old dump: Ivory Dofus NOT FOUND")

print()

if new_ivory:
    new_id = int(new_ivory.group(1))
    print(f"New dump: Ivory Dofus = ID {new_id}")
else:
    print("New dump: Ivory Dofus NOT FOUND")

print()
print("Checking item 865 in both dumps:")
old_865 = re.search(r"INSERT INTO items VALUES\(865,'([^']+)'", old_dump)
new_865 = re.search(r"INSERT INTO items VALUES\(865,'([^']+)'", new_dump)

print(f"  Old dump item 865: {old_865.group(1) if old_865 else 'NOT FOUND'}")
print(f"  New dump item 865: {new_865.group(1) if new_865 else 'NOT FOUND'}")
