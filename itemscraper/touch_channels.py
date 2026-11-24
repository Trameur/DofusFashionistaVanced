# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The two Dofus Touch data channels, login (live) and early (Ankama's test server), and where each one's files go."""

from __future__ import annotations

import os
import sys

import requests

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(CURRENT_DIR)

DEFAULT_CHANNEL = 'login'
CHANNELS = ('login', 'early')
USER_AGENT = 'Dofus/2 CFNetwork'

_HOSTS = {
    'login': 'https://dt-proxy-production-login.ankama-games.com',
    'early': 'https://dt-proxy-production-early.ankama-games.com',
}
_GAME_VERSIONS = {'login': 'touch', 'early': 'touchbeta'}


def check(channel):
    """The channel name, or a ValueError for one that does not exist."""
    if channel not in _HOSTS:
        raise ValueError('unknown Touch channel %r, expected one of %s'
                         % (channel, ', '.join(CHANNELS)))
    return channel


def host(channel=DEFAULT_CHANNEL):
    """The channel's proxy host, which is also its data host when the config names none."""
    return _HOSTS[check(channel)]


def config_url(channel=DEFAULT_CHANNEL):
    """The URL of the channel's client config.json."""
    return host(channel) + '/config.json'


def fallback_data_url(channel=DEFAULT_CHANNEL):
    """The data host to use when the config cannot be read."""
    return host(channel)


def game_version(channel=DEFAULT_CHANNEL):
    """The registry key the channel's data belongs to."""
    return _GAME_VERSIONS[check(channel)]


def channel_of(game_version):
    """The channel whose data a registry key holds, None for a key of another game."""
    for channel, key in _GAME_VERSIONS.items():
        if key == game_version:
            return channel
    return None


def raw_dir(channel=DEFAULT_CHANNEL):
    """Where the channel's raw tables are saved."""
    return os.path.join(CURRENT_DIR, game_version(channel) + '_raw')


def work_dir(channel=DEFAULT_CHANNEL):
    """Where the channel's transformed files are written."""
    return os.path.join(CURRENT_DIR, game_version(channel))


def dump_path(channel=DEFAULT_CHANNEL):
    """The channel's item database dump."""
    return os.path.join(ROOT, 'fashionistapulp', 'fashionistapulp',
                        'item_db_dumped_%s.dump' % game_version(channel))


def static_subdir(channel=DEFAULT_CHANNEL):
    """The icon folder name of the channel under items, pets, resources and monsters."""
    return game_version(channel)


def add_channel_argument(parser):
    """Add --channel to an argument parser, login by default."""
    parser.add_argument('--channel', choices=CHANNELS, default=DEFAULT_CHANNEL,
                        help='Touch data channel: login (live, default) or early '
                             '(the test server, written under touchbeta_raw)')


def read_config(channel=DEFAULT_CHANNEL, lang='fr', timeout=30):
    """The channel's client config as a dict; raises when it cannot be read."""
    resp = requests.get('%s?lang=%s' % (config_url(channel), lang),
                        headers={'User-Agent': USER_AGENT}, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def data_url(channel=DEFAULT_CHANNEL, lang='fr'):
    """The channel's dataUrl from its config, its own host when unreadable."""
    try:
        found = read_config(channel, lang).get('dataUrl')
        if found:
            return found.rstrip('/')
        print('  ! config.json had no dataUrl; using fallback', file=sys.stderr)
    except Exception as exc:
        print('  ! could not read config.json (%s); using fallback' % exc, file=sys.stderr)
    return fallback_data_url(channel)


def assets_url(channel=DEFAULT_CHANNEL, fallback=''):
    """The channel's assetsUrl from its config, or the fallback when unreadable."""
    try:
        found = read_config(channel).get('assetsUrl')
    except Exception:
        found = None
    return (found or fallback).rstrip('/')


def served_languages(channel=DEFAULT_CHANNEL, lang='fr'):
    """The languages the channel serves from its config; empty when unreadable or not listed."""
    try:
        served = read_config(channel, lang).get('serverLanguages')
        return set(served) if served else set()
    except Exception as exc:
        print('  ! could not read serverLanguages (%s); keeping every language' % exc,
              file=sys.stderr)
        return set()
