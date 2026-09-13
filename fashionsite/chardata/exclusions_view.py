# Copyright (C) 2020 The Dofus Fashionista
# 
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

from django.http import HttpResponseBadRequest
from django.views.decorators.http import require_POST
from django.utils import translation
from django.utils.translation import gettext, gettext_lazy

import json

from chardata.lock_forbid import get_all_exclusions_with_names, get_all_exclusions_ids, set_exclusions_list_and_check_inclusions
from chardata.translation_util import localized_stat_name
from chardata.util import set_response, get_char_or_raise, HttpResponseJson
from fashionistapulp.structure import get_structure
from fashionistapulp.translation import get_supported_language


TYPE_COLUMNS = [
    [{'id': 'Weapon', 'name': gettext_lazy('Weapon')}, 
     {'id': 'Shield', 'name': gettext_lazy('Shield')},
     {'id': 'Hat', 'name': gettext_lazy('Hat')}, 
     {'id': 'Cloak', 'name': gettext_lazy('Cloak')},
     {'id': 'Pet', 'name': gettext_lazy('Pet')}],
    [{'id': 'Amulet', 'name': gettext_lazy('Amulet')}, 
     {'id': 'Ring', 'name': gettext_lazy('Ring')},
     {'id': 'Boots', 'name': gettext_lazy('Boots')}, 
     {'id': 'Belt', 'name': gettext_lazy('Belt')},
     {'id': 'Dofus', 'name': gettext_lazy('Dofus')}]
]


def _localized(label, language):
    if not label:
        return ''
    with translation.override(language):
        return gettext(label)


def _stats_text(structure, item, language):
    """What the piece gives, short. The last thing that can tell two pieces
    apart: if their values matched too they would be one piece."""
    parts = []
    with translation.override(language):
        for stat_id, value in (item.stats or ())[:3]:
            stat = structure.get_stat_by_id(stat_id)
            if stat is None:
                continue
            parts.append('%+d %s'
                         % (value, localized_stat_name(stat.name,
                                                       structure.game_version)))
    return ', '.join(parts)


def _what_could_tell_them_apart(structure, item, language):
    """The marks a label can add, in the order a reader would look for them."""
    type_name = _localized(structure.get_type_name_by_id(item.type), language)
    marks = ['%s | %s %s'
             % (type_name, _localized('Lvl.', language), item.level)]
    item_set = (structure.get_set_by_id(item.set)
                if item.set is not None else None)
    if item_set is not None:
        marks.append(item_set.localized_names.get(language, item_set.name))
    marks.append(item.name)
    marks.append(_stats_text(structure, item, language))
    return [mark for mark in marks if mark]


def _one_door_per_piece(structure, language, forbiddable_id):
    """{what the reader types: every piece id that door closes}.

    A door is a name the reader can type into the forbid box. The page used to
    receive a plain {name: id} map, so two different pieces sharing a name in
    his language overwrote each other and one of them had no door at all: 45
    pieces on Dofus 2 in Spanish, 66 on Retro. And 20 of the Retro collisions
    are one ring per set, which a player picks between every day.

    Each piece now gets its own door, and the door says what separates it from
    its namesake: its type and level, then its set, then the name Ankama gives
    it, then what it carries. Pieces that even those four cannot separate are
    indistinguishable to this reader, so they share one door that closes every
    one of them rather than a row he cannot choose between.
    """
    def door(item_ids):
        # One number when the door closes one piece, a list when it closes
        # several: the page carries one of these per catalogue entry, and the
        # brackets alone cost 8 to 12 kB on every load.
        return item_ids[0] if len(item_ids) == 1 else item_ids

    # An item gated behind alternative conditions ships as several rows under
    # one name: the Gelano is one ring the reader forbids once, not two. The
    # suite caught this one; the catalogue's repeated rows are the other way a
    # piece spans several ids.
    or_families = structure.get_available_or_items()

    def which_piece(item):
        family = or_families.get(item.or_name)
        if family is not None and len(family) > 1:
            return ('or', item.or_name)
        rows = structure.get_rows_of_the_same_item(item.id)
        return min(rows) if rows else item.id

    doors = {}
    for name, item_ids in structure.get_all_unique_items_ids_by_name(
            language).items():
        pieces = {}
        for item_id in item_ids:
            item = structure.get_item_by_id(item_id)
            if item is None:
                continue
            pieces.setdefault(which_piece(item), []).append(item)
        if len(pieces) < 2:
            # One id per piece is enough: the solver closes the other rows of
            # the same piece by itself.
            doors[name] = door([forbiddable_id(item_ids[0])])
            continue
        marks = {key: _what_could_tell_them_apart(structure, items[0], language)
                 for key, items in pieces.items()}
        labels = None
        for depth in range(1, 1 + max(len(mark) for mark in marks.values())):
            candidate = {key: '%s (%s)' % (name, ' | '.join(mark[:depth]))
                         for key, mark in marks.items()}
            if len(set(candidate.values())) == len(candidate):
                labels = candidate
                break
        if labels is None:
            doors[name] = door([forbiddable_id(items[0].id)
                               for items in pieces.values()])
            continue
        for key, label in labels.items():
            doors[label] = door([forbiddable_id(pieces[key][0].id)])
    return doors


