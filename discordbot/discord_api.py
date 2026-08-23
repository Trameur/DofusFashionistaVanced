"""A thin read-only client for the bits of Discord's API this project needs.

Deliberately not discord.py: reading a channel's history is a handful of REST
calls, while the library brings a websocket gateway, an event loop and a
dependency tree for a job that runs once and exits. If a bot ever has to react
to messages live, that is the moment to add it -- not before.

The token is read from the environment and never printed, never returned, and
never placed in an exception message. Every helper here takes the session, not
the token, so no caller ever holds it.
"""
from __future__ import annotations

import os
import re
import time

import requests

API = 'https://discord.com/api/v10'

#: Discord answers 429 with the wait in seconds. Retrying blindly gets the app
#: temporarily banned, so the wait is honoured, with a ceiling in case the
#: header is absurd.
_MAX_WAIT = 30.0
_MAX_TRIES = 5


class MissingToken(RuntimeError):
    """No token in the environment. The message names the file, not the value."""


def _load_dotenv(path):
    """Minimal .env reader.

    python-dotenv would do, but this is fifteen lines and keeps the repository
    free of a dependency whose only job is parsing KEY=value.
    """
    if not os.path.exists(path):
        return
    with open(path, encoding='utf-8', errors='replace') as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, _, value = line.partition('=')
            key = key.strip()
            if key and key not in os.environ:
                os.environ[key] = value.strip().strip('"').strip("'")


def session(repo_root=None):
    """An authenticated session, or MissingToken.

    Returns a session rather than a token so that the secret lives in one
    object's headers and never travels through the rest of the program.
    """
    root = repo_root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _load_dotenv(os.path.join(root, '.env'))
    token = os.environ.get('DISCORD_BOT_TOKEN', '').strip()
    if not token:
        raise MissingToken(
            'DISCORD_BOT_TOKEN is not set. Put it in %s, one line: '
            'DISCORD_BOT_TOKEN=... (that file is gitignored).'
            % os.path.join(root, '.env'))
    made = requests.Session()
    made.headers.update({
        'Authorization': 'Bot %s' % token,
        'User-Agent': 'DofusFashionista (https://dofusfashionista.gg, 1.0)',
    })
    return made


def _scrub(text):
    """Remove anything token-shaped from a string bound for a log or an error.

    Requests puts the request headers in some exception reprs, and a traceback
    ends up in a terminal, a file, or a bug report. Cheap insurance.
    """
    return re.sub(r'(?i)bot\s+[\w.-]{20,}', 'Bot <redacted>', str(text))


def get(made, path, **params):
    """One GET, honouring rate limits. Raises with the token scrubbed out."""
    for essai in range(_MAX_TRIES):
        answer = made.get(API + path, params=params or None, timeout=30)
        if answer.status_code == 429:
            wait = min(float(answer.headers.get('Retry-After', 1) or 1), _MAX_WAIT)
            time.sleep(wait)
            continue
        if answer.status_code == 403:
            raise PermissionError(
                'Discord refused %s. The bot is probably missing "View Channel" '
                'or "Read Message History" on it.' % path)
        if not answer.ok:
            raise RuntimeError('%s -> %s %s' % (
                path, answer.status_code, _scrub(answer.text[:300])))
        return answer.json()
    raise RuntimeError('%s: still rate limited after %d tries' % (path, _MAX_TRIES))


def write(made, methode, path, **corps):
    """PUT/POST/PATCH, honouring rate limits like get() does.

    Discord's write buckets are much tighter than its read ones: assigning a
    dozen roles in a loop hits 429 immediately, and a 429 that is not waited
    out is simply a lost assignment.
    """
    for _essai in range(_MAX_TRIES):
        answer = made.request(methode, API + path,
                              json=corps or None, timeout=30)
        if answer.status_code == 429:
            wait = min(float(answer.headers.get('Retry-After', 1) or 1), _MAX_WAIT)
            time.sleep(wait)
            continue
        # Discord asks for a pause between writes even when it does not say so.
        time.sleep(0.6)
        return answer
    return answer


def channels(made, guild_id):
    """Every channel of the guild, as {name: id} for text channels."""
    found = get(made, '/guilds/%s/channels' % guild_id)
    # type 0 is a plain text channel; 5 is an announcement channel, which reads
    # the same way.
    return {c['name']: c['id'] for c in found if c.get('type') in (0, 5)}


def history(made, channel_id, limit=None):
    """Every message of a channel, oldest first.

    Discord hands out 100 at a time, newest first, and `before` walks backwards
    from there. The whole history of a small channel is a few calls; `limit`
    exists so a first run can be tried cheaply.
    """
    collected = []
    before = None
    while True:
        params = {'limit': 100}
        if before:
            params['before'] = before
        batch = get(made, '/channels/%s/messages' % channel_id, **params)
        if not batch:
            break
        collected.extend(batch)
        before = batch[-1]['id']
        if limit and len(collected) >= limit:
            break
        if len(batch) < 100:
            break
    collected.reverse()
    return collected[:limit] if limit else collected


def members(made, guild_id):
    """Guild members, as a list. Requires the Server Members intent."""
    collected = []
    after = '0'
    while True:
        batch = get(made, '/guilds/%s/members' % guild_id, limit=1000, after=after)
        if not batch:
            break
        collected.extend(batch)
        after = batch[-1]['user']['id']
        if len(batch) < 1000:
            break
    return collected
