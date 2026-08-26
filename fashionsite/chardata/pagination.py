# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Which page numbers a long list should link to.

Lived in encyclopedia_view.py while the encyclopedia was its only caller. Four
lists use it now -- items, sets, monsters and shared builds -- and none of them
is the encyclopedia, so it moved here rather than making three views import
from a fourth.
"""

#: A list only has to be shallow, not fully linked: linking every tenth page
#: keeps any page a few clicks away without printing eighty numbers.
#:
#: What it replaced was a chain. Page 1 of the 99-page encyclopedia offered
#: 2, 3, 4 and 99 and nothing else; /sharedbuilds/ offered only 2 and 83.
#: Breadth-first over the links actually rendered, before the change:
#:     encyclopedia    page 49 at 16 clicks, pages 50 to 53 at 17
#:     shared builds   page 42 at 41 clicks, the worst of the 83, mean 20.7
#: Both numbers were first reported smaller by whoever measured them, from a
#: loop bound rather than a walk. A depth is worth walking, not reasoning
#: about. A crawler spends its budget long before it gets that deep, and a
#: reader gives up sooner.
PAGINATION_STRIDE = 10

#: Pages either side of the current one that stay linked, so a reader stepping
#: through the list keeps a local view as well as the long jumps.
PAGINATION_NEIGHBOURS = 3


def pagination_items(page, stride=PAGINATION_STRIDE,
                     neighbours=PAGINATION_NEIGHBOURS):
    """Page numbers to render for `page`, with None where pages were skipped.

    The caller renders an int as a link (or as the current page) and None as an
    ellipsis. Returning the gaps rather than recomputing them in the template
    puts the marker where pages were actually dropped, instead of at two fixed
    positions that stopped meaning anything once the stride was added.

    With the defaults every page is at most three clicks from the first: one to
    the nearest multiple of ten, which is never more than five away, then at
    most two more through the neighbours of that page.
    """
    total = page.paginator.num_pages
    shown = {1, total, page.number}
    shown.update(n for n in range(page.number - neighbours,
                                  page.number + neighbours + 1)
                 if 1 <= n <= total)
    shown.update(range(stride, total + 1, stride))

    rendered = []
    previous = 0
    for number in sorted(shown):
        if number > previous + 1:
            rendered.append(None)
        rendered.append(number)
        previous = number
    return rendered
