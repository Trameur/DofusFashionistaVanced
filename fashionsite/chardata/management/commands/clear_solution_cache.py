# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

"""Forget every memoized solve, so the next one runs on the data just shipped.

The solver's memory is keyed on what the player asked, never on the catalogue
or the solver code, so after a deploy that changed either it keeps handing
back sets optimized for the old ones: on 2026-09-18 the malus of five versions
moved to their best roll and every cached set still weighed the old ones. Most
deploys carry data, so docker-entrypoint.sh runs this at every boot.

Only the memory goes. Saved builds (Char.minimal_solution), their history and
the counters stay.
"""
from django.core.management.base import BaseCommand
from django.db import connection

from chardata.models import SolutionMemory


class Command(BaseCommand):
    help = 'Forget every memoized solve (the saved builds stay).'

    def handle(self, *args, **options):
        count = SolutionMemory.objects.count()
        if not self._truncate():
            SolutionMemory.objects.all().delete()
        self.stdout.write('Forgot %d memoized solve(s).' % count)

    def _truncate(self):
        """Instant on MySQL, where a DELETE walks every row and holds the
        lock; it needs the DROP privilege, so a refusal falls back."""
        if connection.vendor != 'mysql':
            return False
        try:
            with connection.cursor() as cursor:
                cursor.execute('TRUNCATE TABLE %s' % connection.ops.quote_name(
                    SolutionMemory._meta.db_table))
        except Exception as error:
            self.stderr.write('TRUNCATE refused (%s), deleting instead.' % error)
            return False
        return True
