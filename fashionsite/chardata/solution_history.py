# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

import pickle

from chardata.image_store import get_image_url
from chardata.models import SolutionGeneration
from chardata.solution import get_solution_from_blob
from fashionistapulp.dofus_constants import SLOTS
from fashionistapulp.structure import get_structure
from fashionistapulp.translation import get_supported_language
from static_s3.templatetags.static_s3 import static


MAX_GENERATIONS_PER_CHAR = 10


def _to_blob(minimal_solution):
    if isinstance(minimal_solution, bytes):
        return minimal_solution
    return pickle.dumps(minimal_solution)


def record_solution_generation(char, minimal_solution):
    if minimal_solution is None:
        return None
    generation = SolutionGeneration.objects.create(
        char=char,
        game_version=char.game_version,
        minimal_solution=_to_blob(minimal_solution),
    )
    old_ids = list(
        SolutionGeneration.objects
        .filter(char=char, game_version=char.game_version)
        .order_by('-created_time', '-id')
        .values_list('id', flat=True)[MAX_GENERATIONS_PER_CHAR:])
    if old_ids:
        SolutionGeneration.objects.filter(id__in=old_ids).delete()
    return generation


def get_generation_solution(char, generation):
    if generation.char_id != char.id or generation.game_version != char.game_version:
        return None
    return get_solution_from_blob(char, generation.minimal_solution)


def get_generation_preview_items(generation, limit=12):
    try:
        minimal_solution = pickle.loads(generation.minimal_solution)
    except Exception:
        return []

    structure = get_structure(generation.game_version)
    language = get_supported_language()
    preview_items = []
    for slot in SLOTS:
        item_id = (getattr(minimal_solution, 'item_per_slot', {}) or {}).get(slot)
        if item_id is None:
            continue
        item = structure.get_item_by_id(item_id)
        if item is None:
            continue
        preview_items.append({
            'name': structure.get_item_name_in_language(item, language),
            'image_url': static(get_image_url(
                structure.get_type_name_by_id(item.type),
                item.name,
                generation.game_version)),
        })
        if len(preview_items) >= limit:
            break
    return preview_items
