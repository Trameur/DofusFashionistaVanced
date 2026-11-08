# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""Store the site history snapshot shown in the staff page. Reads a file, or standard input with -."""
import json
import sys

from django.core.management.base import BaseCommand, CommandError

from chardata import admin_history
from chardata.models import SiteSetting


class Command(BaseCommand):
    help = 'Validate a site history snapshot and store it, replacing the previous one.'

    def add_arguments(self, parser):
        parser.add_argument('path', help='JSON file, or - for standard input')

    def handle(self, *args, **options):
        raw = self._read(options['path'])
        try:
            snapshot = json.loads(raw.decode('utf-8'))
        except (UnicodeDecodeError, ValueError, RecursionError):
            raise CommandError('The input is not valid UTF-8 JSON.')
        problems = admin_history.validate(snapshot)
        if problems:
            raise CommandError('The snapshot was refused:\n' + '\n'.join(problems))
        SiteSetting.objects.update_or_create(
            key=admin_history.KEY,
            defaults={'value': json.dumps(snapshot, separators=(',', ':'),
                                          ensure_ascii=False)})
        admin_history.forget()
        self.stdout.write('schema %d, as_of %s, %d series, %d eras, %d milestones, '
                          '%d methods, %d classes, %d levels' % (
                              snapshot['schema'], snapshot['as_of'], len(snapshot['series']),
                              len(snapshot['eras']), len(snapshot['milestones']),
                              len(snapshot['methods']), len(snapshot['classes']),
                              len(snapshot['levels'])))

    def _read(self, path):
        limit = admin_history.MAX_BYTES
        try:
            if path == '-':
                raw = sys.stdin.buffer.read(limit + 1)
            else:
                with open(path, 'rb') as handle:
                    raw = handle.read(limit + 1)
        except OSError as error:
            raise CommandError('Cannot read the input: %s' % error.strerror)
        if len(raw) > limit:
            raise CommandError('The input is larger than %d bytes.' % limit)
        return raw
