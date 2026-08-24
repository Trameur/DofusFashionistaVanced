from collections import Counter, defaultdict
import json
import re
import sqlite3

from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.conf import settings
from django.shortcuts import redirect
from django.utils.translation import get_language, gettext as _
from django.utils import translation

from chardata.context_processors import ACTIVE_GAME_VERSIONS
from chardata.image_store import get_image_url, _static_exists, list_static_dir
from chardata.official_site import (
    get_item_link, get_monster_link, get_resource_link, get_set_link)
from chardata.spell_tips import SpellTip, spell_tip_for
from chardata.stat_icons import get_stat_icon_path
from chardata.util import safe_int, set_response, version_reverse
from fashionistapulp.dofus_constants import STAT_ORDER, TYPE_NAMES
from fashionistapulp.fashionista_config import get_items_db_path
from fashionistapulp.fashion_util import is_same_item_name, strip_accents
from fashionistapulp.item_flags import flag_lines
from fashionistapulp.spell_text import fold_spell_blocks
from fashionistapulp.structure import get_structure
from fashionistapulp.translation import SUPPORTED_LANGUAGES, get_supported_language

from chardata.url_language import (build_alternate_urls, language_from_slug,
                                   mark_varies_on_cookie,
                                   redirect_target_for_user)
from chardata.stat_range import format_stat_range, get_stat_range
from chardata.weapon_header import format_weapon_header, format_weapon_hit
from chardata.translation_util import localized_stat_name, LOCALIZED_ELEMENTS, LOCALIZED_WEAPON_TYPES
from static_s3.templatetags.static_s3 import static


LOCALIZED_UI = {
    'en': {
        'title': 'Encyclopedia',
        'subtitle': 'Search items and browse sets, monsters and drops for this game version.',
        'search_label': 'Search',
        'search_placeholder': 'Item name (example: Gelano)',
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
        'resources_label': 'Resources',
        'no_results': 'No items match your filters.',
        'item_level': 'Lvl.',
        'open_item': 'Open item details',
        'details_title': 'Item details',
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
        'dropped_by_label': 'Dropped by',
        'show_more_drops_label': 'Show more',
        'similar_items_label': 'Other items of this type and level',
        'builds_using_label': 'Builds wearing this item',
        'craft_job_label': 'Crafted by',
        'no_recipe': 'No recipe available.',
        'recipe_unknown_ingredient': 'Unknown ingredient',
        'item_not_found': 'Item not found in the encyclopedia.',
        'pet_feedable_label': 'Possible bonuses (when fed)',
        'resource_kind_label': 'Resource',
        'ingredient_kind_label': 'Ingredient',
        'used_to_craft_label': 'Used to craft',
        'set_items_label': 'Items',
        'sort_label': 'Sort by',
        'sort_name': 'Name',
        'sort_level': 'Level',
        'resource_not_found': 'Resource not found in the encyclopedia.',
        'missing_item_title': 'Item unavailable in this version',
        'missing_monster_title': 'Monster unavailable in this version',
        'missing_resource_title': 'Resource unavailable in this version',
        'missing_item_message': 'The item %(name)s does not exist in the %(version)s encyclopedia. Each Dofus version has its own items, drops and data.',
        'missing_monster_message': 'The monster %(name)s does not exist in the %(version)s encyclopedia. Each Dofus version has its own monsters, drops and data.',
        'missing_resource_message': 'The resource %(name)s does not exist in the %(version)s encyclopedia. Each Dofus version has its own resources, drops and data.',
        'missing_back_to_encyclopedia': 'Back to this version encyclopedia',
        'also_in_label': 'Also in',
    },
    'fr': {
        'title': 'Encyclopédie',
        'subtitle': 'Recherchez les objets et parcourez les panoplies, monstres et drops de cette version.',
        'search_label': 'Recherche',
        'search_placeholder': "Nom de l'objet (exemple : Gelano)",
        'type_label': 'Type',
        'all_types': 'Tous les types',
        'min_level': 'Niveau min',
        'max_level': 'Niveau max',
        'stat_filters': 'Filtres de caractéristiques (valeur minimale)',
        'stat_label': 'Caractéristique',
        'min_value_label': 'Valeur min',
        'add_stat_filter': 'Ajouter un filtre',
        'remove_stat_filter': 'Supprimer',
        'order_stats': 'Trier par caractéristiques',
        'order_direction_label': 'Ordre',
        'direction_desc': 'Décroissant',
        'direction_asc': 'Croissant',
        'add_order_stat': 'Ajouter un tri',
        'apply_filters': 'Appliquer les filtres',
        'clear_filters': 'Effacer',
        'results': 'Résultats',
        'resources_label': 'Ressources',
        'no_results': 'Aucun objet ne correspond à vos filtres.',
        'item_level': 'Niv.',
        'open_item': 'Ouvrir les détails',
        'details_title': "Détails de l'objet",
        'set_label': 'Panoplie',
        'stats_label': 'Caractéristiques',
        'conditions_label': 'Conditions',
        'or_label': 'OU',
        'and_label': 'ET',
        'extra_effects_label': 'Effets supplémentaires',
        'weapon_details_label': "Détails de l'arme",
        'description_label': 'Description',
        'additional_info_label': 'Informations supplémentaires',
        'weight_label': 'Poids',
        'recipe_label': 'Recette',
        'dropped_by_label': 'Droppé par',
        'show_more_drops_label': 'Voir plus',
        'similar_items_label': 'Autres objets du même type et niveau',
        'builds_using_label': 'Builds qui portent cet objet',
        'craft_job_label': 'Fabriqué par',
        'no_recipe': 'Aucune recette disponible.',
        'recipe_unknown_ingredient': 'Ingrédient inconnu',
        'item_not_found': "Objet introuvable dans l'encyclopédie.",
        'pet_feedable_label': 'Bonus possibles (selon le nourrissage)',
        'resource_kind_label': 'Ressource',
        'ingredient_kind_label': 'Ingrédient',
        'used_to_craft_label': 'Sert à fabriquer',
        'set_items_label': 'Objets',
        'sort_label': 'Trier par',
        'sort_name': 'Nom',
        'sort_level': 'Niveau',
        'resource_not_found': "Ressource introuvable dans l'encyclopédie.",
        'missing_item_title': 'Objet indisponible dans cette version',
        'missing_monster_title': 'Monstre indisponible dans cette version',
        'missing_resource_title': 'Ressource indisponible dans cette version',
        'missing_item_message': "L'objet %(name)s n'existe pas dans l'encyclopédie %(version)s. Chaque version de Dofus a ses propres objets, drops et données.",
        'missing_monster_message': "Le monstre %(name)s n'existe pas dans l'encyclopédie %(version)s. Chaque version de Dofus a ses propres monstres, drops et données.",
        'missing_resource_message': "La ressource %(name)s n'existe pas dans l'encyclopédie %(version)s. Chaque version de Dofus a ses propres ressources, drops et données.",
        'missing_back_to_encyclopedia': "Retourner à l'encyclopédie de cette version",
        'also_in_label': 'Aussi sur',
    },
    'es': {
        'title': 'Enciclopedia',
        'subtitle': 'Busca objetos y explora sets, monstruos y drops de esta versión.',
        'search_label': 'Búsqueda',
        'search_placeholder': 'Nombre del objeto (ejemplo: Gelanillo)',
        'type_label': 'Tipo',
        'all_types': 'Todos los tipos',
        'min_level': 'Nivel mín',
        'max_level': 'Nivel máx',
        'stat_filters': 'Filtros de estadísticas (valor mínimo)',
        'stat_label': 'Estadística',
        'min_value_label': 'Valor mín',
        'add_stat_filter': 'Agregar filtro',
        'remove_stat_filter': 'Eliminar',
        'order_stats': 'Ordenar por estadísticas',
        'order_direction_label': 'Dirección',
        'direction_desc': 'Descendente',
        'direction_asc': 'Ascendente',
        'add_order_stat': 'Agregar criterio de orden',
        'apply_filters': 'Aplicar filtros',
        'clear_filters': 'Limpiar',
        'results': 'Resultados',
        'resources_label': 'Recursos',
        'no_results': 'No hay objetos con esos filtros.',
        'item_level': 'Nv.',
        'open_item': 'Abrir detalles del objeto',
        'details_title': 'Detalles del objeto',
        'set_label': 'Set',
        'stats_label': 'Estadísticas',
        'conditions_label': 'Condiciones',
        'or_label': 'O',
        'and_label': 'Y',
        'extra_effects_label': 'Efectos extra',
        'weapon_details_label': 'Detalles del arma',
        'description_label': 'Descripción',
        'additional_info_label': 'Información adicional',
        'weight_label': 'Peso',
        'recipe_label': 'Receta',
        'dropped_by_label': 'Soltado por',
        'show_more_drops_label': 'Ver más',
        'similar_items_label': 'Otros objetos del mismo tipo y nivel',
        'builds_using_label': 'Builds que llevan este objeto',
        'craft_job_label': 'Fabricado por',
        'no_recipe': 'No hay receta disponible.',
        'recipe_unknown_ingredient': 'Ingrediente desconocido',
        'item_not_found': 'Objeto no encontrado en la enciclopedia.',
        'pet_feedable_label': 'Bonificaciones posibles (según la comida)',
        'resource_kind_label': 'Recurso',
        'ingredient_kind_label': 'Ingrediente',
        'used_to_craft_label': 'Se usa para fabricar',
        'set_items_label': 'Objetos',
        'sort_label': 'Ordenar por',
        'sort_name': 'Nombre',
        'sort_level': 'Nivel',
        'resource_not_found': 'Recurso no encontrado en la enciclopedia.',
        'missing_item_title': 'Objeto no disponible en esta versión',
        'missing_monster_title': 'Monstruo no disponible en esta versión',
        'missing_resource_title': 'Recurso no disponible en esta versión',
        'missing_item_message': 'El objeto %(name)s no existe en la enciclopedia de %(version)s. Cada versión de Dofus tiene sus propios objetos, drops y datos.',
        'missing_monster_message': 'El monstruo %(name)s no existe en la enciclopedia de %(version)s. Cada versión de Dofus tiene sus propios monstruos, drops y datos.',
        'missing_resource_message': 'El recurso %(name)s no existe en la enciclopedia de %(version)s. Cada versión de Dofus tiene sus propios recursos, drops y datos.',
        'missing_back_to_encyclopedia': 'Volver a la enciclopedia de esta versión',
        'also_in_label': 'También en',
    },
    'pt': {
        'title': 'Enciclopédia',
        'subtitle': 'Busque itens e explore conjuntos, monstros e drops desta versão.',
        'search_label': 'Pesquisa',
        'search_placeholder': 'Nome do item (exemplo: Gelanel)',
        'type_label': 'Tipo',
        'all_types': 'Todos os tipos',
        'min_level': 'Nível mín',
        'max_level': 'Nível máx',
        'stat_filters': 'Filtros de atributos (valor mínimo)',
        'stat_label': 'Atributo',
        'min_value_label': 'Valor mín',
        'add_stat_filter': 'Adicionar filtro',
        'remove_stat_filter': 'Remover',
        'order_stats': 'Ordenar por atributos',
        'order_direction_label': 'Direção',
        'direction_desc': 'Decrescente',
        'direction_asc': 'Crescente',
        'add_order_stat': 'Adicionar critério de ordenação',
        'apply_filters': 'Aplicar filtros',
        'clear_filters': 'Limpar',
        'results': 'Resultados',
        'resources_label': 'Recursos',
        'no_results': 'Nenhum item corresponde aos filtros.',
        'item_level': 'Nv.',
        'open_item': 'Abrir detalhes do item',
        'details_title': 'Detalhes do item',
        'set_label': 'Conjunto',
        'stats_label': 'Atributos',
        'conditions_label': 'Condições',
        'or_label': 'OU',
        'and_label': 'E',
        'extra_effects_label': 'Efeitos extras',
        'weapon_details_label': 'Detalhes da arma',
        'description_label': 'Descrição',
        'additional_info_label': 'Informações adicionais',
        'weight_label': 'Peso',
        'recipe_label': 'Receita',
        'dropped_by_label': 'Dropado por',
        'show_more_drops_label': 'Ver mais',
        'similar_items_label': 'Outros itens do mesmo tipo e nível',
        'builds_using_label': 'Builds que usam este item',
        'craft_job_label': 'Fabricado por',
        'no_recipe': 'Receita não disponível.',
        'recipe_unknown_ingredient': 'Ingrediente desconhecido',
        'item_not_found': 'Item não encontrado na enciclopédia.',
        'pet_feedable_label': 'Bônus possíveis (conforme alimentado)',
        'resource_kind_label': 'Recurso',
        'ingredient_kind_label': 'Ingrediente',
        'used_to_craft_label': 'Usado para fabricar',
        'set_items_label': 'Itens',
        'sort_label': 'Ordenar por',
        'sort_name': 'Nome',
        'sort_level': 'Nível',
        'resource_not_found': 'Recurso não encontrado na enciclopédia.',
        'missing_item_title': 'Item indisponível nesta versão',
        'missing_monster_title': 'Monstro indisponível nesta versão',
        'missing_resource_title': 'Recurso indisponível nesta versão',
        'missing_item_message': 'O item %(name)s não existe na enciclopédia de %(version)s. Cada versão de Dofus tem seus próprios itens, drops e dados.',
        'missing_monster_message': 'O monstro %(name)s não existe na enciclopédia de %(version)s. Cada versão de Dofus tem seus próprios monstros, drops e dados.',
        'missing_resource_message': 'O recurso %(name)s não existe na enciclopédia de %(version)s. Cada versão de Dofus tem seus próprios recursos, drops e dados.',
        'missing_back_to_encyclopedia': 'Voltar para a enciclopédia desta versão',
        'also_in_label': 'Também em',
    },
    'de': {
        'title': 'Enzyklopädie',
        'subtitle': 'Suche Items und durchstöbere Sets, Monster und Drops dieser Version.',
        'search_label': 'Suche',
        'search_placeholder': 'Gegenstandsname (Beispiel: Gelano)',
        'type_label': 'Typ',
        'all_types': 'Alle Typen',
        'min_level': 'Min Stufe',
        'max_level': 'Max Stufe',
        'stat_filters': 'Stat-Filter (Mindestwert)',
        'stat_label': 'Stat',
        'min_value_label': 'Min Wert',
        'add_stat_filter': 'Filter hinzufügen',
        'remove_stat_filter': 'Entfernen',
        'order_stats': 'Nach Werten sortieren',
        'order_direction_label': 'Richtung',
        'direction_desc': 'Absteigend',
        'direction_asc': 'Aufsteigend',
        'add_order_stat': 'Sortierung hinzufügen',
        'apply_filters': 'Filter anwenden',
        'clear_filters': 'Zurücksetzen',
        'results': 'Ergebnisse',
        'resources_label': 'Ressourcen',
        'no_results': 'Keine Gegenstände entsprechen den Filtern.',
        'item_level': 'Lvl.',
        'open_item': 'Gegenstandsdetails öffnen',
        'details_title': 'Gegenstandsdetails',
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
        'dropped_by_label': 'Beute von',
        'show_more_drops_label': 'Mehr anzeigen',
        'similar_items_label': 'Andere Gegenstände dieser Art und Stufe',
        'builds_using_label': 'Builds mit diesem Gegenstand',
        'craft_job_label': 'Hergestellt von',
        'no_recipe': 'Kein Rezept verfügbar.',
        'recipe_unknown_ingredient': 'Unbekannte Zutat',
        'item_not_found': 'Gegenstand nicht in der Enzyklopädie gefunden.',
        'pet_feedable_label': 'Mögliche Boni (je nach Fütterung)',
        'resource_kind_label': 'Ressource',
        'ingredient_kind_label': 'Zutat',
        'used_to_craft_label': 'Wird verwendet für',
        'set_items_label': 'Items',
        'sort_label': 'Sortieren nach',
        'sort_name': 'Name',
        'sort_level': 'Stufe',
        'resource_not_found': 'Ressource nicht in der Enzyklopädie gefunden.',
        'missing_item_title': 'Gegenstand in dieser Version nicht verfügbar',
        'missing_monster_title': 'Monster in dieser Version nicht verfügbar',
        'missing_resource_title': 'Ressource in dieser Version nicht verfügbar',
        'missing_item_message': 'Der Gegenstand %(name)s existiert nicht in der Enzyklopädie für %(version)s. Jede Dofus-Version hat eigene Gegenstände, Drops und Daten.',
        'missing_monster_message': 'Das Monster %(name)s existiert nicht in der Enzyklopädie für %(version)s. Jede Dofus-Version hat eigene Monster, Drops und Daten.',
        'missing_resource_message': 'Die Ressource %(name)s existiert nicht in der Enzyklopädie für %(version)s. Jede Dofus-Version hat eigene Ressourcen, Drops und Daten.',
        'missing_back_to_encyclopedia': 'Zur Enzyklopädie dieser Version',
        'also_in_label': 'Auch in',
    },
}


