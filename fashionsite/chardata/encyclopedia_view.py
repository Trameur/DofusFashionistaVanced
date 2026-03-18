from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.http import Http404
import re
from django.utils.translation import gettext as _

from chardata.image_store import get_image_url
from chardata.official_site import get_item_link
from chardata.util import safe_int, set_response
from fashionistapulp.dofus_constants import STAT_ORDER, TYPE_NAMES
from fashionistapulp.fashion_util import strip_accents
from fashionistapulp.structure import get_structure
from fashionistapulp.translation import get_supported_language
from static_s3.templatetags.static_s3 import static


LOCALIZED_UI = {
    'en': {
        'title': 'Encyclopedia',
        'subtitle': 'Search and filter all available items.',
        'search_label': 'Search',
        'search_placeholder': 'Item name (example: Kings Staff)',
        'type_label': 'Type',
        'all_types': 'All types',
        'min_level': 'Min level',
        'max_level': 'Max level',
        'stat_filters': 'Stat filters (minimum value)',
        'stat_label': 'Stat',
        'min_value_label': 'Min value',
        'add_stat_filter': 'Add stat filter',
        'remove_stat_filter': 'Remove',
        'apply_filters': 'Apply filters',
        'clear_filters': 'Clear',
        'results': 'Results',
        'no_results': 'No items match your filters.',
        'item_level': 'Lvl.',
        'open_item': 'Open item details',
        'details_title': 'Item details',
        'back_to_search': 'Back to encyclopedia',
        'set_label': 'Set',
        'stats_label': 'Stats',
        'conditions_label': 'Conditions',
        'or_label': 'OR',
        'and_label': 'AND',
        'extra_effects_label': 'Extra effects',
        'item_not_found': 'Item not found in the encyclopedia.',
    },
    'fr': {
        'title': 'Encyclopedie',
        'subtitle': 'Recherchez et filtrez tous les objets disponibles.',
        'search_label': 'Recherche',
        'search_placeholder': 'Nom de objet (exemple: Kings Staff)',
        'type_label': 'Type',
        'all_types': 'Tous les types',
        'min_level': 'Niveau min',
        'max_level': 'Niveau max',
        'stat_filters': 'Filtres de caracteristiques (valeur minimale)',
        'stat_label': 'Caracteristique',
        'min_value_label': 'Valeur min',
        'add_stat_filter': 'Ajouter un filtre',
        'remove_stat_filter': 'Supprimer',
        'apply_filters': 'Appliquer les filtres',
        'clear_filters': 'Effacer',
        'results': 'Resultats',
        'no_results': 'Aucun objet ne correspond a vos filtres.',
        'item_level': 'Niv.',
        'open_item': 'Ouvrir les details',
        'details_title': 'Details de objet',
        'back_to_search': 'Retour a encyclopedie',
        'set_label': 'Panoplie',
        'stats_label': 'Caracteristiques',
        'conditions_label': 'Conditions',
        'or_label': 'OU',
        'and_label': 'ET',
        'extra_effects_label': 'Effets supplementaires',
        'item_not_found': 'Objet introuvable dans encyclopedie.',
    },
    'es': {
        'title': 'Enciclopedia',
        'subtitle': 'Busca y filtra todos los objetos disponibles.',
        'search_label': 'Busqueda',
        'search_placeholder': 'Nombre del objeto (ejemplo: Kings Staff)',
        'type_label': 'Tipo',
        'all_types': 'Todos los tipos',
        'min_level': 'Nivel min',
        'max_level': 'Nivel max',
        'stat_filters': 'Filtros de estadisticas (valor minimo)',
        'stat_label': 'Estadistica',
        'min_value_label': 'Valor min',
        'add_stat_filter': 'Agregar filtro',
        'remove_stat_filter': 'Eliminar',
        'apply_filters': 'Aplicar filtros',
        'clear_filters': 'Limpiar',
        'results': 'Resultados',
        'no_results': 'No hay objetos con esos filtros.',
        'item_level': 'Nv.',
        'open_item': 'Abrir detalles del objeto',
        'details_title': 'Detalles del objeto',
        'back_to_search': 'Volver a enciclopedia',
        'set_label': 'Set',
        'stats_label': 'Estadisticas',
        'conditions_label': 'Condiciones',
        'or_label': 'O',
        'and_label': 'Y',
        'extra_effects_label': 'Efectos extra',
        'item_not_found': 'Objeto no encontrado en la enciclopedia.',
    },
    'pt': {
        'title': 'Enciclopedia',
        'subtitle': 'Pesquise e filtre todos os itens disponiveis.',
        'search_label': 'Pesquisa',
        'search_placeholder': 'Nome do item (exemplo: Kings Staff)',
        'type_label': 'Tipo',
        'all_types': 'Todos os tipos',
        'min_level': 'Nivel min',
        'max_level': 'Nivel max',
        'stat_filters': 'Filtros de atributos (valor minimo)',
        'stat_label': 'Atributo',
        'min_value_label': 'Valor min',
        'add_stat_filter': 'Adicionar filtro',
        'remove_stat_filter': 'Remover',
        'apply_filters': 'Aplicar filtros',
        'clear_filters': 'Limpar',
        'results': 'Resultados',
        'no_results': 'Nenhum item corresponde aos filtros.',
        'item_level': 'Nv.',
        'open_item': 'Abrir detalhes do item',
        'details_title': 'Detalhes do item',
        'back_to_search': 'Voltar para enciclopedia',
        'set_label': 'Conjunto',
        'stats_label': 'Atributos',
        'conditions_label': 'Condicoes',
        'or_label': 'OU',
        'and_label': 'E',
        'extra_effects_label': 'Efeitos extras',
        'item_not_found': 'Item nao encontrado na enciclopedia.',
    },
    'de': {
        'title': 'Enzyklopaedie',
        'subtitle': 'Suche und filtere alle verfuegbaren Gegenstaende.',
        'search_label': 'Suche',
        'search_placeholder': 'Gegenstandsname (Beispiel: Kings Staff)',
        'type_label': 'Typ',
        'all_types': 'Alle Typen',
        'min_level': 'Min Stufe',
        'max_level': 'Max Stufe',
        'stat_filters': 'Stat-Filter (Mindestwert)',
        'stat_label': 'Stat',
        'min_value_label': 'Min Wert',
        'add_stat_filter': 'Filter hinzufugen',
        'remove_stat_filter': 'Entfernen',
        'apply_filters': 'Filter anwenden',
        'clear_filters': 'Zuruecksetzen',
        'results': 'Ergebnisse',
        'no_results': 'Keine Gegenstaende entsprechen den Filtern.',
        'item_level': 'Lvl.',
        'open_item': 'Gegenstandsdetails oeffnen',
        'details_title': 'Gegenstandsdetails',
        'back_to_search': 'Zurueck zur Enzyklopaedie',
        'set_label': 'Set',
        'stats_label': 'Werte',
        'conditions_label': 'Bedingungen',
        'or_label': 'ODER',
        'and_label': 'UND',
        'extra_effects_label': 'Zusatzeffekte',
        'item_not_found': 'Gegenstand nicht in der Enzyklopaedie gefunden.',
    },
}


