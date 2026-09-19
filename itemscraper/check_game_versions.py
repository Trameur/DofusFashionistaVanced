#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""What each Dofus version is running, from its own source. Exits 1 if item data
moved, or if an official update list is ahead of our labels or unreadable.

    python itemscraper/check_game_versions.py
    python itemscraper/check_game_versions.py --updates touch=1.75 retro=1.49

Dofus 3, Retro and Touch are also compared with the newest "MAJ x.y" of their
official update list. A newer update is only reported; --updates takes numbers
read in a browser when a list cannot be fetched.

Dofus 3, the beta and Dofus 2 are watched on the version they publish. Touch
does not publish a useful public version, so it is watched on the asset bundle
its client config points at. Retro's public version and client build are not
enough: its item data comes from the lang CDN, so the lang category versions are
the release gate and the client build is only printed as a diagnostic.
"""
from __future__ import annotations

import hashlib
import http.client
import http.cookiejar
import json
import os
import re
import sys
import urllib.request
from html.parser import HTMLParser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cytrus_cdn

TOUCH_CONFIG = 'https://dt-proxy-production-login.ankama-games.com/config.json?lang=fr'
TAGS = 'https://api.github.com/repos/dofusdude/%s/tags'
USER_AGENT = 'Dofus Fashionista version watch'
BROWSER_AGENT = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                 '(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36')

UPDATE_LISTS = {
    'dofus3': 'https://www.dofus.com/fr/mmorpg/actualites/maj',
    'retro': 'https://www.dofus-retro.com/fr/mmorpg/actualites/maj',
    'touch': 'https://www.dofus-touch.com/fr/mmorpg/actualites/maj',
}
UPDATE_ENTRY = re.compile(r'\bM[AÀ]J\s*(\d+\.\d+)(?![.\d])', re.IGNORECASE)
PATCH = re.compile(r'\d+\.\d+')


def _json(url):
    request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.load(response)


def cytrus_version(game_version, raw=None):
    """Strips the client generation prefix."""
    raw = raw or cytrus_cdn.get_version(game_version)
    return raw.split('_', 1)[-1] if '_' in raw else raw


def retro_lang_versions():
    """{category: version} for the lang files the item pipeline reads."""
    import fashionista_version as ours
    from download_retro_langs import fetch_manifest
    live = fetch_manifest('fr')
    return {name: str(live.get(name, 'missing'))
            for name in ours.WATCHED_RETRO_LANG}


# The four clip families the Retro renderers actually read, and nothing else.
# sprites/accessories/ and sprites/chevauchor/ are deliberately out: both moved
# in 1.49.0 and 1.49.1, and no renderer here reads them.
RETRO_ASSET_FAMILIES = (
    ('items', re.compile(
        r'^resources/app/retroclient/clips/items/\d+/\d+\.swf$')),
    ('spells', re.compile(
        r'^resources/app/retroclient/clips/spells/icons/up/\d+\.swf$')),
    ('artworks', re.compile(
        r'^resources/app/retroclient/clips/artworks/big/\d+\.swf$')),
    ('sprites', re.compile(
        r'^resources/app/retroclient/clips/sprites/\d+\.swf$')),
)


def retro_asset_entries(version=None, manifest=None):
    """{name: "hash size"} for every Retro clip this site renders.

    This replaces a nine-file sample that could not do the job. Measured over
    the four Retro build transitions in this repo's history: three of them
    moved rendered clips, and the sample fired on 0 of 9 every time. It could
    not have done better, for two reasons. Its nine names are ids 1, 31, 40,
    100 and 101, the oldest content in a 2004 game, byte-identical at every
    version; and it looked each name UP, so a file that did not exist before
    was never a key and an addition was structurally invisible. 38 of the 48
    rendered changes in 1.48.21 to 1.49.0 were pure additions.

    Reading every watched entry is not the expensive option, it is the cheap
    one. The sample already downloaded this whole 6.9 MB manifest and threw
    away all but nine entries, and its nine find_file calls cost eight times
    the single pass that collects all 9428.
    """
    if manifest is None:
        manifest = cytrus_cdn.download_manifest('retro', version=version)
    out = {}
    for fragment, name, size, digest in cytrus_cdn.iter_entries(manifest):
        if fragment != 'classic':
            continue
        for _family, pattern in RETRO_ASSET_FAMILIES:
            if pattern.match(name):
                out[name] = '%s %d' % (digest, size)
                break
    return out


def retro_asset_digest(entries):
    """One sha1 over the whole watch set. Never write this by hand: the mode
    that prints it reads the live manifest, and a digest typed from a report is
    a digest nobody can reproduce."""
    lines = ''.join('%s %s' % (name, entries[name]) + chr(10)
                    for name in sorted(entries))
    return hashlib.sha1(lines.encode('utf-8')).hexdigest()


def retro_asset_family(name):
    for family, pattern in RETRO_ASSET_FAMILIES:
        if pattern.match(name):
            return family
    return 'other'


def retro_asset_diff(previous, current):
    """{family: {added, removed, changed}} between two entry sets."""
    report = {}
    for name in set(previous) | set(current):
        family = retro_asset_family(name)
        bucket = report.setdefault(
            family, {'added': [], 'removed': [], 'changed': []})
        if name not in previous:
            bucket['added'].append(name)
        elif name not in current:
            bucket['removed'].append(name)
        elif previous[name] != current[name]:
            bucket['changed'].append(name)
    return {family: bucket for family, bucket in report.items()
            if bucket['added'] or bucket['removed'] or bucket['changed']}


def touch_assets():
    url = _json(TOUCH_CONFIG).get('assetsUrl', '')
    return url.rsplit('/', 1)[-1] if url else ''


def patch_key(patch):
    return tuple(int(part) for part in patch.split('.'))


class _MainListLinks(HTMLParser):
    """(href, text) of every link inside <main>; the correctifs sit in <aside>."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.href = None
        self.text = []
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == 'main':
            self.depth += 1
        elif tag == 'a' and self.depth:
            self.href = dict(attrs).get('href') or ''
            self.text = []

    def handle_endtag(self, tag):
        if tag == 'main':
            self.depth = max(0, self.depth - 1)
        elif tag == 'a' and self.href is not None:
            self.links.append((self.href, ' '.join(''.join(self.text).split())))
            self.href = None

    def handle_data(self, data):
        if self.href is not None:
            self.text.append(data)


