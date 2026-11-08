# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""Removing an account for good.

The account goes first, in one short transaction: its builds are detached and
flagged, never deleted there, so the work does not grow with the number of builds.
The detached builds are purged afterwards, in small batches, and a build left by
an interrupted purge is hidden, owned by nobody and holds no name.
"""
import logging
import time
from collections import namedtuple

from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.db import DatabaseError, transaction
from django.db.models import Q
from social_django.models import UserSocialAuth

from chardata.models import BuildTag, Char, PageHit, UserAlias
from chardata.rate_limit import clear_hits

logger = logging.getLogger(__name__)

PURGE_BATCH_SIZE = 200
PURGE_BUDGET_SECONDS = 20
PURGE_LOGGED_IDS = 1000

DeletedAccount = namedtuple('DeletedAccount', 'username alias address build_ids')


def may_be_deleted(user):
    """Read on a fresh row: an administrator is never deleted from the site."""
    if user is None or user.pk is None:
        return False
    flags = User.objects.filter(pk=user.pk).values('is_superuser', 'is_staff').first()
    return flags is not None and not flags['is_superuser'] and not flags['is_staff']


def destroy_account(user_pk):
    """Removes the account and detaches its builds. None when there is nothing to remove.

    A DatabaseError leaves everything as it was.
    """
    with transaction.atomic():
        user = User.objects.select_for_update().filter(pk=user_pk).first()
        if user is None or user.is_superuser or user.is_staff:
            return None
        alias_row = UserAlias.objects.filter(user=user).first()
        deleted = DeletedAccount(
            username=user.username,
            alias=(alias_row.alias or '') if alias_row else '',
            address=user.email or '',
            build_ids=list(Char.objects.filter(owner=user).values_list('pk', flat=True)))
        social_ids = [str(pk) for pk in
                      UserSocialAuth.objects.filter(user=user).values_list('pk', flat=True)]
        # Typed by the owner, so gone with the account; the rest of a build goes at the purge
        BuildTag.objects.filter(char__owner=user).delete()
        Char.objects.filter(owner=user).update(
            owner=None, deleted=True, link_shared=False, name='', char_name='')
        LogEntry.objects.filter(
            Q(content_type=ContentType.objects.get_for_model(User), object_id=str(user.pk))
            | Q(content_type=ContentType.objects.get_for_model(UserSocialAuth),
                object_id__in=social_ids)).delete()
        user.delete()
    return deleted


def forget_the_names(username, alias, address):
    """Drops what still holds the account's names once the account is gone."""
    from chardata.login_view import _username_key
    clear_hits(_username_key(username))
    if address:
        clear_hits('reset-mail:%s' % address.lower()[:120])
        clear_hits('email-change-to:%s' % address.lower()[:120])
    from chardata.middleware import HIT_IDENT
    # Only a name the hit counter stores as it is can be found in its paths
    names = {name for name in (username, alias)
             if name and '<' not in name and not HIT_IDENT.match(name)}
    paths = set()
    prefixes = set()
    for name in names:
        paths.add('/user/%s/' % name)
        paths.add('/email_confirmed/%s/yes/' % name)
        paths.add('/email_confirmed/%s/no/' % name)
        prefixes.add('/do_recover_password/%s/' % name)
        prefixes.add('/confirm_email/%s/' % name)
    condition = Q(path__in=paths)
    for prefix in prefixes:
        condition |= Q(path__startswith=prefix)
    PageHit.objects.filter(condition).delete()


def detached_builds():
    """Builds that belong to nobody and are flagged deleted."""
    return Char.objects.filter(owner=None, deleted=True)


def blanked_builds():
    """Detached builds whose names were blanked, as an account deletion leaves them."""
    return detached_builds().filter(name='', char_name='')


def purge_detached_builds(build_ids, batch_size=PURGE_BATCH_SIZE,
                          budget=PURGE_BUDGET_SECONDS, clock=time.monotonic):
    """Deletes these builds, only while they are still detached and flagged.

    Stops when the budget is spent or the database refuses; what is left stays
    hidden. Answers how many builds were deleted.
    """
    started = clock()
    ids = list(build_ids)
    removed = 0
    for start in range(0, len(ids), batch_size):
        if clock() - started >= budget:
            break
        batch = ids[start:start + batch_size]
        try:
            _total, per_model = Char.objects.filter(
                pk__in=batch, owner=None, deleted=True).delete()
        except DatabaseError as error:
            logger.error('Detached builds could not be purged: %s', type(error).__name__)
            break
        removed += per_model.get(Char._meta.label, 0)
    if removed < len(ids):
        logger.error('%d detached builds were not purged, ids %s',
                     len(ids) - removed, ids[:PURGE_LOGGED_IDS])
    return removed
