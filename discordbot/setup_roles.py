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

#: Discord colours are integers. Amber for support, green for a shipped idea,
#: red-brown for bug hunting, blue for the people others should ask.
ROLES = [
    {
        'name': 'Référent',
        'color': 0x3E7CB1,
        'hoist': True,
        'why': "knows one version or one system deeply enough that the owner "
               "builds from what they say",
        'members': {
            'FenixAP': "co-designed the smithmagic simulator across five long "
                       "reports: missing runes, densities, impossible rolls, "
                       "probability curves, transcendence rules. The owner "
                       "wrote that he had never done smithmagic in his life "
                       "and was learning from the tool.",
            'Keysouke': "two years of precise reports that turned into "
                        "features: locking an empty slot, unifying HP and "
                        "Vitality, minimum stats at 0, the level edit no "
                        "longer resetting AP/MP/Range. Also flagged the 3.7 "
                        "characteristics overhaul before it landed.",
            'Andromeda': "two messages, four real Touch defects: the proxy "
                         "url change, shields gaining stats by feeding, "
                         "equip conditions ignored, rune weights. All fixed "
                         "within a fortnight.",
            'AD#1938': "the Retro reference: base stat tiers, scrolls not "
                       "counted in the tiers, the Divhugalch and the ice "
                       "Dofus that do not exist there.",
        },
    },
    {
        'name': 'Chasseur de bugs',
        'color': 0xA84C3C,
        'hoist': False,
        'why': "reported a defect that was reproduced and fixed",
        'members': {
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
        'hoist': False,
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
        },
    },
]


def resolve(made, noms):
    """{display name: user id}, read from who actually posted.

    The members endpoint needs the Server Members intent and returns everyone;
    the message history already carries the id of every person that matters
    here, and needs nothing extra.
    """
    voulus = set(noms)
    trouves = {}
    disponibles = discord_api.channels(made, GUILD)
    for salon in ('suggestions', 'bug-report'):
        if salon not in disponibles:
            continue
        for m in discord_api.history(made, disponibles[salon]):
            auteur = m.get('author') or {}
            nom = auteur.get('global_name') or auteur.get('username')
            if nom in voulus and nom not in trouves:
                trouves[nom] = auteur['id']
    return trouves


def existing_roles(made):
    return {r['name']: r for r in discord_api.get(made, '/guilds/%s/roles' % GUILD)}


def main():
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass

    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument('--apply', action='store_true',
                         help='actually create the roles and assign them')
    args = parseur.parse_args()

    made = discord_api.session()
    deja = existing_roles(made)
    voulus = sorted({n for r in ROLES for n in r['members']})
    ids = resolve(made, voulus)

    introuvables = [n for n in voulus if n not in ids]
    if introuvables:
        print('  not found in the history, skipped: %s' % ', '.join(introuvables))

    print()
    for role in ROLES:
        etat = 'exists' if role['name'] in deja else 'to create'
        print('%s  [%s]  hoisted=%s' % (role['name'], etat, role['hoist']))
        print('   %s' % role['why'])
        for nom, raison in role['members'].items():
            marque = ' ' if nom in ids else '?'
            print('   %s %-14s %s' % (marque, nom, raison))
        print()

    if not args.apply:
        print('dry run. Nothing was changed. Re-run with --apply to do it.')
        return 0

    for role in ROLES:
        fiche = deja.get(role['name'])
        if not fiche:
            fiche = discord_api.get  # placeholder, replaced below
            reponse = discord_api.write(
                made, 'POST', '/guilds/%s/roles' % GUILD,
                name=role['name'], color=role['color'],
                hoist=role['hoist'], mentionable=False)
            if not reponse.ok:
                print('  could not create %s: %s' % (role['name'], reponse.status_code))
                continue
            fiche = reponse.json()
            print('  created: %s' % role['name'])
        for nom in role['members']:
            if nom not in ids:
                continue
            mise = discord_api.write(
                made, 'PUT', '/guilds/%s/members/%s/roles/%s'
                % (GUILD, ids[nom], fiche['id']))
            etat = ('ok' if mise.ok else
                    'left the server' if mise.status_code == 404
                    else str(mise.status_code))
            print('  %-16s -> %-18s %s' % (nom, role['name'], etat))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
