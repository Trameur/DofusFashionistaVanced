from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.shortcuts import redirect
import json
import re
import sqlite3
from django.utils.translation import gettext as _
from django.utils import translation

from chardata.image_store import get_image_url
from chardata.official_site import get_item_link
from chardata.stat_icons import get_stat_icon_path
from chardata.util import safe_int, set_response, version_reverse
from fashionistapulp.dofus_constants import STAT_ORDER, TYPE_NAMES
from fashionistapulp.fashionista_config import get_items_db_path
from fashionistapulp.fashion_util import strip_accents
from fashionistapulp.structure import get_structure
from fashionistapulp.translation import get_supported_language
from chardata.translation_util import LOCALIZED_ELEMENTS, LOCALIZED_WEAPON_TYPES
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
        'order_stats': 'Order by stats',
        'order_direction_label': 'Direction',
        'direction_desc': 'Descending',
        'direction_asc': 'Ascending',
        'add_order_stat': 'Add order stat',
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
        'weapon_details_label': 'Weapon details',
        'description_label': 'Description',
        'additional_info_label': 'Additional information',
        'weight_label': 'Weight',
        'recipe_label': 'Recipe',
        'no_recipe': 'No recipe available.',
        'recipe_unknown_ingredient': 'Unknown ingredient',
        'item_not_found': 'Item not found in the encyclopedia.',
        'pet_feedable_label': 'Possible bonuses (when fed)',
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
        'order_stats': 'Trier par caracteristiques',
        'order_direction_label': 'Ordre',
        'direction_desc': 'Decroissant',
        'direction_asc': 'Croissant',
        'add_order_stat': 'Ajouter un tri',
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
        'weapon_details_label': 'Details arme',
        'description_label': 'Description',
        'additional_info_label': 'Informations supplementaires',
        'weight_label': 'Poids',
        'recipe_label': 'Recette',
        'no_recipe': 'Aucune recette disponible.',
        'recipe_unknown_ingredient': 'Ingredient inconnu',
        'item_not_found': 'Objet introuvable dans encyclopedie.',
        'pet_feedable_label': 'Bonus possibles (selon le nourrissage)',
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
        'order_stats': 'Ordenar por estadisticas',
        'order_direction_label': 'Direccion',
        'direction_desc': 'Descendente',
        'direction_asc': 'Ascendente',
        'add_order_stat': 'Agregar criterio de orden',
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
        'weapon_details_label': 'Detalles del arma',
        'description_label': 'Descripcion',
        'additional_info_label': 'Informacion adicional',
        'weight_label': 'Peso',
        'recipe_label': 'Receta',
        'no_recipe': 'No hay receta disponible.',
        'recipe_unknown_ingredient': 'Ingrediente desconocido',
        'item_not_found': 'Objeto no encontrado en la enciclopedia.',
        'pet_feedable_label': 'Bonificaciones posibles (segun la comida)',
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
        'order_stats': 'Ordenar por atributos',
        'order_direction_label': 'Direcao',
        'direction_desc': 'Decrescente',
        'direction_asc': 'Crescente',
        'add_order_stat': 'Adicionar criterio de ordenacao',
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
        'weapon_details_label': 'Detalhes da arma',
        'description_label': 'Descricao',
        'additional_info_label': 'Informacoes adicionais',
        'weight_label': 'Peso',
        'recipe_label': 'Receita',
        'no_recipe': 'Receita nao disponivel.',
        'recipe_unknown_ingredient': 'Ingrediente desconhecido',
        'item_not_found': 'Item nao encontrado na enciclopedia.',
        'pet_feedable_label': 'Bonus possiveis (conforme alimentado)',
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
        'order_stats': 'Nach Werten sortieren',
        'order_direction_label': 'Richtung',
        'direction_desc': 'Absteigend',
        'direction_asc': 'Aufsteigend',
        'add_order_stat': 'Sortierung hinzufugen',
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
        'weapon_details_label': 'Waffendetails',
        'description_label': 'Beschreibung',
        'additional_info_label': 'Weitere Informationen',
        'weight_label': 'Gewicht',
        'recipe_label': 'Rezept',
        'no_recipe': 'Kein Rezept verfugbar.',
        'recipe_unknown_ingredient': 'Unbekannte Zutat',
        'item_not_found': 'Gegenstand nicht in der Enzyklopaedie gefunden.',
        'pet_feedable_label': 'Moegliche Boni (je nach Fuetterung)',
    },
}


NON_SEARCHABLE_STAT_KEYS = {
    'hp',
}

