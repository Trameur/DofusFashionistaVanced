# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""What the two pages that read a screenshot have to agree on.

The inventory reads one tooltip and the text import reads a whole build's
worth of them, but it is the same reader underneath: the same five Tesseract
models, entered from the same list. Two copies of that list would drift, and
the drift would be invisible: a language missing from one page is not an
error there, it is simply a language the reader cannot be asked for.

The pinned script tag is deliberately NOT here. `tests_third_party_integrity`
finds third party loads by reading the templates for a literal
`element.src = "https://..."`, so moving the address into a context variable
would take both pages out of that audit while looking like tidying up. The
address stays written out in each template, and a test here checks the two
copies say the same thing.
"""

#: The reader's languages, with the Tesseract model each one needs. Same five
#: the site itself speaks.
OCR_LANGUAGES = [('en', 'eng'), ('fr', 'fra'), ('es', 'spa'),
                 ('pt', 'por'), ('de', 'deu')]


def language_options(language):
    """The list a template renders, with the reader's own language first
    selected: it is the one their game is almost certainly in."""
    return [{'code': code, 'tesseract': tesseract,
             'selected': code == language}
            for code, tesseract in OCR_LANGUAGES]
