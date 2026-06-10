# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""How a project's inventory choice feeds the solver and the solution display.

The Options page / wizard store two keys in the char's options pickle:
inventory_mode ('all' | 'mixed' | 'only') and inventory_folder (id). 'mixed'
keeps the whole encyclopedia but applies the player's saved rolls as stat
overrides; 'only' additionally restricts the item pool to the folder. The
same merged overrides must be used when rendering the solution, so the
displayed items carry the rolls the solver optimized with."""

import pickle

from chardata.lock_forbid import get_inclusions_dict, get_stat_overrides
from fashionistapulp.structure import get_structure


def get_inventory_mode(options):
    """Normalized item-source mode. Projects saved before the mode existed
    only stored a folder, which meant 'only'."""
    mode = options.get('inventory_mode')
    if mode not in ('all', 'mixed', 'only'):
        mode = 'only' if options.get('inventory_folder') else 'all'
    if not options.get('inventory_folder'):
        mode = 'all'
    return mode


def get_inventory_solver_settings(char):
    """('all'|'mixed'|'only', folder) for this project. The folder must still
    belong to the project owner and match the project's game version."""
    options = pickle.loads(char.options) if char.options else {}
    mode = get_inventory_mode(options)
    if mode == 'all':
        return 'all', None
    from chardata.models import InventoryFolder
    folder = InventoryFolder.objects.filter(
        id=options.get('inventory_folder'), user=char.owner,
        game_version=char.game_version).first()
    if folder is None:
        return 'all', None
    return mode, folder


def apply_inventory_restriction(char, exclusions, folder):
    """Exclude every item that is not in the folder. Explicitly locked items
    stay allowed so an inclusion always wins."""
    from chardata.models import InventoryItem
    owned_ids = set(InventoryItem.objects.filter(folder=folder)
                    .values_list('item_id', flat=True))
    included_ids = set()
    for value in get_inclusions_dict(char).values():
        try:
            included_ids.add(int(value))
        except (TypeError, ValueError):
            pass
    structure = get_structure()
    excluded = set(exclusions)
    for item in structure.get_concatenated_items_lists():
        if item.id in owned_ids or item.id in included_ids:
            continue
        excluded.add(item.id)
    return list(excluded)


def get_inventory_stat_overrides(folder):
    """The folder's saved rolls as a stat-override map
    {item_id: {stat_id: value}}. When the user owns several copies of an
    item, the most recently added copy wins."""
    from chardata.inventory_view import parse_custom_stats
    structure = get_structure()
    overrides = {}
    for row in folder.items.order_by('added_time'):
        custom = parse_custom_stats(row.custom_stats, structure)
        if not custom:
            continue
        item = structure.get_item_by_id(row.item_id)
        if item is None:
            continue
        per_item = {}
        for key, value in custom.items():
            stat = structure.get_stat_by_key(key)
            if stat is not None:
                per_item[stat.id] = value
        if per_item:
            overrides[row.item_id] = per_item
    return overrides


def get_effective_stat_overrides(char):
    """The overrides the solver runs with and the solution must display:
    inventory rolls (when an inventory mode is active) with the project's
    manual per-item overrides applied on top."""
    stat_overrides = get_stat_overrides(char)
    _mode, folder = get_inventory_solver_settings(char)
    if folder is None:
        return stat_overrides
    merged = get_inventory_stat_overrides(folder)
    for item_id, item_overrides in stat_overrides.items():
        merged.setdefault(item_id, {}).update(item_overrides)
    return merged