def _ui_text():
    language = get_supported_language()
    if language not in LOCALIZED_UI:
        language = 'en'
    return LOCALIZED_UI[language]


def _normalized_text(value):
    if not value:
        return ''
    return strip_accents(value).lower().strip()


def _normalized_slug(value):
    if not value:
        return ''
    normalized = _normalized_text(value)
    normalized = re.sub(r'[^a-z0-9]+', '-', normalized)
    return normalized.strip('-')


def _get_stats_map(item):
    structure = get_structure()
    stats = {}
    for stat_id, stat_value in item.stats:
        stat = structure.get_stat_by_id(stat_id)
        if stat is None:
            continue
        stats[stat.key] = stats.get(stat.key, 0) + stat_value
    return stats


def _get_stat_lines(structure, item):
    stat_lines = []
    for stat_id, stat_value in sorted(
        item.stats,
        key=lambda stat_pair: STAT_ORDER.get(structure.get_stat_by_id(stat_pair[0]).key, 9999),
    ):
        stat = structure.get_stat_by_id(stat_id)
        if stat is None:
            continue
        stat_lines.append({
            'text': '%d%s%s' % (
                stat_value,
                '' if stat.name.startswith('%') else ' ',
                _(stat.name),
            ),
            'negative': stat_value < 0,
        })
    return stat_lines


