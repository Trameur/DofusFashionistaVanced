from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from fashionistapulp import weapon_forge
from fashionistapulp.dofus_constants import NEUTRAL
from fashionistapulp.translation import get_supported_language

from .translation_util import LOCALIZED_ELEMENTS

KIND_LABELS = {
    'damage': gettext_lazy('Smithmagic Potion'),
    'steal': gettext_lazy('Smithmagic Engraving'),
    'heal': gettext_lazy('Smithmagic Shard'),
}

AUTO = ''
NONE = 'none'


def _values(version, kind, element, tier, language):
    return {'item': (weapon_forge.item_name(version, kind, element, tier, language)
                     or str(KIND_LABELS[kind])),
            'element': str(LOCALIZED_ELEMENTS[element]),
            'rate': weapon_forge.percent(version, kind, tier)}


def conversion_line(version, kind, element, tier, language=None):
    values = _values(version, kind, element, tier, language or get_supported_language())
    if weapon_forge.rate_published(version):
        return _('%(item)s: %(element)s, %(rate)d%%') % values
    return _('%(item)s: %(element)s, %(rate)d%% (assumed, the game does not '
             'publish this rate)') % values


def conversion_lines(version, chosen, kinds=weapon_forge.KINDS, language=None):
    return [conversion_line(version, kind, element, tier, language)
            for kind, element, tier in weapon_forge.applied(chosen)
            if kind in kinds and weapon_forge.percent(version, kind, tier) is not None]


def option_text(version, kind, element, tier, language=None):
    values = _values(version, kind, element, tier, language or get_supported_language())
    return _('%(item)s (%(element)s, %(rate)d%%)') % values


def _current(stored, chosen, kind):
    if kind not in stored:
        return AUTO
    if stored[kind] is None:
        return NONE
    return weapon_forge.write_option(*chosen[kind])


def controls(version, chosen, stored, language=None):
    language = language or get_supported_language()
    chosen = chosen or {}
    stored = stored or {}
    found = []
    for kind in weapon_forge.KINDS:
        if kind not in chosen:
            continue
        options = [{'value': AUTO, 'text': _('Auto: best element for this build')},
                   {'value': NONE, 'text': str(LOCALIZED_ELEMENTS[NEUTRAL])}]
        options += [{'value': weapon_forge.write_option(element, tier),
                     'text': option_text(version, kind, element, tier, language)}
                    for element, tier in weapon_forge.offer(version, kind)]
        note = ''
        if not weapon_forge.rate_published(version):
            note = _('The game does not publish this rate: the site assumes '
                     '%(rate)d%%.') % {
                         'rate': weapon_forge.percent(version, kind, weapon_forge.STRONG)}
        found.append({'kind': kind, 'label': str(KIND_LABELS[kind]),
                      'current': _current(stored, chosen, kind),
                      'options': options, 'note': note})
    return found