# Synthetic Dofus Retro pet variants (one per stat a pet can be fed toward, at
# its cap) live at/above this id and reuse the base pet's ankama id, so they
# group with it. The base pet has no fixed stats, so instead of a blank stat
# list we surface these as the bonuses the pet can be fed toward. Must match
# VARIANT_ID_BASE in itemscraper/store_retro_pet_bonuses.py.
PET_VARIANT_ID_BASE = 10_000_000


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


def _localized_label(label, language):
    if not label:
        return ''
    with translation.override(language):
        return _(label)


def _is_searchable_stat_key(stat_key):
    if not stat_key:
        return False
    return stat_key not in NON_SEARCHABLE_STAT_KEYS and not stat_key.startswith('pvp')


def _get_stat_icon_url(stat_key):
    icon_path = get_stat_icon_path(stat_key)
    if icon_path is None:
        return None
    return static(icon_path)


def _get_stats_map(item):
    structure = get_structure()
    stats = {}
    for stat_id, stat_value in item.stats:
        stat = structure.get_stat_by_id(stat_id)
        if stat is None:
            continue
        stats[stat.key] = stats.get(stat.key, 0) + stat_value
    return stats


def _find_weapon_for_variants(structure, variant_items):
    names_to_try = []
    touch_flags = []

    for item in variant_items:
        if item is None:
            continue
        if item.name:
            names_to_try.append(item.name)
        if item.or_name:
            names_to_try.append(item.or_name)
        touch_flags.append(bool(item.dofus_touch))

    # Deduplicate while preserving order.
    seen_names = set()
    ordered_names = []
    for name in names_to_try:
        if name in seen_names:
            continue
        seen_names.add(name)
        ordered_names.append(name)

    flags_to_try = []
    for flag in touch_flags + [False, True]:
        if flag not in flags_to_try:
            flags_to_try.append(flag)

    for name in ordered_names:
        for dofus_touch in flags_to_try:
            weapon = structure.get_weapon_by_name(name, dofus_touch)
            if weapon is not None and getattr(weapon, 'base_hit', None):
                return weapon

    return None


def _get_weapon_detail_lines(structure, variant_items, language):
    weapon = _find_weapon_for_variants(structure, variant_items)
    if weapon is None or not hasattr(weapon, 'base_hit') or weapon.base_hit is None:
        return []

    with translation.override(language):
        weapon_type_obj = structure.get_weapon_type_by_id(weapon.weapon_type)
        weapon_type_name = weapon_type_obj.name if weapon_type_obj is not None else ''
        localized_weapon_type = LOCALIZED_WEAPON_TYPES.get(weapon_type_name, weapon_type_name)

        lines = []
        if weapon.crit_chance is not None and weapon.crit_bonus is not None:
            lines.append(
                _('(%(weapon_type)s) AP: %(AP)d / CH: %(crit_chance)d%% (+%(crit_bonus)d)')
                % {
                    'weapon_type': localized_weapon_type,
                    'AP': weapon.ap,
                    'crit_chance': weapon.crit_chance,
                    'crit_bonus': weapon.crit_bonus,
                }
            )
        else:
            lines.append(
                _('(%(weapon_type)s) AP: %(AP)d')
                % {'weapon_type': localized_weapon_type, 'AP': weapon.ap}
            )

        for hit in weapon.base_hit:
            if hit.steals:
                line = _('%(min)d to %(max)d (%(element)s steal)') % {
                    'min': hit.min_dam,
                    'max': hit.max_dam,
                    'element': LOCALIZED_ELEMENTS.get(hit.element, hit.element),
                }
            elif hit.heals:
                line = _('%(min)d to %(max)d %(element)s heals') % {
                    'min': hit.min_dam,
                    'max': hit.max_dam,
                    'element': LOCALIZED_ELEMENTS.get(hit.element, hit.element),
                }
            else:
                line = _('%(min)d to %(max)d (%(element)s)') % {
                    'min': hit.min_dam,
                    'max': hit.max_dam,
                    'element': LOCALIZED_ELEMENTS.get(hit.element, hit.element),
                }
            lines.append(line)

    return lines


