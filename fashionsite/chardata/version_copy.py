# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Copy a build to another version of its family, piece by piece, by Ankama id."""
import contextlib
import copy
import pickle

from django.db import transaction
from django.urls import NoReverseMatch, reverse

from chardata.anon_projects import get_anon_char_id, remember_anon_char
from chardata.char_blobs import read_char_blob
from chardata.models import Char, CharBaseStats
from fashionistapulp.dofus_constants import SLOT_NAME_TO_TYPE, slots_for
from fashionistapulp.game_versions import (DEFAULT_VERSION, get_game_version,
                                           sibling_versions)
from fashionistapulp.modelresult import ModelResultMinimal, get_item_in_slot
from fashionistapulp.structure import (get_current_game_version, get_structure,
                                       set_current_game_version)

SESSION_KEY = 'version_copies'
_REPORTS_KEPT = 5
_INVENTORY_OPTIONS_OF_THE_SOURCE = ('inventory_folder', 'inventory_mode')


@contextlib.contextmanager
def in_version(game_version):
    """Run with the thread's catalogue set to this version, then put it back."""
    before = get_current_game_version()
    set_current_game_version(game_version)
    try:
        yield
    finally:
        set_current_game_version(before)


def _type_name(structure, item):
    try:
        return structure.get_type_name_by_id(item.type)
    except (KeyError, AttributeError):
        return None


def _all_items(structure):
    return list((getattr(structure, 'items_dict', None) or {}).values()) + list(
        (getattr(structure, 'dt_items_dict', None) or {}).values())


def _index(structure):
    by_ankama = {}
    for item in _all_items(structure):
        if getattr(item, 'ankama_id', None) is None:
            continue
        key = (item.ankama_id, bool(getattr(item, 'dofus_touch', False)),
               _type_name(structure, item))
        by_ankama.setdefault(key, []).append(item)
    for rows in by_ankama.values():
        rows.sort(key=lambda row: row.id)
    return by_ankama


class PieceMap:
    """Which piece of the target catalogue a piece of the source catalogue is."""

    def __init__(self, source, target):
        self.source = source
        self.target = target
        self._target_rows = _index(target)
        self._source_rows = None

    def source_item(self, item_id, slot=None):
        if item_id is None or item_id == '':
            return None
        try:
            if slot is not None:
                return get_item_in_slot(self.source, item_id, slot)
            return self.source.get_item_by_id(item_id)
        except (TypeError, KeyError):
            return None

    def counterpart(self, item):
        """The same piece in the target, or None when the target lacks it or retired it."""
        found = self._same_piece(item)
        if found is None or getattr(found, 'removed', False):
            return None
        return found

    def _same_piece(self, item):
        if item is None:
            return None
        touch = bool(getattr(item, 'dofus_touch', False))
        type_name = _type_name(self.source, item)
        rows = []
        ankama_id = getattr(item, 'ankama_id', None)
        if ankama_id is not None:
            rows = self._target_rows.get((ankama_id, touch, type_name), [])
        if not rows:
            named = self.target.get_item_by_name(item.name, touch)
            if named is not None and _type_name(self.target, named) == type_name:
                rows = [named]
        if not rows:
            return None
        for row in rows:
            if row.name == item.name:
                return row
        if len(rows) == 1:
            return rows[0]
        if self._source_rows is None:
            self._source_rows = _index(self.source)
        own = self._source_rows.get((ankama_id, touch, type_name), [])
        rank = next((i for i, row in enumerate(own) if row.id == item.id), 0)
        return rows[min(rank, len(rows) - 1)]

    def item_id(self, item_id, slot=None):
        """The target's id for a stored source id, or None."""
        found = self.counterpart(self.source_item(item_id, slot))
        return found.id if found is not None else None

    def stat_id(self, stat_id):
        stat = self.source.get_stat_by_id(stat_id) if stat_id is not None else None
        if stat is None:
            return None
        other = self.target.get_stat_by_key(stat.key)
        return other.id if other is not None else None


def pieces_between(source_version, target_version):
    return PieceMap(get_structure(source_version), get_structure(target_version))


def translated_slots(pieces, item_per_slot, target_slots):
    """({slot: target id or None} over the target's slots, [(slot, source id)] left out)."""
    kept = {slot: None for slot in target_slots}
    missing = []
    for slot, item_id in (item_per_slot or {}).items():
        if item_id is None:
            continue
        found = pieces.item_id(item_id, slot)
        if found is None or slot not in kept:
            missing.append((slot, item_id))
            continue
        kept[slot] = found
    return kept, missing


