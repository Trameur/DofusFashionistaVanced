# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""Create (or update) a local admin account that logs in through the site's
own login form.

Google-login accounts can't be used on a localhost test server (OAuth isn't
wired for localhost), which locks the owner out of the admin. This command
makes a plain username/password superuser. The site login pre-hashes the
password in the browser (SHA256('dofusfashionista' + password), see login.js),
so the stored password is make_password(<that hash>) — otherwise the site
login would reject it.

    python manage.py create_local_admin --username boss --email you@example.com
    # (prompts for a password)

    python manage.py create_local_admin --username boss --password secret --email you@example.com
"""
import getpass
import hashlib

from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError


def _site_login_password(raw_password):
    """Match the browser pre-hash so the site's own login form accepts it."""
    prehashed = hashlib.sha256(('dofusfashionista' + raw_password).encode('utf-8')).hexdigest()
    return make_password(prehashed)


class Command(BaseCommand):
    help = "Create or update a superuser that logs in via the site login form."

    def add_arguments(self, parser):
        parser.add_argument('--username', required=True)
        parser.add_argument('--email', default='')
        parser.add_argument('--password', default=None,
                            help='If omitted, you are prompted (recommended).')

    def handle(self, *args, **options):
        username = options['username']
        email = options['email']
        password = options['password']
        if not password:
            password = getpass.getpass('Password for %s: ' % username)
            confirm = getpass.getpass('Password (again): ')
            if password != confirm:
                raise CommandError('Passwords do not match.')
        if not password:
            raise CommandError('Password cannot be empty.')

        user, created = User.objects.get_or_create(username=username)
        if email:
            user.email = email
        user.password = _site_login_password(password)
        user.is_superuser = True
        user.is_staff = True
        user.is_active = True
        user.save()

        self.stdout.write(self.style.SUCCESS(
            '%s local admin "%s"%s — log in from the site login form '
            '(top-right), then open /admin-tools/ or /admin/.'
            % ('Created' if created else 'Updated', username,
               (' <%s>' % email) if email else '')))
