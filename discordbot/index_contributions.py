"""Who has actually contributed to the site, read from the Discord history.

The owner has named three people from memory, and there are three years of
messages. Scrolling a channel by hand finds the recent and the loud; this reads
every message ever posted in the channels where people report things, and
counts.

What it produces is a list of names with what they wrote and when -- the input
for handing out contributor roles. It decides nothing on its own: a person who
posted twenty times is not automatically worth a role, and the owner is the one
who knows which reports turned into a fix.

Read-only. It never posts, never assigns a role, never deletes anything.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import discord_api  # noqa: E402

GUILD = '1188892643766321173'

#: The channels where a reader tells the owner something. #general is left out
#: on purpose: chatting is not contributing, and counting it would drown the
#: signal under hellos.
DEFAULT_CHANNELS = ('suggestions', 'bug-report')


def gather(made, noms, limit=None):
    """{channel: [message]} for the named channels that exist."""
    disponibles = discord_api.channels(made, GUILD)
    manquants = [n for n in noms if n not in disponibles]
    if manquants:
        print('  channels not found, skipped: %s' % ', '.join(manquants))
        print('  (the guild has: %s)' % ', '.join(sorted(disponibles)))
    return {n: discord_api.history(made, disponibles[n], limit=limit)
            for n in noms if n in disponibles}


def by_author(par_salon, owner_names=('Trameur',)):
    """Fold the messages into one record per person.

    The owner's own messages are counted separately: he answers nearly every
    thread, so leaving him in would put him first on a list meant to surface
    everyone else.
    """
    gens = collections.defaultdict(lambda: {
        'messages': 0, 'salons': collections.Counter(), 'premier': None,
        'dernier': None, 'caracteres': 0, 'exemples': [],
    })
    for salon, messages in par_salon.items():
        for m in messages:
            auteur = m.get('author') or {}
            if auteur.get('bot'):
                continue
            nom = auteur.get('global_name') or auteur.get('username') or '?'
            contenu = (m.get('content') or '').strip()
            if not contenu:
                continue
            fiche = gens[nom]
            fiche['messages'] += 1
            fiche['salons'][salon] += 1
            fiche['caracteres'] += len(contenu)
            quand = (m.get('timestamp') or '')[:10]
            if fiche['premier'] is None or quand < fiche['premier']:
                fiche['premier'] = quand
            if fiche['dernier'] is None or quand > fiche['dernier']:
                fiche['dernier'] = quand
            # The longest messages are the substantial ones: a bug report with
            # steps runs to paragraphs, "thanks!" does not.
            fiche['exemples'].append((len(contenu), quand, salon, contenu[:160]))
    for fiche in gens.values():
        fiche['exemples'].sort(reverse=True)
        fiche['exemples'] = fiche['exemples'][:2]
    proprio = {n: gens.pop(n) for n in list(gens) if n in owner_names}
    return gens, proprio


def report(gens, proprio):
    ordre = sorted(gens.items(),
                   key=lambda kv: (-kv[1]['caracteres'], -kv[1]['messages']))
    print()
    print('=' * 74)
    print('%d personnes ont ecrit dans ces salons (hors proprietaire et bots)'
          % len(ordre))
    print('=' * 74)
    print()
    print('%-22s %5s %8s  %-10s %-10s %s'
          % ('personne', 'msg', 'car.', 'premier', 'dernier', 'salons'))
    print('-' * 74)
    for nom, f in ordre:
        salons = ', '.join('%s:%d' % (s, n) for s, n in f['salons'].most_common())
        print('%-22s %5d %8d  %-10s %-10s %s'
              % (nom[:22], f['messages'], f['caracteres'],
                 f['premier'] or '?', f['dernier'] or '?', salons))
    print()
    print('--- ce que les plus substantiels ont ecrit ---')
    for nom, f in ordre[:8]:
        print()
        print('  %s' % nom)
        for taille, quand, salon, extrait in f['exemples']:
            print('    [%s %s, %d car.] %s' % (quand, salon, taille,
                                               extrait.replace('\n', ' ')))
    for nom, f in proprio.items():
        print()
        print('  (%s, proprietaire : %d messages, non classe)'
              % (nom, f['messages']))


def main():
    # A Windows console defaults to cp1252 and dies on the first accented
    # nickname. Replacing the odd character beats losing the whole report.
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass

    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument('--channels', nargs='+', default=list(DEFAULT_CHANNELS))
    parseur.add_argument('--limit', type=int, default=None,
                         help='stop after N messages per channel (a cheap first run)')
    parseur.add_argument('--json', metavar='FILE',
                         help='also write the raw fold to a file')
    args = parseur.parse_args()

    try:
        made = discord_api.session()
    except discord_api.MissingToken as manque:
        print(manque)
        return 1

    print('reading: %s' % ', '.join(args.channels))
    par_salon = gather(made, args.channels, limit=args.limit)
    for salon, messages in par_salon.items():
        print('  #%-14s %5d messages' % (salon, len(messages)))
    gens, proprio = by_author(par_salon)
    report(gens, proprio)

    if args.json:
        propre = {nom: {**f, 'salons': dict(f['salons'])} for nom, f in gens.items()}
        with open(args.json, 'w', encoding='utf-8') as sortie:
            json.dump(propre, sortie, ensure_ascii=False, indent=1)
        print('\nwritten: %s' % args.json)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