def translated_inclusions(pieces, inclusions, target_slots):
    """Locked pieces: ({slot: target id}, [(slot, source id)] left out)."""
    kept, missing = {}, []
    if not isinstance(inclusions, dict):
        return kept, missing
    for slot, item_id in inclusions.items():
        if item_id in ('', None):
            continue
        found = pieces.item_id(item_id)
        if found is None or slot not in target_slots:
            missing.append((slot, item_id))
            continue
        kept[slot] = found
    return kept, missing


def translated_exclusions(pieces, exclusions):
    kept = []
    for item_id in exclusions if isinstance(exclusions, list) else []:
        found = pieces.item_id(item_id)
        if found is not None and found not in kept:
            kept.append(found)
    return kept


def translated_overrides(pieces, overrides):
    """{item id: {stat id: value}} in the target's ids, rolls on unknown stats dropped."""
    kept = {}
    for item_id, rolls in (overrides if isinstance(overrides, dict) else {}).items():
        found = pieces.item_id(item_id)
        if found is None or not isinstance(rolls, dict):
            continue
        for stat_id, value in rolls.items():
            other = pieces.stat_id(stat_id)
            if other is not None:
                kept.setdefault(found, {})[other] = value
    return kept


def _without_source_options(options):
    if not isinstance(options, dict):
        return options
    return {key: value for key, value in options.items()
            if key not in _INVENTORY_OPTIONS_OF_THE_SOURCE}


def _default_exclusion_ankama_ids(game_version):
    from chardata.lock_forbid import (DEFAULT_EXCLUSION_ANKAMA_IDS,
                                      DEFAULT_EXCLUSION_ANKAMA_IDS_BY_VERSION)
    return set(DEFAULT_EXCLUSION_ANKAMA_IDS) | set(
        DEFAULT_EXCLUSION_ANKAMA_IDS_BY_VERSION.get(game_version, ()))


def _defaults_only_the_target_has(pieces, source_version, target_version):
    """The target's default exclusions a build made on the source could not get."""
    seeded_on_source = _default_exclusion_ankama_ids(source_version)
    ids = []
    for ankama_id in sorted(_default_exclusion_ankama_ids(target_version)):
        item = pieces.target.get_item_by_ankama_id(ankama_id)
        if item is None:
            continue
        if (ankama_id in seeded_on_source
                and pieces.source.get_item_by_ankama_id(ankama_id) is not None):
            continue
        ids.append(item.id)
    return ids


def project_cap_reached(request, game_version):
    """The per-version cap, as duplicating a build counts it."""
    from chardata.create_project_view import MAXIMUM_NUMBER_OF_PROJECTS
    from chardata.util import TESTER_USERS
    if request.user is None or request.user.is_anonymous:
        return False
    chars = Char.objects.filter(owner=request.user, game_version=game_version)
    chars = chars.exclude(deleted=True)
    return (len(chars) >= MAXIMUM_NUMBER_OF_PROJECTS
            and request.user.email not in TESTER_USERS)


def guest_holds_a_build_there(request, game_version):
    """A signed-out visitor keeps one build per version; a copy must not replace it."""
    if request.user is not None and not request.user.is_anonymous:
        return False
    return get_anon_char_id(request, game_version) is not None


def _dedupe(missing):
    seen, kept = set(), []
    for slot, item_id in missing:
        if (slot, item_id) not in seen:
            seen.add((slot, item_id))
            kept.append((slot, item_id))
    return kept


