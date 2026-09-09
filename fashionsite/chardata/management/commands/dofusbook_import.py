# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = ('Read a public DofusBook build from its link and print what we '
            'would import. Reads only, creates nothing.')

    #: Why a command before a page. Everything risky about this feature is on
    #: their side: an undocumented endpoint, a Referer check, and build ids
    #: that repeat across their three hosts. This makes all of that inspectable
    #: by hand, which is what a page cannot do.

    def add_arguments(self, parser):
        parser.add_argument('url', help='a dofusbook.net build link')

    def handle(self, *args, **options):
        from chardata.dofusbook_import import ImportError_, read_build
        from fashionistapulp.structure import get_structure

        try:
            build = read_build(options['url'])
        except ImportError_ as erreur:
            raise CommandError('refused: %s' % erreur.reason)

        self.stdout.write(self.style.SUCCESS(
            '%s  (%s, level %s, %d items)'
            % (build['name'] or '(unnamed)', build['game_version'],
               build['level'], len(build['item_ids']))))
        structure = get_structure(build['game_version'])
        for item_id in build['item_ids']:
            item = structure.get_item_by_id(item_id)
            self.stdout.write('  %-8s %-38s level %s'
                              % (item_id, getattr(item, 'name', '?'),
                                 getattr(item, 'level', '?')))
        for name in build['missing']:
            self.stdout.write(self.style.WARNING('  not in our catalogue: %s'
                                                 % name))
        if build['class_is_unknown']:
            self.stdout.write('')
            self.stdout.write(
                'Their character_class is their own numbering, not Ankama\'s, '
                'and nothing in the payload names the class, so the player '
                'picks it rather than us guessing.')