def _get_pet_feedable_bonuses(structure, grouped_variants, language):
    """For a Retro pet, the maxed stats it can be fed toward (one per variant).

    Each synthetic variant carries a single stat at its cap; the player picks
    one, so these read as alternatives (OR) on the pet's page. Empty for any
    item that isn't a feedable Retro pet.
    """
    bonuses = []
    for variant in sorted(grouped_variants, key=lambda current: current.id):
        if variant.id < PET_VARIANT_ID_BASE:
            continue
        for stat_id, stat_value in variant.stats:
            stat = structure.get_stat_by_id(stat_id)
            if stat is None:
                continue
            rounded_value = int(round(stat_value))
            bonuses.append({
                'text': '%d%s%s' % (
                    rounded_value,
                    '' if stat.name.startswith('%') else ' ',
                    _localized_label(stat.name, language),
                ),
                'icon_url': _get_stat_icon_url(stat.key),
            })
    return bonuses


def _get_set_bonuses(structure, item_set, language):
    """The bonuses a panoply grants per number of pieces worn, grouped, for the item
    page. The data was already loaded (set_bonus table) but only the set name was shown."""
    if item_set is None or not getattr(item_set, 'bonus', None):
        return []
    by_pieces = {}
    for num_items, stat_id, value in item_set.bonus:
        stat = structure.get_stat_by_id(stat_id)
        if stat is None:
            continue
        by_pieces.setdefault(num_items, []).append((
            STAT_ORDER.get(stat.key, 9999),
            {
                'name': _localized_label(stat.name, language),
                'value': int(round(value)),
                'icon_url': _get_stat_icon_url(stat.key),
            },
        ))
    groups = []
    for num_pieces in sorted(by_pieces):
        lines = [line for _, line in sorted(by_pieces[num_pieces], key=lambda pair: pair[0])]
        groups.append({'num_pieces': num_pieces, 'lines': lines})
    return groups


def _get_set_items(structure, item_set, language, game_version):
    """The items belonging to a panoply, as cards for the dedicated set page."""
    cards = []
    seen = set()
    for item_id in getattr(item_set, 'items', None) or []:
        item = structure.get_item_by_id(item_id)
        if item is None or not getattr(item, 'ankama_id', None):
            continue
        if item.ankama_id in seen:
            continue
        seen.add(item.ankama_id)
        type_name = structure.get_type_name_by_id(item.type)
        display_name = _get_display_name_for_group(structure, [item], language)
        cards.append({
            'name': display_name,
            'level': item.level,
            'type_name': _localized_label(type_name, language),
            'image_url': static(get_image_url(type_name, item.name)),
            'detail_url': get_item_link(item.ankama_type, item.ankama_id,
                                        display_name, game_version=game_version),
        })
    cards.sort(key=lambda card: (-(card['level'] or 0), (card['name'] or '').lower()))
    return cards


