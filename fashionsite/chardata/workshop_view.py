# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""Workshop: a craft list per game version, with its ingredient shopping list."""

import json
import logging

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.utils import translation
from django.utils.translation import gettext as _, ngettext
from django.views.decorators.http import require_POST

from chardata.image_store import get_image_url
from chardata.models import WorkshopItem, WorkshopStock
from chardata.official_site import get_item_link, get_set_link
from chardata.recipe_util import aggregate_ingredients, workshop_breakdown
from chardata.util import set_response
from fashionistapulp.structure import get_structure
from fashionistapulp.translation import get_supported_language
from static_s3.templatetags.static_s3 import static


logger = logging.getLogger(__name__)
MAX_QUANTITY = 999
# Enough for the largest reachable need (9000 line quantity x 999 multiplier)
MAX_STOCK_OWNED = 9_999_999
MAX_STOCK_KEYS_PER_REQUEST = 300
MAX_STOCK_ROWS_PER_VERSION = 5000
# WorkshopStock.ingredient_ankama_id is a signed 32-bit column in production
MAX_ANKAMA_ID = 2_147_483_647


def _localized_type(type_name, language):
    """An item type in the given language."""
    if not type_name:
        return ''
    with translation.override(language):
        return _(type_name)


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
            # Item disappeared (renamed / version drift): show a placeholder
            items.append({
                'id': row.id,
                'item_id': row.item_id,
                'name': _('Unknown item #%(id)s') % {'id': row.item_id},
                'type_name': '',
                'level': '',
                'image_url': '',
                'quantity': row.quantity,
                'missing': True,
                'encyclopedia_url': None,
                'set_id': None,
                'set_name': None,
                'set_url': None,
            })
            continue

        type_name = structure.get_type_name_by_id(item.type)
        name = structure.get_item_name_in_language(item, language)
        item_set = None
        if getattr(item, 'set', None) is not None:
            item_set = (structure.sets_dict.get(item.set)
                       or structure.dt_sets_dict.get(item.set))
        set_name = ((item_set.localized_names.get(language)
                    or item_set.localized_names.get('en') or item_set.name)
                   if item_set else None)
        items.append({
            'id': row.id,
            'item_id': row.item_id,
            'name': name,
            # Same language as the name; the image keeps the canonical type
            'type_name': _localized_type(type_name, language),
            'level': item.level,
            'image_url': static(get_image_url(type_name, item.name)),
            'quantity': row.quantity,
            'missing': False,
            'encyclopedia_url': get_item_link(
                item.ankama_type, item.ankama_id, name, game_version),
            'set_id': item_set.id if item_set else None,
            'set_name': set_name,
            'set_url': (get_set_link(item_set.id, set_name, game_version)
                       if item_set else None),
        })
    return items


def _ingredients_payload(recipe, language):
    """What both endpoints return; the plural is built here, the JS catalog lacks it."""
    kinds = len(recipe['ingredients'])
    total = sum(i['quantity'] for i in recipe['ingredients'])
    with translation.override(language):
        meta = ngettext(
            '%(kinds)s ingredient · %(total)s total',
            '%(kinds)s ingredients · %(total)s total',
            kinds) % {'kinds': kinds, 'total': total}
    return {
        'ingredients': recipe['ingredients'],
        'ingredient_kinds': kinds,
        'ingredient_total_units': total,
        'ingredients_meta': meta,
        'recipes_available': recipe['recipes_available'],
    }


def _ingredients_for_workshop(user, game_version):
    """Recipe ingredients for the user's workshop, times each item's quantity."""
    rows = WorkshopItem.objects.filter(user=user, game_version=game_version)
    return aggregate_ingredients(
        ((row.item_id, row.quantity) for row in rows),
        get_supported_language(), game_version,
        unknown_label=_('Unknown ingredient'))


def _breakdown_for_user(user, game_version):
    """Per-item recipe rows and per-resource totals for the item cards."""
    rows = WorkshopItem.objects.filter(user=user, game_version=game_version)
    return workshop_breakdown(
        ((row.item_id, row.quantity) for row in rows),
        get_supported_language(), game_version,
        unknown_label=_('Unknown ingredient'))


def _stock_key(ankama_id, subtype):
    return '%d:%s' % (ankama_id, subtype)


def _stock_map(user, game_version):
    """Owned counts by resource, keyed '<ankama_id>:<subtype>' for JS lookups."""
    return {
        _stock_key(row.ingredient_ankama_id, row.ingredient_subtype): row.owned
        for row in WorkshopStock.objects.filter(user=user, game_version=game_version)
    }


@login_required
def workshop(request):
    game_version = getattr(request, 'game_version', 'dofus3')
    items = _items_for_user(request.user, game_version)
    breakdown = _breakdown_for_user(request.user, game_version)
    return set_response(request,
                        'chardata/workshop.html',
                        {'workshop_items': items,
                         'workshop_count': len(items),
                         'workshop_total_units': sum(
                             it['quantity'] for it in items),
                         # For the template to hand to workshop.js through json_script
                         'workshop_card_rows': breakdown['items'],
                         'workshop_resource_totals': breakdown['resources'],
                         'workshop_stock': _stock_map(request.user, game_version),
                         'workshop_stock_limits': {
                             'max_owned': MAX_STOCK_OWNED,
                             'max_keys_per_request': MAX_STOCK_KEYS_PER_REQUEST,
                         }})