def newest_update(html):
    """(patch, href) of the highest "MAJ x.y" in the page's main list, or None."""
    parser = _MainListLinks()
    parser.feed(html)
    parser.close()
    found = []
    for href, text in parser.links:
        match = UPDATE_ENTRY.search(text)
        if match:
            found.append((patch_key(match.group(1)), match.group(1), href))
    if not found:
        return None
    _key, patch, href = max(found)
    return patch, href


def fetch_update_list(url):
    # Every first visit bounces through account.ankama.com and back with a cookie
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    opener.addheaders = [
        ('User-Agent', BROWSER_AGENT),
        ('Accept', 'text/html,application/xhtml+xml'),
        ('Accept-Language', 'fr-FR,fr;q=0.9'),
    ]
    with opener.open(url, timeout=60) as response:
        charset = response.headers.get_content_charset() or 'utf-8'
        return response.read().decode(charset, 'replace')


def read_update_list(key):
    return newest_update(fetch_update_list(UPDATE_LISTS[key]))


def our_patches():
    """{key: (label patch, PATCH_STARTED patch)} for the versions with an update list."""
    import fashionista_version as ours
    labels = {'dofus3': ours.FASHIONISTA_VERSION,
              'retro': ours.FASHIONISTA_RETRO_VERSION,
              'touch': ours.FASHIONISTA_TOUCH_VERSION}
    return {key: ('.'.join(label.split('.')[:2]), ours.PATCH_STARTED[key][0])
            for key, label in labels.items()}