def _get_stat_lines(structure, item, language):
    stat_lines = []
    for stat_id, stat_value in sorted(
        item.stats,
        key=lambda stat_pair: STAT_ORDER.get(structure.get_stat_by_id(stat_pair[0]).key, 9999),
    ):
        stat = structure.get_stat_by_id(stat_id)
        if stat is None:
            continue
        # Round stat value to nearest integer to avoid floating-point precision issues
        rounded_value = int(round(stat_value))
        stat_lines.append({
            'text': '%d%s%s' % (
                rounded_value,
                '' if stat.name.startswith('%') else ' ',
                _localized_label(stat.name, language),
            ),
            'negative': stat_value < 0,
            'icon_url': _get_stat_icon_url(stat.key),
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


def _format_condition_groups(structure, variant_items, language):
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
            parts.append('%s > %d' % (_localized_label(stat.name, language), stat_value - 1))

        for stat_id, stat_value in sorted(
            variant.max_stats_to_equip,
            key=lambda pair: STAT_ORDER.get(structure.get_stat_by_id(pair[0]).key, 9999),
        ):
            stat = structure.get_stat_by_id(stat_id)
            if stat is None:
                continue
            # Keep legacy wording used elsewhere in project: "Stat < value+1".
            parts.append('%s < %d' % (_localized_label(stat.name, language), stat_value + 1))

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


def _get_item_extra_info(representative_item, language, t, game_version='dofus3'):
    default_data = {
        'description': None,
        'pods': None,
        'recipe': [],
    }

    if representative_item is None:
        return default_data

    conn = None
    try:
        conn = sqlite3.connect(get_items_db_path(game_version))
        cursor = conn.cursor()

        cursor.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'item_descriptions'"
        )
        if cursor.fetchone() is not None:
            cursor.execute(
                "SELECT description FROM item_descriptions WHERE item = ? AND language = ?",
                (representative_item.id, language),
            )
            row = cursor.fetchone()
            if row is None and language != 'en':
                cursor.execute(
                    "SELECT description FROM item_descriptions WHERE item = ? AND language = 'en'",
                    (representative_item.id,),
                )
                row = cursor.fetchone()
            if row is not None:
                default_data['description'] = row[0]

        cursor.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'item_extra_info'"
        )
        if cursor.fetchone() is not None:
            cursor.execute(
                "SELECT pods FROM item_extra_info WHERE item = ?",
                (representative_item.id,),
            )
            row = cursor.fetchone()
            if row is not None:
                default_data['pods'] = row[0]

        cursor.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'item_recipes'"
        )
        has_recipe_table = cursor.fetchone() is not None
        cursor.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'item_recipe_ingredient_names'"
        )
        has_recipe_names_table = cursor.fetchone() is not None

        if has_recipe_table:
            cursor.execute(
                """
                SELECT position, ingredient_ankama_id, ingredient_subtype, quantity
                FROM item_recipes
                WHERE item = ?
                ORDER BY position ASC
                """,
                (representative_item.id,),
            )
            recipe_rows = cursor.fetchall()

            for _, ingredient_ankama_id, ingredient_subtype, quantity in recipe_rows:
                ingredient_name = None
                if has_recipe_names_table:
                    cursor.execute(
                        """
                        SELECT name
                        FROM item_recipe_ingredient_names
                        WHERE ingredient_ankama_id = ?
                          AND ingredient_subtype = ?
                          AND language = ?
                        """,
                        (ingredient_ankama_id, ingredient_subtype, language),
                    )
                    name_row = cursor.fetchone()
                    if name_row is None and language != 'en':
                        cursor.execute(
                            """
                            SELECT name
                            FROM item_recipe_ingredient_names
                            WHERE ingredient_ankama_id = ?
                              AND ingredient_subtype = ?
                              AND language = 'en'
                            """,
                            (ingredient_ankama_id, ingredient_subtype),
                        )
                        name_row = cursor.fetchone()
                    if name_row is not None:
                        ingredient_name = name_row[0]

                if not ingredient_name:
                    ingredient_name = '%s #%s' % (t['recipe_unknown_ingredient'], ingredient_ankama_id)

                local_item_url = None
                local_item_types = {
                    'equipment': 'equipment',
                    'mounts': 'mount',
                    'mount': 'mount',
                    'pet': 'pet',
                    'pets': 'pet',
                }
                local_type = local_item_types.get((ingredient_subtype or '').lower())
                if local_type:
                    cursor.execute(
                        "SELECT ankama_id, ankama_type, id, name, dofustouch FROM items WHERE ankama_id = ? AND ankama_type = ? ORDER BY dofustouch ASC LIMIT 1",
                        (ingredient_ankama_id, local_type),
                    )
                    local_item = cursor.fetchone()
                    if local_item is not None:
                        local_name = local_item[3]
                        local_item_url = get_item_link(local_item[1], local_item[0], local_name, game_version)

                default_data['recipe'].append({
                    'name': ingredient_name,
                    'quantity': quantity,
                    'subtype': ingredient_subtype,
                    'ankama_id': ingredient_ankama_id,
                    'local_item_url': local_item_url,
                })

    except Exception:
        return default_data
    finally:
        if conn is not None:
            conn.close()

    return default_data


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
    selected_stat_orders = []
    selected_order_rows = []

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

        if stat_key and not _is_searchable_stat_key(stat_key):
            stat_key = ''

        selected_stat_rows.append({
            'key': stat_key,
            'min': '' if stat_min_raw == '' else stat_min_raw,
        })
        if stat_key and stat_min is not None and stat_min > 0 and _is_searchable_stat_key(stat_key):
            selected_stat_filters.append((stat_key, stat_min))

    order_keys = []
    order_dirs = []

    order_rows_json = (request.GET.get('order_rows_json') or '').strip()
    if order_rows_json:
        try:
            parsed_rows = json.loads(order_rows_json)
            if isinstance(parsed_rows, list):
                for row in parsed_rows:
                    if not isinstance(row, dict):
                        continue
                    order_keys.append(str(row.get('key', '')).strip())
                    order_dirs.append(str(row.get('dir', '')).strip().lower())
        except (TypeError, ValueError):
            order_keys = []
            order_dirs = []

    if not order_keys and not order_dirs:
        order_keys = request.GET.getlist('order_key')
        order_dirs = request.GET.getlist('order_dir')

    if not order_keys and not order_dirs:
        # Backward compatibility for earlier single-field ordering params.
        legacy_order_key = (request.GET.get('order_stat') or '').strip()
        legacy_order_dir = (request.GET.get('order_direction') or '').strip().lower()
        if legacy_order_key or legacy_order_dir:
            order_keys = [legacy_order_key]
            order_dirs = [legacy_order_dir]

    order_row_count = max(len(order_keys), len(order_dirs), 1)
    for idx in range(order_row_count):
        order_key = (order_keys[idx] if idx < len(order_keys) else '').strip()
        order_dir = (order_dirs[idx] if idx < len(order_dirs) else '').strip().lower()

        if order_key and not _is_searchable_stat_key(order_key):
            order_key = ''
        if order_dir not in ('asc', 'desc'):
            order_dir = 'desc'

        selected_order_rows.append({
            'key': order_key,
            'dir': order_dir,
        })

        if order_key and _is_searchable_stat_key(order_key):
            selected_stat_orders.append((order_key, order_dir))

    all_items = _collect_unique_items(structure)
    grouped_items = {}
    for item in all_items:
        group_key = _get_item_group_key(item)
        grouped_items.setdefault(group_key, []).append(item)

    filtered_items = []

    for _, variants in grouped_items.items():
        item = _get_group_representative(variants)
        # 'or'-group placeholders (e.g. Gelano) carry no ankama id or stats; the real
        # data lives on the named variants in or_items. Use the variant that has an
        # ankama id so the card shows the stat line and a working details link.
        if not getattr(item, 'ankama_id', None):
            _or_variants = (structure.or_items.get(item.name)
                            or structure.dt_or_items.get(item.name) or [])
            _real_variant = next((v for v in _or_variants if getattr(v, 'ankama_id', None)), None)
            if _real_variant is not None:
                item = _real_variant
        display_name = _get_display_name_for_group(structure, variants, language)
        stat_lines = _get_stat_lines(structure, item, language)
        type_name = structure.get_type_name_by_id(item.type)
        localized_type_name = _localized_label(type_name, language)
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

        detail_url = get_item_link(item.ankama_type, item.ankama_id, display_name,
                                   game_version=getattr(request, 'game_version', 'dofus3'))
        filtered_items.append({
            'id': item.id,
            'ankama_id': item.ankama_id,
            'ankama_type': item.ankama_type,
            'name': display_name,
            'or_name': item.or_name,
            'level': item.level,
            'type_name': localized_type_name,
            'image_url': static(get_image_url(type_name, item.name)),
            'detail_url': detail_url,
            'stat_lines': stat_lines,
            'stats_map': stats_map,
        })

    if selected_stat_orders:
        def _sort_key(entry):
            values = []
            for stat_key, order_dir in selected_stat_orders:
                stat_value = entry['stats_map'].get(stat_key, 0)
                values.append(stat_value if order_dir == 'asc' else -stat_value)
            values.append(-entry['level'])
            values.append((entry['name'] or '').lower())
            return tuple(values)

        filtered_items = sorted(filtered_items, key=_sort_key)
    else:
        filtered_items = sorted(filtered_items, key=lambda entry: (-entry['level'], (entry['name'] or '').lower()))

    # Keep page size aligned with a 3-column grid to avoid orphan single-item rows.
    paginator = Paginator(filtered_items, 39)
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
            'name': _localized_label(structure.get_stat_by_key(stat.key).name, language),
            'icon_url': _get_stat_icon_url(stat.key) or '',
        }
        for stat in structure.get_stats_list()
        if _is_searchable_stat_key(stat.key)
    ]
    stat_options = sorted(stat_options, key=lambda entry: STAT_ORDER.get(entry['key'], 9999))

    type_options = [
        {
            'value': type_name,
            'label': _localized_label(type_name, language),
        }
        for type_name in TYPE_NAMES
    ]

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
            'type_options': type_options,
            'selected_stat_filters': selected_stat_filters,
            'selected_stat_rows': selected_stat_rows,
            'selected_order_rows': selected_order_rows,
            'stat_options': stat_options,
            'page_query_prefix': page_query_prefix,
        },
    )


