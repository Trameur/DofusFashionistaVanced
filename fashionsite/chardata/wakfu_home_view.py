# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""The Wakfu landing page."""

from chardata.util import set_response


def home(request):
    return set_response(request, 'chardata/wakfu/home.html', {})