NON_SEARCHABLE_STAT_KEYS = {
    'hp',
}

# Synthetic pet variants (one per stat a pet can be fed toward, at its cap) live
# at or above these ids and reuse the base pet's ankama id. Retro and Touch are
# the two versions whose data carries no bonus for a feeding pet. Must match
# VARIANT_ID_BASE in itemscraper/store_{retro,touch}_pet_bonuses.py. The other
# versions put cross-version duplicates at 100M + ankama id, so they stay out.
PET_VARIANT_ID_BASE_BY_VERSION = {'retro': 10_000_000, 'touch': 200_000_000}
PET_VARIANT_ID_BASE = PET_VARIANT_ID_BASE_BY_VERSION['retro']


def _ui_text():
    language = get_supported_language()
    if language not in LOCALIZED_UI:
        language = 'en'
    return LOCALIZED_UI[language]


def _normalized_text(value):
    if not value:
        return ''
    return strip_accents(value).lower().strip()


# Upstream ships a raw text id where a name is missing entirely. Unlike the
# "[!]" note, it is not a French fallback: there is no name behind it in any
# language, so there is nothing to put on a page.
# The separators are loose because a slug turns it back into words:
# "unknown-text-id-7222" reads "Unknown text id 7222".
_PLACEHOLDER_NAME = re.compile(r'^\[?UNKNOWN[ _-]?TEXT[ _-]?ID', re.IGNORECASE)


def has_display_name(names):
    return any(name and not _PLACEHOLDER_NAME.match(name.strip())
               for name in (names or {}).values())


def _normalized_slug(value):
    """Slug of a name, built by the same function that builds the urls.

    These were two functions with two rules: official_site._slugify_name drops
    "'s" and this one did not, so an item called "Coldbruela's Boots" was
    published at /…-coldbruelas/ and looked up as "coldbruela-s-boots". The
    lookup found nothing, the page fell back to the negotiated language, and a
    crawler -- sending no header -- read English on a url submitted as Spanish.

    One function now decides both, so a url can no longer be built one way and
    resolved another.
    """
    from chardata.official_site import _slugify_name
    return _slugify_name(value, '')


def _localized_label(label, language):
    if not label:
        return ''
    with translation.override(language):
        return _(label)


def _localized_stat(stat_name, language, game_version=None):
    """A stat's name, in the reader's language and its own version's words."""
    if not stat_name:
        return ''
    with translation.override(language):
        return localized_stat_name(stat_name, game_version)


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

    # Retro and Touch let several weapons share a name, so try the item first.
    for item in variant_items:
        weapon = structure.get_weapon_for_item(item)
        if weapon is not None and getattr(weapon, 'base_hit', None):
            return weapon

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
        localized_weapon_type = (
            LOCALIZED_WEAPON_TYPES.get(weapon_type_name, weapon_type_name)
            if weapon_type_name else None)

        header = format_weapon_header(
            structure.game_version, localized_weapon_type, weapon.ap,
            weapon.crit_chance, weapon.crit_bonus)
        lines = [header] if header else []

        for hit in weapon.base_hit:
            lines.append(format_weapon_hit(structure.game_version, hit,
                                           LOCALIZED_ELEMENTS))

    return lines


def _get_pet_feedable_bonuses(structure, grouped_variants, language,
                              variant_id_base=PET_VARIANT_ID_BASE):
    """For a fed pet, the maxed stats it can be fed toward (one per variant).

    The player picks one, so they read as alternatives (OR) on the pet's page.
    """
    bonuses = []
    for variant in sorted(grouped_variants, key=lambda current: current.id):
        if variant.id < variant_id_base:
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
                    _localized_stat(stat.name, language, structure.game_version),
                ),
                'icon_url': _get_stat_icon_url(stat.key),
            })
    return bonuses


def _get_set_bonuses(structure, item_set, language):
    """The bonuses a panoply grants per number of pieces worn, grouped for the item page."""
    if item_set is None or not (getattr(item_set, 'bonus', None)
                                or getattr(item_set, 'max_caps', None)):
        return []
    by_pieces = {}
    for num_items, stat_id, value in item_set.bonus:
        stat = structure.get_stat_by_id(stat_id)
        if stat is None:
            continue
        by_pieces.setdefault(num_items, []).append((
            STAT_ORDER.get(stat.key, 9999),
            {
                'name': _localized_stat(stat.name, language, structure.game_version),
                'value': int(round(value)),
                'icon_url': _get_stat_icon_url(stat.key),
            },
        ))
    # Some sets cap a stat: Cire Momore's Curse holds the wearer to 2 MP on six
    # pieces, under the 3 a character starts with.
    caps_by_pieces = {}
    for num_items, stat_id, max_value in getattr(item_set, 'max_caps', None) or []:
        stat = structure.get_stat_by_id(stat_id)
        if stat is None:
            continue
        caps_by_pieces.setdefault(num_items, []).append((
            STAT_ORDER.get(stat.key, 9999),
            {
                'name': _localized_stat(stat.name, language, structure.game_version),
                'value': int(round(max_value)),
                'icon_url': _get_stat_icon_url(stat.key),
            },
        ))

    groups = []
    for num_pieces in sorted(set(by_pieces) | set(caps_by_pieces)):
        lines = [line for _, line in sorted(by_pieces.get(num_pieces, []),
                                            key=lambda pair: pair[0])]
        caps = [line for _, line in sorted(caps_by_pieces.get(num_pieces, []),
                                           key=lambda pair: pair[0])]
        groups.append({'num_pieces': num_pieces, 'lines': lines, 'caps': caps})
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
            'image_url': static(get_image_url(type_name, item.name, game_version)),
            'detail_url': get_item_link(item.ankama_type, item.ankama_id,
                                        display_name, game_version=game_version),
        })
    cards.sort(key=lambda card: (-(card['level'] or 0), (card['name'] or '').lower()))
    return cards


def _breadcrumb_jsonld(crumbs):
    """A schema.org BreadcrumbList as a JSON string. crumbs: list of (name, absolute_url)."""
    payload = json.dumps({
        '@context': 'https://schema.org',
        '@type': 'BreadcrumbList',
        'itemListElement': [
            {'@type': 'ListItem', 'position': i + 1, 'name': name, 'item': url}
            for i, (name, url) in enumerate(crumbs)
        ],
    }, ensure_ascii=False)
    # The JSON is rendered with |safe inside a <script>, so escape what could
    # break out of the tag.
    return payload.replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')


def _absolute_versioned_url(path, game_version='dofus3', language=None):
    """Absolute url of a hub page, in the language being served.

    Hubs have no name to localise, so they carry their language in a prefix.
    Without this the breadcrumb of a Spanish item page pointed at the English
    hub, and every crawler following it left Spanish on the first click.

    Only the default version is prefixed: that is the only one whose hubs are
    published per language.
    """
    if not path.startswith('/'):
        path = '/%s' % path
    if game_version and game_version != 'dofus3':
        path = '/%s%s' % (game_version, path)
    # Language first: that is the order i18n_patterns produces, and a
    # breadcrumb disagreeing with it would name a url that does not exist.
    if language is None:
        language = get_language()
    if language and language != settings.LANGUAGE_CODE:
        path = '/%s%s' % (language, path)
    return 'https://dofusfashionista.gg%s' % path


def _paginated_canonical(request, path, game_version, page_obj):
    """Canonical url for a list page: itself, except for a filtered or sorted
    view, which points at the plain list.

    The language is read off the requested url, not off the language being
    served. A hub answers on both /encyclopedia/ and /es/encyclopedia/, so a
    Spanish reader whose browser asks for the first gets Spanish text at an
    unprefixed url -- and that same <head> declares /encyclopedia/ to be the
    English alternate and the x-default. Taking the language from
    get_language() there made the page name /es/encyclopedia/ as its canonical
    while claiming to be the English one: a submitted url contradicting its own
    hreflang block. Links and breadcrumbs still follow the served language,
    which is what a reader wants; only the canonical follows the url.
    """
    from chardata.url_language import split_language_prefix
    prefix, _rest = split_language_prefix(request.path_info)
    url = _absolute_versioned_url(path, game_version,
                                  language=prefix.lstrip('/') or settings.LANGUAGE_CODE)
    filters = {key for key in request.GET if key != 'page'}
    number = getattr(page_obj, 'number', 1) or 1
    if filters or number <= 1:
        return url
    return '%s?page=%d' % (url, number)


def _stat_amount_text(item, stat_id, best_value):
    """"7 to 10" when the roll varies, plain "10" when it is fixed.

    The single number is the best roll, which is what the optimiser assumes."""
    stat_range = get_stat_range(item, stat_id)
    if stat_range is None:
        return '%d' % best_value
    return format_stat_range(*stat_range)


def _get_stat_lines(structure, item, language):
    stat_lines = []
    for stat_id, stat_value in sorted(
        item.stats,
        key=lambda stat_pair: STAT_ORDER.get(structure.get_stat_by_id(stat_pair[0]).key, 9999),
    ):
        stat = structure.get_stat_by_id(stat_id)
        if stat is None:
            continue
        rounded_value = int(round(stat_value))
        stat_lines.append({
            'text': '%s%s%s' % (
                _stat_amount_text(item, stat_id, rounded_value),
                '' if stat.name.startswith('%') else ' ',
                _localized_stat(stat.name, language, structure.game_version),
            ),
            'negative': stat_value < 0,
            'icon_url': _get_stat_icon_url(stat.key),
        })
    return stat_lines


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


# Structures are process-lifetime singletons, so the grouping, stats maps and
# search blobs are built once and the localized labels derived from them.
_light_core_cache = {}
_light_index_cache = {}


def _get_light_core(structure):
    key = id(structure)
    cached = _light_core_cache.get(key)
    if cached is not None:
        return cached

    grouped_items = {}
    for item in _collect_unique_items(structure):
        grouped_items.setdefault(_get_item_group_key(item), []).append(item)

    entries = []
    for _, variants in grouped_items.items():
        item = _get_group_representative(variants)
        # 'or'-group placeholders (e.g. Gelano) carry no ankama id or stats; the
        # real data lives on the named variants in or_items.
        if not getattr(item, 'ankama_id', None):
            _or_variants = (structure.or_items.get(item.name)
                            or structure.dt_or_items.get(item.name) or [])
            _real_variant = next((v for v in _or_variants if getattr(v, 'ankama_id', None)), None)
            if _real_variant is not None:
                item = _real_variant
        search_names = [
            structure.get_item_name_in_language(item, search_language)
            for search_language in SUPPORTED_LANGUAGES
        ]
        search_names.append(item.or_name)
        entries.append({
            'item': item,
            'variant_items': variants,
            'level': item.level,
            'raw_type_name': structure.get_type_name_by_id(item.type),
            'stats_map': _get_stats_map(item),
            'search_blob': _normalized_text(' '.join(name or '' for name in search_names)),
        })
    _light_core_cache[key] = entries
    return entries


def _get_light_index(structure, language):
    key = (id(structure), language)
    cached = _light_index_cache.get(key)
    if cached is not None:
        return cached

    entries = []
    for core_entry in _get_light_core(structure):
        display_name = _get_display_name_for_group(
            structure, core_entry['variant_items'], language)
        entries.append({
            'item': core_entry['item'],
            'name': display_name,
            'level': core_entry['level'],
            'raw_type_name': core_entry['raw_type_name'],
            'stats_map': core_entry['stats_map'],
            'search_blob': core_entry['search_blob'],
        })
    _light_index_cache[key] = entries
    return entries


SIMILAR_ITEMS_SHOWN = 6


def _get_popularity(ankama_id, game_version):
    """How many builds wear this item, and what share of those that could.

    Counted over every build ever calculated, not only the public ones, which
    is what makes it worth printing: 142 043 against 1 980. A count says
    nothing about who, so it can be drawn from private builds where a link
    never could.

    None when the answer would be noise: fewer than thirty comparable builds
    is not a share, and printing one would read as a fact.
    """
    from chardata.models import ItemPopularity
    try:
        ligne = ItemPopularity.objects.filter(
            ankama_id=ankama_id, game_version=game_version).first()
    except Exception:
        return None
    if ligne is None or not ligne.builds:
        return None
    part = ligne.share
    return {
        'builds': ligne.builds,
        'share': None if part is None else '%.1f %%' % part,
    }


def _get_builds_using(ankama_id, game_version, limit=6):
    """The shared builds that wear this item, most read first.

    This is the one thing the encyclopedia can say that Ankama and the wikis
    cannot: they publish the same numbers from the same game files, and none
    of them knows what people actually put on. It is also what the page's own
    meta description has been promising since it existed.

    Read from an index rebuilt by reindex_builds_by_item, never from the
    builds themselves: unpickling 3 361 solutions takes twelve seconds and has
    no business happening while somebody waits for a page.
    """
    from chardata.encoded_char_id import encode_char_id
    from chardata.models import ItemInSharedBuild
    try:
        lignes = (ItemInSharedBuild.objects
                  .filter(ankama_id=ankama_id, game_version=game_version)
                  .select_related('char')
                  .order_by('-char__view_count', '-char__modified_time')
                  [:limit * 3])
    except Exception:
        # The block is a bonus. A page that cannot show it still has to render.
        return []
    builds = []
    for ligne in lignes:
        build = ligne.char
        if build is None or build.deleted or not build.link_shared:
            continue
        builds.append({
            'url': '/s/%s/%s/' % (build.char_name or 'shared',
                                  encode_char_id(int(build.id))),
            'name': build.char_name or build.name,
            'char_class': build.char_class,
            'level': build.level,
            'views': build.view_count,
        })
        if len(builds) >= limit:
            break
    return builds


# Les stats autour desquelles un build se construit. Elles ne sont pas rares
# dans le catalogue, 1 624 objets sur 3 826 en portent une, mais elles le sont
# souvent DANS UN EMPLACEMENT : six anneaux de tout le jeu donnent du PA, et
# aucun a moins de vingt niveaux du Gelano. C'est pourquoi elles filtrent, et
# pourquoi la fenetre de niveau ne s'ouvre que si le filtre ne laisse personne
# dedans, au lieu de s'ouvrir d'office comme dans la premiere version : celle-la
# la faisait sauter pour 42 pour cent du catalogue.
RARE_STATS = {4: 'ap', 5: 'mp', 19: 'range', 18: 'summon'}

