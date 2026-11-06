# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""The Wakfu encyclopedia pages."""

import contextlib
import json
import threading

from django.core.paginator import Paginator
from django.http import Http404, HttpResponsePermanentRedirect
from django.urls import reverse
from django.utils import translation
from django.utils.translation import gettext

from chardata import wakfu_encyclopedia_data as data
from chardata import wakfu_official_links
from chardata.encyclopedia_filters import is_filter_key, parse_order_rows, parse_stat_rows
from chardata.image_store import RETRO_PLACEHOLDER, get_image_url
from chardata.official_site import _slugify_name
from chardata.pagination import pagination_items
from chardata.util import safe_int, set_response
from fashionistapulp.translation import SUPPORTED_LANGUAGES, get_supported_language
from static_s3.templatetags.static_s3 import static

SITE_ORIGIN = 'https://dofusfashionista.gg'
EQUIPMENT = 'equipment'
ENGLISH_ONLY_LANGUAGES = ('de',)
GAME_TEXT_LANGUAGE = 'en'
PAGE_SIZE = 39
EXTRA_FILTER_KEYS = ('rarity',)
ORDER_KEYS_BEYOND_STATS = ('level', 'name')

_weapons_lock = threading.Lock()
_weapons = {}


def _weapon_types():
    """The weapon item types, read again when the database file changes."""
    stamp = data._stamp()
    with _weapons_lock:
        if stamp not in _weapons:
            _weapons.clear()
            with contextlib.closing(data.connect()) as conn:
                _weapons[stamp] = wakfu_official_links.weapon_types(conn)
        return _weapons[stamp]


def _name_in(names, language):
    if language in ENGLISH_ONLY_LANGUAGES:
        language = GAME_TEXT_LANGUAGE
    return names.get(language) or names.get(GAME_TEXT_LANGUAGE) or ''


def _item_path(item_id, name):
    return reverse('wakfu:encyclopedia_item', kwargs={
        'ankama_type': EQUIPMENT, 'ankama_id': item_id, 'slug': _slugify_name(name, '')})


def _names_of(item_id):
    with contextlib.closing(data.connect()) as conn:
        return dict(conn.execute('SELECT language, name FROM item_names WHERE item = ?',
                                 (item_id,)).fetchall())


def _alternate_urls(item_id):
    names = _names_of(item_id)
    alternates = {}
    for language in SUPPORTED_LANGUAGES:
        with translation.override(language):
            alternates[language] = SITE_ORIGIN + _item_path(item_id, _name_in(names, language))
    return alternates


def _picture(name, gfx):
    """(static url, whether it is the placeholder) of an item's picture."""
    path = get_image_url('', name, game_version=data.GAME_VERSION, picture=gfx)
    return static(path), path == RETRO_PLACEHOLDER


def _recipe_context(recipe, by_id):
    if recipe is None:
        return None
    ingredients = []
    for one in recipe.ingredients:
        live = by_id.get(one.item_id) if one.item_id is not None else None
        ingredients.append({
            'name': one.name or '',
            'quantity': one.quantity,
            'url': _item_path(live.id, live.name) if live else None,
            'image_url': _picture(live.name, live.gfx)[0] if live else None,
        })
    return {'job': recipe.job, 'level': recipe.level, 'ingredients': ingredients}


def _list_urls():
    """{language: absolute url of the plain item list}."""
    urls = {}
    for language in SUPPORTED_LANGUAGES:
        with translation.override(language):
            urls[language] = SITE_ORIGIN + reverse('wakfu:encyclopedia')
    return urls


def _breadcrumb_jsonld(crumbs):
    """schema.org BreadcrumbList as JSON, safe inside a script tag. crumbs: [(name, url)]."""
    payload = json.dumps({
        '@context': 'https://schema.org',
        '@type': 'BreadcrumbList',
        'itemListElement': [
            {'@type': 'ListItem', 'position': number + 1, 'name': name, 'item': url}
            for number, (name, url) in enumerate(crumbs)
        ],
    }, ensure_ascii=False)
    return payload.replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')


def _list_canonical(request, url, page):
    """Canonical of a list page: filtered views point at the plain list."""
    filtered = any(
        key != 'page' and is_filter_key(key, EXTRA_FILTER_KEYS)
        and any((one or '').strip() for one in values)
        for key, values in request.GET.lists())
    number = getattr(page, 'number', 1) or 1
    if filtered or number <= 1:
        return url
    return '%s?page=%d' % (url, number)


def _search_example(idx):
    """A live item name of the index, the same on every request."""
    named = [one for one in idx.items if one.name]
    return min(named, key=lambda one: one.id).name if named else ''


def _card(item, lines, type_names, rarity_names):
    image_url, is_placeholder = _picture(item.name, item.gfx)
    return {
        'name': item.name,
        'level': item.level,
        'type_name': type_names.get(item.type, ''),
        'rarity_name': rarity_names.get(item.rarity, ''),
        'url': _item_path(item.id, item.name),
        'image_url': image_url,
        'picture_is_placeholder': is_placeholder,
        'stat_lines': [{'text': line.text, 'negative': line.text.startswith('-')}
                       for line in lines],
    }


