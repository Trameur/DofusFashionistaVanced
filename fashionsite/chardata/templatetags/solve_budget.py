# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The seconds a solve of a build may take, for the waiting screen."""
import logging

from django import template

register = template.Library()
logger = logging.getLogger(__name__)


@register.filter(name='solve_budget_seconds')
def solve_budget_seconds(char):
    from chardata.fashion_action import GUARD_BUDGET_SECONDS, solve_budget_seconds as budget
    if getattr(char, 'pk', None) is None:
        return GUARD_BUDGET_SECONDS
    try:
        return budget(char)
    except Exception:
        logger.exception('could not read the solve budget of char %s', char.pk)
        return GUARD_BUDGET_SECONDS
