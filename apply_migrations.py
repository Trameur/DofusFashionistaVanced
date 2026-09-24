#!/usr/bin/env python

# Applies the Django migrations, the "chardata" app in particular
import os
import platform
import subprocess

def main():
    """Runs the Django migrations to repair the missing "chardata_itemdbversion" table."""
    print('=' * 60)
    print('Applying Django migrations for chardata app')
    print('=' * 60)
    
    python_cmd = "python3" if platform.system() != "Windows" else "python"
    
    print("Running all migrations...")
    subprocess.call([python_cmd, 'fashionsite/manage.py', 'migrate'])
    
    print("Running the chardata migrations...")
    # First without --fake-initial
    subprocess.call([python_cmd, 'fashionsite/manage.py', 'migrate', 'chardata'])
    
    # Then with --fake-initial, in case the first attempt failed
    print("Running the migrations with --fake-initial, just in case...")
    subprocess.call([python_cmd, 'fashionsite/manage.py', 'migrate', 'chardata', '--fake-initial'])
    
    print("Checking that the tables were created...")
    subprocess.call([python_cmd, 'fashionsite/manage.py', 'showmigrations', 'chardata'])
    
    print('=' * 60)
    print('Migrations done')
    print('=' * 60)

if __name__ == '__main__':
    main()