def encyclopedia(request):
    language = get_supported_language()
    idx = data.index(language)
    query = request.GET

    search_text = (query.get('q') or '').strip()
    selected_type = safe_int(query.get('type'), None)
    if selected_type not in {one for one, _name in idx.types}:
        selected_type = None
    selected_rarity = safe_int(query.get('rarity'), None)
    if selected_rarity not in {one for one, _name in idx.rarities}:
        selected_rarity = None
    min_level = safe_int(query.get('min_level'), None)
    max_level = safe_int(query.get('max_level'), None)

    def valid_stat(key):
        return data.is_stat_key(idx, key)

    stat_rows, stat_filters = parse_stat_rows(query, valid_stat)
    order_rows, stat_orders = parse_order_rows(
        query, lambda key: key in ORDER_KEYS_BEYOND_STATS or valid_stat(key))

    found = data.filter_items(idx, {
        'q': search_text, 'type': selected_type, 'rarity': selected_rarity,
        'min_level': min_level, 'max_level': max_level,
        'stats': stat_filters, 'orders': stat_orders,
    })
    paginator = Paginator(found, PAGE_SIZE)
    page = paginator.get_page(query.get('page', 1))

    type_names = dict(idx.types)
    rarity_names = dict(idx.rarities)
    lines = data.card_lines([one.id for one in page.object_list], language)
    page.object_list = [_card(one, lines[one.id], type_names, rarity_names)
                        for one in page.object_list]

    without_page = query.copy()
    if 'page' in without_page:
        del without_page['page']
    page_query_prefix = without_page.urlencode()
    if page_query_prefix:
        page_query_prefix += '&'

    alternates = _list_urls()
    canonical_url = _list_canonical(request, alternates[language], page)
    stat_options = [{'key': key, 'name': name} for key, name in idx.stats]
    context = {
        'items_page': page,
        'page_links': pagination_items(page),
        'items_count': len(found),
        'search_text': search_text,
        'search_example': _search_example(idx),
        'selected_type': selected_type,
        'selected_rarity': selected_rarity,
        'min_level': '' if min_level is None else min_level,
        'max_level': '' if max_level is None else max_level,
        'top_level': idx.items[0].level if idx.items else 0,
        'type_options': [{'value': one, 'label': name} for one, name in idx.types],
        'rarity_options': [{'value': one, 'label': name} for one, name in idx.rarities],
        'stat_options': stat_options,
        'order_options': [
            {'key': 'level', 'name': gettext('Level'), 'site_text': True},
            {'key': 'name', 'name': gettext('Name'), 'site_text': True},
        ] + stat_options,
        'selected_stat_rows': stat_rows,
        'selected_order_rows': order_rows,
        'page_query_prefix': page_query_prefix,
        'game_text_lang': GAME_TEXT_LANGUAGE if language in ENGLISH_ONLY_LANGUAGES else '',
        'canonical_url': canonical_url,
        'alternate_urls': alternates,
        'hreflang_urls': alternates,
        'breadcrumb_jsonld': _breadcrumb_jsonld([
            ('Dofus Fashionista', SITE_ORIGIN + '/'),
            (gettext('Wakfu Encyclopedia'), canonical_url),
        ]),
    }
    return set_response(request, 'chardata/wakfu/encyclopedia.html', context)


def encyclopedia_item(request, ankama_type, ankama_id, slug=None):
    if ankama_type != EQUIPMENT:
        raise Http404('no such item type')
    language = get_supported_language()
    item_id = int(ankama_id)
    detail = data.item_detail(item_id, language)
    if detail is None or detail.item.ankama_type != EQUIPMENT:
        raise Http404('no such item')
    item = detail.item
    name = item.name
    if slug != _slugify_name(name, ''):
        target = _item_path(item.id, name)
        if request.META.get('QUERY_STRING'):
            target = '%s?%s' % (target, request.META['QUERY_STRING'])
        return HttpResponsePermanentRedirect(target)
    alternates = _alternate_urls(item.id)
    image_url, is_placeholder = _picture(name, item.gfx)
    context = {
        'item': item,
        'name': name,
        'detail': detail,
        'image_url': image_url,
        'picture_is_placeholder': is_placeholder,
        'worn_level_differs': detail.display_level != item.level,
        'conditions': [one for one in detail.conditions if one.text],
        'recipe': _recipe_context(detail.recipe, data.index(language).by_id),
        'official_url': wakfu_official_links.item_link(
            item.id, item.type, language, _weapon_types()),
        'game_text_lang': GAME_TEXT_LANGUAGE if language in ENGLISH_ONLY_LANGUAGES else '',
        'canonical_url': alternates[language],
        'alternate_urls': alternates,
        'hreflang_urls': alternates,
        'breadcrumb_jsonld': _breadcrumb_jsonld([
            ('Dofus Fashionista', SITE_ORIGIN + '/'),
            (gettext('Wakfu Encyclopedia'), _list_urls()[language]),
            (name, alternates[language]),
        ]),
    }
    return set_response(request, 'chardata/wakfu/encyclopedia_item.html', context)
