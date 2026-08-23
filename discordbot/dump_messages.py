"""Every message, in full, grouped by the person who wrote it.

index_contributions.py counts. This one lets someone read. Deciding who
deserves a contributor role from message counts would reward the talkative
over the useful: the biggest poster in this guild spends much of it debating
class balance, and the person with two messages found four real defects in the
Touch data. Only the text tells them apart.

Read-only, like everything else here.
"""
from __future__ import annotations

import argparse
import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import discord_api  # noqa: E402

GUILD = '1188892643766321173'


def main():
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass

    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument('--channels', nargs='+',
                         default=['suggestions', 'bug-report'])
    parseur.add_argument('--out', default='discordbot/messages.txt')
    parseur.add_argument('--max-chars', type=int, default=2500,
                         help='truncate a single message beyond this')
    args = parseur.parse_args()

    made = discord_api.session()
    disponibles = discord_api.channels(made, GUILD)
    par_auteur = collections.defaultdict(list)
    total = 0
    for nom in args.channels:
        if nom not in disponibles:
            print('  skipped, no such channel: %s' % nom)
            continue
        for m in discord_api.history(made, disponibles[nom]):
            auteur = m.get('author') or {}
            if auteur.get('bot'):
                continue
            contenu = (m.get('content') or '').strip()
            if not contenu:
                continue
            qui = auteur.get('global_name') or auteur.get('username') or '?'
            par_auteur[qui].append((
                (m.get('timestamp') or '')[:10], nom, contenu[:args.max_chars]))
            total += 1
    print('  %d messages from %d people' % (total, len(par_auteur)))

    ordre = sorted(par_auteur.items(),
                   key=lambda kv: -sum(len(c) for _d, _s, c in kv[1]))
    with open(args.out, 'w', encoding='utf-8', newline='\n') as sortie:
        for qui, messages in ordre:
            volume = sum(len(c) for _d, _s, c in messages)
            sortie.write('\n\n' + '=' * 72 + '\n')
            sortie.write('%s  --  %d messages, %d characters\n'
                         % (qui, len(messages), volume))
            sortie.write('=' * 72 + '\n')
            for quand, salon, contenu in sorted(messages):
                sortie.write('\n[%s #%s]\n%s\n' % (quand, salon, contenu))
    print('  written: %s' % args.out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
