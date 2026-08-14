# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Every ad unit on the site goes through here.

Ten templates each spelled out the same include, so the rules that keep a page
readable lived nowhere and could not be enforced. One tag means one place for
the page ceiling, for what loads on scroll and for what a unit reserves.

    {% load ads %}
    {% ad_unit 'content_top' %}
    {% ad_feed forloop.counter forloop.revcounter0 every=12 %}
    {% ad_rails %}
"""
from django import template
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe

register = template.Library()

# What the reader scrolls through at most. Past this a call is a no-op, so a
# template can ask for a unit without knowing what the rest of the page already
# asked for. The gutter rails are outside this count: they sit beside the
# content column rather than in it, and squeezing them out to make room for a
# unit in the text would be the wrong trade.
PAGE_CEILING = 5

# A list gets one unit every FEED_EVERY rows, FEED_LIMIT of them at most, and
# none within FEED_TAIL rows of the end where the page already ends.
FEED_EVERY = 12
FEED_LIMIT = 3
FEED_TAIL = 2

# Units above the fold are worth their cost at once. The rest are built when
# the reader comes near them, which also keeps a rail out of the page until the
# screen is wide enough to show it. home_top keeps its name but sits under the
# buttons now, so it waits like the others.
EAGER_SLOTS = ('content_top',)


def _claim(context):
    """Take one of the page's slots, or None once the ceiling is reached."""
    request = context.get('request')
    if request is None:
        return None
    taken = getattr(request, 'fm_ads_rendered', 0)
    if taken >= PAGE_CEILING:
        return None
    request.fm_ads_rendered = taken + 1
    return taken + 1


def _render(context, slot_name, css_class, ad_format='auto', full_width=True,
            counted=True):
    if not context.get('ads_enabled'):
        return ''
    slot = (context.get('ad_slots') or {}).get(slot_name)
    if not slot:
        return ''
    if counted and _claim(context) is None:
        return ''
    return render_to_string('chardata/ad_slot.html', {
        'ads_enabled': True,
        'ad_slot': slot,
        'ad_client': context.get('ad_client'),
        'extra_class': css_class,
        'ad_format': ad_format,
        'ad_full_width': 'true' if full_width else 'false',
        'ad_lazy': slot_name not in EAGER_SLOTS,
    })


@register.simple_tag(takes_context=True)
def ad_unit(context, slot_name, css_class='fm-ad-inline', ad_format='auto'):
    return _render(context, slot_name, css_class, ad_format)


@register.simple_tag(takes_context=True)
def ad_feed(context, counter, from_end, every=FEED_EVERY, limit=FEED_LIMIT,
            slot_name='list_inline'):
    """One unit every few rows of a long list.

    Called with forloop.counter and forloop.revcounter0, so a list shorter than
    one interval, and the rows next to the end, are left alone. `every` is per
    list: a page of 39 item cards and a page of 24 build cards do not want the
    same spacing.
    """
    try:
        counter, from_end = int(counter), int(from_end)
        every, limit = int(every), int(limit)
    except (TypeError, ValueError):
        return ''
    if every < 1 or counter < 1 or counter % every or from_end < FEED_TAIL:
        return ''
    if counter // every > limit:
        return ''
    return _render(context, slot_name, 'fm-ad-feed')


@register.simple_tag(takes_context=True)
def ad_rails(context, slot_name='rail'):
    """The two gutters a 1200px shell leaves empty on a wide screen.

    Both sides carry the same unit id. The CSS keeps them out of the page until
    the gutter is genuinely wide enough, and a unit that is display:none never
    intersects, so it is never built and never asked to fill.
    """
    left = _render(context, slot_name, 'fm-ad-rail fm-ad-rail-left',
                   'vertical', full_width=False, counted=False)
    if not left:
        return ''
    right = _render(context, slot_name, 'fm-ad-rail fm-ad-rail-right',
                    'vertical', full_width=False, counted=False)
    return mark_safe(left + right)
