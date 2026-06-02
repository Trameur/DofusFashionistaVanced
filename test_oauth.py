#!/usr/bin/env python
import os
import sys


def main():
    root = os.path.dirname(os.path.abspath(__file__))
    for p in (os.path.join(root, "fashionsite"), root):
        if p not in sys.path:
            sys.path.insert(0, p)

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "fashionsite.settings")
    import django
    django.setup()

    from django.conf import settings
    print(f"GOOGLE_KEY: {settings.SOCIAL_AUTH_GOOGLE_OAUTH2_KEY is not None}")
    print(f"GOOGLE_SECRET: {settings.SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET is not None}")


if __name__ == "__main__":
    main()
