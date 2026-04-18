#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import os

current_directory = os.path.dirname(__file__)

with open(f'{current_directory}/itemscraper/transformed_equipment.json', 'r', encoding='utf-8') as f:
    original_data = json.load(f)

# Test: Check if id() returns the same value when iterating multiple times
first_pass_ids = {}
for item in original_data[:5]:
    first_pass_ids[item['name_en']] = id(item)
    print(f"First pass - {item['name_en']}: id={id(item)}, ankama_id={item['ankama_id']}")

print("\nSecond pass:")
for item in original_data[:5]:
    print(f"Second pass - {item['name_en']}: id={id(item)}, same={id(item) == first_pass_ids[item['name_en']]}")
