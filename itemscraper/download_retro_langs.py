#!/usr/bin/env python3
"""
Download and parse the Dofus Retro "lang" files from Ankama's CDN.

These are the same localisation files the Retro client itself downloads, so they're
the authoritative source for items, stats, sets and recipes.

  lang root: the remote dataserver the client config.xml (inside the cytrus
             main manifest) ranks first, plus lang, shaped like
             https://dofusretro.cdn.ankama.com/static-data/<n>/lang
  manifest : <lang root>/versions_<lang>.txt
             body: "&f=items,fr,<version>|itemstats,fr,<version>|..."
             (each entry = <category>,<lang>,<version>)
  swf file : <lang root>/swf/<category>_<lang>_<version>.swf
             CWS = zlib-compressed SWF (decompress from byte 8).

The old root https://dofusretro.cdn.ankama.com/lang still answers but stopped
moving, so it lags the files the live client reads.

With --release beta the config.xml comes from the beta manifest, which names
the beta lang tree, and the files land in retrobeta_raw/.

For each category we want, this downloads and decompresses the SWF and writes:
  - the raw decompressed SWF bytes      -> retro_raw/<category>_<lang>.swfdata
  - the parsed data as JSON             -> retro_raw/<category>_<lang>.json

The parsing (retro_swf_parser) reads the AS2 data in pure Python, so there's no
dependency on JPEXS or a JVM. get_equipments_retro.py takes it from here.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import zlib
from pathlib import Path
from urllib.parse import urlparse
from xml.etree import ElementTree

import requests

try:
    from retro_swf_parser import parse_lang_swf
except ImportError:  # when run as a module
    from itemscraper.retro_swf_parser import parse_lang_swf

try:
    import cytrus_cdn
except ImportError:
    from itemscraper import cytrus_cdn

try:
    import retro_release
except ImportError:
    from itemscraper import retro_release

CLIENT_CONFIG = 'resources/app/retroclient/config.xml'
LANG_ROOT_ENV = 'RETRO_LANG_ROOT'
LANG_HOST_SUFFIX = '.ankama.com'
_resolved_roots = {}
# Categories needed to build an equipment optimizer (others exist: spells, maps…)
DEFAULT_CATEGORIES = ['items', 'itemstats', 'itemsets', 'crafts', 'classes', 'effects']


def lang_root_from_config(config) -> str:
    """The lang folder of the remote dataserver the Retro client config ranks first."""
    tree = ElementTree.fromstring(config)
    remote = []
    for server in tree.iter('dataserver'):
        url = (server.get('url') or '').strip()
        if server.get('type') == 'local':
            continue
        parsed = urlparse(url)
        if parsed.scheme != 'https' or not (parsed.hostname or '').endswith(LANG_HOST_SUFFIX):
            raise ValueError(f"unexpected Retro dataserver {url!r}")
        remote.append((int(server.get('priority')), url))
    if not remote:
        raise ValueError("no remote dataserver in the Retro client config")
    first = min(priority for priority, _url in remote)
    urls = sorted({url.rstrip('/') for priority, url in remote if priority == first})
    if len(urls) != 1:
        raise ValueError(f"{len(urls)} Retro dataservers share priority {first}: {urls}")
    return urls[0] + '/lang'


def client_config(release: str = 'retro', manifest: bytes | None = None) -> bytes:
    """config.xml of the Retro client build cytrus serves for this release."""
    if manifest is None:
        manifest = cytrus_cdn.download_manifest(release)
    entry = cytrus_cdn.find_file(manifest, CLIENT_CONFIG)
    if entry is None:
        raise LookupError(f"{CLIENT_CONFIG} is not in the {release} manifest")
    return cytrus_cdn.fetch_file(entry, game=cytrus_cdn.RELEASES[release][0])


def lang_root_env(release: str = 'retro') -> str:
    """The variable a pipeline hands its resolved lang root through: RETRO_LANG_ROOT for main."""
    return LANG_ROOT_ENV if release == 'retro' else '%s_LANG_ROOT' % release.upper()


def lang_root(release: str = 'retro', manifest: bytes | None = None) -> str:
    """The lang root the Retro client of this release reads, or the one its pipeline already resolved."""
    if manifest is None:
        override = os.environ.get(lang_root_env(release), '').strip()
        if override:
            return override.rstrip('/')
        if release in _resolved_roots:
            return _resolved_roots[release]
    root = lang_root_from_config(client_config(release, manifest))
    _resolved_roots[release] = root
    return root


def parse_manifest(body: str) -> dict:
    """{category: version} from the body of versions_<lang>.txt."""
    body = body.split('=', 1)[-1]
    versions = {}
    for entry in body.split('|'):
        parts = entry.split(',')
        if len(parts) == 3:
            cat, elang, ver = parts
            versions[cat.strip()] = ver.strip()
    return versions


def fetch_manifest(lang: str, root: str | None = None) -> dict:
    """Return {category: version} parsed from versions_<lang>.txt."""
    url = f"{root or lang_root()}/versions_{lang}.txt"
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    return parse_manifest(resp.text)


def download_swf(category: str, lang: str, version: str, dest_dir: Path,
                 root: str | None = None) -> bytes:
    url = f"{root or lang_root()}/swf/{category}_{lang}_{version}.swf"
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    data = resp.content
    if data[:3] not in (b'CWS', b'FWS'):
        raise ValueError(f"{url} did not return a SWF (got {data[:8]!r})")
    if data[:3] == b'CWS':
        raw = zlib.decompress(data[8:])
    else:  # FWS = uncompressed
        raw = data[8:]
    dest_dir.mkdir(parents=True, exist_ok=True)
    (dest_dir / f"{category}_{lang}.swfdata").write_bytes(raw)
    # Parse the AS2 data into structured JSON (the real payload).
    try:
        globals_ = parse_lang_swf(data)
        (dest_dir / f"{category}_{lang}.json").write_text(
            json.dumps(globals_, ensure_ascii=False), encoding='utf-8')
    except Exception as exc:
        print(f"    (parse skipped for {category}: {exc})", file=sys.stderr)
    return raw


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--lang', default='fr')
    parser.add_argument('--categories', nargs='*', default=DEFAULT_CATEGORIES)
    parser.add_argument('--dest', default=None,
                        help='default itemscraper/retro_raw, or the beta raw folder with --release beta')
    retro_release.add_release_argument(parser)
    args = parser.parse_args(argv)

    if args.dest is None:
        args.dest = (str(retro_release.raw_dir(args.release)) if retro_release.is_beta(args.release)
                     else 'itemscraper/retro_raw')
    dest_dir = Path(args.dest)
    root = lang_root(retro_release.version_key(args.release))
    print(f"Fetching Retro lang manifest ({args.lang}) from {root}...")
    versions = fetch_manifest(args.lang, root)
    if not versions:
        print("No versions parsed from manifest", file=sys.stderr)
        return 1
    print(f"  {len(versions)} categories available")

    for cat in args.categories:
        ver = versions.get(cat)
        if ver is None:
            print(f"  warning: category '{cat}' not in manifest, skipping")
            continue
        try:
            raw = download_swf(cat, args.lang, ver, dest_dir, root)
            print(f"  ok {cat}_{args.lang}_{ver}.swf -> {len(raw)} bytes decompressed")
        except Exception as exc:
            print(f"  FAILED {cat}: {exc}", file=sys.stderr)
    print(f"Done. Decompressed .swfdata + parsed .json in {dest_dir}/")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