def updates_behind(newest, ours=None):
    """{key: (newest, label patch, started patch)} where either of ours is older."""
    ours = our_patches() if ours is None else ours
    behind = {}
    for key, patch in newest.items():
        label, started = ours[key]
        if patch_key(patch) > min(patch_key(label), patch_key(started)):
            behind[key] = (patch, label, started)
    return behind


def report_updates(newest, where=None):
    """Prints one line per list and returns the (name, patch) pairs that need a look."""
    ours = our_patches()
    behind = updates_behind(newest, ours)
    flagged = []
    for key in sorted(newest):
        label, started = ours[key]
        print('%-8s update MAJ %-6s label %-6s started %-6s %s%s'
              % (key, newest[key], label, started,
                 'NEWER' if key in behind else 'ok',
                 '   (%s)' % where[key] if where and key in where else ''))
        if key not in behind:
            continue
        flagged.append(('%s update' % key, newest[key]))
        if key == 'dofus3':
            print('  update_data.py --version <tag> moves the label and '
                  'PATCH_STARTED once dofusdude publishes the tag')
        else:
            print('  re-scrape with update_data_%s.py, then set its label and '
                  'PATCH_STARTED by hand' % key)
    return flagged


def check_update_lists():
    newest, where, flagged = {}, {}, []
    for key, url in UPDATE_LISTS.items():
        reason = 'no MAJ entry in its main list'
        try:
            found = read_update_list(key)
        except (OSError, http.client.HTTPException) as exc:
            found, reason = None, exc
        if found is None:
            print('%-8s update list UNREADABLE (%s): read %s in the browser, '
                  'then --updates %s=x.y' % (key, reason, url, key))
            flagged.append(('%s update list' % key, 'unreadable'))
        else:
            newest[key], where[key] = found
    return flagged + report_updates(newest, where)


def updates_from_argv(pairs):
    newest = {}
    for pair in pairs:
        key, _sep, patch = pair.partition('=')
        if key not in UPDATE_LISTS or not PATCH.fullmatch(patch):
            print('expected %s=x.y, got %r' % ('|'.join(UPDATE_LISTS), pair))
            return 2
        newest[key] = patch
    if not newest:
        print('expected at least one %s=x.y' % '|'.join(UPDATE_LISTS))
        return 2
    return 1 if report_updates(newest) else 0


