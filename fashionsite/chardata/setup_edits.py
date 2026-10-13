# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The weights and minimums a player edited on /setup/, saved on the new build."""
import math
import re

from chardata.weights_minimums import MINIMUM_LIMIT, merge_minimum_fields, page_state
from chardata.wizard_sliders import apply_weight_fields

WEIGHT_PREFIX = 'weight_'
MINIMUM_PREFIX = 'min_'
NUMBER = re.compile(r'[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?')


def posted_integer(raw):
    """The whole number a typed value stands for, halves rounding up as the panel's boxes do, or None."""
    text = (raw or '').strip()
    if not NUMBER.fullmatch(text):
        return None
    number = float(text)
    if not math.isfinite(number):
        return None
    floor = math.floor(number)
    return floor + 1 if number - floor >= 0.5 else floor


def _posts_edits(post):
    return any(name.startswith((WEIGHT_PREFIX, MINIMUM_PREFIX)) for name in post)


def touched_fields(char, post):
    """(weights, minimums): the posted values that differ from what the build holds, as page fields."""
    state = page_state(char)
    weights = {}
    for key, shown in state['weights'].items():
        value = posted_integer(post.get(WEIGHT_PREFIX + key))
        if value is not None and value != shown:
            weights[WEIGHT_PREFIX + key] = str(value)
    minimums = {}
    for key, stored in state['minimums'].items():
        name = MINIMUM_PREFIX + key
        if name not in post:
            continue
        raw = (post.get(name) or '').strip()
        if raw == '':
            if stored != '':
                minimums[name] = ''
            continue
        value = posted_integer(raw)
        if value is not None and abs(value) <= MINIMUM_LIMIT and value != stored:
            minimums[name] = str(value)
    return weights, minimums


def apply_touched_fields(char, post):
    """Saves the minimums, then the weights, the player changed; a build nothing was edited on stays as it is."""
    if not _posts_edits(post):
        return
    weights, minimums = touched_fields(char, post)
    if minimums:
        merge_minimum_fields(char, minimums)
    if weights:
        apply_weight_fields(char, weights, WEIGHT_PREFIX)