# Au-dela, deux objets ne se comparent plus utilement. La similarite decroit
# jusque-la au lieu de s'arreter net, pour qu'un ecart de deux niveaux pese
# plus qu'un ecart de neuf.
LEVEL_WINDOW = 10


def _stat_ids(item, positive_only=False):
    """The stats an item carries. Optionally only those it grants.

    A ring that costs a point of range carries stat 19 exactly as one that
    gives it, and grouping the two together would answer "what else has range"
    with the items that take it away.
    """
    lignes = getattr(item, 'stats', None) or []
    return {stat_id for stat_id, value in lignes
            if not positive_only or (value or 0) > 0}


def _get_similar_items(structure, language, game_version, item, limit=None):
    """Items of the same slot that a reader could actually swap this one for.

    Sorting by level alone answered the wrong question. The Gelano is a level
    60 ring whose whole point is the AP it carries, and the ring page offered
    twenty-five rings of the same level, not one of which carried any.

    So a rare stat filters: an item that grants AP is compared to the others
    that grant AP. The level window still applies first, because for most
    slots there are plenty of them nearby; it opens only when the filter
    leaves nobody inside it, which is what happens to the six AP rings.

    Fewer results, or none, is the honest answer when nothing is alike.
    """
    limit = limit or SIMILAR_ITEMS_SHOWN
    from chardata.lock_forbid import get_default_exclusions
    hidden = set(get_default_exclusions(None))
    slot = structure.get_type_name_by_id(item.type)
    here = (item.ankama_type or '', item.ankama_id)
    level = item.level or 0
    mine = _stat_ids(item)
    rare = _stat_ids(item, positive_only=True) & set(RARE_STATS)

    dedans, dehors = [], []
    for entry in _get_light_index(structure, language):
        other = entry['item']
        if entry['raw_type_name'] != slot:
            continue
        if ((other.ankama_type or ''), other.ankama_id) == here:
            continue
        if not other.ankama_id or not other.ankama_type:
            continue
        if other.id in hidden:
            continue
        if rare and not rare <= _stat_ids(other, positive_only=True):
            continue

        distance = abs((entry['level'] or 0) - level)
        # Une stat partagee vaut plus qu'un niveau proche, et le niveau ne
        # departage que des objets deja comparables.
        proximity = max(0.0, 1.0 - distance / float(LEVEL_WINDOW))
        score = len(mine & _stat_ids(other)) + proximity * 2
        (dedans if distance <= LEVEL_WINDOW else dehors).append(
            (-score, distance, entry['name'] or '', entry))

    dedans.sort(key=lambda row: row[:3])
    # La fenetre ne s'ouvre que pour un objet a stat rare, et seulement si elle
    # ne s'est pas remplie. Ce qui vient de loin passe apres tout ce qui vient
    # de pres.
    if rare and len(dedans) < limit:
        dehors.sort(key=lambda row: (row[1], row[2]))
        dedans.extend(dehors[:limit - len(dedans)])

    out = []
    for _score, _distance, _name, entry in dedans[:limit]:
        other = entry['item']
        link = get_item_link(other.ankama_type, other.ankama_id,
                             entry['name'] or other.name,
                             game_version=game_version)
        if not link:
            continue
        out.append({
            'name': entry['name'] or other.name,
            'level': entry['level'],
            'url': link,
            'image_url': static(get_image_url(slot, other.name, game_version)),
        })
    return out

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


def _condition_text(structure, stat_id, value, is_max, language):
    """One gate, worded the way the rest of the project words them."""
    stat = structure.get_stat_by_id(stat_id)
    if stat is None:
        return None
    label = _localized_stat(stat.name, language, structure.game_version)
    return ('%s < %d' % (label, value + 1) if is_max
            else '%s > %d' % (label, value - 1))


def _format_condition_groups(structure, variant_items, language):
    """The template reads a list of groups: within one, the gates all hold; a
    build only has to satisfy one group. An item whose branches used to ship as
    separate rows carries them on itself now, so its groups come from there."""
    groups = []
    for variant in variant_items:
        def order(pair):
            stat = structure.get_stat_by_id(pair[0])
            return STAT_ORDER.get(stat.key, 9999) if stat else 9999

        shared = []
        for stat_id, value in sorted(variant.min_stats_to_equip, key=order):
            text = _condition_text(structure, stat_id, value, False, language)
            if text:
                shared.append(text)
        for stat_id, value in sorted(variant.max_stats_to_equip, key=order):
            text = _condition_text(structure, stat_id, value, True, language)
            if text:
                shared.append(text)

        branches = getattr(variant, 'or_conditions', None) or []
        if not branches:
            if shared:
                groups.append(shared)
            continue
        for branch in branches:
            parts = list(shared)
            for stat_id, is_max, value in sorted(
                    branch, key=lambda gate: order((gate[0],))):
                text = _condition_text(structure, stat_id, value, is_max, language)
                if text:
                    parts.append(text)
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


def _version_label(game_version):
    return dict(ACTIVE_GAME_VERSIONS).get(game_version, 'Dofus 3')


def _humanize_missing_slug(slug, fallback):
    value = re.sub(r'[-_]+', ' ', slug or '').strip()
    value = re.sub(r'\s+', ' ', value)
    if not value:
        return fallback
    return value[:1].upper() + value[1:]


def _resolve_missing_item_name(ankama_type, ankama_id, slug, language, current_game_version):
    fallback = _humanize_missing_slug(slug, '#%s' % ankama_id)
    target_types = _get_ankama_type_aliases(ankama_type)
    for game_version, _label in ACTIVE_GAME_VERSIONS:
        if game_version == current_game_version:
            continue
        try:
            structure = get_structure(game_version)
            for item in structure.get_concatenated_items_lists():
                item_type = (item.ankama_type or '').strip().lower()
                if item.ankama_id == ankama_id and item_type in target_types:
                    name = structure.get_item_name_in_language(item, language)
                    return name or item.or_name or item.name or fallback
        except Exception:
            continue
    return fallback


def _resolve_missing_monster_name(monster_id, slug, language, current_game_version,
                                  current_name=None):
    if current_name and not current_name.startswith('#'):
        return current_name
    fallback = _humanize_missing_slug(slug, '#%s' % monster_id)
    if not has_display_name({language: fallback}):
        fallback = '#%s' % monster_id
    for game_version, _label in ACTIVE_GAME_VERSIONS:
        if game_version == current_game_version:
            continue
        conn = None
        try:
            conn = sqlite3.connect(get_items_db_path(game_version))
            cursor = conn.cursor()
            if not _db_table_exists(cursor, 'monster_names'):
                continue
            name = _get_monster_display_name(cursor, monster_id, language)
            if (name and not name.startswith('#')
                    and has_display_name({language: name})):
                return name
        except Exception:
            continue
        finally:
            if conn is not None:
                conn.close()
    return fallback


def _resolve_missing_resource_name(subtype, ankama_id, slug, language,
                                   current_game_version, current_name=None):
    if current_name:
        return current_name
    fallback = _humanize_missing_slug(slug, '#%s' % ankama_id)
    for game_version, _label in ACTIVE_GAME_VERSIONS:
        if game_version == current_game_version:
            continue
        conn = None
        try:
            conn = sqlite3.connect(get_items_db_path(game_version))
            cursor = conn.cursor()
            if not _db_table_exists(cursor, 'item_recipe_ingredient_names'):
                continue
            cursor.execute(
                """
                SELECT COALESCE(
                    (SELECT name FROM item_recipe_ingredient_names
                     WHERE ingredient_ankama_id = ?
                       AND ingredient_subtype = ?
                       AND language = ? LIMIT 1),
                    (SELECT name FROM item_recipe_ingredient_names
                     WHERE ingredient_ankama_id = ?
                       AND ingredient_subtype = ?
                       AND language = 'en' LIMIT 1))
                """,
                (ankama_id, subtype, language, ankama_id, subtype))
            row = cursor.fetchone()
            if row and row[0]:
                return row[0]
        except Exception:
            continue
        finally:
            if conn is not None:
                conn.close()
    return fallback


def _encyclopedia_missing_response(request, kind, requested_name):
    t = _ui_text()
    game_version = getattr(request, 'game_version', 'dofus3')
    version_label = _version_label(game_version)
    title = t['missing_%s_title' % kind]
    message = t['missing_%s_message' % kind] % {
        'name': requested_name,
        'version': version_label,
    }
    encyclopedia_url = version_reverse(request, 'encyclopedia')
    canonical_url = _absolute_versioned_url('/encyclopedia/', game_version)
    breadcrumb_jsonld = _breadcrumb_jsonld([
        ('Dofus Fashionista', 'https://dofusfashionista.gg/'),
        (t.get('title') or 'Encyclopedia', canonical_url),
        (title, canonical_url),
    ])
    response = set_response(
        request,
        'chardata/encyclopedia_missing.html',
        {
            'request': request,
            'char_id': 0,
            't': t,
            'canonical_url': canonical_url,
            'breadcrumb_jsonld': breadcrumb_jsonld,
            'missing': {
                'title': title,
                'message': message,
                'name': requested_name,
                'version_label': version_label,
                'encyclopedia_url': encyclopedia_url,
                'cta_label': t['missing_back_to_encyclopedia'],
            },
        })
    response.status_code = 404
    return response


# Ingredient icons are stored by ankama id (resource names carry characters
# filenames cannot). dofus3 and beta share an id space and the root directory;
# every other version has its own id space, so it gets its own subdirectory.
_INGREDIENT_ICON_DIRS = {'dofus3': '', 'beta': '', 'touch': 'touch/',
                         'retro': 'retro/', 'dofus2': 'dofus2/'}
_resource_search_index_cache = {}


_ingredient_icon_ids_cache = {}


def _ingredient_icon_ids(game_version):
    """Ids with a local ingredient icon, from one directory listing per process."""
    subdir = _INGREDIENT_ICON_DIRS.get(game_version)
    if subdir is None:
        return frozenset()
    cached = _ingredient_icon_ids_cache.get(subdir)
    if cached is None:
        cached = frozenset(
            int(name.split('-')[0])
            for name in list_static_dir('chardata/resources/%s60x60' % subdir)
            if name.endswith('-60-60.png') and name.split('-')[0].isdigit())
        _ingredient_icon_ids_cache[subdir] = cached
    return cached


RECIPE_LOCAL_TYPES = ('equipment', 'mount', 'pet')


def _recipe_lookups(cursor, recipe_rows, language, has_recipe_names_table):
    """Ingredient names and the items they point at, in two queries."""
    pairs = [(row[1], row[2]) for row in recipe_rows]
    names = {}
    if pairs and has_recipe_names_table:
        holes = ','.join('(?,?)' * 1 for _ in pairs)
        flat = [value for pair in pairs for value in pair]
        rows = cursor.execute(
            """
            SELECT ingredient_ankama_id, ingredient_subtype, language, name
            FROM item_recipe_ingredient_names
            WHERE language IN (?, 'en')
              AND (ingredient_ankama_id, ingredient_subtype) IN (VALUES %s)
            """ % holes, [language] + flat).fetchall()
        english = {}
        for ankama_id, subtype, lang, name in rows:
            target = names if lang == language else english
            target.setdefault((ankama_id, subtype), name)
        for key, name in english.items():
            names.setdefault(key, name)

    local = {}
    wanted = {(row[1], (row[2] or '').lower()) for row in recipe_rows}
    ids = sorted({ankama_id for ankama_id, subtype in wanted})
    if ids:
        holes = ','.join('?' * len(ids))
        types = ','.join('?' * len(RECIPE_LOCAL_TYPES))
        rows = cursor.execute(
            """
            SELECT ankama_id, ankama_type, id, name, dofustouch FROM items
            WHERE ankama_id IN (%s) AND ankama_type IN (%s)
            ORDER BY dofustouch ASC
            """ % (holes, types), ids + list(RECIPE_LOCAL_TYPES)).fetchall()
        for row in rows:
            local.setdefault((row[0], row[1]), row)
    return names, local


def _ingredient_icon_url(game_version, ankama_id):
    # Read once, with .get(): a version with no icon directory of its own is a
    # real case, and the same dictionary was being read twice here, tolerantly
    # above and with a bare index below.
    subdir = _INGREDIENT_ICON_DIRS.get(game_version)
    if subdir is None or ankama_id not in _ingredient_icon_ids(game_version):
        return None
    return static('chardata/resources/%s60x60/%d-60-60.png' % (subdir, ankama_id))


# Monster artwork per version: dofus3/beta share the modern renders, touch has
# its own 2D art from the official Touch CDN, retro the vectors extracted from
# the 1.29 client. Dofus 2 has no artwork source and must not borrow another's.
_MONSTER_IMAGE_DIRS = {'dofus3': '', 'beta': '', 'touch': 'touch/',
                       'retro': 'retro/'}
_monster_image_ids_cache = {}


def _monster_image_ids(game_version):
    """Ids with local monster artwork, from one directory listing per process."""
    subdir = _MONSTER_IMAGE_DIRS.get(game_version)
    if subdir is None:
        return frozenset()
    cached = _monster_image_ids_cache.get(subdir)
    if cached is None:
        cached = frozenset(
            int(name[:-5])
            for name in list_static_dir('chardata/monsters/%s96' % subdir)
            if name.endswith('.webp') and name[:-5].isdigit())
        _monster_image_ids_cache[subdir] = cached
    return cached


def _monster_image_url(game_version, monster_id):
    if monster_id in _monster_image_ids(game_version):
        subdir = _MONSTER_IMAGE_DIRS[game_version]
        return static('chardata/monsters/%s96/%d.webp' % (subdir, monster_id))
    return None


def _get_resource_search_index(game_version):
    cached = _resource_search_index_cache.get(game_version)
    if cached is not None:
        return cached

    conn = None
    try:
        conn = sqlite3.connect(get_items_db_path(game_version))
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'item_recipe_ingredient_names'")
        if cursor.fetchone() is None:
            _resource_search_index_cache[game_version] = []
            return []
        rows = cursor.execute(
            """SELECT ingredient_ankama_id, ingredient_subtype, language, name
               FROM item_recipe_ingredient_names""").fetchall()
    except sqlite3.Error:
        return []
    finally:
        if conn is not None:
            conn.close()

    names_by_key = {}
    for ankama_id, subtype, row_lang, name in rows:
        if not name or not row_lang:
            continue
        names_by_key.setdefault((ankama_id, subtype), {})[row_lang] = name

    entries = []
    for (ankama_id, subtype), names in names_by_key.items():
        normalized_names = [_normalized_text(name) for name in names.values() if name]
        if not normalized_names:
            continue
        entries.append({
            'ankama_id': ankama_id,
            'subtype': subtype,
            'names': names,
            'normalized_names': normalized_names,
            'search_blob': ' '.join(normalized_names),
        })
    _resource_search_index_cache[game_version] = entries
    return entries


_version_item_keys_cache = {}


def _version_item_keys(game_version):
    """(ankama_type, ankama_id) -> name for everything in a version's pool."""
    cached = _version_item_keys_cache.get(game_version)
    if cached is not None:
        return cached
    keys = {}
    conn = None
    try:
        conn = sqlite3.connect(get_items_db_path(game_version))
        for ankama_type, ankama_id, name in conn.execute(
                "SELECT ankama_type, ankama_id, name FROM items "
                "WHERE ankama_id IS NOT NULL AND ankama_type IS NOT NULL"):
            keys[(ankama_type, ankama_id)] = name
    except sqlite3.Error:
        keys = {}
    finally:
        if conn is not None:
            conn.close()
    _version_item_keys_cache[game_version] = keys
    return keys