def _item_matches_search(structure, item, search_text, language):
    if not search_text:
        return True
    localized_name = structure.get_item_name_in_language(item, language)
    candidate = '%s %s' % (localized_name, item.or_name)
    return _normalized_text(search_text) in _normalized_text(candidate)


def _collect_unique_items(structure):
    items = []
    seen_ids = set()
    for type_name in TYPE_NAMES:
        for item in structure.get_unique_items_by_type_and_level(type_name, 200):
            if item.id in seen_ids or item.removed:
                continue
            seen_ids.add(item.id)
            items.append(item)
    return items


def _get_item_group_key(item):
    ankama_type = (item.ankama_type or '').strip().lower()
    if item.ankama_id and ankama_type:
        return ('ankama', ankama_type, int(item.ankama_id))
    return ('item', int(item.id))


def _get_group_representative(items):
    # Prefer active entries, then lower item id for deterministic behavior.
    sorted_items = sorted(items, key=lambda current: (current.removed, current.id))
    return sorted_items[0]


def _split_variant_suffix(name):
    if not name:
        return '', False

    value = name.strip()
    patterns = [
        r'^(.*?)(?:\s*\(#\d+\))$',
        r'^(.*?)(?:\s*#\d+)$',
        r'^(.*?)(?:\s+\d+)$',
    ]

    for pattern in patterns:
        match = re.match(pattern, value)
        if match is not None:
            base = match.group(1).strip(' -_')
            return base, True

    return value, False


def _get_display_name_for_group(structure, variant_items, language):
    representative = _get_group_representative(variant_items)
    representative_name = structure.get_item_name_in_language(representative, language)

    if len(variant_items) < 2:
        return representative_name

    base_names = []
    all_have_suffix = True
    for variant in variant_items:
        variant_name = structure.get_item_name_in_language(variant, language)
        base_name, has_suffix = _split_variant_suffix(variant_name)
        all_have_suffix = all_have_suffix and has_suffix
        base_names.append(base_name)

    if all_have_suffix and len({_normalized_text(name) for name in base_names}) == 1:
        return base_names[0]

    return representative_name


def _format_condition_groups(structure, variant_items):
    groups = []
    for variant in variant_items:
        parts = []
        for stat_id, stat_value in sorted(
            variant.min_stats_to_equip,
            key=lambda pair: STAT_ORDER.get(structure.get_stat_by_id(pair[0]).key, 9999),
        ):
            stat = structure.get_stat_by_id(stat_id)
            if stat is None:
                continue
            # Keep legacy wording used elsewhere in project: "Stat > value-1".
            parts.append('%s > %d' % (stat.name, stat_value - 1))

        for stat_id, stat_value in sorted(
            variant.max_stats_to_equip,
            key=lambda pair: STAT_ORDER.get(structure.get_stat_by_id(pair[0]).key, 9999),
        ):
            stat = structure.get_stat_by_id(stat_id)
            if stat is None:
                continue
            # Keep legacy wording used elsewhere in project: "Stat < value+1".
            parts.append('%s < %d' % (stat.name, stat_value + 1))

        if parts:
            groups.append(parts)

    return groups


