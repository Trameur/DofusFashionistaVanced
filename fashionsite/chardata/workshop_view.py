# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""Workshop / craft list.

A logged-in player can stash items they want to craft or acquire, scoped to
the current game version. Add-to-workshop buttons appear on /solution/ pages.

The list view aggregates every stashed item's recipe into a single shopping
list of raw ingredients (see `chardata.recipe_util`), so the player can see at
a glance how many of each resource they need to craft everything."""

import logging

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils.translation import gettext as _
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


def _ingredients_for_workshop(user, game_version):
    """Aggregated recipe ingredients for everything currently in `user`'s
    workshop, multiplied by each item's quantity."""
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
    return set_response(request,
                        'chardata/workshop.html',
                        {'workshop_items': items,
                         'workshop_count': len(items),
                         'workshop_total_units': sum(it['quantity'] for it in items),
                         'ingredients': recipe['ingredients'],
                         'ingredient_kinds': len(recipe['ingredients']),
                         'ingredient_total_units': sum(i['quantity'] for i in recipe['ingredients']),
                         'recipes_available': recipe['recipes_available']})


@login_required
def workshop_ingredients(request):
    """JSON ingredient list for the current user's workshop. Lets the page
    refresh the shopping list after a quantity change / removal without a full
    reload."""
    game_version = getattr(request, 'game_version', 'dofus3')
    recipe = _ingredients_for_workshop(request.user, game_version)
    return JsonResponse({
        'ingredients': recipe['ingredients'],
        'ingredient_kinds': len(recipe['ingredients']),
        'ingredient_total_units': sum(i['quantity'] for i in recipe['ingredients']),
        'recipes_available': recipe['recipes_available'],
    })


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
    """Unique structure item ids equipped in a solved Char, or None when the
    build has no solution yet."""
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
    """The build if the caller may read it, else None.

    Their own, or one its owner shared by link: the solution page these two
    routes serve is also the page a shared build is read on. Both take a bare
    integer id, and ids are sequential, so without this a signed-in visitor
    could walk them into someone's unshared build. Answering 404 rather than
    403 keeps the id itself quiet.
    """
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
    """JSON shopping list of recipe ingredients for a build's solution (one of
    each equipped item). Drives the 'crafting ingredients' panel on the
    solution page."""
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
    return JsonResponse({
        'ingredients': recipe['ingredients'],
        'ingredient_kinds': len(recipe['ingredients']),
        'ingredient_total_units': sum(i['quantity'] for i in recipe['ingredients']),
        'recipes_available': recipe['recipes_available'],
    })