def _other_versions_with_item(current_version, ankama_type, ankama_id, name):
    """Cross-version links for an item page.

    Only Dofus 3 and the Beta share an id space, so the other version has to
    name the same item as well as carry the id.
    """
    if not ankama_type or not ankama_id:
        return []
    links = []
    # Identity is decided on the english name both pools store, not on the
    # reader's language.
    here = _version_item_keys(current_version).get((ankama_type, ankama_id))
    for game_version, label in ACTIVE_GAME_VERSIONS:
        if game_version == current_version:
            continue
        there = _version_item_keys(game_version).get((ankama_type, ankama_id))
        if is_same_item_name(here, there):
            links.append({
                'label': label,
                'url': get_item_link(ankama_type, ankama_id, name,
                                     game_version=game_version),
            })
    return links


_version_resource_keys_cache = {}


def _version_resource_keys(game_version):
    """(subtype, ankama_id) -> english name for every ingredient with a working
    resource page in a version: those used by at least one of its recipes."""
    cached = _version_resource_keys_cache.get(game_version)
    if cached is not None:
        return cached
    keys = {}
    conn = None
    try:
        conn = sqlite3.connect(get_items_db_path(game_version))
        cursor = conn.cursor()
        if (_db_table_exists(cursor, 'item_recipes')
                and _db_table_exists(cursor, 'item_recipe_ingredient_names')):
            for subtype, ankama_id, name in cursor.execute(
                    """SELECT DISTINCT r.ingredient_subtype, r.ingredient_ankama_id,
                              n.name
                       FROM item_recipes r
                       JOIN item_recipe_ingredient_names n
                         ON n.ingredient_ankama_id = r.ingredient_ankama_id
                        AND n.ingredient_subtype = r.ingredient_subtype
                      WHERE n.language = 'en'"""):
                keys[(subtype, ankama_id)] = name
    except sqlite3.Error:
        keys = {}
    finally:
        if conn is not None:
            conn.close()
    _version_resource_keys_cache[game_version] = keys
    return keys


def _other_versions_with_resource(current_version, subtype, ankama_id, name):
    """Cross-version links for a resource page. Ingredient ids collide across the
    Retro/modern split even harder than item ids, so the name has to match too."""
    links = []
    here = _version_resource_keys(current_version).get((subtype, ankama_id))
    for game_version, label in ACTIVE_GAME_VERSIONS:
        if game_version == current_version:
            continue
        there = _version_resource_keys(game_version).get((subtype, ankama_id))
        if is_same_item_name(here, there):
            links.append({
                'label': label,
                'url': get_resource_link(subtype, ankama_id, name, game_version),
            })
    return links


def _set_item_ankama_ids(structure, item_set):
    """The Ankama ids of a set's items (the cross-version item identity)."""
    ids = set()
    for item_id in getattr(item_set, 'items', None) or ():
        item = structure.get_item_by_id(item_id)
        ankama_id = getattr(item, 'ankama_id', None)
        if ankama_id:
            ids.add(ankama_id)
    return ids


def _other_versions_with_set(current_version, set_id, language):
    """Cross-version links for a set page. A set id is not a shared identity
    across the Retro/modern split (id 11 is the Cawwot Set on dofus3 but the
    unrelated Wabbit Set on Retro, ids 71/72 are the Piwi colours swapped), so
    the rosters have to match too."""
    current_structure = get_structure(current_version)
    current_set = current_structure.sets_dict.get(set_id)
    if current_set is None or not getattr(current_set, 'items', None):
        return []
    current_ids = _set_item_ankama_ids(current_structure, current_set)
    current_en = _normalized_text(
        current_set.localized_names.get('en') or current_set.name or '')
    links = []
    for game_version, label in ACTIVE_GAME_VERSIONS:
        if game_version == current_version:
            continue
        other_structure = get_structure(game_version)
        item_set = other_structure.sets_dict.get(set_id)
        if item_set is None or not getattr(item_set, 'items', None):
            continue
        other_en = _normalized_text(
            item_set.localized_names.get('en') or item_set.name or '')
        other_ids = _set_item_ankama_ids(other_structure, item_set)
        union = current_ids | other_ids
        same_name = bool(current_en) and current_en == other_en
        enough_overlap = bool(union) and len(current_ids & other_ids) >= 0.5 * len(union)
        if not (same_name or enough_overlap):
            continue
        name = (item_set.localized_names.get(language)
                or item_set.localized_names.get('en') or item_set.name)
        if not name:
            continue
        links.append({
            'label': label,
            'url': get_set_link(set_id, name, game_version=game_version),
            # The item count differs by version, even for a same-name match.
            'item_count': len(other_ids),
        })
    return links


def _search_resources(game_version, normalized_search, language, limit=48):
    """Recipe ingredients matching the encyclopedia search box, as links to their
    resource pages. Returns (entries, total): entries are capped at limit, total
    is the real match count."""
    if not normalized_search:
        return [], 0

    hits = []
    for entry in _get_resource_search_index(game_version):
        if normalized_search not in entry['search_blob']:
            continue
        names = entry['names']
        display = names.get(language) or names.get('en') or next(iter(names.values()))
        hits.append({
            'name': display,
            'starts': any(name.startswith(normalized_search)
                          for name in entry['normalized_names']),
            'subtype': entry['subtype'],
            'ankama_id': entry['ankama_id'],
        })
    hits.sort(key=lambda h: (not h['starts'], (h['name'] or '').lower()))
    return [{
        'name': h['name'],
        'url': get_resource_link(h['subtype'], h['ankama_id'], h['name'], game_version),
        'image_url': _ingredient_icon_url(game_version, h['ankama_id']),
    } for h in hits[:limit]], len(hits)


def _search_monsters(game_version, normalized_search, language, limit=48):
    """Monsters matching the encyclopedia search box, as links to their pages.
    Returns (entries, total) like _search_resources."""
    if not normalized_search:
        return [], 0
    hits = []
    for monster in _get_monster_index(game_version, language):
        if normalized_search not in monster['search_blob']:
            continue
        hits.append({
            'name': monster['name'],
            'starts': any(alias.startswith(normalized_search)
                          for alias in monster['name_aliases']),
            'url': monster['url'],
            'id': monster.get('id'),
        })
    hits.sort(key=lambda h: (not h['starts'], (h['name'] or '').lower()))
    entries = hits[:limit]
    for h in entries:
        del h['starts']
        monster_id = h.pop('id')
        h['image_url'] = (_monster_image_url(game_version, monster_id)
                          if monster_id is not None else None)
    return entries, len(hits)


def _get_item_extra_info(representative_item, language, t, game_version='dofus3',
                         variant_items=None):
    default_data = {
        'description': None,
        'pods': None,
        'recipe': [],
        'used_in': [],
        'drops': [],
        'craft_job': None,
    }

    if representative_item is None:
        return default_data

    drop_item_ids = sorted({
        int(item.id) for item in (variant_items or [representative_item])
        if item is not None and getattr(item, 'id', None) is not None
    })

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
            ingredient_names, local_items = _recipe_lookups(
                cursor, recipe_rows, language, has_recipe_names_table)

            for _, ingredient_ankama_id, ingredient_subtype, quantity in recipe_rows:
                ingredient_name = ingredient_names.get(
                    (ingredient_ankama_id, ingredient_subtype))

                resolved_ingredient = ingredient_name is not None
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
                    local_item = local_items.get((ingredient_ankama_id, local_type))
                    if local_item is not None:
                        local_name = local_item[3]
                        local_item_url = get_item_link(local_item[1], local_item[0], local_name, game_version)

                # Resources are not items we carry, but each has its own page.
                resource_url = None
                if local_item_url is None and resolved_ingredient:
                    resource_url = get_resource_link(
                        ingredient_subtype, ingredient_ankama_id, ingredient_name, game_version)

                ingredient_image = _ingredient_icon_url(game_version,
                                                        ingredient_ankama_id)

                default_data['recipe'].append({
                    'name': ingredient_name,
                    'quantity': quantity,
                    'subtype': ingredient_subtype,
                    'ankama_id': ingredient_ankama_id,
                    'local_item_url': local_item_url,
                    'resource_url': resource_url,
                    'image_url': ingredient_image,
                })

            if (getattr(representative_item, 'ankama_id', None)
                    and getattr(representative_item, 'ankama_type', None)):
                ingredient_subtypes = sorted(_get_ankama_type_aliases(
                    representative_item.ankama_type))
                placeholders = ', '.join('?' for _ in ingredient_subtypes)
                cursor.execute(
                    """
                    SELECT DISTINCT i.ankama_id, i.ankama_type, i.name, i.level, it.name,
                           COALESCE(
                               (SELECT item_names.name
                                FROM item_names
                                WHERE item_names.item = i.id
                                  AND item_names.language = ?
                                LIMIT 1),
                               (SELECT item_names.name
                                FROM item_names
                                WHERE item_names.item = i.id
                                  AND item_names.language = 'en'
                                LIMIT 1),
                               i.name
                           ) AS localized_name
                    FROM item_recipes r
                    JOIN items i ON i.id = r.item
                    LEFT JOIN item_types it ON it.id = i.type
                    WHERE r.ingredient_ankama_id = ?
                      AND r.ingredient_subtype IN (%s)
                    ORDER BY i.level DESC, localized_name ASC
                    """ % placeholders,
                    (language, representative_item.ankama_id) + tuple(ingredient_subtypes))
                for (item_ankama_id, item_ankama_type, item_name, item_level,
                     item_type_name, localized_item_name) in cursor.fetchall():
                    default_data['used_in'].append({
                        'name': localized_item_name,
                        'level': item_level,
                        'type_name': _localized_label(item_type_name, language),
                        'url': get_item_link(item_ankama_type, item_ankama_id,
                                             localized_item_name, game_version=game_version),
                        'image_url': static(get_image_url(
                            item_type_name, item_name, game_version)),
                    })

        cursor.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'item_craft_jobs'"
        )
        if cursor.fetchone() is not None:
            # Job 1 ("Base") is Ankama's placeholder for workbench recipes no
            # player profession can learn.
            cursor.execute(
                """
                SELECT cj.level,
                       (SELECT name FROM job_names
                        WHERE job_ankama_id = cj.job_ankama_id AND language = ?),
                       (SELECT name FROM job_names
                        WHERE job_ankama_id = cj.job_ankama_id AND language = 'en')
                FROM item_craft_jobs cj
                WHERE cj.item = ? AND cj.job_ankama_id != 1
                """,
                (language, representative_item.id),
            )
            row = cursor.fetchone()
            if row is not None:
                level, name_loc, name_en = row
                job_name = name_loc or name_en
                if job_name:
                    default_data['craft_job'] = {'name': job_name, 'level': level}

        cursor.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'item_drops'"
        )
        if cursor.fetchone() is not None and drop_item_ids:
            placeholders = ', '.join('?' for _ in drop_item_ids)
            cursor.execute(
                """
                SELECT d.monster_ankama_id, MAX(d.rate) AS rate,
                       (SELECT name FROM monster_names
                        WHERE monster_ankama_id = d.monster_ankama_id AND language = ?),
                       (SELECT name FROM monster_names
                        WHERE monster_ankama_id = d.monster_ankama_id AND language = 'en'),
                       MIN(COALESCE(d.conditions, '')) AS conditions
                FROM item_drops d
                WHERE d.item IN (%s)
                GROUP BY d.monster_ankama_id
                ORDER BY rate DESC
                """ % placeholders,
                (language,) + tuple(drop_item_ids),
            )
            drop_rows = cursor.fetchall()
            level_spans = _monster_level_spans(
                cursor, [row[0] for row in drop_rows])
            drops_ui = _monster_ui_text()
            level_label = drops_ui['level_label']
            for monster_id, rate, name_loc, name_en, conditions in drop_rows:
                monster_name = name_loc or name_en or ('#%s' % monster_id)
                span = level_spans.get(monster_id)
                default_data['drops'].append({
                    'name': monster_name,
                    'rate': rate,
                    'url': get_monster_link(monster_id, monster_name, game_version),
                    'level': _drop_level_text(span, level_label),
                    'level_min': span[0] if span else None,
                    # MIN over '' and criterion strings: empty means some path drops it freely.
                    'has_conditions': bool(conditions),
                    'conditions_text': _drop_conditions_text(conditions, drops_ui),
                })
            default_data['drops'].sort(
                key=lambda d: (-d['rate'],
                               d['level_min'] if d['level_min'] is not None else 10 ** 9))

    except Exception:
        return default_data
    finally:
        if conn is not None:
            conn.close()

    return default_data


# More ordering rows than a reader will ever open by hand.
MAX_ORDER_ROWS = 12


def encyclopedia(request):
    structure = get_structure()
    language = get_supported_language()
    game_version = getattr(request, 'game_version', 'dofus3')
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
                # The repeated-parameter form of this feature is capped by
                # DATA_UPLOAD_MAX_NUMBER_FIELDS; this one was not, and the page
                # renders a full stat select per row, so 880 empty objects in
                # an 8 KB URL asked the server for 9 MB of HTML.
                for row in parsed_rows[:MAX_ORDER_ROWS]:
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

    normalized_search = _normalized_text(search_text) if search_text else ''
    resource_results = []
    monster_results = []
    resource_total = 0
    monster_total = 0
    if normalized_search:
        resource_results, resource_total = _search_resources(
            game_version, normalized_search, language)
        monster_results, monster_total = _search_monsters(
            game_version, normalized_search, language)
    filtered_items = []
    for entry in _get_light_index(structure, language):
        if selected_type and entry['raw_type_name'] != selected_type:
            continue
        if min_level is not None and entry['level'] < min_level:
            continue
        if max_level is not None and entry['level'] > max_level:
            continue
        if normalized_search and normalized_search not in entry['search_blob']:
            continue

        stats_map = entry['stats_map']
        stat_filter_failed = False
        for stat_key, stat_min in selected_stat_filters:
            if stats_map.get(stat_key, 0) < stat_min:
                stat_filter_failed = True
                break
        if stat_filter_failed:
            continue
        filtered_items.append(entry)

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

    # 39 fills a 3-column grid exactly.
    paginator = Paginator(filtered_items, 39)
    page = request.GET.get('page', 1)
    try:
        page_obj = paginator.page(page)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    # Materialize the full cards for the current page only.
    cards = []
    for entry in page_obj.object_list:
        item = entry['item']
        display_name = entry['name']
        type_name = entry['raw_type_name']
        item_set = None
        if getattr(item, 'set', None) is not None:
            item_set = (structure.sets_dict.get(item.set)
                        or structure.dt_sets_dict.get(item.set))
        cards.append({
            'id': item.id,
            'ankama_id': item.ankama_id,
            'ankama_type': item.ankama_type,
            'name': display_name,
            'or_name': item.or_name,
            'level': item.level,
            'type_name': _localized_label(type_name, language),
            'image_url': static(get_image_url(type_name, item.name, game_version)),
            'detail_url': get_item_link(item.ankama_type, item.ankama_id,
                                        display_name, game_version=game_version),
            'set_id': item_set.id if item_set else None,
            'set_name': (item_set.localized_names.get(language)
                         or item_set.localized_names.get('en') or item_set.name) if item_set else None,
            'set_url': get_set_link(
                item_set.id,
                (item_set.localized_names.get(language)
                 or item_set.localized_names.get('en') or item_set.name),
                game_version=game_version) if item_set else None,
            'stat_lines': _get_stat_lines(structure, item, language),
            'stats_map': entry['stats_map'],
        })
    page_obj.object_list = cards

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
            'mt': _monster_ui_text(),
            'canonical_url': _paginated_canonical(
                request, '/encyclopedia/', game_version, page_obj),
            'items_page': page_obj,
            'items_count': len(filtered_items),
            'resource_results': resource_results,
            'monster_results': monster_results,
            'resource_total': resource_total,
            'monster_total': monster_total,
            'result_family_count': sum(
                1 for hits in (filtered_items, resource_results, monster_results)
                if hits),
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


