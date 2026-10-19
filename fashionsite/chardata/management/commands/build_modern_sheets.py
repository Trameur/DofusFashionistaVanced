# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Write the sheets the pages link from static/chardata/modern.css. Run it after every edit of that file."""
import io
import os

from django.core.management.base import BaseCommand

from chardata.modern_sheets import SHEETS, STATIC, build_sheets, read_source


class Command(BaseCommand):
    help = 'Cut modern-core.css, modern-solution.css, modern-encyclopedia.css and modern-rest.css from modern.css.'

    def handle(self, *args, **options):
        built = build_sheets(read_source())
        for key, name in SHEETS.items():
            with io.open(os.path.join(STATIC, name), 'w', encoding='utf-8', newline='\n') as handle:
                handle.write(built[key])
            self.stdout.write('%s: %d bytes' % (name, len(built[key].encode('utf-8'))))
