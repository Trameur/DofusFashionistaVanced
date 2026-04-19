import json
from collections import Counter

# Load data
with open('transformed_equipment.json', 'r', encoding='utf-8') as f:
    equipment_data = json.load(f)

MOUNT_ID_OFFSET = 1000000
DUPLICATE_ID_OFFSET = 100000000

# Build the mapping
item_id_mapping = {}
new_ids = []
ankama_id_counter = {}

for i, item in enumerate(equipment_data):
    old_id = i + 1
    ankama_id = item['ankama_id']
    
    # Track duplicates
    if ankama_id not in ankama_id_counter:
        ankama_id_counter[ankama_id] = 0
    else:
        ankama_id_counter[ankama_id] += 1
    
    # Calculate ID
    if item.get('ankama_type') == 'mounts':
        new_id = MOUNT_ID_OFFSET + ankama_id
        if ankama_id_counter[ankama_id] > 0:
            new_id += DUPLICATE_ID_OFFSET * ankama_id_counter[ankama_id]
    else:
        new_id = ankama_id
        if ankama_id_counter[ankama_id] > 0:
            new_id += DUPLICATE_ID_OFFSET * ankama_id_counter[ankama_id]
    
    item_id_mapping[old_id] = new_id
    new_ids.append(new_id)

print(f"Total mappings: {len(item_id_mapping)}")
print(f"Total new IDs: {len(new_ids)}")
print(f"Unique new IDs: {len(set(new_ids))}")

# Check for duplicates
dupes = {k: v for k, v in Counter(new_ids).items() if v > 1}
if dupes:
    print(f"\n❌ DUPLICATES FOUND: {len(dupes)}")
    for dup_id, count in list(dupes.items())[:5]:
        print(f"  ID {dup_id}: appears {count} times")
        # Find which items have this ID
        for i, item in enumerate(equipment_data):
            old_id = i + 1
            if item_id_mapping[old_id] == dup_id:
                print(f"    - {item['name_en']} (ankama_type: {item.get('ankama_type')})")
else:
    print("\n✅ No duplicates - mapping is valid!")

# Check for None/NULL values
none_count = sum(1 for v in new_ids if v is None)
if none_count:
    print(f"\n⚠️ Found {none_count} None values in mapping")