def encyclopedia_set(request, set_id, slug=None):
    structure = get_structure()
    language = get_supported_language()
    t = _ui_text()

    set_id = safe_int(set_id, None)
    # sets_dict holds the bonus-bearing set.
    item_set = None
    if set_id is not None:
        item_set = structure.sets_dict.get(set_id) or structure.dt_sets_dict.get(set_id)
    if item_set is None:
        response = encyclopedia(request)
        response.status_code = 404
        return response

    game_version = getattr(request, 'game_version', 'dofus3')

    # The slug names the language, exactly as it does for items.
    url_language = language_from_slug(item_set.localized_names, slug,
                                      _normalized_slug)
    if url_language is None:
        url_language = language
    elif url_language != language:
        translation.activate(url_language)
        language = url_language
        t = _ui_text()

    set_name = (item_set.localized_names.get(language)
                or item_set.localized_names.get('en') or item_set.name)
    canonical_path = get_set_link(set_id, set_name, game_version=game_version)
    canonical_url = 'https://dofusfashionista.gg' + (canonical_path or '/encyclopedia/sets/')
    alternate_urls = build_alternate_urls(
        lambda name: get_set_link(set_id, name, game_version=game_version),
        item_set.localized_names, 'https://dofusfashionista.gg')
    redirect_to = redirect_target_for_user(request, url_language, alternate_urls)
    if redirect_to:
        return mark_varies_on_cookie(redirect(redirect_to))
    encyclopedia_url = _absolute_versioned_url('/encyclopedia/', game_version)
    breadcrumb_jsonld = _breadcrumb_jsonld([
        ('Dofus Fashionista', 'https://dofusfashionista.gg/'),
        (t.get('title') or 'Encyclopedia', encyclopedia_url),
        (set_name, canonical_url),
    ])

    return set_response(
        request,
        'chardata/encyclopedia_set.html',
        {
            'request': request,
            'char_id': 0,
            't': t,
            'canonical_url': canonical_url,
            'alternate_urls': alternate_urls,
            'breadcrumb_jsonld': breadcrumb_jsonld,
            'set_name': set_name,
            'set_items': _get_set_items(structure, item_set, language, game_version),
            'set_bonuses': _get_set_bonuses(structure, item_set, language),
            'other_versions': _other_versions_with_set(game_version, set_id, language),
        },
    )


SET_SORTS = ('name', 'level')


def encyclopedia_sets(request):
    structure = get_structure()
    language = get_supported_language()
    t = _ui_text()

    search_text = (request.GET.get('q') or '').strip()
    needle = _normalized_text(search_text) if search_text else ''
    sort_key = request.GET.get('sort', 'name')
    if sort_key not in SET_SORTS:
        sort_key = 'name'

    sets = []
    for set_id, item_set in structure.sets_dict.items():
        if not getattr(item_set, 'items', None):
            continue
        name = (item_set.localized_names.get(language)
                or item_set.localized_names.get('en') or item_set.name)
        if not name:
            continue
        searchable_parts = [name, item_set.name]
        item_names = []
        levels = []
        seen_item_keys = set()
        for item_id in item_set.items:
            item = structure.get_item_by_id(item_id)
            if item is None:
                continue
            item_key = (item.ankama_type, item.ankama_id or item.id)
            if item_key in seen_item_keys:
                continue
            seen_item_keys.add(item_key)
            if item.level is not None:
                levels.append(item.level)
            item_name = structure.get_item_name_in_language(item, language)
            if item_name:
                item_names.append(item_name)
            searchable_parts.extend(
                structure.get_item_name_in_language(item, search_language)
                for search_language in SUPPORTED_LANGUAGES
            )
            searchable_parts.append(item.or_name)
        if needle and needle not in _normalized_text(
                ' '.join(part or '' for part in searchable_parts)):
            continue
        max_pieces = 0
        if getattr(item_set, 'bonus', None):
            max_pieces = max((num for num, _, _ in item_set.bonus), default=0)
        sets.append({
            'name': name,
            'max_pieces': max_pieces,
            'level_min': min(levels) if levels else None,
            'level_max': max(levels) if levels else None,
            'sample_items': item_names[:4],
            'more_items_count': max(len(item_names) - 4, 0),
            'url': get_set_link(set_id, name,
                                game_version=getattr(request, 'game_version', 'dofus3')),
        })

    def set_sort_key(entry):
        name_key = ((entry['name'] or '').lower(),)
        if sort_key == 'level':
            # A set's top item level is its tier; sets with no level data sink
            # to the end.
            return (entry['level_max'] is None, entry['level_max'] or 0,
                    entry['level_min'] or 0) + name_key
        return name_key

    sets.sort(key=set_sort_key)

    has_levels = any(entry['level_max'] is not None for entry in sets)
    sort_options = [
        {
            'value': value,
            'label': t['sort_%s' % value],
            'selected': value == sort_key,
        }
        for value in SET_SORTS
        if value != 'level' or has_levels
    ]

    paginator = Paginator(sets, 60)
    page = request.GET.get('page', 1)
    try:
        sets_page = paginator.page(page)
    except PageNotAnInteger:
        sets_page = paginator.page(1)
    except EmptyPage:
        sets_page = paginator.page(paginator.num_pages)

    query_without_page = request.GET.copy()
    if 'page' in query_without_page:
        del query_without_page['page']
    page_query_prefix = query_without_page.urlencode()
    if page_query_prefix:
        page_query_prefix = '%s&' % page_query_prefix

    sets_canonical = _paginated_canonical(
        request, '/encyclopedia/sets/',
        getattr(request, 'game_version', 'dofus3'), sets_page)

    return set_response(
        request,
        'chardata/encyclopedia_sets.html',
        {
            'request': request,
            'char_id': 0,
            't': t,
            'canonical_url': sets_canonical,
            'breadcrumb_jsonld': _breadcrumb_jsonld([
                ('Dofus Fashionista', 'https://dofusfashionista.gg/'),
                (t.get('title') or 'Encyclopedia',
                 _absolute_versioned_url(
                     '/encyclopedia/',
                     getattr(request, 'game_version', 'dofus3'))),
                (_('Sets'), sets_canonical),
            ]),
            'sets_page': sets_page,
            'search_text': search_text,
            'sets_count': len(sets),
            'sort_key': sort_key,
            'sort_options': sort_options,
            'page_query_prefix': page_query_prefix,
        },
    )


def encyclopedia_item(request, ankama_type, ankama_id, slug=None):
    structure = get_structure()
    language = get_supported_language()
    t = _ui_text()
    game_version = getattr(request, 'game_version', 'dofus3')

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
        requested_name = _resolve_missing_item_name(
            ankama_type, target_ankama_id, slug, language, game_version)
        return _encyclopedia_missing_response(request, 'item', requested_name)

    # The slug already names the language: /44-epee-de-boisaille/ is the French
    # page and nothing else. Taking the language from it, rather than from
    # Accept-Language, is what lets a crawler -- which sends no such header --
    # see anything but English. Before this, every localised URL served English
    # to Googlebot and declared a canonical pointing at the English slug, so
    # each one announced itself as a duplicate.
    item_names_by_language = {
        lang: structure.get_item_name_in_language(matched_item, lang)
        for lang in SUPPORTED_LANGUAGES
    }
    url_language = language_from_slug(item_names_by_language, slug,
                                      _normalized_slug)
    if url_language is None:
        # An unrecognised slug is not a reason to change behaviour: keep
        # whatever the request negotiated, exactly as before.
        url_language = language
    elif url_language != language:
        translation.activate(url_language)
        language = url_language
        t = _ui_text()

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
    # sets_dict first: get_set_by_id() checks dt_sets_dict first, and id 1 exists
    # in both (touch "Jellix Set" against dofus3 "Gobball Set").
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
            'name': _localized_stat(stat.name, language, structure.game_version),
            'value': stat_value,
            'amount_text': _stat_amount_text(representative_item, stat_id,
                                             int(round(stat_value))),
            'icon_url': _get_stat_icon_url(stat.key),
        })

    # Retro and Touch pets carry no bonus in the data: they are fed up to a cap,
    # and the page would otherwise show a pet with an empty characteristics list.
    variant_id_base = PET_VARIANT_ID_BASE_BY_VERSION.get(
        getattr(request, 'game_version', None))
    pet_feedable_bonuses = (
        _get_pet_feedable_bonuses(structure, grouped_variants, language,
                                  variant_id_base)
        if variant_id_base else [])
    set_bonuses = _get_set_bonuses(structure, item_set, language)

    condition_groups = _format_condition_groups(structure, grouped_variants, language)

    extras = representative_item.localized_extras.get(language)
    if extras is None:
        extras = representative_item.localized_extras.get('en', [])
    # A special spell prints as its name on one line and its rules under it.
    extras, folded = fold_spell_blocks(extras)
    with translation.override(language):
        extras = [label for label, _icon
                  in flag_lines(getattr(representative_item, 'flags', []))] + extras
    # An extra line names a spell without saying what it does.
    spell_tooltips = dict(
        getattr(representative_item, 'spell_tooltips', {}).get(language) or {},
        **folded)
    extras = [{'text': line, 'spell_tip': spell_tip_for(line, spell_tooltips)}
              for line in extras]

    extra_info = _get_item_extra_info(
        representative_item, language, t,
        game_version=getattr(request, 'game_version', 'dofus3'),
        variant_items=grouped_variants)
    weapon_lines = _get_weapon_detail_lines(structure, grouped_variants, language)

    # A version whose data matches the live one shows the same page. Saying
    # so is the difference between one page and two identical ones; the
    # comparison is on the data, so the day beta diverges its pages become
    # canonical in their own right with nothing to change.
    from chardata.version_content import repeats_the_live_version
    canonical_version = game_version
    if repeats_the_live_version(game_version,
                                representative_item.ankama_type,
                                representative_item.ankama_id):
        canonical_version = 'dofus3'

    canonical_path = get_item_link(representative_item.ankama_type,
                                   representative_item.ankama_id, localized_name,
                                   game_version=canonical_version)
    canonical_url = 'https://dofusfashionista.gg' + (canonical_path or '/encyclopedia/')

    # One absolute URL per language, for the hreflang block. Each is built with
    # that language active because get_item_link derives a localised category
    # segment from get_language().
    alternate_urls = build_alternate_urls(
        lambda name: get_item_link(representative_item.ankama_type,
                                   representative_item.ankama_id, name,
                                   game_version=canonical_version),
        {lang: structure.get_item_name_in_language(representative_item, lang)
         for lang in SUPPORTED_LANGUAGES},
        'https://dofusfashionista.gg')

    # A signed-in visitor who chose a language is sent to their own version, so
    # a Spanish link shared with a French account still lands on French.
    # Anonymous visitors -- every crawler among them -- are never redirected,
    # which is what keeps one URL bound to one language for indexing.
    redirect_to = redirect_target_for_user(request, url_language, alternate_urls)
    if redirect_to:
        return mark_varies_on_cookie(redirect(redirect_to))

    encyclopedia_url = _absolute_versioned_url('/encyclopedia/', game_version)
    breadcrumb_jsonld = _breadcrumb_jsonld([
        ('Dofus Fashionista', 'https://dofusfashionista.gg/'),
        (t.get('title') or 'Encyclopedia', encyclopedia_url),
        (localized_name, canonical_url),
    ])

    return set_response(
        request,
        'chardata/encyclopedia_item.html',
        {
            'request': request,
            'char_id': 0,
            't': t,
            'drop_conditions_label': _monster_ui_text()['drop_conditions_label'],
            'canonical_url': canonical_url,
            'alternate_urls': alternate_urls,
            'breadcrumb_jsonld': breadcrumb_jsonld,
            'item': {
                'name': localized_name,
                'or_name': representative_item.or_name,
                'level': representative_item.level,
                'type_name': localized_type_name,
                'ankama_id': representative_item.ankama_id,
                'ankama_type': representative_item.ankama_type,
                'image_url': static(get_image_url(
                    type_name, representative_item.name, game_version)),
            },
            'item_set_name': item_set.localized_names.get(language) if item_set else None,
            'item_set_id': item_set.id if item_set else None,
            'item_set_url': get_set_link(
                item_set.id,
                item_set.localized_names.get(language)
                or item_set.localized_names.get('en') or item_set.name,
                game_version=game_version) if item_set else None,
            'set_bonuses': set_bonuses,
            'stats': stat_lines,
            'pet_feedable_bonuses': pet_feedable_bonuses,
            'condition_groups': condition_groups,
            'extras': extras,
            'weapon_lines': weapon_lines,
            'description': extra_info['description'],
            'pods': extra_info['pods'],
            'recipe': extra_info['recipe'],
            'used_in': extra_info['used_in'],
            'drops': extra_info['drops'],
            'craft_job': extra_info['craft_job'],
            'other_versions': _other_versions_with_item(
                game_version, representative_item.ankama_type,
                representative_item.ankama_id, localized_name),
            'similar_items': _get_similar_items(
                structure, language, game_version, representative_item),
            'similar_items_label': t['similar_items_label'],
            'builds_using': _get_builds_using(representative_item.ankama_id,
                                              game_version),
            'builds_using_label': t['builds_using_label'],
            'item_popularity': _get_popularity(representative_item.ankama_id,
                                               game_version),
        },
    )


