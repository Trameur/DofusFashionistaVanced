# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Read-only preview of the weights and minimums a /setup/ choice gives a new build, from the fields the form posts."""
import json
import pickle
import re
from contextlib import contextmanager
from functools import lru_cache

from django.http import HttpResponse, JsonResponse
from django.utils.cache import patch_cache_control
from django.views.decorators.http import require_safe

from chardata.data_versions import current_data_version
from chardata.models import Char
from chardata.presets import (DEFAULT_PLAY_MODE, DEFAULT_PRIORITY, GUARD_KIND, PRIORITY_BY_KEY,
                              play_modes, setup_boxes, solved_aspects, with_mode_boxes,
                              within_focus_limit)
from chardata.smart_build import (ALL_ASPECTS, get_standard_weights, inert_aspects,
                                  level_minimums)
from chardata.version_compat import class_exists_in_version
from chardata.weights_minimums import _caps, block_context, page_state
from fashionistapulp.dofus_constants import CHARACTER_CLASSES
from fashionistapulp.structure import get_current_game_version, set_current_game_version
from fashionistapulp.temporix import version_has_temporix

MAX_LEVEL = 200
CACHE_ENTRIES = 512
CACHE_SECONDS = 600
BOX_PREFIX = 'check_'
SWITCH_VALUES = ('on', 'off')
_NUMBER = re.compile(r'[0-9]{1,3}')


class _InvalidPreview(Exception):
    def __init__(self, field):
        super().__init__(field)
        self.field = field


@contextmanager
def _in_version(game_version):
    previous = get_current_game_version()
    set_current_game_version(game_version)
    try:
        yield
    finally:
        set_current_game_version(previous)


def _preview_char(game_version, char_class, level, aspects, priority, play_mode, temporix):
    boxes = with_mode_boxes(aspects, play_mode)
    solved = solved_aspects(boxes, priority)
    char = Char(char_class=char_class, level=level, game_version=game_version,
                aspects=pickle.dumps(solved), minimum_stats=pickle.dumps({}),
                options=pickle.dumps({'temporix': True} if temporix else {}))
    char.stats_weight = pickle.dumps(get_standard_weights(char))
    char.minimum_stats = pickle.dumps(level_minimums(char, solved))
    char.aspects = pickle.dumps(boxes)
    return char


def preview_state(game_version, char_class, level, aspects,
                  priority=DEFAULT_PRIORITY, play_mode=DEFAULT_PLAY_MODE, temporix=False):
    with _in_version(game_version):
        char = _preview_char(game_version, char_class, level, aspects, priority, play_mode,
                             temporix)
        return dict(page_state(char), caps=_caps(char))


def panel_context(game_version):
    """What the read-only panel on /setup/ renders: the rows of the version, filled in by the first preview."""
    char_class = sorted(name for name in CHARACTER_CLASSES
                        if class_exists_in_version(name, game_version))[0]
    with _in_version(game_version):
        char = _preview_char(game_version, char_class, MAX_LEVEL, frozenset(),
                             DEFAULT_PRIORITY, DEFAULT_PLAY_MODE, False)
        context = block_context(char)
        context['wm_state'] = dict(context['wm_state'], caps=_caps(char))
    for section in context['sections']:
        section['open'] = section['key'] == 'apmprange'
    context.update(combined_open=False, others=[], temporix_on=False, wm_setup=True,
                   temporix_switch=version_has_temporix(game_version), guard_kinds=dict(GUARD_KIND))
    return context


@lru_cache(maxsize=CACHE_ENTRIES)
def _preview_body(game_version, data_version, char_class, level, aspects, priority,
                  play_mode, temporix):
    state = preview_state(game_version, char_class, level, aspects, priority, play_mode,
                          temporix)
    return json.dumps(state, separators=(',', ':')).encode('utf-8')


def _single(query, name, default=None):
    values = query.getlist(name)
    if not values:
        if default is None:
            raise _InvalidPreview(name)
        return default
    if len(values) > 1:
        raise _InvalidPreview(name)
    return values[0]


def _switch(query, name):
    value = _single(query, name)
    if value not in SWITCH_VALUES:
        raise _InvalidPreview(name)
    return value == 'on'


def _ticked_aspects(query, game_version):
    offered = setup_boxes(game_version) - set(inert_aspects(game_version))
    ticked = set()
    for name in query:
        if not name.startswith(BOX_PREFIX):
            continue
        if name[len(BOX_PREFIX):] not in offered:
            raise _InvalidPreview(name)
        if _switch(query, name):
            ticked.add(name[len(BOX_PREFIX):])
    aspects = frozenset(ticked & ALL_ASPECTS)
    if not within_focus_limit(aspects):
        raise _InvalidPreview('focus')
    return aspects


def _parsed_query(query, game_version):
    char_class = _single(query, 'class')
    if char_class not in CHARACTER_CLASSES or not class_exists_in_version(char_class, game_version):
        raise _InvalidPreview('class')
    text = _single(query, 'level')
    if not _NUMBER.fullmatch(text) or not 1 <= int(text) <= MAX_LEVEL:
        raise _InvalidPreview('level')
    aspects = _ticked_aspects(query, game_version)
    priority = _single(query, 'priority', DEFAULT_PRIORITY)
    if priority not in PRIORITY_BY_KEY:
        raise _InvalidPreview('priority')
    play_mode = _single(query, 'play_mode', DEFAULT_PLAY_MODE)
    if play_mode not in [key for key, _label in play_modes(game_version)]:
        raise _InvalidPreview('play_mode')
    temporix = False
    if 'temporix' in query:
        if not version_has_temporix(game_version):
            raise _InvalidPreview('temporix')
        temporix = _switch(query, 'temporix')
    return char_class, int(text), aspects, priority, play_mode, temporix


@require_safe
def setup_preview(request):
    game_version = getattr(request, 'game_version', 'dofus3')
    try:
        parsed = _parsed_query(request.GET, game_version)
    except _InvalidPreview as problem:
        return JsonResponse({'error': 'invalid', 'field': problem.field}, status=400)
    response = HttpResponse(
        _preview_body(game_version, current_data_version(game_version), *parsed),
        content_type='application/json')
    patch_cache_control(response, max_age=CACHE_SECONDS)
    return response
