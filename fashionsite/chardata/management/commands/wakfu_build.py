# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

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
        parser.add_argument('--elements', default=None,
                            help='elements the damage role casts, comma '
                                 'separated: fire, water, earth, air. Required '
                                 'unless --weights is given')
        parser.add_argument('--reach', default=None,
                            choices=('distance', 'melee'),
                            help='mastery the role hits with. Required unless '
                                 '--weights is given')
        parser.add_argument('--defense', type=float, default=None,
                            help='weight of log(effective life) against '
                                 'log(turn damage) (default %s)'
                                 % RULES['defense_weight'].value)
        parser.add_argument('--rounds', type=int, default=5,
                            help='most damage model solves (default 5)')
        parser.add_argument('--forbid', default='',
                            help='comma separated item ids to leave out')
        parser.add_argument('--lock', default='',
                            help='comma separated items every set wears, each an '
                                 'id or id@POSITION (e.g. 12345@LEFT_HAND)')
        parser.add_argument('--seconds', type=float, default=90,
                            help='wall time the whole solve may take (default 90)')
        parser.add_argument('--allow-legacy', action='store_true',
                            help='let the solver pick legacy items, left out '
                                 'by default')
        parser.add_argument('--class-id', type=int, default=None,
                            help="Ankama class id: print that class's best turn "
                                 'on the kept set (damage model only)')
        parser.add_argument('--class-turn', action='store_true',
                            help="solve on the best turn of --class-id, every AP "
                                 'total priced by that turn, instead of AP x '
                                 'mastery; the generic set is kept when that turn '
                                 'values it higher (damage model only)')
        parser.add_argument('--movement', type=float, default=None,
                            help='share of its MP the role spends moving, 0 to 1, '
                                 'in the --class-id turn and the --class-turn solve '
                                 '(default none: every MP goes to spells)')

    def handle(self, *args, **options):
        from fashionistapulp.fashionista_config import get_items_db_path
        from fashionistapulp.structure import get_structure
        from fashionistapulp.wakfu_model import PROVEN, TIME_LIMIT
        from fashionistapulp.wakfu_slots import SLOTS
        from fashionistapulp import wakfu_solve
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
        for flag, given in (('--class-turn', options['class_turn']),
                            ('--movement', options['movement'] is not None)):
            if given and (weights is not None or not options['class_id']):
                raise CommandError('%s needs --class-id and no --weights' % flag)
        if weights is None:
            try:
                role = wakfu_solve.make_role(
                    options['elements'], options['reach'], options['defense'],
                    options['movement'])
            except ValueError as error:
                raise CommandError(str(error))
        locked = self.read_locks(options['lock'], SLOTS)

        forbidden = [int(x) for x in options['forbid'].split(',') if x.strip()]
        structure = get_structure('wakfu')
        try:
            if role is None:
                result = wakfu_solve.solve_weights(
                    structure, level=options['level'], weights=weights,
                    forbidden=forbidden, locked=locked,
                    allow_legacy=options['allow_legacy'], seconds=options['seconds'])
            else:
                result = wakfu_solve.solve_build(
                    structure, level=options['level'],
                    elements=options['elements'], reach=options['reach'],
                    class_id=options['class_id'],
                    forbidden=forbidden, locked=locked,
                    allow_legacy=options['allow_legacy'],
                    movement=options['movement'], seconds=options['seconds'],
                    defense=options['defense'], rounds=options['rounds'],
                    on_class_turn=options['class_turn'])
        except wakfu_solve.WakfuIllegalSet as error:
            raise CommandError('the solver returned an illegal set: %s' % error)
        except ValueError as error:
            raise CommandError(str(error))
        worn, build, model, turn = result.worn, result.build, result.model, result.turn_model
        duration = result.seconds
        if not options['allow_legacy']:
            self.stdout.write('leaving out %d legacy items (--allow-legacy '
                              'lets the solver pick them)' % result.legacy_left_out)

        if worn is None:
            self.stdout.write(self.style.WARNING(
                'no legal Wakfu set at level %d for %s (%.1fs)'
                % (options['level'],
                   'those weights' if role is None else 'that role', duration)))
            self.stdout.write('reason: %s' % (
                'no set within the time limit' if result.reason == TIME_LIMIT
                else result.reason))
            return

        self.stdout.write(self.style.SUCCESS(
            'level %d, %d pieces, solved in %.1fs'
            % (options['level'], len(worn), duration)))
        self.stdout.write('proven best' if result.status == PROVEN
                          else 'best set found within the time limit')
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
            self.print_model(role, options['level'], model, turn)
            if options['class_id']:
                self.print_turn(role, options['level'], options['class_id'], totals)
            self.stdout.write('')
            self.stdout.write('  systems the model leaves out: '
                              + ', '.join(wakfu_solve.SYSTEMS_NOT_COUNTED))

    @staticmethod
    def read_locks(text, slots):
        """[(item id, position or None)] of --lock."""
        out = []
        for part in text.split(','):
            part = part.strip()
            if not part:
                continue
            ident, _at, position = part.partition('@')
            try:
                number = int(ident)
            except ValueError:
                raise CommandError('--lock takes an item id or id@POSITION, got %r' % part)
            if position and position not in slots:
                raise CommandError('%r is not a slot; slots are %s' % (position, ', '.join(slots)))
            out.append((number, position or None))
        return out

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

    def print_model(self, role, level, model, turn=None):
        from fashionistapulp import wakfu_value

        self.stdout.write('')
        self.stdout.write('  damage model: %s, %s, defense %g%s; %d rounds, %s'
                          % ('+'.join(role.elements), role.reach, role.defense,
                             ', on the class turn' if turn is not None else '',
                             len(model.rounds),
                             'settled' if model.converged
                             else 'not settled, best round kept'))
        self.stdout.write('  kept at least: ' + ', '.join(
            '%s %s' % (key.upper(), lowest)
            for key, lowest in sorted(role.minimums().items())))
        labels = [('round %d%s' % (number, ' *' if one is model.best else '  '), one)
                  for number, one in enumerate(model.rounds, 1)]
        generic = not any(one is model.best for one in model.rounds)
        if generic:
            labels.append(('generic set *', model.best))
        for label, one in labels:
            if turn is None:
                damage = 'damage x%.2f' % wakfu_value.damage_factor(role, one.totals)
            else:
                damage = 'turn %.0f' % turn.damage(one.totals)
            self.stdout.write(
                '  %s value %.4f  %s over %d AP  crit %d%%  effective life %.0f'
                % (label, one.value, damage, one.totals.get('ap', 0),
                   round(100 * wakfu_value.critical_chance(
                       one.totals.get('ferocity', 0))),
                   wakfu_value.effective_life(level, one.totals)))
        weights = dict(model.best.weights)
        if turn is None:
            note = ''
        elif generic:
            note = ', from the generic solve, whose set the class turn values higher'
        else:
            weights.pop('ap', None)
            note = ', each AP total priced by the class turn'
        self.stdout.write('  weights of the kept round, percent of value per point%s'
                          % note)
        self.stdout.write('  ' + '  '.join('%s %.4g' % (key.upper(), weights[key])
                                           for key in sorted(weights)
                                           if weights[key]))

    def class_spells(self, level, class_id):
        """(damage spells, class mechanics, {spell id: name}, source of the critical values)."""
        from fashionistapulp import wakfu_solve

        return wakfu_solve.class_spells(level, class_id)

    def print_turn(self, role, level, class_id, totals):
        from fashionistapulp import wakfu_turn

        spells, mechanics, names, source = self.class_spells(level, class_id)
        self.stdout.write('')
        if not spells:
            self.stdout.write(self.style.WARNING(
                'class %d has no damage spell in the tables' % class_id))
            return
        turn = wakfu_turn.best_turn(spells, role, totals, class_mechanics=mechanics)
        names.update((spell.id, spell.name) for spell in spells)
        self.stdout.write('  best turn of class %d: %.0f expected damage, %s'
                          % (class_id, turn.damage,
                             ', '.join(names[one] for one in turn.casts) or 'no cast'))
        self.stdout.write('  budget %(ap)d AP, %(wp)d WP, %(mp)d MP on spells and '
                          '%(mp_moving)d moving, a spell at most %(casts_per_spell)d '
                          'times' % turn.settings)
        self.stdout.write('  critical values: %s' % source)
        if turn.stance:
            self.stdout.write('  stance: %s' % wakfu_turn.describe(turn.stance))
        for label, entries in (('counted', turn.counted), ('not counted', turn.dropped)):
            for spell_id, position, keys, heading in entries:
                self.stdout.write('  %s: %s row %d, %s%s' % (
                    label, names[spell_id], position,
                    ', '.join(wakfu_turn.describe(key) for key in keys),
                    ' (%s)' % heading if heading else ''))
        for spell_ids, key, detail in turn.unmodelled:
            self.stdout.write('  not modelled: %s, %s: %s' % (
                ', '.join(names[one] for one in spell_ids),
                wakfu_turn.describe(key), detail))

    @staticmethod
    def harvest_criticals(level):
        """(critical values of the French harvest at `level` or None, where they come from)."""
        from fashionistapulp import wakfu_solve

        return wakfu_solve.harvest_criticals(level)

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
