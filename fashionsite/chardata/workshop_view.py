# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""Workshop / craft list.

A logged-in player can stash items they want to craft or acquire, scoped to
the current game version. Add-to-workshop buttons appear on /solution/ pages.

MVP: list view + add / remove / clear / set quantity. Resource aggregation
(summing all ingredient counts of recipes) will be plugged in once recipe
tables are populated in production — the model already carries `item_id`
and `game_version`, so the extension is purely a presentation layer."""

import logging

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseRedirect
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from chardata.image_store import get_image_url
from chardata.models import WorkshopItem
from chardata.util import set_response, version_reverse
from fashionistapulp.structure import get_structure
from fashionistapulp.translation import get_supported_language
from static_s3.templatetags.static_s3 import static


logger = logging.getLogger(__name__)
MAX_QUANTITY = 999


def _items_for_user(user, game_version):
    rows = (WorkshopItem.objects
            .filter(user=user, game_version=game_version)
            .order_by('-added_time'))

    structure = get_structure(game_version)
    language = get_supported_language()
    items = []
    for row in rows:
        item = structure.get_item_by_id(row.item_id)
        if item is None:
            # Item disappeared (renamed / version drift). Surface as a
            # placeholder so the user can remove it.
            items.append({
                'id': row.id,
                'item_id': row.item_id,
                'name': _('Unknown item #%(id)s') % {'id': row.item_id},
                'type_name': '',
                'level': '',
                'image_url': '',
                'quantity': row.quantity,
                'missing': True,
            })
            continue

        type_name = structure.get_type_name_by_id(item.type)
        items.append({
            'id': row.id,
            'item_id': row.item_id,
            'name': structure.get_item_name_in_language(item, language),
            'type_name': type_name,
            'level': item.level,
            'image_url': static(get_image_url(type_name, item.name)),
            'quantity': row.quantity,
            'missing': False,
        })
    return items


@login_required
def workshop(request):
    game_version = getattr(request, 'game_version', 'dofus3')
    items = _items_for_user(request.user, game_version)
    return set_response(request,
                        'chardata/workshop.html',
                        {'workshop_items': items,
                         'workshop_count': len(items),
                         'workshop_total_units': sum(it['quantity'] for it in items)})


def _coerce_quantity(value, default=1):
    try:
        q = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, min(q, MAX_QUANTITY))


@login_required
@require_POST
def add_to_workshop(request):
    game_version = getattr(request, 'game_version', 'dofus3')
    item_id_raw = request.POST.get('item_id')
    try:
        item_id = int(item_id_raw)
    except (TypeError, ValueError):
        return JsonResponse({'error': _('Invalid item')}, status=400)

    structure = get_structure(game_version)
    if structure.get_item_by_id(item_id) is None:
        return JsonResponse({'error': _('Item not found')}, status=404)

    quantity_delta = _coerce_quantity(request.POST.get('quantity', 1))
    obj, created = WorkshopItem.objects.get_or_create(
        user=request.user, item_id=item_id, game_version=game_version,
        defaults={'quantity': quantity_delta})
    if not created:
        new_qty = min(MAX_QUANTITY, obj.quantity + quantity_delta)
        obj.quantity = new_qty
        obj.save(update_fields=['quantity'])

    total = WorkshopItem.objects.filter(user=request.user, game_version=game_version).count()
    return JsonResponse({'success': True, 'created': created,
                         'quantity': obj.quantity, 'workshop_count': total})


@login_required
@require_POST
def set_workshop_quantity(request, workshop_item_id):
    try:
        wi = WorkshopItem.objects.get(id=workshop_item_id, user=request.user)
    except WorkshopItem.DoesNotExist:
        return JsonResponse({'error': _('Item not found')}, status=404)
    wi.quantity = _coerce_quantity(request.POST.get('quantity', 1))
    wi.save(update_fields=['quantity'])
    return JsonResponse({'success': True, 'quantity': wi.quantity})


@login_required
@require_POST
def remove_from_workshop(request, workshop_item_id):
    deleted, _details = WorkshopItem.objects.filter(
        id=workshop_item_id, user=request.user).delete()
    return JsonResponse({'success': True, 'removed': bool(deleted)})


@login_required
@require_POST
def clear_workshop(request):
    game_version = getattr(request, 'game_version', 'dofus3')
    deleted, _details = WorkshopItem.objects.filter(
        user=request.user, game_version=game_version).delete()
    return JsonResponse({'success': True, 'removed_count': deleted})


@login_required
@require_POST
def add_solution_to_workshop(request, char_id):
    """Bulk-add every equipped item of a solved Char to the user's workshop."""
    from chardata.models import Char
    from chardata.solution import get_solution
    try:
        char = Char.objects.get(id=char_id)
    except Char.DoesNotExist:
        return JsonResponse({'error': _('Build not found')}, status=404)

    game_version = char.game_version or 'dofus3'
    sol = get_solution(char)
    if sol is None:
        return JsonResponse({'error': _('Build has no solution yet')}, status=400)

    added = 0
    seen_item_ids = set()
    for item_info in getattr(sol, 'item_list', []) or []:
        item_id = getattr(item_info, 'item_id', None) or getattr(item_info, 'id', None)
        if item_id is None or item_id in seen_item_ids:
            continue
        seen_item_ids.add(item_id)
        obj, created = WorkshopItem.objects.get_or_create(
            user=request.user, item_id=item_id, game_version=game_version,
            defaults={'quantity': 1})
        if not created:
            obj.quantity = min(MAX_QUANTITY, obj.quantity + 1)
            obj.save(update_fields=['quantity'])
        added += 1

    return JsonResponse({'success': True, 'added': added})
