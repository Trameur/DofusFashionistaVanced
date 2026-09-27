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
        from fashionistapulp.wakfu_value_rules import RULES

        parser.add_argument('--level', type=int, default=200,
                            help='character level (default 200)')
        parser.add_argument('--weights', default=None,
                            help='comma separated stat=weight, e.g. %s; '
                                 'replaces the damage model' % self.EXEMPLE)
        parser.add_argument('--elements', default='fire',
                            help='elements the damage role casts, comma '
                                 'separated (default fire)')
        parser.add_argument('--reach', default='distance',
                            choices=('distance', 'melee'),
                            help='mastery the role hits with (default distance)')
        parser.add_argument('--defense', type=float, default=None,
                            help='weight of log(effective life) against '
                                 'log(turn damage) (default %s)'
                                 % RULES['defense_weight'].value)
        parser.add_argument('--rounds', type=int, default=5,
                            help='most damage model solves (default 5)')
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
        from fashionistapulp import wakfu_value
        import os

        chemin = get_items_db_path('wakfu')
        if not os.path.exists(chemin):
            # The database is gitignored, so a fresh checkout has none.
            raise CommandError(
                'no Wakfu database at %s. Build it with '
                'python update_data_wakfu.py' % chemin)

        role = weights = None
        if options['weights'] is not None:
            weights = self.hand_weights(options['weights'])
        else:
            try:
                role = wakfu_value.DamageDealer(
                    options['elements'].split(','), options['reach'],
                    options['defense'])
            except ValueError as error:
                raise CommandError(str(error))

        forbidden = [int(x) for x in options['forbid'].split(',') if x.strip()]
        structure = get_structure('wakfu')
        if not options['allow_legacy']:
            legacy = default_exclusions(structure)
            forbidden.extend(legacy)
            self.stdout.write('leaving out %d legacy items (--allow-legacy '
                              'lets the solver pick them)' % len(legacy))

        start = time.time()
        model = None
        if role is None:
            build = WakfuBuild(structure, options['level'], weights, forbidden)
            worn = build.build().solve()
        else:
            model = wakfu_value.solve(structure, options['level'], role,
                                      forbidden, options['rounds'])
            build = model.best.build if model.best else None
            worn = model.best.worn if model.best else None
        duration = time.time() - start

        if worn is None:
            self.stdout.write(self.style.WARNING(
                'no legal Wakfu set at level %d for %s (%.1fs)'
                % (options['level'],
                   'those weights' if role is None else 'that role', duration)))
            return

        self.stdout.write(self.style.SUCCESS(
            'level %d, %d pieces, solved in %.1fs'
            % (options['level'], len(worn), duration)))
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
        if model is not None:
            self.print_model(role, options['level'], model)

    def hand_weights(self, text):
        weights = {}
        for part in text.split(','):
            if not part.strip():
                continue
            if '=' not in part:
                raise CommandError('weights look like %s, got %r'
                                   % (self.EXEMPLE, part))
            key, number = part.split('=', 1)
            try:
                weights[key.strip().lower()] = float(number)
            except ValueError:
                raise CommandError('%r is not a number' % number)
        if not weights:
            raise CommandError('give at least one stat=weight')
        return weights

    def print_model(self, role, level, model):
        from fashionistapulp import wakfu_value

        self.stdout.write('')
        self.stdout.write('  damage model: %s, %s, defense %g; %d rounds, %s'
                          % ('+'.join(role.elements), role.reach, role.defense,
                             len(model.rounds),
                             'settled' if model.converged
                             else 'not settled, best round kept'))
        self.stdout.write('  kept at least: ' + ', '.join(
            '%s %s' % (key.upper(), lowest)
            for key, lowest in sorted(role.minimums().items())))
        for number, one in enumerate(model.rounds, 1):
            self.stdout.write(
                '  round %d%s value %.4f  damage x%.2f over %d AP  crit %d%%  '
                'effective life %.0f'
                % (number, ' *' if one is model.best else '  ', one.value,
                   wakfu_value.damage_factor(role, one.totals),
                   one.totals.get('ap', 0),
                   round(100 * wakfu_value.critical_chance(
                       one.totals.get('ferocity', 0))),
                   wakfu_value.effective_life(level, one.totals)))
        weights = model.best.weights
        self.stdout.write('  weights of the kept round, percent of value per point')
        self.stdout.write('  ' + '  '.join('%s %.4g' % (key.upper(), weights[key])
                                           for key in sorted(weights)
                                           if weights[key]))

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