MONSTER_UI = {
    'en': {
        'monsters_label': 'Monsters',
        'monster_kind_label': 'Monster',
        'stats_section_label': 'Stats per grade',
        'weakest_hint': 'Green marks the weakest element (most damage).',
        'weakness_label': 'Weakness',
        'weakness_filter_all': 'Any weakness',
        'weakness_filter_link_title': 'Show monsters with this weakness',
        'weakness_guide_prompt': 'Not sure which element to hit?',
        'weakness_guide_link': 'Read the monster weaknesses guide',
        'drop_conditions_label': 'under conditions',
        'drop_conditions_player_level': 'player level',
        'grade_label': 'Grade',
        'level_label': 'Level',
        'hp_label': 'HP',
        'ap_label': 'AP',
        'mp_label': 'MP',
        'earth_label': 'Earth',
        'fire_label': 'Fire',
        'water_label': 'Water',
        'air_label': 'Air',
        'neutral_label': 'Neutral',
        'monster_search_placeholder': 'Monster or drop name',
        'drop_preview_label': 'Drops',
        'dropped_resources_label': 'Dropped resources',
        'dropped_items_label': 'Dropped items',
        'no_monsters': 'No monsters match your search.',
        'drop_filter_label': 'Drop type',
        'drop_filter_all': 'All drops',
        'drop_filter_resources': 'With resources',
        'drop_filter_items': 'With items',
        'drop_filter_both': 'Resources and items',
        'sort_label': 'Sort by',
        'sort_name': 'Name',
        'sort_level': 'Level',
        'subareas_label': 'Found in',
        'spells_label': 'Spells',
        'range_label': 'range',
        'sort_total_drops': 'Most drops',
        'sort_resource_drops': 'Most resources',
        'sort_item_drops': 'Most items',
        'other_versions_label': 'Other versions',
    },
    'fr': {
        'monsters_label': 'Monstres',
        'monster_kind_label': 'Monstre',
        'stats_section_label': 'Caractéristiques par grade',
        'weakest_hint': "Le vert indique l'élément le plus faible (dégâts maximum).",
        'weakness_label': 'Faiblesse',
        'weakness_filter_all': 'Toutes faiblesses',
        'weakness_filter_link_title': 'Voir les monstres avec cette faiblesse',
        'weakness_guide_prompt': "Pas sûr de l'élément à taper ?",
        'weakness_guide_link': 'Lis le guide des faiblesses des monstres',
        'drop_conditions_label': 'sous conditions',
        'drop_conditions_player_level': 'niveau joueur',
        'grade_label': 'Grade',
        'level_label': 'Niveau',
        'hp_label': 'PV',
        'ap_label': 'PA',
        'mp_label': 'PM',
        'earth_label': 'Terre',
        'fire_label': 'Feu',
        'water_label': 'Eau',
        'air_label': 'Air',
        'neutral_label': 'Neutre',
        'monster_search_placeholder': 'Nom du monstre ou du drop',
        'drop_preview_label': 'Drops',
        'dropped_resources_label': 'Ressources droppées',
        'dropped_items_label': 'Objets droppés',
        'no_monsters': 'Aucun monstre ne correspond à votre recherche.',
        'drop_filter_label': 'Type de drop',
        'drop_filter_all': 'Tous les drops',
        'drop_filter_resources': 'Avec ressources',
        'drop_filter_items': 'Avec objets',
        'drop_filter_both': 'Ressources et objets',
        'sort_label': 'Trier par',
        'sort_name': 'Nom',
        'sort_level': 'Niveau',
        'subareas_label': 'Où le trouver',
        'spells_label': 'Sorts',
        'range_label': 'portée',
        'sort_total_drops': 'Plus de drops',
        'sort_resource_drops': 'Plus de ressources',
        'sort_item_drops': 'Plus d\'objets',
        'other_versions_label': 'Autres versions',
    },
    'es': {
        'monsters_label': 'Monstruos',
        'monster_kind_label': 'Monstruo',
        'stats_section_label': 'Características por grado',
        'weakest_hint': 'El verde marca el elemento más débil (más daño).',
        'weakness_label': 'Debilidad',
        'weakness_filter_all': 'Cualquier debilidad',
        'weakness_filter_link_title': 'Ver los monstruos con esta debilidad',
        'weakness_guide_prompt': '¿No sabes en qué elemento pegar?',
        'weakness_guide_link': 'Lee la guía de debilidades de los monstruos',
        'drop_conditions_label': 'con condiciones',
        'drop_conditions_player_level': 'nivel del jugador',
        'grade_label': 'Grado',
        'level_label': 'Nivel',
        'hp_label': 'PdV',
        'ap_label': 'PA',
        'mp_label': 'PM',
        'earth_label': 'Tierra',
        'fire_label': 'Fuego',
        'water_label': 'Agua',
        'air_label': 'Aire',
        'neutral_label': 'Neutral',
        'monster_search_placeholder': 'Nombre del monstruo o drop',
        'drop_preview_label': 'Botín',
        'dropped_resources_label': 'Recursos soltados',
        'dropped_items_label': 'Objetos soltados',
        'no_monsters': 'Ningún monstruo coincide con tu búsqueda.',
        'drop_filter_label': 'Tipo de botín',
        'drop_filter_all': 'Todos los drops',
        'drop_filter_resources': 'Con recursos',
        'drop_filter_items': 'Con objetos',
        'drop_filter_both': 'Recursos y objetos',
        'sort_label': 'Ordenar por',
        'sort_name': 'Nombre',
        'sort_level': 'Nivel',
        'subareas_label': 'Dónde encontrarlo',
        'spells_label': 'Hechizos',
        'range_label': 'alcance',
        'sort_total_drops': 'Más drops',
        'sort_resource_drops': 'Más recursos',
        'sort_item_drops': 'Más objetos',
        'other_versions_label': 'Otras versiones',
    },
    'pt': {
        'monsters_label': 'Monstros',
        'monster_kind_label': 'Monstro',
        'stats_section_label': 'Características por grau',
        'weakest_hint': 'O verde marca o elemento mais fraco (mais dano).',
        'weakness_label': 'Fraqueza',
        'weakness_filter_all': 'Qualquer fraqueza',
        'weakness_filter_link_title': 'Ver os monstros com esta fraqueza',
        'weakness_guide_prompt': 'Não sabe em qual elemento bater?',
        'weakness_guide_link': 'Leia o guia de fraquezas dos monstros',
        'drop_conditions_label': 'com condições',
        'drop_conditions_player_level': 'nível do jogador',
        'grade_label': 'Grau',
        'level_label': 'Nível',
        'hp_label': 'PV',
        'ap_label': 'PA',
        'mp_label': 'PM',
        'earth_label': 'Terra',
        'fire_label': 'Fogo',
        'water_label': 'Água',
        'air_label': 'Ar',
        'neutral_label': 'Neutro',
        'monster_search_placeholder': 'Nome do monstro ou drop',
        'drop_preview_label': 'Drops',
        'dropped_resources_label': 'Recursos dropados',
        'dropped_items_label': 'Itens dropados',
        'no_monsters': 'Nenhum monstro corresponde à sua pesquisa.',
        'drop_filter_label': 'Tipo de drop',
        'drop_filter_all': 'Todos os drops',
        'drop_filter_resources': 'Com recursos',
        'drop_filter_items': 'Com itens',
        'drop_filter_both': 'Recursos e itens',
        'sort_label': 'Ordenar por',
        'sort_name': 'Nome',
        'sort_level': 'Nível',
        'subareas_label': 'Onde encontrá-lo',
        'spells_label': 'Feitiços',
        'range_label': 'alcance',
        'sort_total_drops': 'Mais drops',
        'sort_resource_drops': 'Mais recursos',
        'sort_item_drops': 'Mais itens',
        'other_versions_label': 'Outras versões',
    },
    'de': {
        'monsters_label': 'Monster',
        'monster_kind_label': 'Monster',
        'stats_section_label': 'Werte pro Stufe',
        'weakest_hint': 'Grün markiert das schwächste Element (höchster Schaden).',
        'weakness_label': 'Schwäche',
        'weakness_filter_all': 'Beliebige Schwäche',
        'weakness_filter_link_title': 'Monster mit dieser Schwäche anzeigen',
        'weakness_guide_prompt': 'Nicht sicher, welches Element du treffen sollst?',
        'weakness_guide_link': 'Lies den Guide zu den Monster-Schwächen',
        'drop_conditions_label': 'mit Bedingungen',
        'drop_conditions_player_level': 'Spielerstufe',
        'grade_label': 'Grad',
        'level_label': 'Stufe',
        'hp_label': 'LP',
        'ap_label': 'AP',
        'mp_label': 'BP',
        'earth_label': 'Erde',
        'fire_label': 'Feuer',
        'water_label': 'Wasser',
        'air_label': 'Luft',
        'neutral_label': 'Neutral',
        'monster_search_placeholder': 'Monster- oder Dropname',
        'drop_preview_label': 'Drops',
        'dropped_resources_label': 'Gedroppte Ressourcen',
        'dropped_items_label': 'Gedroppte Gegenstände',
        'no_monsters': 'Keine Monster entsprechen deiner Suche.',
        'drop_filter_label': 'Drop-Typ',
        'drop_filter_all': 'Alle Drops',
        'drop_filter_resources': 'Mit Ressourcen',
        'drop_filter_items': 'Mit Items',
        'drop_filter_both': 'Ressourcen und Items',
        'sort_label': 'Sortieren nach',
        'sort_name': 'Name',
        'sort_level': 'Stufe',
        'subareas_label': 'Fundorte',
        'spells_label': 'Zauber',
        'range_label': 'Reichweite',
        'sort_total_drops': 'Meiste Drops',
        'sort_resource_drops': 'Meiste Ressourcen',
        'sort_item_drops': 'Meiste Items',
        'other_versions_label': 'Andere Versionen',
    },
}


MONSTER_DROP_FILTERS = ('all', 'resources', 'items', 'both')
MONSTER_SORTS = ('name', 'level', 'total_drops', 'resource_drops', 'item_drops')
_monster_index_cache = {}
_monster_core_cache = {}


def _monster_ui_text():
    language = get_supported_language()
    return MONSTER_UI.get(language, MONSTER_UI['en'])


def _db_table_exists(cursor, table_name):
    cursor.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table_name,))
    return cursor.fetchone() is not None


def _monster_level_spans(cursor, monster_ids):
    """{monster_ankama_id: (min_level, max_level)} across the monster's grades.
    Empty when monster_grades is absent (older version DBs)."""
    spans = {}
    monster_ids = [mid for mid in set(monster_ids) if mid is not None]
    if not monster_ids or not _db_table_exists(cursor, 'monster_grades'):
        return spans
    placeholders = ', '.join('?' for _ in monster_ids)
    cursor.execute(
        "SELECT monster_ankama_id, MIN(level), MAX(level) FROM monster_grades "
        "WHERE level IS NOT NULL AND monster_ankama_id IN (%s) "
        "GROUP BY monster_ankama_id" % placeholders,
        tuple(monster_ids))
    for monster_id, level_min, level_max in cursor.fetchall():
        spans[monster_id] = (level_min, level_max)
    return spans


def _drop_level_text(level_span, level_label):
    """"Level 8" or "Level 8-14" from a (min, max) span, or None if unknown."""
    if not level_span:
        return None
    level_min, level_max = level_span
    if level_min is None:
        return None
    if level_max is None or level_max == level_min:
        return '%s %s' % (level_label, level_min)
    return '%s %s-%s' % (level_label, level_min, level_max)


def _drop_conditions_text(conditions, ui):
    """"player level > 19, < 61" when the criterion is only PL bounds,
    None otherwise (the caller falls back to the generic label)."""
    if not conditions or not re.fullmatch(r'PL[<>]\d+(&PL[<>]\d+)*', conditions):
        return None
    parts = ['%s %s' % (m.group(1), m.group(2))
             for m in re.finditer(r'PL([<>])(\d+)', conditions)]
    return '%s %s' % (ui['drop_conditions_player_level'], ', '.join(parts))


def _get_monster_names_by_language(cursor, monster_id):
    """Every stored name of a monster, keyed by language.

    Needed to tell which language a URL slug names: two localised slugs are
    the same monster in two languages, and each must serve its own.
    See chardata.url_language.
    """
    cursor.execute(
        "SELECT language, name FROM monster_names WHERE monster_ankama_id = ?",
        (monster_id,))
    return {row[0]: row[1] for row in cursor.fetchall() if row[1]}


def _get_resource_names_by_language(cursor, ankama_id, subtype):
    """Every stored name of a crafting ingredient, keyed by language."""
    cursor.execute(
        "SELECT language, name FROM item_recipe_ingredient_names "
        "WHERE ingredient_ankama_id = ? AND ingredient_subtype = ?",
        (ankama_id, subtype))
    return {row[0]: row[1] for row in cursor.fetchall() if row[1]}


def _get_monster_display_name(cursor, monster_id, language):
    cursor.execute(
        "SELECT name FROM monster_names WHERE monster_ankama_id = ? AND language = ? LIMIT 1",
        (monster_id, language))
    row = cursor.fetchone()
    if row is None and language != 'en':
        cursor.execute(
            "SELECT name FROM monster_names WHERE monster_ankama_id = ? AND language = 'en' LIMIT 1",
            (monster_id,))
        row = cursor.fetchone()
    return row[0] if row is not None else '#%s' % monster_id


def _append_monster_drop(drop_groups, monster_id, name, rate, kind, ankama_id,
                         subtype=None, ankama_type=None):
    if not name:
        return
    key = (name, kind, ankama_id, subtype, ankama_type)
    current = drop_groups[monster_id].get(key)
    if current is None or (rate or 0) > (current['rate'] or 0):
        drop_groups[monster_id][key] = {
            'name': name,
            'rate': rate,
            'kind': kind,
            'ankama_id': ankama_id,
            'subtype': subtype,
            'ankama_type': ankama_type,
        }


def _format_monster_drop_previews(drop_groups, game_version, limit=4):
    previews = {}
    for monster_id, grouped_drops in drop_groups.items():
        drops = []
        sorted_drops = sorted(
            grouped_drops.values(),
            key=lambda drop: (-(drop['rate'] or 0), (drop['name'] or '').lower()))
        for drop in sorted_drops[:limit]:
            kind = drop['kind']
            name = drop['name']
            ankama_id = drop['ankama_id']
            if kind == 'resource':
                url = get_resource_link(drop['subtype'], ankama_id, name, game_version)
            else:
                url = get_item_link(drop['ankama_type'], ankama_id, name,
                                    game_version=game_version)
            drops.append({
                'name': name,
                'rate': drop['rate'],
                'url': url or '',
            })
        previews[monster_id] = drops
    return previews


def _get_monster_drop_previews(cursor, monster_ids, language, game_version, limit=4):
    monster_ids = list(dict.fromkeys(monster_ids))
    if not monster_ids:
        return {}

    placeholders = ','.join('?' for _ in monster_ids)
    drop_groups = defaultdict(dict)

    if _db_table_exists(cursor, 'resource_drops'):
        if _db_table_exists(cursor, 'item_recipe_ingredient_names'):
            resource_name_sql = """
                COALESCE(
                    (SELECT n.name FROM item_recipe_ingredient_names n
                     WHERE n.ingredient_ankama_id = rd.resource_ankama_id
                       AND n.ingredient_subtype = 'resources'
                       AND n.language = ? LIMIT 1),
                    (SELECT n.name FROM item_recipe_ingredient_names n
                     WHERE n.ingredient_ankama_id = rd.resource_ankama_id
                       AND n.ingredient_subtype = 'resources'
                       AND n.language = 'en' LIMIT 1),
                    '#' || rd.resource_ankama_id)
            """
            resource_params = [language] + monster_ids
        else:
            resource_name_sql = "'#' || rd.resource_ankama_id"
            resource_params = monster_ids
        cursor.execute(
            """
            SELECT rd.monster_ankama_id, %s AS name, rd.rate,
                   rd.resource_ankama_id
            FROM resource_drops rd
            WHERE rd.monster_ankama_id IN (%s)
            """ % (resource_name_sql, placeholders),
            resource_params)
        for monster_id, name, rate, resource_id in cursor.fetchall():
            _append_monster_drop(
                drop_groups, monster_id, name, rate, 'resource',
                resource_id, subtype='resources')

    if _db_table_exists(cursor, 'item_drops') and _db_table_exists(cursor, 'items'):
        if _db_table_exists(cursor, 'item_names'):
            item_name_sql = """
                COALESCE(
                    (SELECT item_names.name FROM item_names
                     WHERE item_names.item = i.id
                       AND item_names.language = ? LIMIT 1),
                    (SELECT item_names.name FROM item_names
                     WHERE item_names.item = i.id
                       AND item_names.language = 'en' LIMIT 1),
                    i.name)
            """
            item_params = [language] + monster_ids
        else:
            item_name_sql = "i.name"
            item_params = monster_ids
        cursor.execute(
            """
            SELECT d.monster_ankama_id, %s AS name, d.rate,
                   i.ankama_id, i.ankama_type
            FROM item_drops d
            JOIN items i ON i.id = d.item
            WHERE d.monster_ankama_id IN (%s)
            """ % (item_name_sql, placeholders),
            item_params)
        for monster_id, name, rate, ankama_id, ankama_type in cursor.fetchall():
            _append_monster_drop(
                drop_groups, monster_id, name, rate, 'item',
                ankama_id, ankama_type=ankama_type)

    return _format_monster_drop_previews(drop_groups, game_version, limit=limit)


