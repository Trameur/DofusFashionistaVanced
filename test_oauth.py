#!/bin/bash
from django.conf import settings
print(f"GOOGLE_KEY: {settings.SOCIAL_AUTH_GOOGLE_OAUTH2_KEY is not None}")
print(f"GOOGLE_SECRET: {settings.SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET is not None}")
