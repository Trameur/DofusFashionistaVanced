# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""{% capture as name %}...{% endcapture %}: render once, reuse in the page.

The title of a page and its description each live in a block a child
template fills. Open Graph wants the same two sentences again, and a block
can appear only once in a template, so every page either overrode the
Open Graph block by hand or fell back to the site-wide sentence. On 2026-09-11
fifteen of the sixteen hub pages fell back: a link to the set builder pasted
in a chat previewed as "Equipment Set Optimizer", the same as every other
page.

Blocks nested inside this tag still belong to the template's block tree
(get_nodes_by_type walks the tag's nodelist), so a child's override renders
here, and the rendered text is kept for the rest of the page.
"""

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