def encyclopedia_set(request, set_id):
    structure = get_structure()
    language = get_supported_language()
    t = _ui_text()

    set_id = safe_int(set_id, None)
    if set_id is None:
        return redirect(version_reverse(request, 'encyclopedia'))
    # sets_dict first, like read_set_bonus_table / get_set_by_id (the bonus-bearing set).
    item_set = structure.sets_dict.get(set_id) or structure.dt_sets_dict.get(set_id)
    if item_set is None:
        return redirect(version_reverse(request, 'encyclopedia'))

    game_version = getattr(request, 'game_version', 'dofus3')
    set_name = (item_set.localized_names.get(language)
                or item_set.localized_names.get('en') or item_set.name)

    return set_response(
        request,
        'chardata/encyclopedia_set.html',
        {
            'request': request,
            'char_id': 0,
            't': t,
            'set_name': set_name,
            'set_items': _get_set_items(structure, item_set, language, game_version),
            'set_bonuses': _get_set_bonuses(structure, item_set, language),
        },
    )


def encyclopedia_sets(request):
    structure = get_structure()
    language = get_supported_language()
    t = _ui_text()

    search_text = (request.GET.get('q') or '').strip()
    needle = _normalized_slug(search_text) if search_text else ''

    sets = []
    for set_id, item_set in structure.sets_dict.items():
        if not getattr(item_set, 'items', None):
            continue
        name = (item_set.localized_names.get(language)
                or item_set.localized_names.get('en') or item_set.name)
        if not name:
            continue
        if needle and needle not in _normalized_slug(name):
            continue
        max_pieces = 0
        if getattr(item_set, 'bonus', None):
            max_pieces = max((num for num, _, _ in item_set.bonus), default=0)
        sets.append({
            'name': name,
            'max_pieces': max_pieces,
            'url': version_reverse(request, 'encyclopedia_set', set_id),
        })
    sets.sort(key=lambda entry: (entry['name'] or '').lower())

    return set_response(
        request,
        'chardata/encyclopedia_sets.html',
        {
            'request': request,
            'char_id': 0,
            't': t,
            'sets': sets,
            'search_text': search_text,
            'sets_count': len(sets),
        },
    )