def _get_ankama_type_aliases(ankama_type):
    normalized = (ankama_type or '').strip().lower()
    alias_map = {
        'mount': {'mount', 'mounts'},
        'mounts': {'mount', 'mounts'},
        'pet': {'pet', 'pets'},
        'pets': {'pet', 'pets'},
        'equipment': {'equipment', 'equipement', 'equipements', 'equipments'},
    }
    return alias_map.get(normalized, {normalized})


def encyclopedia(request):
    structure = get_structure()
    language = get_supported_language()
    t = _ui_text()

    search_text = (request.GET.get('q') or '').strip()
    selected_type = (request.GET.get('type') or '').strip()
    min_level = safe_int(request.GET.get('min_level'), None)
    max_level = safe_int(request.GET.get('max_level'), None)

    selected_stat_filters = []
    selected_stat_rows = []

    stat_keys = request.GET.getlist('stat_key')
    stat_mins = request.GET.getlist('stat_min')

    if not stat_keys and not stat_mins:
        # Backward compatibility with earlier indexed query params.
        idx = 1
        while ('stat%d' % idx) in request.GET or ('stat%d_min' % idx) in request.GET:
            stat_keys.append(request.GET.get('stat%d' % idx, ''))
            stat_mins.append(request.GET.get('stat%d_min' % idx, ''))
            idx += 1

    row_count = max(len(stat_keys), len(stat_mins), 1)
    for idx in range(row_count):
        stat_key = (stat_keys[idx] if idx < len(stat_keys) else '').strip()
        stat_min_raw = (stat_mins[idx] if idx < len(stat_mins) else '').strip()
        stat_min = safe_int(stat_min_raw, None)
        selected_stat_rows.append({
            'key': stat_key,
            'min': '' if stat_min_raw == '' else stat_min_raw,
        })
        if stat_key and stat_min is not None and stat_min > 0:
            selected_stat_filters.append((stat_key, stat_min))

    all_items = _collect_unique_items(structure)
    grouped_items = {}
    for item in all_items:
        group_key = _get_item_group_key(item)
        grouped_items.setdefault(group_key, []).append(item)

    filtered_items = []

    for _, variants in grouped_items.items():
        item = _get_group_representative(variants)
        display_name = _get_display_name_for_group(structure, variants, language)
        stat_lines = _get_stat_lines(structure, item)
        type_name = structure.get_type_name_by_id(item.type)
        if selected_type and type_name != selected_type:
            continue
        if min_level is not None and item.level < min_level:
            continue
        if max_level is not None and item.level > max_level:
            continue
        if not _item_matches_search(structure, item, search_text, language):
            continue

        stats_map = _get_stats_map(item)
        stat_filter_failed = False
        for stat_key, stat_min in selected_stat_filters:
            if stats_map.get(stat_key, 0) < stat_min:
                stat_filter_failed = True
                break
        if stat_filter_failed:
            continue

        detail_url = get_item_link(item.ankama_type, item.ankama_id, display_name)
        filtered_items.append({
            'id': item.id,
            'ankama_id': item.ankama_id,
            'ankama_type': item.ankama_type,
            'name': display_name,
            'or_name': item.or_name,
            'level': item.level,
            'type_name': type_name,
            'image_url': static(get_image_url(type_name, item.name)),
            'detail_url': detail_url,
            'stat_lines': stat_lines,
            'stats_map': stats_map,
        })

    filtered_items = sorted(filtered_items, key=lambda entry: (-entry['level'], entry['name'].lower()))

    paginator = Paginator(filtered_items, 40)
    page = request.GET.get('page', 1)
    try:
        page_obj = paginator.page(page)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    query_without_page = request.GET.copy()
    if 'page' in query_without_page:
        del query_without_page['page']
    page_query_prefix = query_without_page.urlencode()
    if page_query_prefix:
        page_query_prefix = '%s&' % page_query_prefix

    stat_options = [
        {
            'key': stat.key,
            'name': structure.get_stat_by_key(stat.key).name,
        }
        for stat in structure.get_stats_list()
    ]
    stat_options = sorted(stat_options, key=lambda entry: STAT_ORDER.get(entry['key'], 9999))

    return set_response(
        request,
        'chardata/encyclopedia.html',
        {
            'request': request,
            'char_id': 0,
            't': t,
            'items_page': page_obj,
            'items_count': len(filtered_items),
            'search_text': search_text,
            'selected_type': selected_type,
            'min_level': '' if min_level is None else min_level,
            'max_level': '' if max_level is None else max_level,
            'type_names': TYPE_NAMES,
            'selected_stat_filters': selected_stat_filters,
            'selected_stat_rows': selected_stat_rows,
            'stat_options': stat_options,
            'page_query_prefix': page_query_prefix,
        },
    )


