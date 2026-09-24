#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Fixes the syntax error in the DofusFashionistaVanced settings.py file.
"""

import os

print("Fixing settings.py...")

settings_path = os.path.join(os.path.dirname(__file__), 'fashionsite', 'fashionsite', 'settings.py')

if not os.path.exists(settings_path):
    print(f"Error: the file {settings_path} does not exist")
    exit(1)

with open(settings_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Backup
backup_path = settings_path + ".bak"
with open(backup_path, 'w', encoding='utf-8') as f:
    f.writelines(lines)
print(f"Backup created: {backup_path}")

# Look for the extra closing brace
for i, line in enumerate(lines):
    stripped = line.strip()
    if stripped == '}' and i > 0 and lines[i-1].strip().endswith('}'):
        # The extra brace follows the CACHES definition
        prev_section = ''.join(lines[max(0, i-10):i])
        if 'CACHES' in prev_section:
            print(f"Extra brace found on line {i+1}")
            lines[i] = ''
            break

with open(settings_path, 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("Fix done.")