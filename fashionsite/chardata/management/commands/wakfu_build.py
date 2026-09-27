# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

import time

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = ('Solve one Wakfu set and print it. The only way to try Wakfu by '
            'hand: it has no page, on purpose.')

    #: Why this is a command and not a page. Wakfu is registered
    #: experimental=True, and game_versions.py states the rule it stands for:
    #: "real everywhere the data pipeline is concerned and invisible everywhere
    #: a reader could reach it". version_keys() drops it, so /wakfu/ is a 404
    #: and no template, no url and no button mentions it. A command adds no
    #: reader surface at all, so trying Wakfu locally cannot start leaking it
    #: into the site by accident.
    EXEMPLE = 'hp=1,ap=200,mp=150'

    def add_arguments(self, parser):
        parser.add_argument('--level', type=int, default=200,
                            help='character level (default 200)')
        parser.add_argument('--weights', default=self.EXEMPLE,
                            help='comma separated stat=weight, e.g. ' + self.EXEMPLE)
        parser.add_argument('--forbid', default='',
                            help='comma separated item ids to leave out')
        parser.add_argument('--allow-legacy', action='store_true',
                            help='let the solver pick legacy items, left out '
                                 'by default')

    def handle(self, *args, **options):
        from fashionistapulp.fashionista_config import get_items_db_path
        from fashionistapulp.structure import get_structure
        from fashionistapulp.wakfu_exclusions import default_exclusions
        from fashionistapulp.wakfu_model import WakfuBuild
        from fashionistapulp.wakfu_slots import SLOTS
        import os

        chemin = get_items_db_path('wakfu')
        if not os.path.exists(chemin):
            # The database is gitignored, so a fresh checkout has none.
            raise CommandError(
                'no Wakfu database at %s. Build it with '
                'python update_data_wakfu.py' % chemin)

        weights = {}
        for morceau in options['weights'].split(','):
            if not morceau.strip():
                continue
            if '=' not in morceau:
                raise CommandError('weights look like %s, got %r'
                                   % (self.EXEMPLE, morceau))
            cle, valeur = morceau.split('=', 1)
            try:
                weights[cle.strip().lower()] = float(valeur)
            except ValueError:
                raise CommandError('%r is not a number' % valeur)
        if not weights:
            raise CommandError('give at least one stat=weight')

        forbidden = [int(x) for x in options['forbid'].split(',') if x.strip()]
        structure = get_structure('wakfu')
        if not options['allow_legacy']:
            legacy = default_exclusions(structure)
            forbidden.extend(legacy)
            self.stdout.write('leaving out %d legacy items (--allow-legacy '
                              'lets the solver pick them)' % len(legacy))

        debut = time.time()
        build = WakfuBuild(structure, options['level'], weights, forbidden)
        worn = build.build().solve()
        duree = time.time() - debut

        if worn is None:
            self.stdout.write(self.style.WARNING(
                'no legal Wakfu set at level %d for those weights (%.1fs)'
                % (options['level'], duree)))
            return

        self.stdout.write(self.style.SUCCESS(
            'level %d, %d pieces, solved in %.1fs'
            % (options['level'], len(worn), duree)))
        if worn.full_set_dropped:
            self.stdout.write(self.style.WARNING(
                'the every-slot model gave no set (%s), so empty slots were '
                'allowed' % worn.full_set_status))
        empty = [slot for slot in SLOTS if slot not in worn]
        if empty:
            self.stdout.write('empty: %s' % ', '.join(
                '%s (%s)' % (slot, self.why_empty(worn, slot)) for slot in empty))
        for slot in sorted(worn):
            item = worn[slot]
            self.stdout.write('  %-16s %-38s level %s'
                              % (slot, getattr(item, 'name', item.id), item.level))

        spread = build.spread_lines(worn)
        if spread:
            self.stdout.write('')
            self.stdout.write('  spread lines and the elements each landed on')
            for slot, item, key, value, landed in spread:
                self.stdout.write('  %-16s %-38s %+d %s -> %s'
                                  % (slot, getattr(item, 'name', item.id),
                                     value, key.upper(),
                                     ', '.join(name.upper() for name in landed)))

        totals = build.totals(worn)
        interessantes = [cle for cle in sorted(totals) if totals[cle]]
        self.stdout.write('')
        self.stdout.write('  ' + '  '.join('%s %s' % (cle.upper(), totals[cle])
                                           for cle in interessantes))

    @staticmethod
    def why_empty(worn, slot):
        from fashionistapulp.wakfu_slots import BLOCKED_BY_TWO_HANDED
        if slot in worn.no_candidate:
            return 'no item fits'
        weapon = worn.get('FIRST_WEAPON')
        if (slot == BLOCKED_BY_TWO_HANDED and weapon is not None
                and 'two_handed' in (weapon.flags or ())):
            return 'two-handed weapon'
        return 'left empty by the solver'
