# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""The name an account shows in public: what it may hold and whose it already is."""
import re

from django.contrib.auth.models import User
from social_django.models import UserSocialAuth

from chardata.models import UserAlias, public_handle

# A slash has no profile route, control characters break the pages that show the name
_UNSAFE = re.compile(r'[/\x00-\x1f\x7f-\x9f]')
_HANDLE = re.compile(r'^player\d+$', re.IGNORECASE)


def clean_public_name(raw, limit):
    return _UNSAFE.sub('', raw or '').strip()[:limit].strip()


def has_unsafe_character(name):
    return bool(_UNSAFE.search(name))


def default_public_name(user):
    if UserSocialAuth.objects.filter(user=user).exists():
        return public_handle(user.pk)
    return user.username


def public_name_is_taken(name, user=None):
    """Whether this name belongs to another account, or is the handle of one."""
    folded = name.casefold()
    own_names = ()
    if user is not None:
        own_names = (user.username.casefold(), public_handle(user.pk).casefold())
    if _HANDLE.match(name) and folded not in own_names:
        return True
    aliases = UserAlias.objects.filter(alias__iexact=name)
    usernames = User.objects.filter(username__iexact=name)
    if user is not None:
        aliases = aliases.exclude(user=user)
        usernames = usernames.exclude(pk=user.pk)
    return aliases.exists() or usernames.exists()
