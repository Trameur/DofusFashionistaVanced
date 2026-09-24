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
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--channels', nargs='+',
                         default=['suggestions', 'bug-report'])
    parser.add_argument('--out', default='discordbot/messages.txt')
    parser.add_argument('--max-chars', type=int, default=2500,
                         help='truncate a single message beyond this')
    args = parser.parse_args()

    made = discord_api.session()
    available = discord_api.channels(made, GUILD)
    by_author = collections.defaultdict(list)
    total = 0
    for channel_name in args.channels:
        if channel_name not in available:
            print('  skipped, no such channel: %s' % channel_name)
            continue
        for m in discord_api.history(made, available[channel_name]):
            author = m.get('author') or {}
            if author.get('bot'):
                continue
            content = (m.get('content') or '').strip()
            if not content:
                continue
            who = author.get('global_name') or author.get('username') or '?'
            by_author[who].append((
                (m.get('timestamp') or '')[:10], channel_name, content[:args.max_chars]))
            total += 1
    print('  %d messages from %d people' % (total, len(by_author)))

    ranked = sorted(by_author.items(),
                    key=lambda kv: -sum(len(c) for _d, _s, c in kv[1]))
    with open(args.out, 'w', encoding='utf-8', newline='\n') as handle:
        for who, messages in ranked:
            volume = sum(len(c) for _d, _s, c in messages)
            handle.write('\n\n' + '=' * 72 + '\n')
            handle.write('%s  --  %d messages, %d characters\n'
                         % (who, len(messages), volume))
            handle.write('=' * 72 + '\n')
            for when, channel, content in sorted(messages):
                handle.write('\n[%s #%s]\n%s\n' % (when, channel, content))
    print('  written: %s' % args.out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
