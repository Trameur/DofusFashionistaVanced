#!/usr/bin/env python3
"""
download_retro_langs.py — Stage 1 of the Dofus Retro data pipeline.

Source (confirmed authoritative + always up to date): Ankama's official
Dofus Retro "lang" CDN.

  manifest : https://dofusretro.cdn.ankama.com/lang/versions_<lang>.txt
             body: "&f=items,fr,1260|itemstats,fr,1259|itemsets,fr,1254|..."
             (each entry = <category>,<lang>,<version>)
  swf file : https://dofusretro.cdn.ankama.com/lang/swf/<category>_<lang>_<version>.swf
             CWS = zlib-compressed SWF (decompress from byte 8).

This stage downloads + decompresses the categories we need and dumps:
  - the raw decompressed SWF bytes      -> retro_raw/<category>_<lang>.swfdata
  - the parsed data as JSON             -> retro_raw/<category>_<lang>.json
    (via retro_swf_parser — pure-Python AS2 extraction, no JPEXS/Java)

Verified: items -> globals['I']['u'] = 11203 records {n,l,t,e,c,s,…}.

Stage 3 (TODO) maps these Retro records onto the internal item model and feeds
the transform/dump/load pipeline to produce items_retro.db, then conditions the
LP solver / smart_build by game_version == 'retro'.
"""

from __future__ import annotations

import argparse
import json
import sys
import zlib
from pathlib import Path

import requests

try:
    from retro_swf_parser import parse_lang_swf
except ImportError:  # when run as a module
    from itemscraper.retro_swf_parser import parse_lang_swf

CDN_BASE = "https://dofusretro.cdn.ankama.com/lang"
# Categories needed to build an equipment optimizer (others exist: spells, maps…)
DEFAULT_CATEGORIES = ['items', 'itemstats', 'itemsets', 'crafts', 'classes', 'effects']


def fetch_manifest(lang: str) -> dict:
    """Return {category: version} parsed from versions_<lang>.txt."""
    url = f"{CDN_BASE}/versions_{lang}.txt"
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    body = resp.text
    # body looks like: &f=items,fr,1260|itemstats,fr,1259|...|
    body = body.split('=', 1)[-1]
    versions = {}
    for entry in body.split('|'):
        parts = entry.split(',')
        if len(parts) == 3:
            cat, elang, ver = parts
            versions[cat.strip()] = ver.strip()
    return versions


def download_swf(category: str, lang: str, version: str, dest_dir: Path) -> bytes:
    url = f"{CDN_BASE}/swf/{category}_{lang}_{version}.swf"
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
    parser.add_argument('--dest', default='itemscraper/retro_raw')
    args = parser.parse_args(argv)

    dest_dir = Path(args.dest)
    print(f"Fetching Retro lang manifest ({args.lang})...")
    versions = fetch_manifest(args.lang)
    if not versions:
        print("No versions parsed from manifest", file=sys.stderr)
        return 1
    print(f"  {len(versions)} categories available")

    for cat in args.categories:
        ver = versions.get(cat)
        if ver is None:
            print(f"  ! category '{cat}' not in manifest, skipping")
            continue
        try:
            raw = download_swf(cat, args.lang, ver, dest_dir)
            print(f"  ok {cat}_{args.lang}_{ver}.swf -> {len(raw)} bytes decompressed")
        except Exception as exc:
            print(f"  FAILED {cat}: {exc}", file=sys.stderr)
    print(f"Done. Decompressed .swfdata + parsed .json in {dest_dir}/")
    print("Next (stage 3): map the parsed Retro records onto the internal item "
          "model -> items_retro.db, and condition the LP solver by game_version.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