def _build_monster_core(game_version):
    """Language-neutral part of the monster index (drop counts, all localized
    names, normalized search blob), built once per version."""
    monsters = []
    conn = None
    try:
        conn = sqlite3.connect(get_items_db_path(game_version))
        cursor = conn.cursor()
        if not _db_table_exists(cursor, 'monster_names'):
            return monsters

        norm_cache = {}

        def norm(value):
            normalized = norm_cache.get(value)
            if normalized is None:
                normalized = _normalized_text(value)
                norm_cache[value] = normalized
            return normalized

        monster_names = defaultdict(dict)
        monster_aliases = defaultdict(set)
        cursor.execute('SELECT monster_ankama_id, language, name FROM monster_names')
        for monster_id, name_language, name in cursor.fetchall():
            monster_names[monster_id][name_language] = name
            if name:
                monster_aliases[monster_id].add(norm(name))

        resource_counts = Counter()
        resource_aliases = defaultdict(set)
        if _db_table_exists(cursor, 'resource_drops'):
            resource_names = defaultdict(set)
            if _db_table_exists(cursor, 'item_recipe_ingredient_names'):
                cursor.execute(
                    """
                    SELECT ingredient_ankama_id, name
                    FROM item_recipe_ingredient_names
                    WHERE ingredient_subtype = 'resources'
                    """)
                for resource_id, name in cursor.fetchall():
                    if name:
                        resource_names[resource_id].add(norm(name))
            cursor.execute('SELECT resource_ankama_id, monster_ankama_id FROM resource_drops')
            for resource_id, monster_id in cursor.fetchall():
                resource_counts[monster_id] += 1
                resource_aliases[monster_id].update(resource_names.get(resource_id, ()))

        item_counts = Counter()
        item_aliases = defaultdict(set)
        if _db_table_exists(cursor, 'item_drops'):
            item_names = defaultdict(set)
            if _db_table_exists(cursor, 'items'):
                cursor.execute('SELECT id, name FROM items')
                for item_id, name in cursor.fetchall():
                    if name:
                        item_names[item_id].add(norm(name))
            if _db_table_exists(cursor, 'item_names'):
                cursor.execute('SELECT item, name FROM item_names')
                for item_id, name in cursor.fetchall():
                    if name:
                        item_names[item_id].add(norm(name))
            cursor.execute('SELECT item, monster_ankama_id FROM item_drops')
            for item_id, monster_id in cursor.fetchall():
                item_counts[monster_id] += 1
                item_aliases[monster_id].update(item_names.get(item_id, ()))

        level_spans = {}
        if _db_table_exists(cursor, 'monster_grades'):
            cursor.execute(
                """
                SELECT monster_ankama_id, MIN(level), MAX(level)
                FROM monster_grades WHERE level IS NOT NULL
                GROUP BY monster_ankama_id
                """)
            for monster_id, level_min, level_max in cursor.fetchall():
                level_spans[monster_id] = (level_min, level_max)

        # The single element every grade is weakest to. None when the grades
        # disagree or the resists are flat.
        weakest_by_monster = {}
        if _db_table_exists(cursor, 'monster_grades'):
            grades_by_monster = defaultdict(list)
            cursor.execute(
                """
                SELECT monster_ankama_id, earth_resistance, fire_resistance,
                       water_resistance, air_resistance, neutral_resistance
                FROM monster_grades
                """)
            for row in cursor.fetchall():
                grades_by_monster[row[0]].append({
                    'earth': row[1], 'fire': row[2], 'water': row[3],
                    'air': row[4], 'neutral': row[5],
                })
            for monster_id, grades in grades_by_monster.items():
                for grade in grades:
                    grade['weakest'] = _weakest_elements(grade)
                weakest_by_monster[monster_id] = _consistent_weakest(grades)

        dropped_monster_ids = sorted(set(resource_counts) | set(item_counts))
        for monster_id in dropped_monster_ids:
            if not has_display_name(monster_names.get(monster_id)):
                continue
            pieces = set()
            pieces.update(monster_aliases.get(monster_id, ()))
            pieces.update(resource_aliases.get(monster_id, ()))
            pieces.update(item_aliases.get(monster_id, ()))
            pieces.add(str(monster_id))
            resource_count = resource_counts[monster_id]
            item_count = item_counts[monster_id]
            level_min, level_max = level_spans.get(monster_id, (None, None))
            monsters.append({
                'id': monster_id,
                'names': dict(monster_names.get(monster_id, {})),
                'name_aliases': sorted(monster_aliases.get(monster_id, ())),
                'resource_count': resource_count,
                'item_count': item_count,
                'total_drops': resource_count + item_count,
                'level_min': level_min,
                'level_max': level_max,
                'weakest_element': weakest_by_monster.get(monster_id),
                'search_blob': ' '.join(sorted(piece for piece in pieces if piece)),
            })
    except Exception:
        monsters = []
    finally:
        if conn is not None:
            conn.close()
    return monsters


def _get_monster_core(game_version):
    core = _monster_core_cache.get(game_version)
    if core is None:
        core = _build_monster_core(game_version)
        _monster_core_cache[game_version] = core
    return core


_monster_core_by_id_cache = {}


def _get_monster_core_by_id(game_version):
    cached = _monster_core_by_id_cache.get(game_version)
    if cached is None:
        cached = {entry['id']: entry for entry in _get_monster_core(game_version)}
        _monster_core_by_id_cache[game_version] = cached
    return cached


def _get_monster_index(game_version, language):
    cache_key = (game_version, language)
    cached = _monster_index_cache.get(cache_key)
    if cached is not None:
        return cached

    core = _get_monster_core(game_version)

    monsters = []
    for entry in core:
        names = entry['names']
        name = names.get(language) or names.get('en') or '#%s' % entry['id']
        monsters.append({
            'id': entry['id'],
            'name': name,
            'resource_count': entry['resource_count'],
            'item_count': entry['item_count'],
            'total_drops': entry['total_drops'],
            'level_min': entry['level_min'],
            'level_max': entry['level_max'],
            'weakest_element': entry.get('weakest_element'),
            'url': get_monster_link(entry['id'], name, game_version),
            'name_aliases': entry['name_aliases'],
            'search_blob': entry['search_blob'],
        })

    _monster_index_cache[cache_key] = monsters
    return monsters


def warm_caches():
    """Pre-build the per-version encyclopedia caches. Called from a background
    thread at wsgi startup."""
    for game_version, _label in ACTIVE_GAME_VERSIONS:
        structure = get_structure(game_version)
        _get_light_core(structure)
        for language in SUPPORTED_LANGUAGES:
            _get_light_index(structure, language)
            _get_monster_index(game_version, language)
        _get_monster_core_by_id(game_version)
        _monster_image_ids(game_version)
        _ingredient_icon_ids(game_version)
        _version_item_keys(game_version)
        _version_resource_keys(game_version)
        _get_resource_search_index(game_version)


def _get_monster_version_links(monster_id, current_game_version, language):
    """Cross-version links for a monster page, from the cached monster core
    (which only carries monsters that drop something).

    A monster id is no more a shared identity than an item id, so the english
    names have to agree."""
    links = []
    here = _get_monster_core_by_id(current_game_version).get(monster_id) or {}
    here_en = (here.get('names') or {}).get('en')
    for game_version, version_label in ACTIVE_GAME_VERSIONS:
        if game_version == current_game_version:
            continue
        entry = _get_monster_core_by_id(game_version).get(monster_id)
        if entry is None:
            continue
        names = entry['names']
        if not is_same_item_name(here_en, names.get('en')):
            continue
        monster_name = names.get(language) or names.get('en')
        if not monster_name:
            continue
        links.append({
            'game_version': game_version,
            'label': version_label,
            'name': monster_name,
            'resource_count': entry['resource_count'],
            'item_count': entry['item_count'],
            'url': get_monster_link(monster_id, monster_name, game_version),
        })
    return links


def encyclopedia_monsters(request):
    language = get_supported_language()
    t = _ui_text()
    mt = _monster_ui_text()
    game_version = getattr(request, 'game_version', 'dofus3')
    search_text = (request.GET.get('q') or '').strip()
    needle = _normalized_text(search_text) if search_text else ''
    drop_kind = request.GET.get('drop_kind', 'all')
    if drop_kind not in MONSTER_DROP_FILTERS:
        drop_kind = 'all'
    sort_key = request.GET.get('sort', 'name')
    if sort_key not in MONSTER_SORTS:
        sort_key = 'name'
    weakness = request.GET.get('weak', 'all')
    if weakness != 'all' and weakness not in _GRADE_ELEMENTS:
        weakness = 'all'

    monsters = []
    for entry in _get_monster_index(game_version, language):
        if drop_kind == 'resources' and entry['resource_count'] <= 0:
            continue
        if drop_kind == 'items' and entry['item_count'] <= 0:
            continue
        if drop_kind == 'both' and (entry['resource_count'] <= 0 or entry['item_count'] <= 0):
            continue
        if weakness != 'all' and entry.get('weakest_element') != weakness:
            continue
        if needle and needle not in entry['search_blob']:
            continue
        monsters.append(entry.copy())

    def monster_sort_key(entry):
        name_key = ((entry['name'] or '').lower(), entry['id'])
        if sort_key == 'total_drops':
            return (-entry['total_drops'],) + name_key
        if sort_key == 'resource_drops':
            return (-entry['resource_count'],) + name_key
        if sort_key == 'item_drops':
            return (-entry['item_count'],) + name_key
        if sort_key == 'level':
            return (entry['level_min'] is None, entry['level_min'] or 0) + name_key
        return name_key

    monsters.sort(key=monster_sort_key)
    paginator = Paginator(monsters, 60)
    page = request.GET.get('page', 1)
    try:
        page_obj = paginator.page(page)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)
    for entry in page_obj.object_list:
        entry['image_url'] = _monster_image_url(game_version, entry['id'])
        element = entry.get('weakest_element')
        entry['weakest_element_name'] = mt['%s_label' % element] if element else None

    preview_ids = [monster['id'] for monster in page_obj.object_list]
    if preview_ids:
        preview_conn = None
        try:
            preview_conn = sqlite3.connect(get_items_db_path(game_version))
            preview_cursor = preview_conn.cursor()
            previews = _get_monster_drop_previews(
                preview_cursor, preview_ids, language, game_version)
            for monster in page_obj.object_list:
                monster['sample_drops'] = previews.get(monster['id'], [])
        except Exception:
            for monster in page_obj.object_list:
                monster['sample_drops'] = []
        finally:
            if preview_conn is not None:
                preview_conn.close()

    query_without_page = request.GET.copy()
    if 'page' in query_without_page:
        del query_without_page['page']
    page_query_prefix = query_without_page.urlencode()
    if page_query_prefix:
        page_query_prefix = '%s&' % page_query_prefix

    drop_filter_options = [
        {
            'value': value,
            'label': mt['drop_filter_%s' % value],
            'selected': value == drop_kind,
        }
        for value in MONSTER_DROP_FILTERS
    ]
    # dofus2 has no source for per-grade stats, so it gets no level sort.
    has_levels = any(entry['level_min'] is not None
                     for entry in _get_monster_index(game_version, language))
    sort_options = [
        {
            'value': value,
            'label': mt['sort_%s' % value],
            'selected': value == sort_key,
        }
        for value in MONSTER_SORTS
        if value != 'level' or has_levels
    ]
    present_weaknesses = {entry['weakest_element']
                          for entry in _get_monster_index(game_version, language)
                          if entry.get('weakest_element')}
    weakness_options = []
    if present_weaknesses:
        weakness_options.append({
            'value': 'all',
            'label': mt['weakness_filter_all'],
            'selected': weakness == 'all',
        })
        weakness_options.extend(
            {
                'value': element,
                'label': mt['%s_label' % element],
                'selected': weakness == element,
            }
            for element in _GRADE_ELEMENTS
            if element in present_weaknesses
        )

    monsters_canonical = _paginated_canonical(
        request, '/encyclopedia/monsters/', game_version, page_obj)

    return set_response(
        request,
        'chardata/encyclopedia_monsters.html',
        {
            'request': request,
            'char_id': 0,
            't': t,
            'mt': mt,
            'canonical_url': monsters_canonical,
            'breadcrumb_jsonld': _breadcrumb_jsonld([
                ('Dofus Fashionista', 'https://dofusfashionista.gg/'),
                (t.get('title') or 'Encyclopedia',
                 _absolute_versioned_url('/encyclopedia/', game_version)),
                (mt['monsters_label'], monsters_canonical),
            ]),
            'monsters_page': page_obj,
            'monsters_count': len(monsters),
            'search_text': search_text,
            'drop_kind': drop_kind,
            'sort_key': sort_key,
            'weakness_filter': weakness,
            'drop_filter_options': drop_filter_options,
            'sort_options': sort_options,
            'weakness_options': weakness_options,
            'page_query_prefix': page_query_prefix,
        },
    )


def _monster_not_found_response(request, monster_id=None, slug=None, current_name=None):
    language = get_supported_language()
    mt = _monster_ui_text()
    game_version = getattr(request, 'game_version', 'dofus3')
    if monster_id is None:
        requested_name = _humanize_missing_slug(slug, mt['monster_kind_label'])
    else:
        requested_name = _resolve_missing_monster_name(
            monster_id, slug, language, game_version, current_name=current_name)
    return _encyclopedia_missing_response(request, 'monster', requested_name)


def _resource_not_found_response(request, subtype, ankama_id, slug=None, current_name=None):
    language = get_supported_language()
    game_version = getattr(request, 'game_version', 'dofus3')
    requested_name = _resolve_missing_resource_name(
        subtype, ankama_id, slug, language, game_version, current_name=current_name)
    return _encyclopedia_missing_response(request, 'resource', requested_name)


def _grade_level_span(grades):
    """'22-30' (or '22') across the version's own grades, for title/meta."""
    levels = [g['level'] for g in grades if g.get('level') is not None]
    if not levels:
        return None
    low, high = min(levels), max(levels)
    return '%d-%d' % (low, high) if high != low else '%d' % low


_GRADE_ELEMENTS = ('earth', 'fire', 'water', 'air', 'neutral')


def _weakest_elements(grade):
    """Element keys with the lowest resistance in a grade (what the monster takes
    the most damage from). Empty when resistances are missing or all equal."""
    present = {key: grade.get(key) for key in _GRADE_ELEMENTS
               if grade.get(key) is not None}
    if len(present) < 2:
        return set()
    low = min(present.values())
    if low == max(present.values()):
        return set()
    return {key for key, value in present.items() if value == low}


def _consistent_weakest(grades):
    """The single element every grade is weakest to. None when the grades
    disagree, tie, or have no distinct weakness."""
    weak_sets = [grade.get('weakest') or set() for grade in grades]
    if not weak_sets or any(len(weak) != 1 for weak in weak_sets):
        return None
    elements = set().union(*weak_sets)
    return next(iter(elements)) if len(elements) == 1 else None


def _monster_spells(cursor, monster_ankama_id, language):
    """Its spells in order, named and priced."""
    rows = cursor.execute(
        """
        SELECT ms.spell_ankama_id, ms.grade_mapping,
               COALESCE(mine.name, fallback.name),
               COALESCE(mine.description, fallback.description)
        FROM monster_spells ms
        LEFT JOIN monster_spell_names mine
          ON mine.spell_ankama_id = ms.spell_ankama_id AND mine.language = ?
        LEFT JOIN monster_spell_names fallback
          ON fallback.spell_ankama_id = ms.spell_ankama_id AND fallback.language = 'en'
        WHERE ms.monster_ankama_id = ?
        ORDER BY ms.position
        """, (language, monster_ankama_id)).fetchall()
    wanted = {}
    for spell_id, mapping, name, _description in rows:
        if not name:
            continue
        grades = [int(grade) for grade in (mapping or '').split(',') if grade.isdigit()]
        wanted[spell_id] = grades[0] if grades else 1

    # The fullest monster carries forty spells.
    details = {}
    if wanted:
        placeholders = ','.join('?' * len(wanted))
        for row in cursor.execute(
                """
                SELECT spell_ankama_id, grade, ap_cost, range_min, range_max
                FROM monster_spell_levels
                WHERE spell_ankama_id IN (%s)
                """ % placeholders, list(wanted)):
            if wanted.get(row[0]) == row[1]:
                details[row[0]] = row[2:]

    spells = []
    for spell_id, mapping, name, description in rows:
        if not name:
            continue
        ap_cost, range_min, range_max = details.get(spell_id, (None, None, None))
        spells.append({
            'id': spell_id,
            'name': name,
            'spell_tip': SpellTip(name, description) if description else None,
            'ap_cost': ap_cost,
            'range_min': range_min,
            'range_max': range_max,
            'has_range': range_max is not None,
        })
    return spells


