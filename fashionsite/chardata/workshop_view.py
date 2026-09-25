# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""Workshop: a craft list per game version, with its ingredient shopping list."""

import json
import logging
import math
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone, translation
from django.utils.translation import gettext as _, ngettext
from django.views.decorators.http import require_POST

from chardata.image_store import get_image_url
from chardata.models import WorkshopItem, WorkshopStock, WorkshopUndo
from chardata.official_site import get_item_link, get_set_link
from chardata.recipe_util import (
    MAX_SUBRECIPE_DEPTH, MAX_SUBRECIPE_KEYS_PER_REQUEST, aggregate_ingredients,
    expand_subrecipes, workshop_breakdown)
from chardata.util import safe_int, set_response
from chardata.workshop_sources import (
    MAX_SOURCE_KEYS_PER_REQUEST, get_item_craft_jobs, get_resource_sources)
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
MAX_CARDS_PER_VERSION = 500
# The undo button shows for 10 s; a little cache slack covers the round trip
UNDO_WINDOW_SECONDS = 20


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
    internal_ids_by_item_id = {}
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
                'job_name': None,
                'job_level': None,
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
            'job_name': None,
            'job_level': None,
        })
        internal_ids_by_item_id[row.item_id] = item.id

    job_info = get_item_craft_jobs(
        internal_ids_by_item_id.values(), game_version, language)
    for it in items:
        internal_id = internal_ids_by_item_id.get(it['item_id'])
        job = job_info['items'].get(internal_id)
        if job:
            it['job_name'] = job['job_name']
            it['job_level'] = job['level']
    return items, job_info['summary']


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


def _card_count(user, game_version):
    return WorkshopItem.objects.filter(user=user, game_version=game_version).count()


def _workshop_full_message():
    return _('Workshop full for this version (limit: %(max)s items). '
             'Remove some items before adding more.') % {'max': MAX_CARDS_PER_VERSION}


def _workshop_full_response():
    return JsonResponse({'error': _workshop_full_message()}, status=400)


def _stock_rows_for_keys(user, game_version, keys, for_update=False):
    """WorkshopStock rows matching exactly these (ankama_id, subtype) keys."""
    keys = list(keys)
    if not keys:
        return WorkshopStock.objects.none()
    query = Q()
    for ankama_id, subtype in keys:
        query |= Q(ingredient_ankama_id=ankama_id, ingredient_subtype=subtype)
    rows = WorkshopStock.objects.filter(query, user=user, game_version=game_version)
    # A fixed lock order across every caller avoids a MySQL deadlock between
    # two transactions locking the same rows in different orders.
    rows = rows.order_by('ingredient_ankama_id', 'ingredient_subtype')
    return rows.select_for_update() if for_update else rows


def _stock_row_get_or_create(user, game_version, ankama_id, subtype):
    """The WorkshopStock row for this resource, locked; created at owned=0 if absent.

    get_or_create() retries its own get() on IntegrityError, so two requests
    racing to create the same row never raise.
    """
    return WorkshopStock.objects.select_for_update().get_or_create(
        user=user, game_version=game_version,
        ingredient_ankama_id=ankama_id, ingredient_subtype=subtype,
        defaults={'owned': 0})


def _per_unit_recipe_needs(item_id, game_version):
    """{(ankama_id, subtype): quantity} for one unit of a WorkshopItem.item_id.

    Goes through workshop_breakdown, so a retired id still resolves to its
    current recipe (Structure.current_item_id).
    """
    breakdown = workshop_breakdown([(item_id, 1)], get_supported_language(), game_version)
    needs = {}
    for row in breakdown['items'].get(item_id, []):
        key = (row['ankama_id'], row['subtype'])
        needs[key] = needs.get(key, 0) + row['quantity']
    return needs


