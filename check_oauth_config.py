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

if settings.SOCIAL_AUTH_GOOGLE_OAUTH2_KEY:
    key = settings.SOCIAL_AUTH_GOOGLE_OAUTH2_KEY
    print(f"OAUTH KEY (first 50 chars): {key[:50]}...")
    
if settings.SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET:
    secret = settings.SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET
    print(f"OAUTH SECRET (first 20 chars): {secret[:20]}...")

print("=" * 60)