def encyclopedia_item(request, ankama_type, ankama_id, slug=None):
    structure = get_structure()
    language = get_supported_language()
    t = _ui_text()

    try:
        target_ankama_id = int(ankama_id)
    except (TypeError, ValueError):
        return redirect(version_reverse(request, 'encyclopedia'))

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
        # Item doesn't exist in this game version (e.g. after switching versions
        # from an item page) — fall back to the version's main encyclopedia
        # rather than showing a 404.
        return redirect(version_reverse(request, 'encyclopedia'))

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
    localized_type_name = _localized_label(type_name, language)
    # Resolve the set the way read_set_bonus_table stored its bonuses (sets_dict
    # first). get_set_by_id() checks dt_sets_dict first, which for the one id that
    # exists in both (1) returns the touch "Jellix Set" instead of the dofus3
    # "Gobball Set" -> wrong name AND no .bonus to show.
    item_set = None
    if representative_item.set is not None:
        item_set = (structure.sets_dict.get(representative_item.set)
                    or structure.dt_sets_dict.get(representative_item.set))

    stat_lines = []
    for stat_id, stat_value in sorted(
        representative_item.stats,
        key=lambda stat_pair: STAT_ORDER.get(structure.get_stat_by_id(stat_pair[0]).key, 9999),
    ):
        stat = structure.get_stat_by_id(stat_id)
        if stat is None:
            continue
        stat_lines.append({
            'name': _localized_label(stat.name, language),
            'value': stat_value,
            'icon_url': _get_stat_icon_url(stat.key),
        })

    pet_feedable_bonuses = _get_pet_feedable_bonuses(structure, grouped_variants, language)
    set_bonuses = _get_set_bonuses(structure, item_set, language)

    condition_groups = _format_condition_groups(structure, grouped_variants, language)

    extras = representative_item.localized_extras.get(language)
    if extras is None:
        extras = representative_item.localized_extras.get('en', [])

    extra_info = _get_item_extra_info(representative_item, language, t,
                                      game_version=getattr(request, 'game_version', 'dofus3'))
    weapon_lines = _get_weapon_detail_lines(structure, grouped_variants, language)

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
                'type_name': localized_type_name,
                'ankama_id': representative_item.ankama_id,
                'ankama_type': representative_item.ankama_type,
                'image_url': static(get_image_url(type_name, representative_item.name)),
            },
            'item_set_name': item_set.localized_names.get(language) if item_set else None,
            'item_set_id': item_set.id if item_set else None,
            'set_bonuses': set_bonuses,
            'stats': stat_lines,
            'pet_feedable_bonuses': pet_feedable_bonuses,
            'condition_groups': condition_groups,
            'extras': extras,
            'weapon_lines': weapon_lines,
            'description': extra_info['description'],
            'pods': extra_info['pods'],
            'recipe': extra_info['recipe'],
        },
    )