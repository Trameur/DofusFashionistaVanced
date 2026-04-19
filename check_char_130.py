import os
import sys
import django
import pickle

sys.path.insert(0, 'fashionsite')
sys.path.insert(0, 'fashionistapulp')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fashionsite.settings')
django.setup()

from chardata.models import Char
from fashionistapulp.modelresult import ModelResultMinimal

char = Char.objects.get(id=130)
print(f"Character: {char.name}")
print(f"Has minimal_solution: {bool(char.minimal_solution)}")

if char.minimal_solution:
    minimal = pickle.loads(char.minimal_solution)
    print(f"\nItems in build:")
    for slot, item_id in minimal.item_per_slot.items():
        if item_id is not None:
            print(f"  {slot}: {item_id}")
    
    # Check for item 865
    if 865 in minimal.item_per_slot.values():
        print(f"\n*** FOUND: Item 865 in build! ***")
    else:
        print(f"\n*** Item 865 NOT in build ***")
