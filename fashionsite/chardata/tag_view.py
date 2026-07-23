# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""Tag endpoints, add / remove a free-form tag on a build (owner only)."""

import re
import unicodedata

from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.http import JsonResponse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from chardata.models import BuildTag, Char


MAX_TAG_LENGTH = 40
MAX_TAGS_PER_BUILD = 8
_TAG_CLEAN_RE = re.compile(r'\s+')


def _normalize_tag(raw):
    """Return (normalized_key, display_name) or (None, None) if invalid."""
    if not raw:
        return None, None
    display = _TAG_CLEAN_RE.sub(' ', raw.strip())
    if not display:
        return None, None
    if len(display) > MAX_TAG_LENGTH:
        display = display[:MAX_TAG_LENGTH]
    folded = unicodedata.normalize('NFKD', display)
    folded = ''.join(c for c in folded if not unicodedata.combining(c))
    key = folded.lower()
    # NFKD expands ligatures and the like, so the folded key can end up longer than the display.
    if len(key) > MAX_TAG_LENGTH:
        key = key[:MAX_TAG_LENGTH]
    return key, display


def _serialize(tag):
    return {'id': tag.id, 'name': tag.name, 'display_name': tag.display_name}


@login_required
@require_POST
def add_tag(request, char_id):
    try:
        char = Char.objects.get(id=char_id, deleted=False)
    except Char.DoesNotExist:
        return JsonResponse({'error': _('Build not found')}, status=404)
    if char.owner_id != request.user.id:
        return JsonResponse({'error': _('Not allowed')}, status=403)

    if BuildTag.objects.filter(char=char).count() >= MAX_TAGS_PER_BUILD:
        return JsonResponse({'error': _('Too many tags on this build')}, status=400)

    key, display = _normalize_tag(request.POST.get('tag', ''))
    if key is None:
        return JsonResponse({'error': _('Invalid tag')}, status=400)
    try:
        tag = BuildTag.objects.create(char=char, name=key, display_name=display)
    except IntegrityError:
        return JsonResponse({'error': _('Tag already on this build')}, status=400)
    return JsonResponse({'success': True, 'tag': _serialize(tag)})


@login_required
@require_POST
def remove_tag(request, tag_id):
    try:
        tag = BuildTag.objects.select_related('char').get(id=tag_id)
    except BuildTag.DoesNotExist:
        return JsonResponse({'error': _('Tag not found')}, status=404)
    if tag.char.owner_id != request.user.id:
        return JsonResponse({'error': _('Not allowed')}, status=403)
    tag.delete()
    return JsonResponse({'success': True})
