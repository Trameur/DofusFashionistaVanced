"""Create the contributor roles and hand them to the people who earned them.

The list below is not derived from message counts. It comes from reading all
393 messages: the biggest poster spends a good part of it debating class
balance, and the person with two messages found four real defects in the Touch
data. Volume and contribution are different things.

Each name carries the reason it is there, in the ROLES table, so the decision
can be argued with rather than trusted.

Dry run by default. Nothing changes without --apply.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import discord_api  # noqa: E402

GUILD = '1188892643766321173'

#: Two roles, not three, and both displayed the same way. A role named after a
#: rank -- "Référent" -- reads as standing above the others, when what these
#: people did was contribute in two different ways: they found what was wrong,
#: or they asked for something that now exists. Whoever did both carries both
#: badges, which says more than any title could, and says it without putting
#: anyone underneath.
ROLES = [
    {
        'name': 'Chasseur de bugs',
        'color': 0xA84C3C,
        'hoist': True,
        'why': "reported a defect that was reproduced and fixed",
        'members': {
            'FenixAP': "five long reports on the smithmagic simulator: runes "
                       "missing from the list, wrong densities, a rune that "
                       "does not exist, impossible rolls being offered, "
                       "probabilities off. Plus the base characteristic cost "
                       "counting double, and fire heal lines read as fire "
                       "damage. The owner had never done smithmagic and "
                       "learnt it from these.",
            'Keysouke': "the 50% resistance cap ignored in the minimum "
                        "characteristics, prospecting not scaling with Chance, "
                        "the Cire Momore set's MP ceiling, wild mounts "
                        "carrying 22% resistance that does not exist in game, "
                        "editing a level resetting AP/MP/Range.",
            'Andromeda': "four Touch defects in two messages: the proxy url "
                         "change, shields that gain their stats by feeding, "
                         "equip conditions ignored, rune weights out of date.",
            'AD#1938': "Retro: base stat tiers wrong, scrolls not counted in "
                       "them, the Divhugalch and the ice Dofus offered where "
                       "they cannot be obtained.",
            'Trak_age': "Touch: the worn koulosse staff removing AP instead "
                        "of granting it, trophies ignoring the set-bonus "
                        "condition, pets without stats, the scroll arithmetic.",
            'Xenaltrof': "held on to the set-bonus < 3 defect until it was "
                         "understood, then found the same class of bug on "
                         "weapon conditions (Limbo wand, Dreggon daggers).",
            'DieuTricheur': "the Volkorne bow's missing damage line, and the "
                            "search that would not find 'ben le' -- and he "
                            "tested in game to confirm the site was RIGHT "
                            "when others thought it wrong.",
            'HacH': "the clearest report of the minimum-characteristics bug: "
                    "three steps, reproducible, filed politely in 2024.",
            'SpyNight': "the same bug with a numbered reproduction, which is "
                        "what made it findable.",
            'Djaul': "trophies with a < 3 restriction on three set pieces, "
                     "and lord daggers that cannot be obtained.",
            'TheRev': "sharing a comparison sharing the wrong thing, and "
                      "restrictions silently dropped when a weight changed.",
            'LiniSeum': "site crashes with the share link attached every "
                        "time, and the comparison using the last build's base "
                        "characteristics for both sides.",
        },
    },
    {
        'name': 'Idée en ligne',
        'color': 0x3F8F5E,
        'hoist': True,
        'why': "suggested something that is running on the site today",
        'members': {
            'Keysouke': "locking an empty slot, and unifying HP with Vitality "
                        "in the filters. Both shipped and announced.",
            'TheRev': "editing an item's stats for one project. Shipped in "
                      "May 2026 as a big update.",
            'LiniSeum': "a total weight for a build, so two generations can "
                        "be compared. Shipped as the build score.",
            'Trak_age': "picking a project from the list instead of pasting "
                        "a url into the comparison tool.",
            'FenixAP': "asked whether the generator could suggest the best "
                       "transcendence rune for each item. They went in."
        },
    },
]


def resolve(made, names):
    """{display name: user id}, read from who actually posted.

    The members endpoint needs the Server Members intent and returns everyone;
    the message history already carries the id of every person that matters
    here, and needs nothing extra.
    """
    wanted = set(names)
    found = {}
    available = discord_api.channels(made, GUILD)
    for channel in ('suggestions', 'bug-report'):
        if channel not in available:
            continue
        for m in discord_api.history(made, available[channel]):
            author = m.get('author') or {}
            member = author.get('global_name') or author.get('username')
            if member in wanted and member not in found:
                found[member] = author['id']
    return found


def existing_roles(made):
    return {r['name']: r for r in discord_api.get(made, '/guilds/%s/roles' % GUILD)}


def main():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true',
                         help='actually create the roles and assign them')
    args = parser.parse_args()

    made = discord_api.session()
    existing = existing_roles(made)
    wanted = sorted({n for r in ROLES for n in r['members']})
    ids = resolve(made, wanted)

    not_found = [n for n in wanted if n not in ids]
    if not_found:
        print('  not found in the history, skipped: %s' % ', '.join(not_found))

    print()
    for role in ROLES:
        state = 'exists' if role['name'] in existing else 'to create'
        print('%s  [%s]  hoisted=%s' % (role['name'], state, role['hoist']))
        print('   %s' % role['why'])
        for member, reason in role['members'].items():
            mark = ' ' if member in ids else '?'
            print('   %s %-14s %s' % (mark, member, reason))
        print()

    if not args.apply:
        print('dry run. Nothing was changed. Re-run with --apply to do it.')
        return 0

    for role in ROLES:
        record = existing.get(role['name'])
        if not record:
            record = discord_api.get  # placeholder, replaced below
            response = discord_api.write(
                made, 'POST', '/guilds/%s/roles' % GUILD,
                name=role['name'], color=role['color'],
                hoist=role['hoist'], mentionable=False)
            if not response.ok:
                print('  could not create %s: %s' % (role['name'], response.status_code))
                continue
            record = response.json()
            print('  created: %s' % role['name'])
        for member in role['members']:
            if member not in ids:
                continue
            result = discord_api.write(
                made, 'PUT', '/guilds/%s/members/%s/roles/%s'
                % (GUILD, ids[member], record['id']))
            state = ('ok' if result.ok else
                     'left the server' if result.status_code == 404
                     else str(result.status_code))
            print('  %-16s -> %-18s %s' % (member, role['name'], state))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
