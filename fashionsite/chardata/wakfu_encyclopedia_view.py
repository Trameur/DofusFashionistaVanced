# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""The Wakfu encyclopedia pages."""

import contextlib
import threading

from django.http import Http404, HttpResponsePermanentRedirect
from django.urls import reverse
from django.utils import translation

from chardata import wakfu_encyclopedia_data as data
from chardata import wakfu_official_links
from chardata.image_store import RETRO_PLACEHOLDER, get_image_url
from chardata.official_site import _slugify_name
from chardata.util import set_response
from fashionistapulp.translation import SUPPORTED_LANGUAGES, get_supported_language
from static_s3.templatetags.static_s3 import static

SITE_ORIGIN = 'https://dofusfashionista.gg'
EQUIPMENT = 'equipment'
ENGLISH_ONLY_LANGUAGES = ('de',)
GAME_TEXT_LANGUAGE = 'en'

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
        'version_switch_base_path': '/',
        'version_switch_is_entity': False,
    }
    return set_response(request, 'chardata/wakfu/encyclopedia_item.html', context)
