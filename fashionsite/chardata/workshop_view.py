# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""Workshop: a craft list per game version, with its ingredient shopping list."""

import logging

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import translation
from django.utils.translation import gettext as _, ngettext
from django.views.decorators.http import require_POST

from chardata.image_store import get_image_url
from chardata.models import WorkshopItem
from chardata.recipe_util import aggregate_ingredients
from chardata.util import set_response
from fashionistapulp.structure import get_structure
from fashionistapulp.translation import get_supported_language
from static_s3.templatetags.static_s3 import static


logger = logging.getLogger(__name__)
MAX_QUANTITY = 999


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
            })
            continue

        type_name = structure.get_type_name_by_id(item.type)
        items.append({
            'id': row.id,
            'item_id': row.item_id,
            'name': structure.get_item_name_in_language(item, language),
            # Same language as the name; the image keeps the canonical type
            'type_name': _localized_type(type_name, language),
            'level': item.level,
            'image_url': static(get_image_url(type_name, item.name)),
            'quantity': row.quantity,
            'missing': False,
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


@login_required
def workshop(request):
    game_version = getattr(request, 'game_version', 'dofus3')
    items = _items_for_user(request.user, game_version)
    recipe = _ingredients_for_workshop(request.user, game_version)
    charge = _ingredients_payload(recipe, get_supported_language())
    return set_response(request,
                        'chardata/workshop.html',
                        {'workshop_items': items,
                         'workshop_count': len(items),
                         'workshop_total_units': sum(
                             it['quantity'] for it in items),
                         'ingredients': charge['ingredients'],
                         'ingredient_kinds': charge['ingredient_kinds'],
                         'ingredient_total_units':
                             charge['ingredient_total_units'],
                         # Same phrase as the refresh JSON
                         'ingredients_meta': charge['ingredients_meta'],
                         'recipes_available':
                             charge['recipes_available']})


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
