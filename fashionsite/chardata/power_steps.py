# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The steps of the /setup/ power slider: how long a search may run and how far from the best it may stop."""
from collections import namedtuple

from django.utils.formats import number_format
from django.utils.translation import gettext, gettext_lazy as _

from chardata.char_blobs import read_char_blob
from chardata.options import set_options
from fashionistapulp.lpproblem import TIME_LIMIT_SECONDS

POWER_FIELD = 'power'
DEFAULT_POWER = 'standard'

PowerStep = namedtuple('PowerStep', 'key label seconds gap')

POWER_STEPS = (
    PowerStep('flash', _('Flash'), 10, 0.03),
    PowerStep('fast', _('Fast'), 30, 0.01),
    PowerStep(DEFAULT_POWER, _('Standard'), TIME_LIMIT_SECONDS, 0),
)
POWER_BY_KEY = {step.key: step for step in POWER_STEPS}


def offered_power(key):
    """The step key if the slider offers it, else Standard."""
    return key if key in POWER_BY_KEY else DEFAULT_POWER


def stored_power(char):
    """The build's step; a build without one searches as every build always did."""
    options = read_char_blob(char.options, {}, 'options', char)
    return POWER_BY_KEY[offered_power(options.get(POWER_FIELD))]


def apply_posted_power(char, post):
    """Stores the posted step on a new build; Standard, or no slider, leaves the options as they always were."""
    key = offered_power(post.get(POWER_FIELD))
    if key != DEFAULT_POWER:
        set_options(char, {POWER_FIELD: key})


def gap_percent(gap):
    """A relative gap as the percent the page writes, whole when it is."""
    percent = round(gap * 100, 6)
    return number_format(percent, 0 if percent == int(percent) else 1)


def step_text(step):
    if step.gap:
        return gettext('The search stops as soon as its set is within %(gap)s%% of the best on your '
                       'criteria, or after %(seconds)s s per search. The build page tells you which.') % {
            'gap': gap_percent(step.gap), 'seconds': step.seconds}
    return gettext('Looks for the best set on your criteria for up to %(seconds)s s per search. '
                   'The build page tells you whether it was proven.') % {'seconds': step.seconds}


def power_context():
    """The slider of the /setup/ page, Standard selected."""
    steps = [{'key': step.key, 'label': step.label, 'text': step_text(step), 'index': index}
             for index, step in enumerate(POWER_STEPS)]
    default = [step for step in steps if step['key'] == DEFAULT_POWER][0]
    return {'steps': steps, 'default': DEFAULT_POWER, 'default_index': default['index'],
            'default_label': default['label'], 'last_index': len(steps) - 1}
