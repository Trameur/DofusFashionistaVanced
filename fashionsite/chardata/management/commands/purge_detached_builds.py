# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

from django.core.management.base import BaseCommand, CommandError

from chardata.account_deletion import (PURGE_BATCH_SIZE, blanked_builds,
                                       detached_builds, purge_detached_builds)


class Command(BaseCommand):
    help = ('Delete the builds that belong to nobody and are flagged deleted. '
            'Counts them and deletes nothing unless --go is given.')

    # Safety stop so a filter that deletes nothing cannot loop forever
    PASSES_MAX = 100000

    def add_arguments(self, parser):
        parser.add_argument('--go', action='store_true',
                            help='Really delete. Without it the command only counts.')
        parser.add_argument('--blanked', action='store_true',
                            help='Only the builds an account deletion left, '
                                 'those with an empty name.')
        parser.add_argument('--ids', default='',
                            help='Only these builds, as a comma separated list of ids.')

    def handle(self, *args, **options):
        try:
            ids = [int(part) for part in options['ids'].split(',') if part.strip()]
        except ValueError:
            raise CommandError('--ids takes a comma separated list of numbers.')
        selected = blanked_builds() if options['blanked'] else detached_builds()
        if ids:
            selected = selected.filter(pk__in=ids)
        waiting = selected.count()
        narrowed = options['blanked'] or ids
        if narrowed:
            self.stdout.write('%d other detached builds are left alone.'
                              % (detached_builds().count() - waiting))
        if not options['go']:
            self.stdout.write('%d detached builds would be deleted. '
                              'Run again with --go to delete them.' % waiting)
            return
        total = 0
        for _pass in range(self.PASSES_MAX):
            batch = list(selected.values_list('pk', flat=True)[:PURGE_BATCH_SIZE])
            if not batch:
                break
            # Without a budget: this runs by hand, not in a request
            removed = purge_detached_builds(batch, budget=float('inf'))
            total += removed
            if not removed:
                self.stdout.write(self.style.WARNING(
                    'stopped: a batch could not be deleted.'))
                break
        self.stdout.write(self.style.SUCCESS('Deleted %d detached builds' % total))