@login_required
def workshop(request):
    game_version = getattr(request, 'game_version', 'dofus3')
    items, job_summary = _items_for_user(request.user, game_version)
    breakdown = _breakdown_for_user(request.user, game_version)
    return set_response(request,
                        'chardata/workshop.html',
                        {'workshop_items': items,
                         'workshop_count': len(items),
                         'workshop_total_units': sum(
                             it['quantity'] for it in items),
                         'workshop_job_summary': job_summary,
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


def _parse_source_keys(raw):
    """[(ankama_id, subtype), ...] from a "id:subtype,id:subtype" query string.

    Malformed entries are dropped rather than rejected outright; the caller
    still sees an empty list and answers accordingly.
    """
    keys = []
    for chunk in (raw or '').split(','):
        chunk = chunk.strip()
        if not chunk:
            continue
        ankama_id_raw, sep, subtype = chunk.partition(':')
        if not sep:
            continue
        ankama_id = safe_int(ankama_id_raw, None)
        subtype = subtype.strip().lower()
        if ankama_id is None or not subtype:
            continue
        keys.append((ankama_id, subtype))
    return keys


@login_required
def workshop_sources(request):
    """JSON source info (top monsters, crafted flag) for a batch of resources.

    GET ?keys=<ankama_id>:<subtype>,<ankama_id>:<subtype>,..., at most
    MAX_SOURCE_KEYS_PER_REQUEST entries.
    """
    game_version = getattr(request, 'game_version', 'dofus3')
    raw_keys = request.GET.get('keys', '')
    if len(raw_keys.split(',')) > MAX_SOURCE_KEYS_PER_REQUEST:
        return JsonResponse(
            {'error': _('Too many resources in one request')}, status=400)

    keys = _parse_source_keys(raw_keys)
    if not keys:
        return JsonResponse({'error': _('Invalid request')}, status=400)

    sources = get_resource_sources(keys, game_version, get_supported_language())
    return JsonResponse({'success': True, 'sources': sources})


@login_required
def workshop_subrecipe(request):
    """JSON: one level of the recipe for a batch of craftable ingredients.

    GET ?keys=<ankama_id>:<subtype>,..., at most MAX_SUBRECIPE_KEYS_PER_REQUEST
    entries. &depth=<n> is the depth of the children being requested (a
    card's own ingredient row is depth 0, so its first "Craftable" tag asks
    for depth 1); requests past MAX_SUBRECIPE_DEPTH are refused. &path=<keys>
    carries every ancestor already opened above these keys, in the same
    "<id>:<subtype>" shape; a key already present in its own path is a
    circular recipe and is refused on its own, without failing the rest of
    the batch.
    """
    game_version = getattr(request, 'game_version', 'dofus3')
    raw_keys = request.GET.get('keys', '')
    if len(raw_keys.split(',')) > MAX_SUBRECIPE_KEYS_PER_REQUEST:
        return JsonResponse({'error': _('Too many resources in one request')}, status=400)

    keys = _parse_source_keys(raw_keys)
    if not keys:
        return JsonResponse({'error': _('Invalid request')}, status=400)

    depth = safe_int(request.GET.get('depth'), None)
    if depth is None or not 1 <= depth <= MAX_SUBRECIPE_DEPTH:
        return JsonResponse(
            {'error': _('This recipe is nested too deep to expand')}, status=400)

    path_keys = set(_parse_source_keys(request.GET.get('path', '')))
    honoured = [key for key in keys if key not in path_keys]
    cyclical = [key for key in keys if key in path_keys]

    subrecipes = expand_subrecipes(honoured, game_version, get_supported_language())
    for ankama_id, subtype in cyclical:
        subrecipes[_stock_key(ankama_id, subtype)] = {
            'found': True, 'children': [], 'cycle': True}

    return JsonResponse({'success': True, 'depth': depth, 'subrecipes': subrecipes})


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
    already = WorkshopItem.objects.filter(
        user=request.user, item_id=item_id, game_version=game_version).exists()
    if not already and _card_count(request.user, game_version) >= MAX_CARDS_PER_VERSION:
        return _workshop_full_response()

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
    # A live undo token for this card must go with it, or a later uncraft
    # call would resurrect a card the user explicitly removed.
    with transaction.atomic():
        deleted, _details = WorkshopItem.objects.filter(
            id=workshop_item_id, user=request.user).delete()
        if not deleted:
            return JsonResponse({'error': _('Item not found')}, status=404)
        WorkshopUndo.objects.filter(
            user=request.user, workshop_item_id=workshop_item_id).delete()
    return JsonResponse({'success': True, 'removed': True})


@login_required
@require_POST
def clear_workshop(request):
    game_version = getattr(request, 'game_version', 'dofus3')
    with transaction.atomic():
        deleted, _details = WorkshopItem.objects.filter(
            user=request.user, game_version=game_version).delete()
        WorkshopUndo.objects.filter(
            user=request.user, game_version=game_version).delete()
    return JsonResponse({'success': True, 'removed_count': deleted})


def _reject_json_constant(name):
    raise ValueError(name)


def _finite_json_float(text):
    value = float(text)
    if not math.isfinite(value):
        raise ValueError(text)
    return value


def _clamp_owned(value):
    try:
        owned = int(value)
    except (TypeError, ValueError, OverflowError):
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
        payload = json.loads(request.body.decode('utf-8') or '{}',
                             parse_constant=_reject_json_constant,
                             parse_float=_finite_json_float)
    except (ValueError, UnicodeDecodeError, RecursionError):
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
        except (TypeError, ValueError, OverflowError):
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
    """Bulk-add every equipped item of a solved Char to the user's workshop.

    mode=increment (default, today's behaviour): +1 on every item, creating
    it at quantity 1 when absent. mode=missing: only items absent from the
    workshop are added, at quantity 1; an already-listed item is untouched.
    """
    char = _readable_char(request, char_id)
    if char is None:
        return JsonResponse({'error': _('Build not found')}, status=404)

    game_version = char.game_version or 'dofus3'
    item_ids = _solution_item_ids(char)
    if item_ids is None:
        return JsonResponse({'error': _('Build has no solution yet')}, status=400)

    mode = request.POST.get('mode')
    if mode not in ('missing', 'increment'):
        mode = 'increment'

    existing = set(WorkshopItem.objects.filter(
        user=request.user, item_id__in=item_ids, game_version=game_version
    ).values_list('item_id', flat=True))

    added = 0
    limited = False
    count = _card_count(request.user, game_version)
    for item_id in item_ids:
        if item_id in existing:
            if mode == 'missing':
                continue
            obj = WorkshopItem.objects.get(
                user=request.user, item_id=item_id, game_version=game_version)
            obj.quantity = min(MAX_QUANTITY, obj.quantity + 1)
            obj.save(update_fields=['quantity'])
            added += 1
            continue
        if count >= MAX_CARDS_PER_VERSION:
            limited = True
            break
        WorkshopItem.objects.create(
            user=request.user, item_id=item_id, game_version=game_version, quantity=1)
        existing.add(item_id)
        count += 1
        added += 1

    response = {'success': True, 'added': added, 'mode': mode}
    if limited:
        response['limited'] = True
        response['message'] = _workshop_full_message()
    return JsonResponse(response)


@login_required
@require_POST
def workshop_add_set(request, set_id):
    """Add each craftable item of a set once: quantity 1 when absent, unchanged when present."""
    game_version = getattr(request, 'game_version', 'dofus3')
    structure = get_structure(game_version)
    set_id = safe_int(set_id, None)
    item_set = structure.get_set_by_id(set_id) if set_id is not None else None
    if item_set is None:
        return JsonResponse({'error': _('Set not found')}, status=404)

    item_ids = []
    seen = set()
    for raw_id in getattr(item_set, 'items', None) or []:
        item = structure.get_item_by_id(raw_id)
        if item is None or item.id in seen:
            continue
        seen.add(item.id)
        item_ids.append(item.id)

    if not item_ids:
        return JsonResponse({'success': True, 'added': 0, 'craftable': 0})

    breakdown = workshop_breakdown(
        ((item_id, 1) for item_id in item_ids), get_supported_language(), game_version)
    craftable_ids = [item_id for item_id in item_ids if breakdown['items'].get(item_id)]

    existing = set(WorkshopItem.objects.filter(
        user=request.user, item_id__in=craftable_ids, game_version=game_version
    ).values_list('item_id', flat=True))

    added = 0
    limited = False
    count = _card_count(request.user, game_version)
    for item_id in craftable_ids:
        if item_id in existing:
            continue
        if count >= MAX_CARDS_PER_VERSION:
            limited = True
            break
        WorkshopItem.objects.create(
            user=request.user, item_id=item_id, game_version=game_version, quantity=1)
        count += 1
        added += 1

    response = {'success': True, 'added': added, 'craftable': len(craftable_ids)}
    if limited:
        response['limited'] = True
        response['message'] = _workshop_full_message()
    return JsonResponse(response)


@login_required
@require_POST
def craft_workshop_item(request, workshop_item_id):
    """Craft one unit: consumes the recipe from stock, lowers the multiplier by 1.

    Only runs when every row of the card is already met for its current
    multiplier. Keeps a short-lived undo record for uncraft_workshop_item.
    """
    game_version = getattr(request, 'game_version', 'dofus3')
    with transaction.atomic():
        try:
            wi = WorkshopItem.objects.select_for_update().get(
                id=workshop_item_id, user=request.user, game_version=game_version)
        except WorkshopItem.DoesNotExist:
            return JsonResponse({'error': _('Item not found')}, status=404)

        needs = _per_unit_recipe_needs(wi.item_id, game_version)
        if not needs:
            return JsonResponse({'error': _('This item has no known recipe')}, status=400)

        stock_by_key = {
            (row.ingredient_ankama_id, row.ingredient_subtype): row
            for row in _stock_rows_for_keys(
                request.user, game_version, needs.keys(), for_update=True)
        }

        for key, per_unit in needs.items():
            owned = stock_by_key[key].owned if key in stock_by_key else 0
            if owned < per_unit * wi.quantity:
                return JsonResponse(
                    {'error': _('This item is not ready to craft yet')}, status=400)

        item_id = wi.item_id
        quantity_before = wi.quantity
        stock_deltas = []
        stock_result = {}
        for key, per_unit in needs.items():
            ankama_id, subtype = key
            row = stock_by_key.get(key)
            owned_before = row.owned if row is not None else 0
            new_owned = max(0, owned_before - per_unit)
            # The amount actually subtracted, not the pre-craft snapshot: undo
            # must add this back onto whatever the row holds by then, since a
            # card sharing this resource can change it before the undo click.
            stock_deltas.append({'ankama_id': ankama_id, 'subtype': subtype,
                                 'per_unit': per_unit})
            if new_owned == 0:
                if row is not None:
                    row.delete()
            elif row is not None:
                row.owned = new_owned
                row.save(update_fields=['owned'])
            else:
                row, _created = _stock_row_get_or_create(
                    request.user, game_version, ankama_id, subtype)
                row.owned = new_owned
                row.save(update_fields=['owned'])
            stock_result[_stock_key(ankama_id, subtype)] = new_owned

        new_quantity = quantity_before - 1
        removed = new_quantity <= 0
        if removed:
            wi.delete()
        else:
            wi.quantity = new_quantity
            wi.save(update_fields=['quantity'])

        WorkshopUndo.objects.update_or_create(
            user=request.user, workshop_item_id=workshop_item_id,
            defaults={
                'game_version': game_version,
                'item_id': item_id,
                'stock_deltas': stock_deltas,
                # Explicit, not auto_now_add: a re-craft of the same card
                # resets its own undo window instead of inheriting an older one.
                'created_time': timezone.now(),
            })
        WorkshopUndo.objects.filter(
            user=request.user,
            created_time__lt=timezone.now() - timedelta(seconds=UNDO_WINDOW_SECONDS)
        ).delete()

    return JsonResponse({'success': True, 'removed': removed,
                         'quantity': 0 if removed else new_quantity,
                         'stock': stock_result})


@login_required
@require_POST
def uncraft_workshop_item(request, workshop_item_id):
    """Undo the last craft on this card, within its short window.

    Adds back exactly what the craft subtracted, onto whatever the card and
    its stock rows hold right now, instead of overwriting them with a
    pre-craft snapshot. That keeps any change made to a shared resource, or
    to the card itself, in the meantime (another card's craft, a manual edit,
    a reset).

    Claiming the WorkshopUndo row and applying the restore happen in the same
    transaction, so two racing uncrafts can never both apply it: whichever
    request's delete removes zero rows treats the token as already gone.

    Locks WorkshopItem before WorkshopUndo, the same order craft_workshop_item
    uses (its update_or_create on WorkshopUndo runs last); the reverse order
    here would let a racing craft and uncraft on the same card deadlock each
    other on MySQL. Not exercised by the sqlite test backend, where
    select_for_update is a no-op.
    """
    stock_result = {}
    with transaction.atomic():
        # Unlocked: only to learn which card/version the token is for, before
        # taking the WorkshopItem lock in craft's order.
        peek = WorkshopUndo.objects.filter(
            user=request.user, workshop_item_id=workshop_item_id).first()
        if peek is None:
            return JsonResponse({'error': _('Nothing to undo')}, status=404)

        game_version = peek.game_version
        try:
            wi = WorkshopItem.objects.select_for_update().get(
                user=request.user, item_id=peek.item_id, game_version=game_version)
        except WorkshopItem.DoesNotExist:
            wi = None

        # Re-locked and re-checked by pk: the peek above was unlocked, so the
        # token may have been claimed or gone stale by now.
        token = WorkshopUndo.objects.select_for_update().filter(
            pk=peek.pk, user=request.user, workshop_item_id=workshop_item_id).first()
        if token is None:
            return JsonResponse({'error': _('Nothing to undo')}, status=404)

        stale = (timezone.now() - token.created_time).total_seconds() > UNDO_WINDOW_SECONDS
        claimed_count, _details = token.delete()
        if stale or not claimed_count:
            return JsonResponse({'error': _('Nothing to undo')}, status=404)

        if wi is None:
            # The card was crafted away (quantity reached 0) and nothing
            # re-added it since: recreate it at quantity 1.
            wi = WorkshopItem.objects.create(
                user=request.user, item_id=token.item_id,
                game_version=game_version, quantity=1)
        else:
            wi.quantity = min(MAX_QUANTITY, wi.quantity + 1)
            wi.save(update_fields=['quantity'])

        # Same fixed lock order as _stock_rows_for_keys, so a racing craft or
        # uncraft on another card cannot deadlock against this one.
        deltas = sorted(token.stock_deltas, key=lambda d: (d['ankama_id'], d['subtype']))
        for delta in deltas:
            ankama_id, subtype = delta['ankama_id'], delta['subtype']
            per_unit = delta['per_unit']
            row, _created = _stock_row_get_or_create(
                request.user, game_version, ankama_id, subtype)
            row.owned = min(MAX_STOCK_OWNED, row.owned + per_unit)
            row.save(update_fields=['owned'])
            stock_result[_stock_key(ankama_id, subtype)] = row.owned

    return JsonResponse({'success': True, 'workshop_item_id': wi.id,
                         'quantity': wi.quantity, 'stock': stock_result})


@login_required
@require_POST
def workshop_reset_stock(request):
    """Clear every owned count for this version; never touches WorkshopItem cards."""
    game_version = getattr(request, 'game_version', 'dofus3')
    deleted, _details = WorkshopStock.objects.filter(
        user=request.user, game_version=game_version).delete()
    return JsonResponse({'success': True, 'removed_count': deleted})


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