def copy_build(request, source, target_version):
    """(the new build, [(slot, source item id)] the target lacks); (None, []) when refused.

    Refused at the cap, and for a guest who already holds a build on the target.
    """
    if target_version not in sibling_versions(source.game_version):
        raise ValueError('%s is not a sibling of %s'
                         % (target_version, source.game_version))
    if (project_cap_reached(request, target_version)
            or guest_holds_a_build_there(request, target_version)):
        return None, []
    signed_out = request.user is None or request.user.is_anonymous
    pieces = pieces_between(source.game_version, target_version)
    target_slots = slots_for(target_version)

    stored = Char.objects.get(pk=source.pk)
    minimal = read_char_blob(stored.minimal_solution, None, 'minimal_solution', stored)
    missing = []
    item_per_slot = None
    if minimal is not None:
        from chardata.legacy_ids import repair_minimal_solution
        repair_minimal_solution(stored, minimal)
        item_per_slot, missing = translated_slots(
            pieces, getattr(minimal, 'item_per_slot', None), target_slots)
    inclusions, locks_missing = translated_inclusions(
        pieces, read_char_blob(stored.inclusions, {}, 'inclusions', stored),
        target_slots)
    missing = _dedupe(missing + locks_missing)
    exclusions = [item_id for item_id in translated_exclusions(
        pieces, read_char_blob(stored.exclusions, [], 'exclusions', stored))
        if item_id not in inclusions.values()]
    for item_id in _defaults_only_the_target_has(
            pieces, source.game_version, target_version):
        if item_id not in exclusions and item_id not in inclusions.values():
            exclusions.append(item_id)
    overrides = translated_overrides(
        pieces, read_char_blob(stored.stat_overrides, {}, 'stat_overrides', stored))
    empty_slots = [slot for slot in read_char_blob(
        stored.empty_slots, [], 'empty_slots', stored) if slot in target_slots]
    options = _without_source_options(
        read_char_blob(stored.options, {}, 'options', stored))

    with transaction.atomic():
        new_char = _save_the_copy(request, stored, target_version, inclusions,
                                  exclusions, overrides, empty_slots, options)
        if item_per_slot is not None:
            _store_the_set(new_char, minimal, item_per_slot)

    if signed_out:
        remember_anon_char(request, new_char)
    _remember_report(request, new_char, source.game_version, missing)
    return new_char, missing


def _save_the_copy(request, stored, target_version, inclusions, exclusions,
                   overrides, empty_slots, options):
    from chardata.create_project_view import wants_to_publish
    source_pk = stored.pk
    signed_out = request.user is None or request.user.is_anonymous
    if signed_out:
        auto_publish = False
    elif stored.owner_id == request.user.id:
        auto_publish = stored.auto_publish
    else:
        auto_publish = wants_to_publish(request)
    new_char = stored
    new_char.pk = None
    new_char.id = None
    new_char._state.adding = True
    new_char.owner = None if signed_out else request.user
    new_char.game_version = target_version
    new_char.link_shared = False
    new_char.auto_publish = auto_publish
    new_char.view_count = 0
    new_char.deleted = False
    new_char.minimal_solution = b''
    new_char.solved_version = ''
    new_char.solved_time = None
    new_char.stuff_time = None
    new_char.created_time = None
    new_char.inclusions = pickle.dumps(inclusions)
    new_char.exclusions = pickle.dumps(exclusions)
    new_char.stat_overrides = pickle.dumps(overrides)
    new_char.empty_slots = pickle.dumps(empty_slots)
    new_char.options = pickle.dumps(options)
    new_char.save()

    for row in CharBaseStats.objects.filter(char_id=source_pk):
        CharBaseStats.objects.create(char=new_char, stat=row.stat,
                                     total_value=row.total_value,
                                     scrolled_value=row.scrolled_value)
    return new_char


def _store_the_set(char, minimal, item_per_slot):
    """The set read again from the target's catalogue and stored as an equip stores it."""
    from chardata.solution import get_solution_from_minimal, set_solution
    entry = copy.deepcopy(getattr(minimal, 'input', None) or {})
    if isinstance(entry, dict) and 'options' in entry:
        entry['options'] = _without_source_options(entry['options'])
    fresh = ModelResultMinimal(item_per_slot, entry, None)
    publish_later = char.auto_publish
    char.auto_publish = False
    with in_version(char.game_version):
        result = get_solution_from_minimal(char, fresh)
        if result is not None:
            set_solution(char, result)
    if publish_later:
        char.auto_publish = True
        char.save(update_fields=['auto_publish'])


def _remember_report(request, char, source_version, missing):
    reports = dict(request.session.get(SESSION_KEY) or {})
    reports[str(char.pk)] = {'from': source_version,
                             'missing': [[slot, item_id] for slot, item_id in missing]}
    for stale in list(reports)[:-_REPORTS_KEPT]:
        reports.pop(stale, None)
    request.session[SESSION_KEY] = reports
    request.session.modified = True


def take_report(request, char):
    """The copy report of this build, once: {'from', 'missing': [(type, name)]}, or None."""
    session = getattr(request, 'session', None)
    if session is None or char is None or getattr(char, 'pk', None) is None:
        return None
    reports = session.get(SESSION_KEY) or {}
    report = reports.get(str(char.pk))
    if report is None:
        return None
    reports = dict(reports)
    reports.pop(str(char.pk), None)
    session[SESSION_KEY] = reports
    session.modified = True
    return {'from': report.get('from'),
            'missing': missing_labels(report.get('from'), report.get('missing') or [])}


