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


def gather(made, names, limit=None):
    """{channel: [message]} for the named channels that exist."""
    available = discord_api.channels(made, GUILD)
    missing = [n for n in names if n not in available]
    if missing:
        print('  channels not found, skipped: %s' % ', '.join(missing))
        print('  (the guild has: %s)' % ', '.join(sorted(available)))
    return {n: discord_api.history(made, available[n], limit=limit)
            for n in names if n in available}


def by_author(by_channel, owner_names=('Trameur',)):
    """Fold the messages into one record per person.

    The owner's own messages are counted separately: he answers nearly every
    thread, so leaving him in would put him first on a list meant to surface
    everyone else.
    """
    people = collections.defaultdict(lambda: {
        'messages': 0, 'channels': collections.Counter(), 'first': None,
        'last': None, 'chars': 0, 'examples': [],
    })
    for channel, messages in by_channel.items():
        for m in messages:
            author = m.get('author') or {}
            if author.get('bot'):
                continue
            name = author.get('global_name') or author.get('username') or '?'
            content = (m.get('content') or '').strip()
            if not content:
                continue
            record = people[name]
            record['messages'] += 1
            record['channels'][channel] += 1
            record['chars'] += len(content)
            when = (m.get('timestamp') or '')[:10]
            if record['first'] is None or when < record['first']:
                record['first'] = when
            if record['last'] is None or when > record['last']:
                record['last'] = when
            # The longest messages are the substantial ones: a bug report with
            # steps runs to paragraphs, "thanks!" does not.
            record['examples'].append((len(content), when, channel, content[:160]))
    for record in people.values():
        record['examples'].sort(reverse=True)
        record['examples'] = record['examples'][:2]
    owner = {n: people.pop(n) for n in list(people) if n in owner_names}
    return people, owner


def report(people, owner):
    ranked = sorted(people.items(),
                    key=lambda kv: (-kv[1]['chars'], -kv[1]['messages']))
    print()
    print('=' * 74)
    print('%d people wrote in these channels (owner and bots left out)'
          % len(ranked))
    print('=' * 74)
    print()
    print('%-22s %5s %8s  %-10s %-10s %s'
          % ('person', 'msg', 'chars', 'first', 'last', 'channels'))
    print('-' * 74)
    for name, f in ranked:
        channel_counts = ', '.join('%s:%d' % (s, n) for s, n in f['channels'].most_common())
        print('%-22s %5d %8d  %-10s %-10s %s'
              % (name[:22], f['messages'], f['chars'],
                 f['first'] or '?', f['last'] or '?', channel_counts))
    print()
    print('--- what the most substantial posters wrote ---')
    for name, f in ranked[:8]:
        print()
        print('  %s' % name)
        for size, when, channel, excerpt in f['examples']:
            print('    [%s %s, %d chars] %s' % (when, channel, size,
                                                excerpt.replace('\n', ' ')))
    for name, f in owner.items():
        print()
        print('  (%s, owner: %d messages, not ranked)'
              % (name, f['messages']))


def main():
    # A Windows console defaults to cp1252 and dies on the first accented
    # nickname. Replacing the odd character beats losing the whole report.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--channels', nargs='+', default=list(DEFAULT_CHANNELS))
    parser.add_argument('--limit', type=int, default=None,
                         help='stop after N messages per channel (a cheap first run)')
    parser.add_argument('--json', metavar='FILE',
                         help='also write the raw fold to a file')
    args = parser.parse_args()

    try:
        made = discord_api.session()
    except discord_api.MissingToken as exc:
        print(exc)
        return 1

    print('reading: %s' % ', '.join(args.channels))
    by_channel = gather(made, args.channels, limit=args.limit)
    for channel, messages in by_channel.items():
        print('  #%-14s %5d messages' % (channel, len(messages)))
    people, owner = by_author(by_channel)
    report(people, owner)

    if args.json:
        plain = {name: {**f, 'channels': dict(f['channels'])} for name, f in people.items()}
        with open(args.json, 'w', encoding='utf-8') as out:
            json.dump(plain, out, ensure_ascii=False, indent=1)
        print('\nwritten: %s' % args.json)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