@login_required
def workshop_ingredients(request):
    """JSON ingredient list, to refresh the page after a quantity change."""
    game_version = getattr(request, 'game_version', 'dofus3')
    recipe = _ingredients_for_workshop(request.user, game_version)
    return JsonResponse(_ingredients_payload(recipe, get_supported_language()))


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


def _clamp_owned(value):
    try:
        owned = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, min(owned, MAX_STOCK_OWNED))


@login_required
@require_POST
def workshop_set_stock(request):
    """Batch-set owned resource counts. Writing 0 deletes the row.

    POST body: JSON {"updates": [{"ingredient_ankama_id": int,
    "subtype": str, "owned": int}, ...]}, at most MAX_STOCK_KEYS_PER_REQUEST
    entries. Bad entries are skipped; out-of-range values are clamped.
    """
    game_version = getattr(request, 'game_version', 'dofus3')
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({'error': _('Invalid request')}, status=400)

    updates = payload.get('updates') if isinstance(payload, dict) else None
    if not isinstance(updates, list) or not updates:
        return JsonResponse({'error': _('Invalid request')}, status=400)
    if len(updates) > MAX_STOCK_KEYS_PER_REQUEST:
        return JsonResponse(
            {'error': _('Too many resources in one request')}, status=400)

    wanted = {}
    for entry in updates:
        if not isinstance(entry, dict):
            continue
        try:
            ankama_id = int(entry.get('ingredient_ankama_id'))
        except (TypeError, ValueError):
            continue
        if not 0 <= ankama_id <= MAX_ANKAMA_ID:
            continue
        subtype_raw = entry.get('subtype')
        if not isinstance(subtype_raw, str) or not subtype_raw:
            continue
        wanted[(ankama_id, subtype_raw[:32])] = _clamp_owned(entry.get('owned'))

    if not wanted:
        return JsonResponse({'error': _('Invalid request')}, status=400)

    existing_keys = set(WorkshopStock.objects.filter(
        user=request.user, game_version=game_version
    ).values_list('ingredient_ankama_id', 'ingredient_subtype'))
    new_key_count = sum(1 for key, owned in wanted.items()
                        if owned and key not in existing_keys)
    if len(existing_keys) + new_key_count > MAX_STOCK_ROWS_PER_VERSION:
        return JsonResponse(
            {'error': _('Too many stocked resources for this version')},
            status=400)

    result = {}
    with transaction.atomic():
        for (ankama_id, subtype), owned in wanted.items():
            if owned == 0:
                WorkshopStock.objects.filter(
                    user=request.user, game_version=game_version,
                    ingredient_ankama_id=ankama_id,
                    ingredient_subtype=subtype).delete()
            else:
                WorkshopStock.objects.update_or_create(
                    user=request.user, game_version=game_version,
                    ingredient_ankama_id=ankama_id, ingredient_subtype=subtype,
                    defaults={'owned': owned})
            result[_stock_key(ankama_id, subtype)] = owned

    return JsonResponse({'success': True, 'stock': result})


def _solution_item_ids(char):
    """Unique item ids of a solved Char, or None when it has no solution yet."""
    from chardata.solution import get_solution
    sol = get_solution(char)
    if sol is None:
        return None
    item_ids = []
    seen = set()
    for item_info in getattr(sol, 'item_list', []) or []:
        item_id = getattr(item_info, 'item_id', None) or getattr(item_info, 'id', None)
        if item_id is None or item_id in seen:
            continue
        seen.add(item_id)
        item_ids.append(item_id)
    return item_ids


def _readable_char(request, char_id):
    """The build if the caller owns it or it is link shared, else None."""
    from chardata.models import Char
    from chardata.util import char_belongs_to_user
    try:
        char = Char.objects.get(id=char_id)
    except Char.DoesNotExist:
        return None
    if char_belongs_to_user(request, char) or char.link_shared:
        return char
    return None


@login_required
@require_POST
def add_solution_to_workshop(request, char_id):
    """Bulk-add every equipped item of a solved Char to the user's workshop."""
    char = _readable_char(request, char_id)
    if char is None:
        return JsonResponse({'error': _('Build not found')}, status=404)

    game_version = char.game_version or 'dofus3'
    item_ids = _solution_item_ids(char)
    if item_ids is None:
        return JsonResponse({'error': _('Build has no solution yet')}, status=400)

    added = 0
    for item_id in item_ids:
        obj, created = WorkshopItem.objects.get_or_create(
            user=request.user, item_id=item_id, game_version=game_version,
            defaults={'quantity': 1})
        if not created:
            obj.quantity = min(MAX_QUANTITY, obj.quantity + 1)
            obj.save(update_fields=['quantity'])
        added += 1

    return JsonResponse({'success': True, 'added': added})


@login_required
def solution_ingredients(request, char_id):
    """JSON ingredient list for a build's solution, one of each item."""
    char = _readable_char(request, char_id)
    if char is None:
        return JsonResponse({'error': _('Build not found')}, status=404)

    game_version = char.game_version or 'dofus3'
    item_ids = _solution_item_ids(char)
    if item_ids is None:
        return JsonResponse({'error': _('Build has no solution yet')}, status=400)

    recipe = aggregate_ingredients(
        ((item_id, 1) for item_id in item_ids),
        get_supported_language(), game_version,
        unknown_label=_('Unknown ingredient'))
    return JsonResponse(_ingredients_payload(recipe, get_supported_language()))
