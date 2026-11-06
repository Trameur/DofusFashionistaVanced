# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""The name an account shows in public: what it may hold and whose it already is."""
import re
import unicodedata

from django.contrib.auth.models import User
from social_django.models import UserSocialAuth

from chardata.models import UserAlias, public_handle

# A slash has no profile route, control characters break the pages that show the name,
# invisible ones let a name pass for another account's
_UNSAFE_CATEGORIES = ('Cc', 'Cf', 'Zl', 'Zp')
_UNSAFE_CHARACTERS = re.compile(
    '[/\u034f\u115f\u1160\u17b4\u17b5\u180b-\u180f\u2800\u3164\ufe00-\ufe0f\uffa0'
    '\U000e0100-\U000e01ef]')
_HANDLE = re.compile(r'^player\d+$')
_ADDRESS = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


def _is_unsafe(character):
    return (unicodedata.category(character) in _UNSAFE_CATEGORIES
            or bool(_UNSAFE_CHARACTERS.match(character)))


def _folded(name):
    decomposed = unicodedata.normalize('NFKD', name)
    return ''.join(c for c in decomposed if not unicodedata.combining(c)).casefold()


def clean_public_name(raw, limit):
    kept = ''.join(c for c in raw or '' if not _is_unsafe(c))
    return kept.strip()[:limit].strip()


def has_unsafe_character(name):
    return any(_is_unsafe(c) for c in name)


def looks_like_an_address(name):
    return bool(_ADDRESS.match(name.strip()))


def default_public_name(user):
    if (looks_like_an_address(user.username)
            or UserSocialAuth.objects.filter(user=user).exists()):
        return public_handle(user.pk)
    return user.username


def public_name_is_taken(name, user=None):
    """Whether this name belongs to another account, or is the handle of one."""
    folded = _folded(name)
    own_names = ()
    if user is not None:
        own_names = (_folded(user.username), _folded(public_handle(user.pk)))
    if _HANDLE.match(folded) and folded not in own_names:
        return True
    aliases = UserAlias.objects.filter(alias__iexact=name)
    usernames = User.objects.filter(username__iexact=name)
    if user is not None:
        aliases = aliases.exclude(user=user)
        usernames = usernames.exclude(pk=user.pk)
    return aliases.exists() or usernames.exists()