def exclusions(request, char_id):
    char = get_char_or_raise(request, char_id) 
    s = get_structure()
    language = get_supported_language()
    
    sets_names = s.get_set_names(language)
    sets_names_dicts = {set_name: None for set_name in sets_names}

    all_items = s.get_all_unique_items_ids_with_type()

    # Grouped variants (Gelano) are indexed under an id that cannot be forbidden;
    # map them to a forbiddable variant, which forbids the whole group.
    forbiddable_ids = set(all_items)
    or_name_to_forbiddable = {}
    for item_id in all_items:
        item = s.get_item_by_id(item_id)
        if item is not None:
            or_name_to_forbiddable.setdefault(item.or_name, item_id)

    def forbiddable_id(item_id):
        if item_id is None or item_id in forbiddable_ids:
            return item_id
        item = s.get_item_by_id(item_id)
        alt = (or_name_to_forbiddable.get(item.or_name)
               if item is not None else None)
        return alt if alt is not None else item_id

    doors = _one_door_per_piece(s, language, forbiddable_id)
    # A set is forbidden through the plain name of each of its pieces, which
    # is what get_complete_sets_list hands out. A plain name that is still a
    # door needs no entry here, so this map only carries the few that lost
    # their key to a qualified label: a handful per language, not a second
    # copy of the whole catalogue.
    ids_by_plain_name = {
        name: [forbiddable_id(item_id) for item_id in item_ids]
        for name, item_ids
        in s.get_all_unique_items_ids_by_name(language).items()
        if name not in doors}

    all_names = sets_names_dicts.copy()
    all_names.update(doors)
    
    complete_sets = s.get_complete_sets_list(language)
    exclusions = get_all_exclusions_with_names(char, language)

    return set_response(request, 
                        'chardata/exclusions.html', 
                        {'char_id': char_id,
                         'advanced': True,
                         'type_columns': TYPE_COLUMNS,
                         'all_items_json': json.dumps(all_items),
                         'all_items_names_json': json.dumps(all_names),
                         'ids_by_plain_name_json': json.dumps(ids_by_plain_name),
                         'sets_with_items_json': json.dumps(complete_sets),
                         'exclusions': json.dumps(exclusions)}, 
                        char)


@require_POST
def exclusions_post(request, char_id):
    char = get_char_or_raise(request, char_id)
    
    # A missing list used to raise out of the view, and a list that is not a
    # list of numbers used to raise out of json or int: three 500s for a request
    # the page never sends and a stale tab does.
    exclusions_string = request.POST.get('exclusions', None)
    if exclusions_string is None:
        return HttpResponseBadRequest('exclusions list not received')
    try:
        exclusions = json.loads(exclusions_string)
        actual_exclusions = [int(iditem) for iditem in exclusions]
    except (TypeError, ValueError):
        return HttpResponseBadRequest('exclusions list not understood')
    set_exclusions_list_and_check_inclusions(char, actual_exclusions)
    
    return HttpResponseJson(json.dumps(get_all_exclusions_ids(char)))
