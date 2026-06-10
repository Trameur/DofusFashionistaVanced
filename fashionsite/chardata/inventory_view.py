# -*- coding: utf-8 -*-

# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""Player inventory.

Logged-in players keep folders of items they actually own (typically one
folder per server, or any custom label), per game version. Items can carry
their real rolls (saved from the smithmagic page or a solution's stat
editor). A project can then be restricted on the Options page to only use
items from one folder."""

import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils.translation import gettext as _
from django.utils import translation
from django.views.decorators.http import require_POST

from chardata.image_store import get_image_url
from chardata.models import InventoryFolder, InventoryItem
from chardata.stat_icons import get_stat_icon_path
from chardata.util import safe_int, set_response, version_reverse
from fashionistapulp.dofus_constants import STAT_ORDER
from fashionistapulp.structure import get_structure
from fashionistapulp.translation import get_supported_language
from static_s3.templatetags.static_s3 import static


MAX_FOLDERS_PER_VERSION = 30
MAX_ITEMS_PER_FOLDER = 500

LOCALIZED_UI = {
    'en': {
        'title': 'My Inventory',
        'subtitle': 'The items you own, grouped in folders (one per server, or any custom label).',
        'solver_hint': 'A project can be restricted to one folder on its Options page ("only use items I own").',
        'folders': 'Folders',
        'folder_placeholder': 'Server or folder name',
        'folder_create': 'Create folder',
        'folder_delete': 'Delete folder',
        'folder_delete_confirm': 'Delete this folder and all the items in it?',
        'folders_none': 'No folder yet. Create the first one - use your server name or any custom label.',
        'items_title': 'Items',
        'add_item_label': 'Add an item',
        'add_item_placeholder': 'Type an item name (example: Gelano)',
        'no_results': 'No item found.',
        'item_level': 'Lvl.',
        'remove_item': 'Remove',
        'custom_rolls': 'Saved rolls',
        'stats_as_listed': 'Stats as listed in the encyclopedia.',
        'no_items': 'This folder is empty. Add items with the search above, from the Smithmagic page, or from a solution.',
        'item_added': 'Added!',
        'edit_rolls': 'Edit rolls',
        'editor_save': 'Save',
        'editor_cancel': 'Cancel',
        'editor_add_stat': 'Add a stat…',
    },
    'fr': {
        'title': 'Mon Inventaire',
        'subtitle': 'Les objets que vous possédez, regroupés en dossiers (un par serveur, ou un nom personnalisé).',
        'solver_hint': 'Un projet peut être restreint à un dossier depuis sa page Options (« utiliser uniquement les objets que je possède »).',
        'folders': 'Dossiers',
        'folder_placeholder': 'Nom du serveur ou du dossier',
        'folder_create': 'Créer le dossier',
        'folder_delete': 'Supprimer le dossier',
        'folder_delete_confirm': 'Supprimer ce dossier et tous les objets qu’il contient ?',
        'folders_none': 'Aucun dossier pour l’instant. Créez le premier - utilisez le nom de votre serveur ou un nom personnalisé.',
        'items_title': 'Objets',
        'add_item_label': 'Ajouter un objet',
        'add_item_placeholder': 'Tapez un nom d’objet (exemple : Gelano)',
        'no_results': 'Aucun objet trouvé.',
        'item_level': 'Niv.',
        'remove_item': 'Retirer',
        'custom_rolls': 'Jets enregistrés',
        'stats_as_listed': 'Stats telles que listées dans l’encyclopédie.',
        'no_items': 'Ce dossier est vide. Ajoutez des objets via la recherche ci-dessus, depuis la page Forgemagie, ou depuis une solution.',
        'item_added': 'Ajouté !',
        'edit_rolls': 'Modifier les jets',
        'editor_save': 'Enregistrer',
        'editor_cancel': 'Annuler',
        'editor_add_stat': 'Ajouter une stat…',
    },
    'es': {
        'title': 'Mi Inventario',
        'subtitle': 'Los objetos que posees, agrupados en carpetas (una por servidor, o un nombre personalizado).',
        'solver_hint': 'Un proyecto puede restringirse a una carpeta desde su página de Opciones («usar solo los objetos que poseo»).',
        'folders': 'Carpetas',
        'folder_placeholder': 'Nombre del servidor o de la carpeta',
        'folder_create': 'Crear carpeta',
        'folder_delete': 'Eliminar carpeta',
        'folder_delete_confirm': '¿Eliminar esta carpeta y todos los objetos que contiene?',
        'folders_none': 'Todavía no hay carpetas. Crea la primera - usa el nombre de tu servidor o un nombre personalizado.',
        'items_title': 'Objetos',
        'add_item_label': 'Añadir un objeto',
        'add_item_placeholder': 'Escribe el nombre de un objeto (ejemplo: Gelano)',
        'no_results': 'No se encontró ningún objeto.',
        'item_level': 'Nv.',
        'remove_item': 'Quitar',
        'custom_rolls': 'Tiradas guardadas',
        'stats_as_listed': 'Estadísticas tal como aparecen en la enciclopedia.',
        'no_items': 'Esta carpeta está vacía. Añade objetos con la búsqueda de arriba, desde la página de Forjamagia o desde una solución.',
        'item_added': '¡Añadido!',
        'edit_rolls': 'Editar tiradas',
        'editor_save': 'Guardar',
        'editor_cancel': 'Cancelar',
        'editor_add_stat': 'Añadir una estadística…',
    },
    'pt': {
        'title': 'Meu Inventário',
        'subtitle': 'Os itens que você possui, agrupados em pastas (uma por servidor, ou um nome personalizado).',
        'solver_hint': 'Um projeto pode ser restrito a uma pasta na página de Opções ("usar apenas os itens que possuo").',
        'folders': 'Pastas',
        'folder_placeholder': 'Nome do servidor ou da pasta',
        'folder_create': 'Criar pasta',
        'folder_delete': 'Excluir pasta',
        'folder_delete_confirm': 'Excluir esta pasta e todos os itens dela?',
        'folders_none': 'Nenhuma pasta ainda. Crie a primeira - use o nome do seu servidor ou um nome personalizado.',
        'items_title': 'Itens',
        'add_item_label': 'Adicionar um item',
        'add_item_placeholder': 'Digite o nome de um item (exemplo: Gelano)',
        'no_results': 'Nenhum item encontrado.',
        'item_level': 'Nv.',
        'remove_item': 'Remover',
        'custom_rolls': 'Rolagens salvas',
        'stats_as_listed': 'Atributos como listados na enciclopédia.',
        'no_items': 'Esta pasta está vazia. Adicione itens pela busca acima, pela página de Forjamagia ou por uma solução.',
        'item_added': 'Adicionado!',
        'edit_rolls': 'Editar rolagens',
        'editor_save': 'Salvar',
        'editor_cancel': 'Cancelar',
        'editor_add_stat': 'Adicionar um atributo…',
    },
    'de': {
        'title': 'Mein Inventar',
        'subtitle': 'Die Gegenstaende, die du besitzt, in Ordnern gruppiert (einer pro Server oder ein eigener Name).',
        'solver_hint': 'Ein Projekt kann auf seiner Optionen-Seite auf einen Ordner beschraenkt werden ("nur Gegenstaende verwenden, die ich besitze").',
        'folders': 'Ordner',
        'folder_placeholder': 'Server- oder Ordnername',
        'folder_create': 'Ordner erstellen',
        'folder_delete': 'Ordner loeschen',
        'folder_delete_confirm': 'Diesen Ordner und alle Gegenstaende darin loeschen?',
        'folders_none': 'Noch kein Ordner. Erstelle den ersten - mit deinem Servernamen oder einem eigenen Namen.',
        'items_title': 'Gegenstaende',
        'add_item_label': 'Gegenstand hinzufuegen',
        'add_item_placeholder': 'Gegenstandsname eingeben (Beispiel: Gelano)',
        'no_results': 'Kein Gegenstand gefunden.',
        'item_level': 'St.',
        'remove_item': 'Entfernen',
        'custom_rolls': 'Gespeicherte Wuerfe',
        'stats_as_listed': 'Werte wie in der Enzyklopaedie gelistet.',
        'no_items': 'Dieser Ordner ist leer. Fuege Gegenstaende ueber die Suche oben, die Schmiedemagie-Seite oder eine Loesung hinzu.',
        'item_added': 'Hinzugefuegt!',
        'edit_rolls': 'Wuerfe bearbeiten',
        'editor_save': 'Speichern',
        'editor_cancel': 'Abbrechen',
        'editor_add_stat': 'Wert hinzufuegen…',
    },
}


def _ui_text():
    language = get_supported_language()
    if language not in LOCALIZED_UI:
        language = 'en'
    return LOCALIZED_UI[language]


def _localized_label(label, language):
    if not label:
        return ''
    with translation.override(language):
        return _(label)


def _get_stat_icon_url(stat_key):
    icon_path = get_stat_icon_path(stat_key)
    if icon_path is None:
        return None
    return static(icon_path)


def get_user_folders(user, game_version):
    return (InventoryFolder.objects
            .filter(user=user, game_version=game_version)
            .order_by('name'))


def parse_custom_stats(raw, structure):
    """Validate a {stat_key: value} JSON map; unknown keys / junk dropped."""
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    cleaned = {}
    for key, value in list(data.items())[:60]:
        if structure.get_stat_by_key(str(key)) is None:
            continue
        try:
            value = int(value)
        except (TypeError, ValueError):
            continue
        cleaned[str(key)] = max(-9999, min(99999, value))
    return cleaned


def _custom_stat_lines(structure, item, custom_stats, language):
    """Display lines for saved rolls, colored against the encyclopedia value."""
    base = {}
    if item is not None:
        for stat_id, stat_value in item.stats:
            stat = structure.get_stat_by_id(stat_id)
            if stat is not None:
                base[stat.key] = base.get(stat.key, 0) + stat_value
    lines = []
    for key, value in sorted(custom_stats.items(),
                             key=lambda pair: STAT_ORDER.get(pair[0], 9999)):
        stat = structure.get_stat_by_key(key)
        if stat is None:
            continue
        base_value = int(round(base.get(key, 0)))
        lines.append({
            'text': '%d%s%s' % (value, '' if stat.name.startswith('%') else ' ',
                                _localized_label(stat.name, language)),
            'icon_url': _get_stat_icon_url(key),
            'over': value > base_value,
            'under': value < base_value,
        })
    return lines


def _editor_rows(structure, item, custom_stats, language):
    """Editable lines for an item: its encyclopedia stats plus any extra keys
    already saved (exos), with the saved roll as current value."""
    base = {}
    for stat_id, stat_value in item.stats:
        stat = structure.get_stat_by_id(stat_id)
        if stat is not None:
            base[stat.key] = base.get(stat.key, 0) + stat_value
    keys = set(base)
    keys.update(key for key in custom_stats
                if structure.get_stat_by_key(key) is not None)
    rows = []
    for key in sorted(keys, key=lambda current: STAT_ORDER.get(current, 9999)):
        stat = structure.get_stat_by_key(key)
        base_value = int(round(base.get(key, 0)))
        rows.append({
            'key': key,
            'name': _localized_label(stat.name, language),
            'icon': _get_stat_icon_url(key),
            'base': base_value,
            'value': custom_stats.get(key, base_value),
        })
    return rows


def _addable_stat_options(structure, language):
    options = []
    for stat in structure.get_stats_list():
        if stat.key == 'hp' or stat.key.startswith('pvp'):
            continue
        options.append({
            'key': stat.key,
            'name': _localized_label(stat.name, language),
            'icon': _get_stat_icon_url(stat.key),
        })
    options.sort(key=lambda entry: STAT_ORDER.get(entry['key'], 9999))
    return options


def _folder_payload(folders):
    return [{'id': folder.id, 'name': folder.name,
             'count': folder.items.count()} for folder in folders]


@login_required
def inventory(request):
    game_version = getattr(request, 'game_version', 'dofus3')
    structure = get_structure()
    language = get_supported_language()
    t = _ui_text()

    folders = list(get_user_folders(request.user, game_version))
    selected_id = safe_int(request.GET.get('folder'), None)
    selected = None
    for folder in folders:
        if folder.id == selected_id:
            selected = folder
            break
    if selected is None and folders:
        selected = folders[0]

    items = []
    editor_data = {}
    if selected is not None:
        for row in selected.items.order_by('-added_time'):
            item = structure.get_item_by_id(row.item_id)
            custom_stats = parse_custom_stats(row.custom_stats, structure)
            if item is None:
                items.append({
                    'id': row.id,
                    'name': 'Unknown item #%s' % row.item_id,
                    'level': '',
                    'type_name': '',
                    'image_url': '',
                    'custom_lines': [],
                    'missing': True,
                })
                continue
            type_name = structure.get_type_name_by_id(item.type)
            items.append({
                'id': row.id,
                'name': structure.get_item_name_in_language(item, language),
                'level': item.level,
                'type_name': _localized_label(type_name, language),
                'image_url': static(get_image_url(type_name, item.name)),
                'custom_lines': _custom_stat_lines(structure, item, custom_stats, language),
                'missing': False,
            })
            editor_data[str(row.id)] = {
                'rows': _editor_rows(structure, item, custom_stats, language),
            }

    return set_response(request, 'chardata/inventory.html', {
        'request': request,
        'char_id': 0,
        't': t,
        'folders': [{'id': folder.id, 'name': folder.name,
                     'count': folder.items.count(),
                     'selected': selected is not None and folder.id == selected.id}
                    for folder in folders],
        'selected_folder': selected,
        'inventory_items': items,
        'items_count': len(items),
        'editor_data': editor_data,
        'stat_options': _addable_stat_options(structure, language),
        'search_url': version_reverse(request, 'forgemagie_items'),
        'add_url': version_reverse(request, 'inventory_add'),
        'remove_url': version_reverse(request, 'inventory_remove'),
        'update_url': version_reverse(request, 'inventory_update'),
    })


@login_required
def inventory_folders(request):
    """JSON folder list for the current game version (used by the smithmagic
    page, the solution page and the options page widgets)."""
    game_version = getattr(request, 'game_version', 'dofus3')
    folders = get_user_folders(request.user, game_version)
    return JsonResponse({'folders': _folder_payload(folders)})


def _create_folder(user, game_version, name):
    name = (name or '').strip()[:50]
    if not name:
        return None
    if (InventoryFolder.objects
            .filter(user=user, game_version=game_version).count()
            >= MAX_FOLDERS_PER_VERSION):
        return None
    folder, _created = InventoryFolder.objects.get_or_create(
        user=user, game_version=game_version, name=name)
    return folder


@login_required
@require_POST
def inventory_folder_add(request):
    game_version = getattr(request, 'game_version', 'dofus3')
    folder = _create_folder(request.user, game_version,
                            request.POST.get('name'))
    if request.POST.get('json'):
        if folder is None:
            return JsonResponse({'ok': False}, status=400)
        return JsonResponse({'ok': True, 'folder': {
            'id': folder.id, 'name': folder.name,
            'count': folder.items.count()}})
    url = version_reverse(request, 'inventory')
    if folder is not None:
        url = '%s?folder=%d' % (url, folder.id)
    return redirect(url)


@login_required
@require_POST
def inventory_folder_delete(request):
    game_version = getattr(request, 'game_version', 'dofus3')
    folder_id = safe_int(request.POST.get('folder_id'), None)
    if folder_id is not None:
        InventoryFolder.objects.filter(
            id=folder_id, user=request.user, game_version=game_version).delete()
    return redirect(version_reverse(request, 'inventory'))


@login_required
@require_POST
def inventory_add(request):
    """Add one owned item to a folder. Accepts either an existing folder_id
    or new_folder_name (created on the fly); stats is an optional JSON
    {stat_key: value} map of the item's real rolls."""
    game_version = getattr(request, 'game_version', 'dofus3')
    structure = get_structure()

    folder = None
    folder_id = safe_int(request.POST.get('folder_id'), None)
    if folder_id is not None:
        folder = InventoryFolder.objects.filter(
            id=folder_id, user=request.user, game_version=game_version).first()
    if folder is None and request.POST.get('new_folder_name'):
        folder = _create_folder(request.user, game_version,
                                request.POST.get('new_folder_name'))
    if folder is None:
        return JsonResponse({'ok': False, 'error': 'folder'}, status=400)

    item_id = safe_int(request.POST.get('item_id'), None)
    item = structure.get_item_by_id(item_id) if item_id is not None else None
    if item is None:
        return JsonResponse({'ok': False, 'error': 'item'}, status=400)

    if folder.items.count() >= MAX_ITEMS_PER_FOLDER:
        return JsonResponse({'ok': False, 'error': 'full'}, status=400)

    custom_stats = parse_custom_stats(request.POST.get('stats'), structure)
    InventoryItem.objects.create(
        folder=folder,
        item_id=item.id,
        custom_stats=json.dumps(custom_stats) if custom_stats else '')

    return JsonResponse({'ok': True, 'folder_id': folder.id,
                         'count': folder.items.count()})


@login_required
@require_POST
def inventory_update(request):
    """Replace an owned item's saved rolls with the posted snapshot."""
    inv_id = safe_int(request.POST.get('id'), None)
    row = (InventoryItem.objects
           .filter(id=inv_id, folder__user=request.user)
           .select_related('folder').first())
    if row is None:
        return JsonResponse({'ok': False}, status=400)
    structure = get_structure(row.folder.game_version)
    custom_stats = parse_custom_stats(request.POST.get('stats'), structure)
    row.custom_stats = json.dumps(custom_stats) if custom_stats else ''
    row.save()
    return JsonResponse({'ok': True})


@login_required
@require_POST
def inventory_remove(request):
    inv_id = safe_int(request.POST.get('id'), None)
    if inv_id is not None:
        InventoryItem.objects.filter(
            id=inv_id, folder__user=request.user).delete()
    return JsonResponse({'ok': True})
