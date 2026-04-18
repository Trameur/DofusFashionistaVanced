# Copyright (C) 2020 The Dofus Fashionista
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

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from chardata.models import BuildView


class Command(BaseCommand):
    help = 'Delete BuildView records older than 24 hours to keep database clean'

    def handle(self, *args, **options):
        cutoff_time = timezone.now() - timedelta(hours=24)
        deleted_count, _ = BuildView.objects.filter(viewed_at__lt=cutoff_time).delete()
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully deleted {deleted_count} old view records')
        )