def encyclopedia_item(request, ankama_type, ankama_id, slug=None):
    structure = get_structure()
    language = get_supported_language()
    t = _ui_text()

    try:
        target_ankama_id = int(ankama_id)
    except (TypeError, ValueError):
        raise Http404(t['item_not_found'])

    matched_item = None
    target_types = _get_ankama_type_aliases(ankama_type)

    # First pass: match on both type (with aliases) and ankama id.
    for item in structure.get_concatenated_items_lists():
        item_type = (item.ankama_type or '').strip().lower()
        if item.ankama_id == target_ankama_id and item_type in target_types:
            matched_item = item
            if not item.removed:
                break

    # Fallback: if type label differs from URL but id exists, still resolve item.
    if matched_item is None:
        for item in structure.get_concatenated_items_lists():
            if item.ankama_id == target_ankama_id:
                matched_item = item
                if not item.removed:
                    break

    # Final fallback: support outdated IDs by matching slug + type aliases.
    if matched_item is None:
        target_slug = _normalized_slug(slug)
        if target_slug:
            for item in structure.get_concatenated_items_lists():
                item_type = (item.ankama_type or '').strip().lower()
                if item_type not in target_types:
                    continue
                localized_name = structure.get_item_name_in_language(item, language)
                item_slugs = {
                    _normalized_slug(localized_name),
                    _normalized_slug(item.or_name),
                    _normalized_slug(item.name),
                }
                if target_slug in item_slugs:
                    matched_item = item
                    if not item.removed:
                        break

    if matched_item is None:
        raise Http404(t['item_not_found'])

    group_key = _get_item_group_key(matched_item)
    grouped_variants = [
        item for item in structure.get_concatenated_items_lists()
        if _get_item_group_key(item) == group_key
    ]
    if not grouped_variants:
        grouped_variants = [matched_item]

    representative_item = _get_group_representative(grouped_variants)

    localized_name = _get_display_name_for_group(structure, grouped_variants, language)
    type_name = structure.get_type_name_by_id(representative_item.type)
    item_set = (structure.get_set_by_id(representative_item.set)
                if representative_item.set is not None else None)

    stat_lines = []
    for stat_id, stat_value in sorted(
        representative_item.stats,
        key=lambda stat_pair: STAT_ORDER.get(structure.get_stat_by_id(stat_pair[0]).key, 9999),
    ):
        stat = structure.get_stat_by_id(stat_id)
        if stat is None:
            continue
        stat_lines.append({
            'name': stat.name,
            'value': stat_value,
        })

    condition_groups = _format_condition_groups(structure, grouped_variants)

    extras = representative_item.localized_extras.get(language)
    if extras is None:
        extras = representative_item.localized_extras.get('en', [])

    return set_response(
        request,
        'chardata/encyclopedia_item.html',
        {
            'request': request,
            'char_id': 0,
            't': t,
            'item': {
                'name': localized_name,
                'or_name': representative_item.or_name,
                'level': representative_item.level,
                'type_name': type_name,
                'ankama_id': representative_item.ankama_id,
                'ankama_type': representative_item.ankama_type,
                'image_url': static(get_image_url(type_name, representative_item.name)),
            },
            'item_set_name': item_set.localized_names.get(language) if item_set else None,
            'stats': stat_lines,
            'condition_groups': condition_groups,
            'extras': extras,
        },
    )