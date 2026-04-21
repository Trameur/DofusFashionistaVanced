import os
import sys
sys.path.insert(0, '/app')
sys.path.insert(0, '/app/fashionsite')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fashionsite.settings')

import django
django.setup()

from django.conf import settings

print("=" * 60)
print("OAuth Configuration Check")
print("=" * 60)
print(f"SOCIAL_AUTH_GOOGLE_OAUTH2_KEY exists: {settings.SOCIAL_AUTH_GOOGLE_OAUTH2_KEY is not None}")
print(f"SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET exists: {settings.SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET is not None}")

print("=" * 60)
