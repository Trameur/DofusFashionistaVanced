# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""{% capture as name %}...{% endcapture %}: render once, reuse in the page; blocks nested inside still belong to the template's block tree."""

from django import template
from django.utils.safestring import mark_safe

register = template.Library()


class CaptureNode(template.Node):
    def __init__(self, nodelist, variable):
        self.nodelist = nodelist
        self.variable = variable

    def render(self, context):
        # Rendered under the page's own autoescaping, so the text is already
        # escaped once; marking it safe keeps {{ var }} from escaping it twice.
        context[self.variable] = mark_safe(self.nodelist.render(context))
        return ''


@register.tag
def capture(parser, token):
    bits = token.split_contents()
    if len(bits) != 3 or bits[1] != 'as':
        raise template.TemplateSyntaxError(
            "'%s' expects: {%% capture as name %%}" % bits[0])
    nodelist = parser.parse(('endcapture',))
    parser.delete_first_token()
    return CaptureNode(nodelist, bits[2])
