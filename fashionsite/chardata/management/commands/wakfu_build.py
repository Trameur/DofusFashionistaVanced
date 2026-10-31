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
        parser.add_argument('--preset', default=None,
                            help='a Wakfu preset: the role comes from the registry for '
                                 '--class-id (damage_<reach>_<target>, tank, heal, '
                                 'support, placement, hindrance, mule). Takes no --reach '
                                 'or --defense, and --elements except for the mule')
        parser.add_argument('--content', default='pvm', choices=('pvm', 'pvp'),
                            help='the content a --preset is valued for (default pvm)')
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
        parser.add_argument('--wakfu-gauge', type=int, default=None,
                            help='Wakfu gauge of the character, 0 to 100 (default 0)')
        parser.add_argument('--stasis-gauge', type=int, default=None,
                            help='Stasis gauge of the character, 0 to 100 (default 0)')
        parser.add_argument('--nation', type=int, default=None,
                            help='id of the nation the character belongs to '
                                 '(default none)')
        parser.add_argument('--citizenship', action='append', default=[],
                            help='citizenship points, POINTS toward the --nation '
                                 'or NATION=POINTS; repeat for several nations')
        parser.add_argument('--company-rank', type=int, default=None,
                            help='rank in a company (default 0)')
        parser.add_argument('--pvp-rank', type=int, default=None,
                            help='PvP rank (default 0)')
        parser.add_argument('--guild-level', type=int, default=None,
                            help='level of the guild (default 0)')
        parser.add_argument('--aptitudes', default='solve',
                            help='solve (the solver spreads the points, default), '
                                 'none (leave aptitudes out) or ID=POINTS,ID=POINTS '
                                 '(e.g. 2=1,23=40, checked against the budgets and '
                                 'caps of --level)')
        parser.add_argument('--battleground', action='store_true',
                            help='count the set bonus tiers of the bracket of '
                                 '--level, which only a battleground gives')
        parser.add_argument('--pet-level', type=int, default=None,
                            help='level the pet is worn at (default: the highest '
                                 'level the client allows)')
        parser.add_argument('--mount-level', type=int, default=None,
                            help='level the mount is worn at (default: the highest '
                                 'level the client allows)')
        parser.add_argument('--item-level', default='',
                            help='ID=LEVEL,ID=LEVEL: the level of single pets or '
                                 'mounts, over --pet-level and --mount-level '
                                 '(default: the highest level the client allows)')
        parser.add_argument('--runes', default='optimistic', choices=('optimistic', 'none'),
                            help='optimistic: every socket of the worn pieces holds the rune '
                                 'the solver picks, at the tier the piece allows (default); '
                                 'none: runes left out')
        parser.add_argument('--rune-tier', type=int, default=None,
                            help='the highest tier a socket may hold, up to the top tier of '
                                 'the rune table; 0 is the same as --runes none '
                                 '(default: the tier each piece allows)')
        parser.add_argument('--sublimations', default='optimistic',
                            choices=('optimistic', 'none'),
                            help='optimistic: the solver places a sublimation in every '
                                 'position whose pieces have the sockets (default); none: '
                                 'only the states the worn pieces carry count')
        parser.add_argument('--passives', default='solve', choices=('solve', 'none'),
                            help="solve: the solver picks the passives of --class-id that "
                                 "the level opens (default; with no --class-id, none); "
                                 "none: no passive")
        parser.add_argument('--opt-in', action='append', default=[], metavar='FAMILY=RATE',
                            help='the share, 0 to 1, of the lines of a family from E to H '
                                 'a fight is assumed to give; repeat for several families')
        parser.add_argument('--list-sublimations', action='store_true',
                            help='print every sublimation the model keeps with its state, '
                                 'level, kind, pattern, family and cap, then exit')
        parser.add_argument('--list-passives', action='store_true',
                            help='print the passive slots open at --level and every passive '
                                 'of --class-id with its family or why it is not counted, '
                                 'then exit')
        parser.add_argument('--list-runes', action='store_true',
                            help='print every rune with its colour, stat, doubled positions '
                                 'and its value, shards and item level per tier, then exit')
        parser.add_argument('--list-aptitudes', action='store_true',
                            help='print every aptitude with its category, cap and '
                                 'lines per point, and the budgets at --level, '
                                 'then exit')

    def handle(self, *args, **options):
        from fashionistapulp.fashionista_config import get_items_db_path
        from fashionistapulp.structure import get_structure
        from fashionistapulp.wakfu_model import TIME_LIMIT
        from fashionistapulp.wakfu_slots import SOLVED_SLOTS
        from fashionistapulp import wakfu_solve, wakfu_value
        import os

        chemin = get_items_db_path('wakfu')
        if not os.path.exists(chemin):
            # The database is gitignored, so a fresh checkout has none.
            raise CommandError(
                'no Wakfu database at %s. Build it with '
                'python update_data_wakfu.py' % chemin)

        if options['list_aptitudes']:
            self.print_aptitude_list(get_structure('wakfu'), options['level'])
            return
        if options['list_runes']:
            self.print_rune_list(get_structure('wakfu'))
            return
        if options['list_sublimations']:
            self.print_sublimation_list()
            return
        if options['list_passives']:
            self.print_passive_list(options['level'], options['class_id'])
            return
        opt_in = self.read_opt_in(options['opt_in'])
        aptitudes = self.read_aptitudes(options['aptitudes'])
        role = weights = None
        if options['weights'] is not None:
            weights = self.hand_weights(options['weights'])
        for flag, given in (('--class-turn', options['class_turn']),
                            ('--movement', options['movement'] is not None)):
            if given and (weights is not None or not options['class_id']):
                raise CommandError('%s needs --class-id and no --weights' % flag)
        preset = options['preset']
        if preset is not None and weights is not None:
            raise CommandError('--preset needs no --weights')
        if preset is not None and options['reach'] is not None:
            raise CommandError('--preset takes the reach from the preset, not --reach')
        if preset is not None and options['defense'] is not None:
            raise CommandError('--preset takes its shares from the registry, not --defense')
        if preset is not None and not options['class_id']:
            raise CommandError('--preset needs --class-id')
        if weights is None:
            try:
                if preset is None:
                    role = wakfu_solve.make_role(
                        options['elements'], options['reach'], options['defense'],
                        options['movement'])
                else:
                    from fashionistapulp import wakfu_presets
                    role = wakfu_presets.role(
                        options['class_id'], preset, options['elements'] or (),
                        options['level'], options['content'])
            except ValueError as error:
                raise CommandError(str(error))
        locked = self.read_locks(options['lock'], SOLVED_SLOTS)
        item_levels = self.read_item_levels(options['item_level'])

        forbidden = [int(x) for x in options['forbid'].split(',') if x.strip()]
        structure = get_structure('wakfu')
        try:
            state = self.read_state(structure, options)
        except ValueError as error:
            raise CommandError(str(error))
        try:
            if role is None:
                result = wakfu_solve.solve_weights(
                    structure, level=options['level'], weights=weights,
                    forbidden=forbidden, locked=locked,
                    allow_legacy=options['allow_legacy'], seconds=options['seconds'],
                    class_id=options['class_id'], state=state, aptitudes=aptitudes,
                    battleground=options['battleground'],
                    pet_level=options['pet_level'],
                    mount_level=options['mount_level'], item_levels=item_levels,
                    runes=options['runes'], rune_tier=options['rune_tier'])
            else:
                result = wakfu_solve.solve_build(
                    structure, level=options['level'],
                    elements=options['elements'], reach=options['reach'],
                    class_id=options['class_id'], preset=preset,
                    content=options['content'],
                    forbidden=forbidden, locked=locked,
                    allow_legacy=options['allow_legacy'],
                    movement=options['movement'], seconds=options['seconds'],
                    defense=options['defense'], rounds=options['rounds'],
                    on_class_turn=options['class_turn'] or preset is not None, state=state,
                    aptitudes=aptitudes, battleground=options['battleground'],
                    pet_level=options['pet_level'],
                    mount_level=options['mount_level'], item_levels=item_levels,
                    runes=options['runes'], rune_tier=options['rune_tier'],
                    sublimations=options['sublimations'], passives=options['passives'],
                    opt_in=opt_in)
        except wakfu_solve.WakfuIllegalSet as error:
            raise CommandError('the solver returned an illegal set: %s' % error)
        except (ValueError, wakfu_value.SolverCrashed) as error:
            raise CommandError(str(error))
        worn, build, model, turn = result.worn, result.build, result.model, result.turn_model
        duration = result.seconds
        self.print_state(structure, result)
        if not options['allow_legacy']:
            self.stdout.write('leaving out %d legacy items (--allow-legacy '
                              'lets the solver pick them)' % result.legacy_left_out)

        if worn is None:
            self.print_unlocks(structure, result)
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
        self.stdout.write(self.solve_line(result))
        if worn.full_set_dropped:
            self.stdout.write(self.style.WARNING(
                'the every-slot model gave no set (%s), so empty slots were '
                'allowed' % worn.full_set_status))
        empty = [slot for slot in SOLVED_SLOTS if slot not in worn]
        if empty:
            self.stdout.write('empty: %s' % ', '.join(
                '%s (%s)' % (slot, self.why_empty(worn, slot)) for slot in empty))
        for slot in sorted(worn):
            item = worn[slot]
            self.stdout.write('  %-16s %-38s level %s%s'
                              % (slot, getattr(item, 'name', item.id), item.level,
                                 self.companion_note(item, result.levels)))

        self.print_runes(structure, worn, result)
        self.print_sublimations(worn, result)
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
        self.print_aptitudes(structure, result)
        self.print_fight(result)
        self.print_unlocks(structure, result)
        if model is not None:
            self.print_model(role, options['level'], model, turn,
                             structure, options['class_id'])
            if preset is not None:
                self.print_components(role, options['level'], totals, turn)
            elif options['class_id']:
                self.print_turn(role, options['level'], options['class_id'], totals)
            self.stdout.write('')
            left_out = [note for note in result.not_counted
                        if note.startswith(('sublimations', 'states', 'passives', 'runes'))]
            if result.aptitude_mode is None:
                left_out.append('aptitudes')
            self.stdout.write('  systems the model leaves out: '
                              + (', '.join(left_out) or 'none'))

    COLOUR_NAMES = {0: 'any', 1: 'red', 2: 'green', 3: 'blue', 4: 'white'}

    @staticmethod
    def read_opt_in(given):
        """{family: rate} of the --opt-in options."""
        out = {}
        for part in given:
            family, equals, rate = part.partition('=')
            try:
                if not equals:
                    raise ValueError(part)
                number = float(rate)
            except ValueError:
                raise CommandError('--opt-in is FAMILY=RATE, got %r' % part)
            family = family.strip().upper()
            if family in out:
                raise CommandError('--opt-in names family %s twice' % family)
            out[family] = number
        return out

    @staticmethod
    def pattern_text(pattern):
        return '-'.join(Command.COLOUR_NAMES[colour] for colour in pattern) or 'no pattern'

    def print_sublimation_list(self):
        from fashionistapulp import wakfu_sublimations

        block = wakfu_sublimations.load()
        if block is None:
            raise CommandError('there is no sublimation table, build it with '
                               'python update_data_wakfu.py')
        for ident, (state, level, kind, pattern) in sorted(block.SUBLIMATIONS.items()):
            entry = block.STATES[state]
            self.stdout.write('%d %s: state %d, level %d, %s, %s, family %s, cap %s' % (
                ident, entry['name'], state, level, kind, self.pattern_text(pattern),
                entry['family'], 'none' if entry['cap'] is None else entry['cap']))

    def print_passive_list(self, level, class_id):
        from fashionistapulp import wakfu_sublimations

        block = wakfu_sublimations.load()
        if block is None:
            raise CommandError('there is no passive table, build it with '
                               'python update_data_wakfu.py')
        if not class_id:
            raise CommandError('--list-passives needs --class-id')
        self.stdout.write('level %d opens %d passive slots' % (
            level, wakfu_sublimations.slots_open(level)))
        for ident, entry in sorted(block.PASSIVES.items(),
                                   key=lambda one: (one[1]['unlock'], one[0])):
            if not wakfu_sublimations.passive_of_class(entry, class_id, block):
                continue
            reasons = sorted({reason for _family, _ident, reason in entry['uncounted']})
            self.stdout.write('%d %s: unlock %d%s, family %s, %s' % (
                ident, entry['name'], entry['unlock'],
                '' if entry['unlock'] <= level else ' (not open)', entry['family'],
                '%d counted lines' % len(entry['lines']) if entry['lines']
                else '%d counted conversions' % len(entry['conversions'])
                if entry['conversions'] else 'nothing counted'))
            for reason in reasons:
                self.stdout.write('  not counted: %s' % reason)

    def print_sublimation(self, position, result):
        from fashionistapulp import wakfu_sublimations

        if position not in result.sublimations:
            return
        _ident, state, level, pattern = result.sublimations[position]
        self.stdout.write('  sublimation: %s %s level %d' % (
            wakfu_sublimations.load().STATES[state]['name'], self.pattern_text(pattern),
            level))

    def print_sublimations(self, worn, result):
        """The sublimations no socket line carried, then the relic or epic ones."""
        from fashionistapulp import wakfu_sublimations

        block = wakfu_sublimations.load()
        if block is None or (not result.sublimations and not result.specials):
            return
        self.stdout.write('')
        for position in sorted(set(result.sublimations) - set(result.runes)):
            self.stdout.write('  %-16s' % position)
            self.print_sublimation(position, result)
        for position in sorted(result.specials):
            ident, state, kind = result.specials[position]
            self.stdout.write('  %-16s relic/epic sublimation: %s (%s)' % (
                position, block.STATES[state]['name'], kind))

    def print_fight(self, result):
        """The states with their lines, the passives, what was left out, how it settled."""
        from fashionistapulp import wakfu_sublimations

        block = wakfu_sublimations.load()
        if block is not None and result.states:
            self.stdout.write('states:')
            for key in sorted(result.states, key=str):
                report = result.states[key]
                if isinstance(key, tuple):
                    continue
                self.stdout.write('  %s: summed %d, cap %s, counted %d, family %s%s: %s' % (
                    block.STATES[key]['name'], report.summed,
                    'none' if report.cap is None else report.cap, report.counted,
                    report.family, '' if report.condition else ', condition not held',
                    ', '.join('%+d %s' % (value, line.upper())
                              for line, value in sorted(report.lines.items())) or 'no line'))
        if result.passive_mode is not None:
            self.stdout.write('passives (%d of %d slots): %s' % (
                len(result.passives), result.passive_slots,
                ', '.join('%s: %s' % (block.PASSIVES[spell]['name'], ', '.join(
                    '%+d %s' % (value, line.upper()) for line, value in sorted(
                        result.states[(wakfu_sublimations.PASSIVE, spell)].lines.items())))
                    for spell in result.passives) or 'none'))
        left = [note for note in result.not_counted
                if note.startswith(('state ', 'passive ', 'gear state '))]
        if left:
            self.stdout.write('not counted:')
            for note in left:
                self.stdout.write('  %s' % note)
        crashed = getattr(result.model, 'crashed', ())
        for number, message in crashed:
            self.stdout.write(self.style.WARNING(
                'round %d: the solver crashed (%s), the best set so far is kept'
                % (number, message)))
        if result.model is None:
            pass
        elif crashed:
            self.stdout.write('not settled, a round crashed')
        elif result.settled_by == 'gap':
            self.stdout.write('settled by gap %.2f' % result.gap)
        elif result.settled_by == 'key':
            self.stdout.write('settled (same set)')
        elif result.gap is not None:
            self.stdout.write('not settled (gap %.1f)' % result.gap)
        else:
            self.stdout.write('not settled')
        for rule, text in result.warnings:
            self.stdout.write(self.style.WARNING('warning: %s' % text))

    @staticmethod
    def solve_line(result):
        """How the last solve ended; 'proven best' only for a single solve that ended Optimal,
        'settled' for rounds that settled, as the value is not concave."""
        from fashionistapulp.wakfu_model import PROVEN, STEPWISE

        if result.status == PROVEN:
            if result.model is None:
                return 'proven best'
            if result.settled:
                return 'settled'
            if getattr(result.model, 'crashed', ()):
                return 'a round crashed, the best set so far is kept'
            return 'last round solved to the end'
        if result.status == STEPWISE:
            return 'solved in steps'
        return 'best set found within the time limit'

    def print_rune_list(self, structure):
        from fashionistapulp import wakfu_runes

        if not structure.shards:
            raise CommandError('the Wakfu database has no rune tables, rebuild it '
                               'with python update_data_wakfu.py')
        for ident, rune in sorted(structure.shards.items()):
            name = rune.names.get('en', str(ident))
            colour = self.COLOUR_NAMES.get(rune.colour, str(rune.colour))
            if rune.stat is None:
                self.stdout.write('%d %s %s: gives nothing' % (ident, name, colour))
                continue
            stat = structure.get_stat_by_id(rune.stat)
            self.stdout.write('%d %s %s %s, doubled on %s' % (
                ident, name, colour, stat.key if stat else rune.stat,
                ', '.join(sorted(rune.doubles)) or 'no position'))
            for tier in range(1, len(rune.costs) + 1):
                self.stdout.write(
                    '  tier %-2d item level %-3d  +%d single  +%d doubled  %d shards' % (
                        tier, rune.requirements[tier - 1],
                        wakfu_runes.value(rune, tier, False),
                        wakfu_runes.value(rune, tier, True),
                        wakfu_runes.shards_at(rune, tier)))

    def print_runes(self, structure, worn, result):
        """Per position the piece, its tier and sockets, then one line per socket."""
        if not result.runes:
            return
        total = 0
        self.stdout.write('')
        self.stdout.write('  runes (%s%s)' % (
            result.rune_mode, '' if result.rune_tier is None
            else ', at most tier %d' % result.rune_tier))
        for position in sorted(result.runes):
            sockets = result.runes[position]
            if position not in worn or not sockets:
                continue
            filled = [one for one in sockets if one.rune is not None]
            top = max((one.tier for one in filled), default=None)
            self.stdout.write('  %-16s %-38s %s, %d sockets' % (
                position, getattr(worn[position], 'name', worn[position].id),
                'tier %d' % top if top else 'no rune', len(sockets)))
            for socket in sockets:
                if socket.rune is None:
                    self.stdout.write('  %d empty' % (socket.index + 1))
                    continue
                rune = structure.shards[socket.rune]
                stat = structure.get_stat_by_id(rune.stat)
                total += socket.shards
                self.stdout.write('  %d %s %s %d tier %d +%d %s%s, %d shards' % (
                    socket.index + 1, self.COLOUR_NAMES[socket.colour],
                    rune.names.get('en', socket.rune), socket.rune, socket.tier,
                    socket.value, stat.key, ' (doubled)' if socket.doubled else '',
                    socket.shards))
            self.print_sublimation(position, result)
        self.stdout.write('  total shards: %d' % total)

    @staticmethod
    def companion_note(item, levels):
        """', pet level 10 of 50' for a worn pet or mount, '' for any other item."""
        cap = getattr(item, 'level_cap', None)
        if cap is None:
            return ''
        return ', %s level %d of %d' % (
            'pet' if item.level_slot == 'PET' else 'mount', levels[item.id], cap)

    @staticmethod
    def read_item_levels(text):
        """{item id: level} of --item-level."""
        given = {}
        for part in text.split(','):
            part = part.strip()
            if not part:
                continue
            left, equals, right = part.partition('=')
            try:
                if not equals:
                    raise ValueError(part)
                ident, level = int(left), int(right)
            except ValueError:
                raise CommandError('--item-level is ID=LEVEL,ID=LEVEL, got %r' % part)
            if ident in given:
                raise CommandError('--item-level names item %d twice' % ident)
            given[ident] = level
        return given

    @staticmethod
    def read_aptitudes(text):
        """SOLVE, None or {ability id: points} of --aptitudes."""
        from fashionistapulp.wakfu_model import SOLVE

        text = text.strip().lower()
        if text == 'solve':
            return SOLVE
        if text == 'none':
            return None
        given = {}
        for part in text.split(','):
            part = part.strip()
            if not part:
                continue
            left, equals, right = part.partition('=')
            try:
                if not equals:
                    raise ValueError(part)
                ident, points = int(left), int(right)
            except ValueError:
                raise CommandError('--aptitudes is solve, none or ID=POINTS,ID=POINTS, '
                                   'got %r' % part)
            if ident in given:
                raise CommandError('--aptitudes names aptitude %d twice' % ident)
            given[ident] = points
        if not given:
            raise CommandError('--aptitudes is solve, none or ID=POINTS,ID=POINTS')
        return given

    @staticmethod
    def _names(structure):
        """({ability id: name}, {category id: name}) in English."""
        abilities = {ident: structure.aptitude_ability_names.get((ident, 'en'), str(ident))
                     for ident in structure.aptitude_abilities}
        categories = {ident: structure.aptitude_category_names.get((ident, 'en'), str(ident))
                      for ident in structure.aptitude_categories}
        return abilities, categories

    def print_aptitude_list(self, structure, level):
        from fashionistapulp import wakfu_aptitudes

        if not structure.aptitude_abilities:
            raise CommandError('the Wakfu database has no aptitude tables, rebuild it '
                               'with python update_data_wakfu.py')
        names, categories = self._names(structure)
        table = wakfu_aptitudes.table(structure, level, False)
        budgets = wakfu_aptitudes.budgets(structure, level)
        self.stdout.write('aptitudes at level %d' % level)
        for ident, (category, cap, lines, notes) in sorted(
                table.abilities.items(), key=lambda one: (one[1][0], one[0])):
            self.stdout.write('  %-3d %-10s cap %-3d %-30s %s%s' % (
                ident, categories[category], cap, names[ident],
                ', '.join('%s %s' % (key.upper(), number) for key, number in lines)
                or 'no counted line',
                ''.join('; %s' % note for note in notes)))
        self.stdout.write('budgets: ' + ', '.join(
            '%s %d' % (categories[category], budgets[category])
            for category in sorted(budgets)))

    def print_aptitudes(self, structure, result):
        if result.aptitude_mode is None:
            self.stdout.write('aptitudes: left out')
            return
        names, categories = self._names(structure)
        by_category = {}
        for ident, points in sorted(result.aptitudes.items()):
            by_category.setdefault(structure.aptitude_abilities[ident][0], []).append(
                '%s %d' % (names[ident], points))
        self.stdout.write('aptitudes (%s): %s' % (
            'solver distributes' if result.aptitude_mode == 'solve' else 'fixed',
            '; '.join('%s: %s' % (categories[category], ', '.join(parts))
                      for category, parts in sorted(by_category.items())) or 'none'))
        self.stdout.write('unspent: ' + (', '.join(
            '%s %d' % (categories[category], left)
            for category, left in sorted(result.unspent.items()) if left) or 'none'))
        if result.set_tiers:
            self.stdout.write('set bonuses: ' + ', '.join(
                '%d %d' % tier for tier in result.set_tiers))
        for note in result.not_counted:
            if '(aptitude ' in note:
                self.stdout.write('  not valued: %s' % note)

    @staticmethod
    def read_state(structure, options):
        """The PlayerState the flags describe; ValueError on a bad value."""
        from fashionistapulp import wakfu_criteria

        given = {name: options[name] for name in (
            'wakfu_gauge', 'stasis_gauge', 'nation', 'company_rank', 'pvp_rank',
            'guild_level') if options[name] is not None}
        points = {}
        for text in options['citizenship']:
            left, equals, right = text.partition('=')
            try:
                if equals:
                    points[int(left)] = int(right)
                elif given.get('nation'):
                    points[given['nation']] = int(left)
                else:
                    raise ValueError('--citizenship POINTS needs --nation')
            except ValueError as error:
                if 'needs --nation' in str(error):
                    raise
                raise ValueError('--citizenship takes POINTS or NATION=POINTS, '
                                 'got %r' % text)
        if points:
            given['citizenship'] = points
        return wakfu_criteria.player_state(structure, **given)

    def print_state(self, structure, result):
        from fashionistapulp import wakfu_criteria

        start = wakfu_criteria.start_state()
        state = result.state
        changed = [
            '%s %s' % (option.name, getattr(state, option.name))
            for option in wakfu_criteria.STATE_OPTIONS
            if getattr(state, option.name) != getattr(start, option.name)]
        self.stdout.write('player state: %s' % (
            ', '.join(changed) if changed else "the game's start values"))

    def print_unlocks(self, structure, result, shown=8):
        """The highest pieces the player state keeps out, each with its unlocking value."""
        unlocks = result.state_unlocks
        if not unlocks:
            return
        self.stdout.write('the player state keeps out %d pieces; the highest:'
                          % len(unlocks))
        for ident, needs in unlocks[:shown]:
            item = structure.get_item_by_id(ident)
            self.stdout.write('  %-38s level %s needs %s' % (
                item.name, item.level, ', '.join(
                    self.needs_text(item, key, bound)
                    for key, bound in sorted(needs.items(), key=str))))

    @staticmethod
    def needs_text(item, key, bound):
        option, nation = (key, None) if isinstance(key, str) else key
        operator = '>='
        for condition in item.state_conditions:
            if condition.option == option and condition.nation == nation:
                operator = condition.operator
        label = option if nation is None else '%s of nation %s' % (option, nation)
        return '%s %s %s' % (label, operator, bound)

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

    def print_model(self, role, level, model, turn=None, structure=None,
                    class_id=None):
        from fashionistapulp import wakfu_criteria, wakfu_value

        self.stdout.write('')
        self.stdout.write('  damage model: %s, %s, defense %g%s; %d rounds, %s'
                          % ('+'.join(role.elements), role.reach, role.defense,
                             ', on the class turn' if turn is not None else '',
                             len(model.rounds),
                             'settled' if model.converged
                             else 'not settled, best round kept'))
        self.stdout.write('  kept at least: ' + ', '.join(
            '%s %s' % (key.upper(), lowest)
            for key, lowest in sorted(role.minimums(
                wakfu_criteria.base_values(structure, class_id)).items())))
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

    def print_components(self, role, level, totals, turn):
        from fashionistapulp import wakfu_value

        self.stdout.write('')
        self.stdout.write('  preset role: %s, %s, %s, %s; shares %s' % (
            '+'.join(role.elements) or 'no element', role.reach, role.target, role.content,
            ', '.join('%s %g' % one for one in role.shares.items())))
        for name, worth in wakfu_value.components(role, level, totals, turn).items():
            self.stdout.write('  %s %.4g' % (name, worth))

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
        from fashionistapulp.wakfu_slots import (BLOCKED_BY_TWO_HANDED,
                                                 TWO_HANDED_FLAG)
        if slot in worn.no_candidate:
            return 'no item fits'
        weapon = worn.get('FIRST_WEAPON')
        if (slot == BLOCKED_BY_TWO_HANDED and weapon is not None
                and TWO_HANDED_FLAG in (weapon.flags or ())):
            return 'two-handed weapon'
        return 'left empty by the solver'