def encyclopedia_monster(request, monster_id, slug=None):
    language = get_supported_language()
    t = _ui_text()
    mt = _monster_ui_text()
    game_version = getattr(request, 'game_version', 'dofus3')
    target_monster_id = safe_int(monster_id, None)
    if target_monster_id is None:
        return _monster_not_found_response(request, slug=slug)

    monster_name = None
    monster_names_by_language = {}
    url_language = language
    resource_drops = []
    item_drops = []
    grades = []
    conn = None
    try:
        conn = sqlite3.connect(get_items_db_path(game_version))
        cursor = conn.cursor()
        if not _db_table_exists(cursor, 'monster_names'):
            return _monster_not_found_response(request, target_monster_id, slug)
        monster_name = _get_monster_display_name(cursor, target_monster_id, language)
        # No name in any language, or none stored at all: nothing to show but
        # the upstream placeholder, or our own "#7953".
        if (monster_name == '#%s' % target_monster_id
                or not has_display_name({language: monster_name})):
            return _monster_not_found_response(request, target_monster_id, slug)

        # The slug names the language, exactly as it does for items.
        monster_names_by_language = _get_monster_names_by_language(
            cursor, target_monster_id)
        url_language = language_from_slug(monster_names_by_language, slug,
                                          _normalized_slug)
        if url_language is None:
            url_language = language
        elif url_language != language:
            translation.activate(url_language)
            language = url_language
            t = _ui_text()
            mt = _monster_ui_text()
            monster_name = _get_monster_display_name(
                cursor, target_monster_id, language)

        # Per-grade stats, stored per version from that version's own source
        # (touch: the backend Monsters table).
        if _db_table_exists(cursor, 'monster_grades'):
            for row in cursor.execute(
                    """
                    SELECT grade, level, life_points, action_points,
                           movement_points, earth_resistance, fire_resistance,
                           water_resistance, air_resistance, neutral_resistance
                    FROM monster_grades
                    WHERE monster_ankama_id = ?
                    ORDER BY grade
                    """, (target_monster_id,)):
                grade = {
                    'grade': row[0], 'level': row[1], 'hp': row[2],
                    'ap': row[3], 'mp': row[4], 'earth': row[5],
                    'fire': row[6], 'water': row[7], 'air': row[8],
                    'neutral': row[9],
                }
                grade['weakest'] = _weakest_elements(grade)
                grades.append(grade)
        # Where the monster can be found, from the version's own source (retro:
        # the Solomonk bestiary subarea blocks). Localized, French as fallback.
        subareas = []
        if _db_table_exists(cursor, 'monster_subareas'):
            rows = cursor.execute(
                """
                SELECT name FROM monster_subareas
                WHERE monster_ankama_id = ? AND language = ?
                ORDER BY position
                """, (target_monster_id, language)).fetchall()
            if not rows and language != 'fr':
                rows = cursor.execute(
                    """
                    SELECT name FROM monster_subareas
                    WHERE monster_ankama_id = ? AND language = 'fr'
                    ORDER BY position
                    """, (target_monster_id,)).fetchall()
            subareas = [row[0] for row in rows]

        # Cost and reach at the monster's first grade.
        spells = []
        if _db_table_exists(cursor, 'monster_spells'):
            spells = _monster_spells(cursor, target_monster_id, language)

        if monster_name.startswith('#'):
            return _monster_not_found_response(request, target_monster_id, slug)

        if _db_table_exists(cursor, 'resource_drops'):
            cursor.execute(
                """
                SELECT d.resource_ankama_id, d.rate,
                       (SELECT name FROM item_recipe_ingredient_names
                        WHERE ingredient_ankama_id = d.resource_ankama_id
                          AND ingredient_subtype = 'resources'
                          AND language = ? LIMIT 1),
                       (SELECT name FROM item_recipe_ingredient_names
                        WHERE ingredient_ankama_id = d.resource_ankama_id
                          AND ingredient_subtype = 'resources'
                          AND language = 'en' LIMIT 1),
                       d.conditions
                FROM resource_drops d
                WHERE d.monster_ankama_id = ?
                ORDER BY d.rate DESC
                """,
                (language, target_monster_id))
            for resource_id, rate, name_loc, name_en, conditions in cursor.fetchall():
                resource_name = name_loc or name_en or ('#%s' % resource_id)
                resource_drops.append({
                    'id': resource_id,
                    'name': resource_name,
                    'rate': rate,
                    'url': get_resource_link('resources', resource_id, resource_name, game_version),
                    'has_conditions': bool(conditions),
                    'conditions_text': _drop_conditions_text(conditions, mt),
                })

        if _db_table_exists(cursor, 'item_drops'):
            cursor.execute(
                """
                SELECT d.item, d.rate, i.ankama_id, i.ankama_type, i.name, i.level, it.name,
                       COALESCE(
                           (SELECT item_names.name FROM item_names
                             WHERE item_names.item = i.id AND item_names.language = ? LIMIT 1),
                           (SELECT item_names.name FROM item_names
                            WHERE item_names.item = i.id AND item_names.language = 'en' LIMIT 1),
                           i.name
                       ) AS localized_name,
                       d.conditions
                FROM item_drops d
                JOIN items i ON i.id = d.item
                LEFT JOIN item_types it ON it.id = i.type
                WHERE d.monster_ankama_id = ?
                ORDER BY d.rate DESC, localized_name ASC
                """,
                (language, target_monster_id))
            for (_item_id, rate, item_ankama_id, item_ankama_type, item_name, item_level,
                 item_type_name, localized_item_name, conditions) in cursor.fetchall():
                item_drops.append({
                    'name': localized_item_name,
                    'level': item_level,
                    'type_name': _localized_label(item_type_name, language),
                    'rate': rate,
                    'url': get_item_link(item_ankama_type, item_ankama_id, localized_item_name,
                                         game_version=game_version),
                    'image_url': static(get_image_url(
                        item_type_name, item_name, game_version)),
                    'has_conditions': bool(conditions),
                    'conditions_text': _drop_conditions_text(conditions, mt),
                })
    except Exception:
        return _monster_not_found_response(request, target_monster_id, slug, monster_name)
    finally:
        if conn is not None:
            conn.close()

    if not resource_drops and not item_drops:
        return _monster_not_found_response(request, target_monster_id, slug, monster_name)

    monster_version_links = _get_monster_version_links(
        target_monster_id, game_version, language)
    canonical_path = get_monster_link(target_monster_id, monster_name, game_version)
    canonical_url = 'https://dofusfashionista.gg' + (canonical_path or '/encyclopedia/monsters/')
    alternate_urls = build_alternate_urls(
        lambda name: get_monster_link(target_monster_id, name, game_version),
        monster_names_by_language, 'https://dofusfashionista.gg')
    redirect_to = redirect_target_for_user(request, url_language, alternate_urls)
    if redirect_to:
        return mark_varies_on_cookie(redirect(redirect_to))
    encyclopedia_url = _absolute_versioned_url('/encyclopedia/', game_version)
    monsters_url = _absolute_versioned_url('/encyclopedia/monsters/', game_version)
    breadcrumb_jsonld = _breadcrumb_jsonld([
        ('Dofus Fashionista', 'https://dofusfashionista.gg/'),
        (t.get('title') or 'Encyclopedia', encyclopedia_url),
        (mt.get('monsters_label') or 'Monsters', monsters_url),
        (monster_name, canonical_url),
    ])

    weakest_key = _consistent_weakest(grades)
    weakness_element_name = mt.get('%s_label' % weakest_key) if weakest_key else None

    return set_response(
        request,
        'chardata/encyclopedia_monster.html',
        {
            'request': request,
            'char_id': 0,
            't': t,
            'mt': mt,
            'canonical_url': canonical_url,
            'alternate_urls': alternate_urls,
            'breadcrumb_jsonld': breadcrumb_jsonld,
            'monster': {
                'id': target_monster_id,
                'name': monster_name,
                'image_url': _monster_image_url(game_version, target_monster_id),
            },
            'resource_drops': resource_drops,
            'item_drops': item_drops,
            'grades': grades,
            'has_weakness': any(g['weakest'] for g in grades),
            'weakness_element_name': weakness_element_name,
            'level_span': _grade_level_span(grades),
            'subareas': subareas,
            'spells': spells,
            'monster_version_links': monster_version_links,
        })


def encyclopedia_resource(request, subtype, ankama_id, slug=None):
    """A crafting ingredient (resource) page: every item it is used to craft, in
    the current game version."""
    language = get_supported_language()
    t = _ui_text()
    game_version = getattr(request, 'game_version', 'dofus3')

    try:
        target_ankama_id = int(ankama_id)
    except (TypeError, ValueError):
        return redirect(version_reverse(request, 'encyclopedia'))

    resource_name = None
    resource_names_by_language = {}
    url_language = language
    used_in = []
    drops = []
    conn = None
    try:
        conn = sqlite3.connect(get_items_db_path(game_version))
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'item_recipe_ingredient_names'")
        if cursor.fetchone() is not None:
            cursor.execute(
                "SELECT name FROM item_recipe_ingredient_names "
                "WHERE ingredient_ankama_id = ? AND ingredient_subtype = ? AND language = ?",
                (target_ankama_id, subtype, language))
            row = cursor.fetchone()
            if row is None and language != 'en':
                cursor.execute(
                    "SELECT name FROM item_recipe_ingredient_names "
                    "WHERE ingredient_ankama_id = ? AND ingredient_subtype = ? AND language = 'en'",
                    (target_ankama_id, subtype))
                row = cursor.fetchone()
            if row is not None:
                resource_name = row[0]

            # The slug names the language, exactly as it does for items.
            resource_names_by_language = _get_resource_names_by_language(
                cursor, target_ankama_id, subtype)
            slug_language = language_from_slug(
                resource_names_by_language, slug, _normalized_slug)
            if slug_language is not None and slug_language != language:
                translation.activate(slug_language)
                language = slug_language
                url_language = slug_language
                t = _ui_text()
                resource_name = (resource_names_by_language.get(language)
                                 or resource_name)

        cursor.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'item_recipes'")
        if resource_name is not None and cursor.fetchone() is not None:
            cursor.execute(
                """
                SELECT DISTINCT i.ankama_id, i.ankama_type, i.name, i.level, it.name,
                       COALESCE(
                           (SELECT item_names.name
                            FROM item_names
                            WHERE item_names.item = i.id
                              AND item_names.language = ?
                            LIMIT 1),
                           (SELECT item_names.name
                            FROM item_names
                            WHERE item_names.item = i.id
                              AND item_names.language = 'en'
                            LIMIT 1),
                           i.name
                       ) AS localized_name
                FROM item_recipes r
                JOIN items i ON i.id = r.item
                LEFT JOIN item_types it ON it.id = i.type
                WHERE r.ingredient_ankama_id = ? AND r.ingredient_subtype = ?
                ORDER BY i.level DESC, localized_name ASC
                """,
                (language, target_ankama_id, subtype))
            for (item_ankama_id, item_ankama_type, item_name, item_level,
                 item_type_name, localized_item_name) in cursor.fetchall():
                used_in.append({
                    'name': localized_item_name,
                    'level': item_level,
                    'type_name': _localized_label(item_type_name, language),
                    'url': get_item_link(item_ankama_type, item_ankama_id, localized_item_name,
                                         game_version=game_version),
                    'image_url': static(get_image_url(
                        item_type_name, item_name, game_version)),
                })

        # Resources are also dropped by monsters.
        cursor.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'resource_drops'")
        if resource_name is not None and cursor.fetchone() is not None:
            cursor.execute(
                """
                SELECT d.monster_ankama_id, d.rate,
                       (SELECT name FROM monster_names
                        WHERE monster_ankama_id = d.monster_ankama_id AND language = ?),
                       (SELECT name FROM monster_names
                        WHERE monster_ankama_id = d.monster_ankama_id AND language = 'en'),
                       d.conditions
                FROM resource_drops d
                WHERE d.resource_ankama_id = ?
                ORDER BY d.rate DESC
                """,
                (language, target_ankama_id))
            drop_rows = cursor.fetchall()
            level_spans = _monster_level_spans(
                cursor, [row[0] for row in drop_rows])
            drops_ui = _monster_ui_text()
            level_label = drops_ui['level_label']
            for monster_id, rate, name_loc, name_en, conditions in drop_rows:
                monster_name = name_loc or name_en or ('#%s' % monster_id)
                span = level_spans.get(monster_id)
                drops.append({
                    'name': monster_name,
                    'rate': rate,
                    'url': get_monster_link(monster_id, monster_name, game_version),
                    'level': _drop_level_text(span, level_label),
                    'level_min': span[0] if span else None,
                    'has_conditions': bool(conditions),
                    'conditions_text': _drop_conditions_text(conditions, drops_ui),
                })
            drops.sort(key=lambda d: (-d['rate'],
                                      d['level_min'] if d['level_min'] is not None else 10 ** 9))
    except Exception:
        pass
    finally:
        if conn is not None:
            conn.close()

    if not resource_name or not used_in:
        return _resource_not_found_response(
            request, subtype, target_ankama_id, slug, current_name=resource_name)

    canonical_path = get_resource_link(subtype, target_ankama_id, resource_name, game_version)
    canonical_url = 'https://dofusfashionista.gg' + (canonical_path or '/encyclopedia/')
    alternate_urls = build_alternate_urls(
        lambda name: get_resource_link(subtype, target_ankama_id, name,
                                       game_version),
        resource_names_by_language, 'https://dofusfashionista.gg')
    redirect_to = redirect_target_for_user(request, url_language, alternate_urls)
    if redirect_to:
        return mark_varies_on_cookie(redirect(redirect_to))
    encyclopedia_url = _absolute_versioned_url('/encyclopedia/', game_version)
    breadcrumb_jsonld = _breadcrumb_jsonld([
        ('Dofus Fashionista', 'https://dofusfashionista.gg/'),
        (t.get('title') or 'Encyclopedia', encyclopedia_url),
        (resource_name, canonical_url),
    ])
    kind_label = (
        t['resource_kind_label'] if subtype == 'resources'
        else t.get('ingredient_kind_label', t['resource_kind_label']))

    resource_image = _ingredient_icon_url(game_version, target_ankama_id)

    return set_response(
        request,
        'chardata/encyclopedia_resource.html',
        {
            'request': request,
            'char_id': 0,
            't': t,
            'drop_conditions_label': _monster_ui_text()['drop_conditions_label'],
            'canonical_url': canonical_url,
            'alternate_urls': alternate_urls,
            'breadcrumb_jsonld': breadcrumb_jsonld,
            'resource': {
                'name': resource_name,
                'kind_label': kind_label,
                'subtype': subtype,
                'ankama_id': target_ankama_id,
            },
            'resource_image': resource_image,
            'used_in': used_in,
            'drops': drops,
            'other_versions': _other_versions_with_resource(
                game_version, subtype, target_ankama_id, resource_name),
        })