def emit_snapshot():
    """Print the two lines fashionista_version.py should carry, read live.

    The point is that nobody types a digest. A digest copied out of a report is
    a digest no one can reproduce, and three of four hand-carried ones in the
    proposal that led to this code were wrong.
    """
    entries = retro_asset_entries()
    print('WATCHED_RETRO_ASSET_DIGEST = "%s"' % retro_asset_digest(entries))
    print('WATCHED_RETRO_ASSET_COUNT = %d' % len(entries))
    return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if '--emit-snapshot' in argv:
        return emit_snapshot()
    if '--updates' in argv:
        return updates_from_argv(argv[argv.index('--updates') + 1:])

    import fashionista_version as ours

    # Touch keeps the same public number across content patches, so it is
    # watched on its asset bundle. Retro is handled below through lang files.
    checks = [
        ('dofus3', ours.FASHIONISTA_VERSION, cytrus_version('dofus3'), None),
        ('beta', ours.FASHIONISTA_BETA_VERSION, cytrus_version('beta'), None),
        ('dofus2', ours.FASHIONISTA_DOFUS2_VERSION, cytrus_version('dofus2'), None),
        ('touch', ours.FASHIONISTA_TOUCH_VERSION, touch_assets(),
         ours.WATCHED_TOUCH_ASSETS),
    ]
    moved = []
    for name, shown, live, watched in checks:
        compared = watched if watched is not None else shown
        same = live == compared
        if not same:
            moved.append((name, live))
        # Print what was compared. Showing the frozen public number beside a
        # different live build, followed by ok, reads as a contradiction.
        print('%-8s ours %-40s live %-40s %s%s'
              % (name, compared, live, 'ok' if same else 'MOVED',
                 '' if watched is None else '   (public number %s)' % shown))

    retro_raw_build = cytrus_cdn.get_version('retro')
    # Downloaded once and passed around: the asset comparison and the diff that
    # names what moved both read it.
    retro_manifest = cytrus_cdn.download_manifest('retro', version=retro_raw_build)
    retro_build = cytrus_version('retro', retro_raw_build)
    print('%-8s build %-40s live %-40s %s   (public number %s; item data watches lang)'
          % ('retro', ours.WATCHED_RETRO_BUILD, retro_build,
             'ok' if retro_build == ours.WATCHED_RETRO_BUILD else 'changed',
             ours.FASHIONISTA_RETRO_VERSION))

    for name, repo in (('dofus3', 'dofus3-main'), ('beta', 'dofus3-beta')):
        tag = _json(TAGS % repo)[0]['name']
        print('%-8s tag  %s' % (name, tag))

    import fashionista_version as watched
    live_lang = retro_lang_versions()
    lang_moved = sorted(name for name, version in live_lang.items()
                        if version != watched.WATCHED_RETRO_LANG[name])
    print('%-8s lang %s'
          % ('retro', ', '.join('%s=%s' % (name, live_lang[name])
                                for name in sorted(live_lang))))
    if lang_moved:
        moved.append(('retro lang', ', '.join(lang_moved)))
        print('retro lang MOVED on %s, re-scrape retro and update '
              'WATCHED_RETRO_LANG' % ', '.join(lang_moved))

    # Unconditionally, and not only when the build moved with the lang data
    # standing still. Gating the image question on the item question silenced
    # it exactly on the content patches where images matter most, and the
    # comparison costs 0.07s on a manifest this script already downloads.
    live_entries = retro_asset_entries(manifest=retro_manifest)
    live_digest = retro_asset_digest(live_entries)
    assets_moved = live_digest != ours.WATCHED_RETRO_ASSET_DIGEST
    print('%-8s assets %s (%d files, digest %s)'
          % ('retro', 'MOVED' if assets_moved else 'ok',
             len(live_entries), live_digest[:8]))
    if assets_moved:
        moved.append(('retro assets', live_digest))
        # Name what moved rather than only that something did. Manifests are
        # version-addressed and Ankama still serves the old ones, so the
        # previous build is one download away and nothing has to be committed
        # to keep a reference copy.
        prefix = retro_raw_build.split('_', 1)[0] + '_' if '_' in retro_raw_build else ''
        try:
            previous = retro_asset_entries(
                version=prefix + ours.WATCHED_RETRO_BUILD)
        except Exception as exc:
            print('  could not read the %s manifest to say what moved (%s)'
                  % (ours.WATCHED_RETRO_BUILD, exc))
        else:
            report = retro_asset_diff(previous, live_entries)
            for family in sorted(report):
                bucket = report[family]
                print('  %-9s +%d -%d ~%d   %s'
                      % (family, len(bucket['added']), len(bucket['removed']),
                         len(bucket['changed']),
                         ', '.join(sorted(bucket['added'] + bucket['changed'])[:3])))
            print('  refresh the Retro images for those families, then run '
                  '--emit-snapshot and paste the two lines it prints')

    moved.extend(check_update_lists())

    for name, live in moved:
        if name == 'touch':
            print('after re-scraping %s, set WATCHED_%s_%s = "%s"'
                  % (name, name.upper(),
                     'ASSETS', live))
    if retro_build != ours.WATCHED_RETRO_BUILD and not lang_moved and not assets_moved:
        print('retro build moved but the lang data and all %d rendered clips '
              'are unchanged; no item re-scrape or image refresh required'
              % len(live_entries))
    return 1 if moved else 0


if __name__ == '__main__':
    sys.exit(main())