def missing_labels(source_version, missing, language=None):
    """[(slot type in the reader's language, piece name in the reader's language)]."""
    from django.utils.translation import gettext
    from fashionistapulp.translation import get_supported_language
    language = language or get_supported_language()
    try:
        structure = get_structure(source_version)
    except Exception:
        structure = None
    labels = []
    for slot, item_id in missing:
        item = get_item_in_slot(structure, item_id, slot) if structure else None
        name = (structure.get_item_name_in_language(item, language) or item.name
                if item is not None else str(item_id))
        kind = SLOT_NAME_TO_TYPE.get(slot)
        label = (gettext(kind) if kind else slot, name)
        if label not in labels:
            labels.append(label)
    return labels


def version_path(game_version, url_name, *args):
    """A route under a version's own prefix, with the reader's language prefix."""
    name = url_name if game_version == DEFAULT_VERSION else '%s:%s' % (game_version, url_name)
    try:
        return reverse(name, args=args)
    except NoReverseMatch:
        return reverse(url_name, args=args)


def copy_targets(game_version):
    """[{'key', 'name'}] of the versions a build of this version can be copied to."""
    return [{'key': key, 'name': get_game_version(key).game_name}
            for key in sibling_versions(game_version)]


def link_build_in(build, target_version, language=None):
    """A link reader's build moved to a sibling version; pieces it lacks join 'missing'."""
    from fashionistapulp.translation import get_supported_language
    language = language or get_supported_language()
    pieces = pieces_between(build['game_version'], target_version)
    moved = dict(build, game_version=target_version)
    ids = {}
    missing, missing_ankama_ids, found_there = [], [], []
    unplaced = list(build.get('missing_ankama_ids') or [])
    for index, label in enumerate(build.get('missing') or []):
        ankama_id = unplaced[index] if index < len(unplaced) else None
        item = (pieces.target.get_item_by_ankama_id(ankama_id)
                if ankama_id is not None else None)
        if item is None or getattr(item, 'removed', False):
            missing.append(label)
            missing_ankama_ids.append(ankama_id)
        else:
            found_there.append(item.id)
    for item_id in build.get('item_ids') or []:
        found = pieces.item_id(item_id)
        if found is None:
            item = pieces.source_item(item_id)
            missing.append(pieces.source.get_item_name_in_language(item, language)
                           if item is not None else str(item_id))
            missing_ankama_ids.append(getattr(item, 'ankama_id', None))
            continue
        ids[item_id] = found
    moved['item_ids'] = [ids[item_id] for item_id in build.get('item_ids') or []
                         if item_id in ids] + found_there
    moved['missing'] = missing
    moved['missing_ankama_ids'] = missing_ankama_ids
    moved['rolls'] = {ids[item_id]: rolls for item_id, rolls
                      in (build.get('rolls') or {}).items() if item_id in ids}
    moved['fm_unmapped'] = [(ids[item_id], code, value) for item_id, code, value
                            in build.get('fm_unmapped') or [] if item_id in ids]
    for key in ('fm_not_carried', 'not_wearable'):
        if key in build:
            moved[key] = [ids[item_id] for item_id in build.get(key) or []
                          if item_id in ids]
    return moved


def import_offers(text, game_version, language, link_build=None):
    """The siblings that know pieces of a paste this version lacks: [{'key', 'name', 'url', 'count', 'names'}]."""
    from chardata.text_build_import import read_items
    offers = []
    for key in sibling_versions(game_version):
        pieces = pieces_between(key, game_version)
        read_there = read_items(text, key, language) if (text or '').strip() else None
        names = []
        for item_id in (read_there or {}).get('item_ids') or []:
            item = pieces.source_item(item_id)
            if item is not None and pieces.counterpart(item) is None:
                names.append(pieces.source.get_item_name_in_language(item, language))
        for ankama_id in (link_build or {}).get('missing_ankama_ids') or []:
            item = (pieces.source.get_item_by_ankama_id(ankama_id)
                    if ankama_id is not None else None)
            if item is not None and not getattr(item, 'removed', False):
                names.append(pieces.source.get_item_name_in_language(item, language))
        if not names:
            continue
        offers.append({'key': key, 'name': get_game_version(key).game_name,
                       'url': version_path(key, 'text_build_import'),
                       'count': len(names), 'names': names})
    return offers
