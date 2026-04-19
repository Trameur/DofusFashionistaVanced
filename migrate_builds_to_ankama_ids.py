#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Migrate Django database builds from sequential IDs to ankama_ids.

This script updates the minimal_solution field in all Char objects to use
ankama_ids instead of sequential IDs.
"""

import sys
sys.stdout.reconfigure(line_buffering=True)  # Force immediate output

import os
import sys
import django
import pickle

# Add paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'fashionsite'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'fashionistapulp'))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fashionsite.settings')
django.setup()

from chardata.models import Char
from fashionistapulp.modelresult import ModelResultMinimal

def get_id_mapping():
    """
    Load the mapping from old sequential IDs to new ankama_ids
    """
    import json
    
    mapping_file = 'id_mapping.json'
    try:
        with open(mapping_file, 'r', encoding='utf-8') as f:
            mapping = json.load(f)
        # Convert string keys to integers
        mapping = {int(k): int(v) for k, v in mapping.items()}
        print(f"Loaded mapping for {len(mapping)} items from {mapping_file}")
        return mapping
    except FileNotFoundError:
        print(f"ERROR: {mapping_file} not found!")
        print("Please run build_id_mapping.py first to create the mapping file.")
        sys.exit(1)

def migrate_build(char, id_mapping):
    """Migrate a single build's item IDs using the mapping"""
    if not char.minimal_solution:
        return False
        
    try:
        minimal = pickle.loads(char.minimal_solution)
        if not isinstance(minimal, ModelResultMinimal):
            return False
            
        changed = False
        new_item_per_slot = {}
        
        for slot, item_id in minimal.item_per_slot.items():
            if item_id is None:
                new_item_per_slot[slot] = None
                continue
                
            # Check if this is an old ID that needs mapping
            if item_id in id_mapping:
                new_id = id_mapping[item_id]
                new_item_per_slot[slot] = new_id
                changed = True
                print(f"    Mapped item {item_id} -> {new_id} in slot {slot}")
            else:
                # ID not in mapping - either already migrated or item doesn't exist
                new_item_per_slot[slot] = item_id
        
        if changed:
            minimal.item_per_slot = new_item_per_slot
            char.minimal_solution = pickle.dumps(minimal)
            return True
            
    except Exception as e:
        print(f"  Error migrating build {char.id}: {e}")
        return False
    
    return False

def migrate_exclusions(char, id_mapping):
    """Migrate char exclusions (pickled list of item IDs)"""
    if not char.exclusions:
        return False
        
    try:
        exclusions = pickle.loads(char.exclusions)
        if not isinstance(exclusions, list):
            return False
            
        changed = False
        new_exclusions = []
        
        for item_id in exclusions:
            if item_id in id_mapping:
                new_id = id_mapping[item_id]
                new_exclusions.append(new_id)
                changed = True
            else:
                # Keep original ID (already migrated or doesn't exist)
                new_exclusions.append(item_id)
        
        if changed:
            char.exclusions = pickle.dumps(new_exclusions)
            return True
            
    except Exception as e:
        print(f"  Error migrating exclusions for char {char.id}: {e}")
        return False
    
    return False

def migrate_inclusions(char, id_mapping):
    """Migrate char inclusions (pickled dict of slot -> item_id)"""
    if not char.inclusions:
        return False
        
    try:
        inclusions = pickle.loads(char.inclusions)
        if not isinstance(inclusions, dict):
            return False
            
        changed = False
        new_inclusions = {}
        
        for slot, item_id in inclusions.items():
            if item_id == '':
                new_inclusions[slot] = ''
                continue
                
            item_id_int = int(item_id)
            if item_id_int in id_mapping:
                new_id = id_mapping[item_id_int]
                new_inclusions[slot] = new_id
                changed = True
            else:
                # Keep original ID
                new_inclusions[slot] = item_id
        
        if changed:
            char.inclusions = pickle.dumps(new_inclusions)
            return True
            
    except Exception as e:
        print(f"  Error migrating inclusions for char {char.id}: {e}")
        return False
    
    return False

def main():
    print("Starting build migration to ankama_ids...")
    print("=" * 60)
    
    id_mapping = get_id_mapping()
    
    # Get all characters
    chars = Char.objects.all()
    total = chars.count()
    
    print(f"\nFound {total} characters to check")
    print()
    
    migrated_builds = 0
    migrated_exclusions = 0
    migrated_inclusions = 0
    errors = 0
    
    for i, char in enumerate(chars, 1):
        # Print progress every 100 characters
        if i % 100 == 0 or i == 1:
            print(f"[PROGRESS] {i}/{total} characters processed ({(i/total)*100:.1f}%) - Migrated: {migrated_builds} builds, {migrated_exclusions} exclusions")
        
        char_changed = False
        
        try:
            # Migrate build
            if char.minimal_solution:
                if migrate_build(char, id_mapping):
                    migrated_builds += 1
                    char_changed = True
            
            # Migrate exclusions
            if char.exclusions:
                if migrate_exclusions(char, id_mapping):
                    migrated_exclusions += 1
                    char_changed = True
            
            # Migrate inclusions
            if char.inclusions:
                if migrate_inclusions(char, id_mapping):
                    migrated_inclusions += 1
                    char_changed = True
            
            if char_changed:
                char.save()
                
        except Exception as e:
            print(f"  [ERROR] Character {char.id}: {e}")
            errors += 1
    
    print()
    print("=" * 60)
    print(f"Migration complete!")
    print(f"  Total characters checked: {total}")
    print(f"  Builds migrated: {migrated_builds}")
    print(f"  Exclusions migrated: {migrated_exclusions}")
    print(f"  Inclusions migrated: {migrated_inclusions}")
    print(f"  Errors: {errors}")
    print()
    print("Note: Old sequential item IDs have been converted to ankama_ids")
    print("      using the name-based mapping from the dump files.")

if __name__ == '__main__':
    main()
