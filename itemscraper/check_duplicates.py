import json
from collections import Counter

# Check equipment
with open('transformed_equipment.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

ankama_ids = [item['ankama_id'] for item in data]
print(f'Total items: {len(ankama_ids)}')
print(f'Unique ankama_ids: {len(set(ankama_ids))}')

dupes = {k: v for k, v in Counter(ankama_ids).items() if v > 1}
if dupes:
    print(f'Duplicate ankama_ids found: {dupes}')
    for dup_id in list(dupes.keys())[:5]:  # Show first 5 duplicates
        items_with_dup = [item['name_en'] for item in data if item['ankama_id'] == dup_id]
        print(f'  ID {dup_id}: {items_with_dup}')
else:
    print('No duplicates in equipment')

# Check how many items in DB
import sqlite3
conn = sqlite3.connect('../fashionistapulp/fashionistapulp/items.db')
cursor = conn.cursor()
cursor.execute('SELECT COUNT(*) FROM items')
db_count = cursor.fetchone()[0]
print(f'\nItems in database: {db_count}')
conn.close()

print(f'\nDifference: {db_count - len(ankama_ids)} items')
