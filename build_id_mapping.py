#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Build a mapping from old sequential IDs to new ankama_ids
by comparing item names in two dump files.
"""

import re
import json
import sys

def extract_items_from_dump(filepath):
    """Extract item ID and name from dump file"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find all INSERT INTO items VALUES(id,'name',...)
    items = re.findall(r"INSERT INTO items VALUES\((\d+),'([^']+)'", content)
    
    # Build dict: name -> id
    items_dict = {}
    for item_id, name in items:
        items_dict[name] = int(item_id)
    
    return items_dict

def build_mapping():
    """Build mapping from old ID to new ID"""
    print("Reading old dump file (sequential IDs)...")
    old_items = extract_items_from_dump('fashionistapulp/fashionistapulp/item_db_dumped.dump')
    print(f"  Found {len(old_items)} items")
    
    print("Reading new dump file (ankama_ids)...")
    new_items = extract_items_from_dump('fashionistapulp/fashionistapulp/item_db_dumped copy 4.dump')
    print(f"  Found {len(new_items)} items")
    
    print("\nBuilding ID mapping...")
    mapping = {}  # old_id -> new_id
    unmapped = []
    
    for name, old_id in old_items.items():
        if name in new_items:
            new_id = new_items[name]
            mapping[old_id] = new_id
        else:
            unmapped.append((old_id, name))
    
    print(f"  Mapped: {len(mapping)} items")
    print(f"  Unmapped: {len(unmapped)} items")
    
    if unmapped:
        print("\nUnmapped items (first 10):")
        for old_id, name in unmapped[:10]:
            print(f"  {old_id}: {name}")
    
    # Save mapping to JSON
    mapping_file = 'id_mapping.json'
    with open(mapping_file, 'w', encoding='utf-8') as f:
        json.dump(mapping, f, indent=2)
    
    print(f"\nMapping saved to {mapping_file}")
    
    # Show some examples
    print("\nExample mappings:")
    for old_id in sorted(mapping.keys())[:10]:
        new_id = mapping[old_id]
        print(f"  {old_id} -> {new_id}")
    
    return mapping

if __name__ == '__main__':
    build_mapping()
