#!/usr/bin/env python3
"""Retro item -> monster drops index from Solomonk.fr, shaped like get_monsters.py.

Usage (from repo root):
    python itemscraper/get_monsters_retro.py --output itemscraper/transformed_drops_retro.json

With --release beta nothing is asked from Solomonk, which shows the live
servers: the beta rows come from the beta lang monsterdrops category where it
differs from main's, the main rows are reused where it does not, and every
main row is reused when the category does not answer. The counts are printed.
"""
from __future__ import annotations

import argparse
import html
import http.client
import json
import re
import struct
import sys
import time
import zlib
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.append(str(Path(__file__).resolve().parent))
import retro_release  # noqa: E402

# Solomonk only answers fr, en and es; pt and de come from Ankama below
LANGUAGES: Sequence[str] = ("fr", "en", "es")
DEFAULT_OUTPUT = Path("itemscraper/transformed_drops_retro.json")
MAIN_DROPS = Path(__file__).resolve().parent / "transformed_drops_retro.json"
BETA_OUTPUT_NAME = "transformed_drops_retrobeta.json"
NAME_LANGUAGES: Sequence[str] = ("fr", "en", "es", "pt", "de")

BASE = "https://solomonk.fr"
AJAX = BASE + "/ajax/select_monster.php"
REFERER = BASE + "/fr/monstres/chercher"
BATCH = 10  # the endpoint only honours Q=10; larger values return an empty body
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
# The endpoint only answers when these collapse settings are sent.
COLLAPSE = {
    "CS[bestiaryCollapseSpells]": "true",
    "CS[bestiaryCollapseSubareas]": "true",
    "CS[bestiaryCollapseDrops]": "true",
    "CS[bestiaryCollapseDropsTemporis]": "true",
}

# card-solo-monster-title also sits on a decorative div, hence the <a>
TITLE_RE = re.compile(
    r'card-solo-monster-title"><a[^>]*href="[^"]*?/(\d+)/[^"/]+"[^>]*>([^<]+)</a>')
# Item link then ( <rate>%, the rate bare or in a span whose text is the rank 1 rate
DROP_RE = re.compile(
    r'href="[^"]*?/(\d+)/[^"/]+"[^>]*>.*?</a>\s*\(\s*(?:<span[^>]*>\s*)?'
    r'([\d.,]+)\s*(?:</span>)?\s*%', re.S)


def _http_get_json(url: str, retries: int = 3, timeout: int = 30) -> Dict[str, Any] | None:
    req = Request(url, headers={
        "User-Agent": USER_AGENT,
        "X-Requested-With": "XMLHttpRequest",
        "Referer": REFERER,
        "Accept": "*/*",
        "Accept-Language": "fr,en;q=0.8",
    })
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            with urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8", "replace")
            if not raw.strip():
                return None  # past the last page: empty body
            return json.loads(raw)
        except (URLError, HTTPError, TimeoutError) as exc:
            last_err = exc
            time.sleep(1.5 * (attempt + 1))
        except json.JSONDecodeError:
            return None  # non-JSON => treat as end-of-data
    raise RuntimeError("Solomonk request failed after %d retries: %s" % (retries, last_err))


def _parse_drops(card_html: str) -> List[Tuple[int, float]]:
    """Extract [(item_ankama_id, rate)] from one monster card's regular-drops block."""
    start = card_html.find('data-collapse-target="bestiaryCollapseDrops"')
    if start == -1:
        return []  # class invocations and some monsters have no drops
    # Temporis drops are a seasonal server's own table, not regular drops.
    end = card_html.find("bestiaryCollapseDropsTemporis", start)
    region = card_html[start:end] if end != -1 else card_html[start:]
    drops: List[Tuple[int, float]] = []
    for item_id, rate_txt in DROP_RE.findall(region):
        try:
            rate = float(rate_txt.replace(",", "."))
        except ValueError:
            continue
        if rate > 0:
            drops.append((int(item_id), rate))
    return drops


def _parse_cards(page_html: str) -> List[Tuple[int, str, List[Tuple[int, float]]]]:
    """Parse one page into [(monster_id, monster_name, [(item_id, rate), ...])]."""
    titles = list(TITLE_RE.finditer(page_html))
    cards: List[Tuple[int, str, List[Tuple[int, float]]]] = []
    for i, match in enumerate(titles):
        monster_id = int(match.group(1))
        monster_name = html.unescape(match.group(2)).strip()
        if not monster_name:
            continue
        span_end = titles[i + 1].start() if i + 1 < len(titles) else len(page_html)
        card_html = page_html[match.end():span_end]
        cards.append((monster_id, monster_name, _parse_drops(card_html)))
    return cards


def _fetch_language(lang: str, delay: float, max_pages: int,
                    ) -> Dict[int, Dict[str, Any]]:
    """Return {monster_id: {"name": str, "drops": [(item_id, rate)]}} for one lang."""
    monsters: Dict[int, Dict[str, Any]] = {}
    offset = 0
    pages_done = 0
    empty_streak = 0
    while pages_done < max_pages:
        query = urlencode({"lang": lang, "Q": BATCH, "O": offset, "T": "all", **COLLAPSE})
        data = _http_get_json("%s?%s" % (AJAX, query))
        cards = _parse_cards((data or {}).get("html") or "")
        if not cards:
            # The endpoint sometimes serves an empty page mid-crawl
            empty_streak += 1
            if empty_streak > 2:
                break
            time.sleep(2.0)
            continue
        empty_streak = 0
        pages_done += 1
        for monster_id, name, drops in cards:
            monsters[monster_id] = {"name": name, "drops": drops}
        next_offset = data.get("offset")
        if next_offset is None or next_offset <= offset:
            break
        offset = next_offset
        if delay:
            time.sleep(delay)
    return monsters


# Ankama's Retro lang files, for the languages Solomonk lacks
ANKAMA_LANGUAGES: Sequence[str] = ("pt", "de")
# Far below this means the payload key moved
MIN_ANKAMA_NAMES = 800


def _ankama_lang_root(release: str = retro_release.MAIN) -> str:
    """The lang root the Retro client of this release reads."""
    try:
        from download_retro_langs import lang_root
    except ImportError:
        from itemscraper.download_retro_langs import lang_root
    if retro_release.is_beta(release):
        return lang_root(retro_release.version_key(release))
    return lang_root()


def _ankama_manifest(lang: str, root: str) -> Dict[str, str]:
    """{category: version} parsed from versions_<lang>.txt."""
    request = Request("%s/versions_%s.txt" % (root, lang),
                      headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=60) as response:
        body = response.read().decode("utf-8", "replace")
    versions: Dict[str, str] = {}
    for entry in body.split("=", 1)[-1].split("|"):
        parts = entry.split(",")
        if len(parts) == 3:
            versions[parts[0].strip()] = parts[2].strip()
    return versions


def ankama_monster_names(languages: Sequence[str] = ANKAMA_LANGUAGES,
                         delay: float = 0.2, root: str | None = None
                         ) -> Dict[int, Dict[str, str]]:
    """Monster names from Ankama's files, as {monster_ankama_id: {lang: name}}."""
    try:
        from retro_swf_parser import parse_lang_swf
    except ImportError:  # when run as a module
        from itemscraper.retro_swf_parser import parse_lang_swf

    names: Dict[int, Dict[str, str]] = {}
    root = root or _ankama_lang_root()
    for lang in languages:
        time.sleep(delay)
        version = _ankama_manifest(lang, root).get("monsters")
        if not version:
            raise RuntimeError(
                "no `monsters` category in the %s manifest: the CDN layout "
                "moved, the names did not disappear" % lang)
        request = Request("%s/swf/monsters_%s_%s.swf"
                          % (root, lang, version),
                          headers={"User-Agent": USER_AGENT})
        with urlopen(request, timeout=120) as response:
            data = response.read()
        entries = (parse_lang_swf(data) or {}).get("M") or {}
        found = 0
        for raw_id, entry in entries.items():
            name = entry.get("n") if isinstance(entry, dict) else None
            if not name:
                continue
            try:
                monster_id = int(raw_id)
            except (TypeError, ValueError):
                continue
            names.setdefault(monster_id, {})[lang] = name
            found += 1
        if found < MIN_ANKAMA_NAMES:
            raise RuntimeError(
                "only %d %s monster names parsed, expected at least %d: the "
                "payload key moved" % (found, lang, MIN_ANKAMA_NAMES))
        print("  ankama %s: %d monster names" % (lang, found))
    return names


def merge_ankama_names(index: Dict[str, Any],
                       languages: Sequence[str] = ANKAMA_LANGUAGES) -> int:
    """Add the Ankama-only languages to monsters the index already has."""
    extra = ankama_monster_names(languages)
    ajoutes = 0
    for monsters in index.values():
        for monster in monsters:
            noms = monster.get("names")
            if not isinstance(noms, dict):
                continue
            for lang, name in (extra.get(monster.get("monster_ankama_id"))
                               or {}).items():
                if not noms.get(lang):
                    noms[lang] = name
                    ajoutes += 1
    return ajoutes


def count_named(index: Dict[str, Any],
                languages: Sequence[str]) -> Dict[str, int]:
    """How many distinct monsters carry a name in each language."""
    par_langue: Dict[str, set] = {lang: set() for lang in languages}
    for monsters in index.values():
        for monster in monsters:
            noms = monster.get("names") or {}
            for lang in languages:
                if noms.get(lang):
                    par_langue[lang].add(monster.get("monster_ankama_id"))
    return {lang: len(ids) for lang, ids in par_langue.items()}


def build_drops_index(languages: Sequence[str] = LANGUAGES,
                      delay: float = 0.1, max_pages: int = 400,
                      ankama_languages: Sequence[str] = ANKAMA_LANGUAGES
                      ) -> Dict[str, Any]:
    per_lang = {lang: _fetch_language(lang, delay, max_pages) for lang in languages}
    primary = languages[0]  # fr: authoritative for the drop tables

    names_by_monster: Dict[int, Dict[str, str]] = {}
    for lang in languages:
        for monster_id, info in per_lang[lang].items():
            names_by_monster.setdefault(monster_id, {})[lang] = info["name"]

    # pt and de from Ankama, only for monsters Solomonk already named
    if ankama_languages:
        for monster_id, extra in ankama_monster_names(
                ankama_languages).items():
            if monster_id in names_by_monster:
                for lang, name in extra.items():
                    names_by_monster[monster_id].setdefault(lang, name)

    # item_ankama_id -> {monster_ankama_id: rate}
    index: Dict[int, Dict[int, float]] = {}
    for monster_id, info in per_lang[primary].items():
        for item_id, rate in info["drops"]:
            per_item = index.setdefault(item_id, {})
            if rate > per_item.get(monster_id, 0):
                per_item[monster_id] = rate

    out: Dict[str, Any] = {}
    for item_id in sorted(index):
        monsters_list = [
            {"monster_ankama_id": monster_id,
             "names": names_by_monster.get(monster_id, {}),
             "rates": [rate]}
            for monster_id, rate in sorted(index[item_id].items(),
                                           key=lambda kv: kv[1], reverse=True)
        ]
        out[str(item_id)] = monsters_list
    return out


def as2_number(value: Any) -> Any:
    """A lang number as the client reads it: the parser takes an AS2 double with its two words swapped."""
    if not isinstance(value, float):
        return value
    low, high = struct.unpack("<II", struct.pack("<d", value))
    return struct.unpack("<d", struct.pack("<II", high, low))[0]


LANG_FAILURES = (OSError, ValueError, IndexError, struct.error, zlib.error, http.client.HTTPException)


def lang_drops(root: str, lang: str = "fr"
               ) -> Tuple[str | None, Dict[Tuple[int, int], Dict[str, Any]] | None]:
    """(version, {(item id, monster id): entry}) of a lang tree's monsterdrops, (None, None) without one."""
    try:
        from retro_swf_parser import parse_lang_swf
    except ImportError:  # when run as a module
        from itemscraper.retro_swf_parser import parse_lang_swf

    version = _ankama_manifest(lang, root).get("monsterdrops")
    if not version:
        return None, None
    request = Request("%s/swf/monsterdrops_%s_%s.swf" % (root, lang, version),
                      headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=120) as response:
        data = response.read()
    table = (parse_lang_swf(data) or {}).get("MD") or {}
    entries: Dict[Tuple[int, int], Dict[str, Any]] = {}
    for monster_id, drops in table.items():
        if not isinstance(drops, dict):
            continue
        for item_id, entry in drops.items():
            if not isinstance(entry, dict):
                continue
            entries[(int(item_id), int(monster_id))] = {
                key: ([as2_number(v) for v in value] if isinstance(value, list)
                      else as2_number(value))
                for key, value in entry.items()}
    return version, entries


def drop_rate(entry: Dict[str, Any]) -> float:
    """The rate of the last grade on Solomonk's scale, the lang rate divided by its sr when it has one."""
    rates = [rate for rate in entry.get("t") or [] if isinstance(rate, (int, float))]
    if not rates:
        return 0.0
    divisor = entry.get("sr")
    if isinstance(divisor, (int, float)) and divisor > 0:
        return float(rates[-1]) / divisor
    return float(rates[-1])


def rate_inputs(entry: Dict[str, Any]) -> Tuple[Any, Any]:
    """The fields of a lang entry that drive its rate."""
    return entry.get("t"), entry.get("sr")


def merge_release_drops(main_index: Dict[str, Any],
                        main_lang: Dict[Tuple[int, int], Dict[str, Any]] | None,
                        lang: Dict[Tuple[int, int], Dict[str, Any]] | None,
                        names_of) -> Tuple[Dict[str, Any], Dict[str, int]]:
    """The drops index of a release: its lang where it differs from main's lang, main's rows elsewhere."""
    counts = {"read": 0, "reused": 0, "reused_unlisted": 0, "removed": 0,
              "zero_rate": 0, "left_out_as_main": 0, "reused_other_fields": 0}
    rows: Dict[Tuple[int, int], Dict[str, Any]] = {}
    for item_id, monsters in main_index.items():
        for row in monsters:
            rows[(int(item_id), int(row["monster_ankama_id"]))] = row
    pairs: Dict[Tuple[int, int], Dict[str, Any]] = {}
    if main_lang is None or lang is None:
        pairs = dict(rows)
        counts["reused"] = len(rows)
    else:
        for pair, row in rows.items():
            ours, theirs = lang.get(pair), main_lang.get(pair)
            if ours is None and theirs is None:
                pairs[pair] = row
                counts["reused_unlisted"] += 1
            elif ours is None:
                counts["removed"] += 1
            elif ours == theirs or (theirs is not None and rate_inputs(ours) == rate_inputs(theirs)):
                pairs[pair] = row
                counts["reused"] += 1
                if ours != theirs:
                    counts["reused_other_fields"] += 1
            elif drop_rate(ours) > 0:
                pairs[pair] = {"monster_ankama_id": pair[1], "names": row.get("names") or {},
                               "rates": [drop_rate(ours)]}
                counts["read"] += 1
            else:
                counts["zero_rate"] += 1
        for pair, ours in sorted(lang.items()):
            if pair in rows:
                continue
            theirs = main_lang.get(pair)
            if theirs is not None and rate_inputs(theirs) == rate_inputs(ours):
                counts["left_out_as_main"] += 1
            elif drop_rate(ours) > 0:
                pairs[pair] = {"monster_ankama_id": pair[1], "names": names_of(pair[1]),
                               "rates": [drop_rate(ours)]}
                counts["read"] += 1
            else:
                counts["zero_rate"] += 1
    by_item: Dict[int, List[Dict[str, Any]]] = {}
    for (item_id, _monster_id), row in pairs.items():
        by_item.setdefault(item_id, []).append(row)
    index = {str(item_id): sorted(by_item[item_id], key=lambda row: (-row["rates"][0],
                                                                     row["monster_ankama_id"]))
             for item_id in sorted(by_item)}
    return index, counts


def build_release_drops(release: str, main_drops: Path) -> Tuple[Dict[str, Any], Dict[str, int]]:
    """The drops index of a release other than main, with the counts it reports."""
    main_index = json.loads(main_drops.read_text(encoding="utf-8"))
    root = _ankama_lang_root(release)
    try:
        version, lang = lang_drops(root)
    except LANG_FAILURES as exc:
        print("the %s monsterdrops did not answer: %s" % (release, exc))
        version, lang = None, None
    main_version, main_lang = (None, None)
    if lang is not None:
        try:
            main_version, main_lang = lang_drops(_ankama_lang_root())
        except LANG_FAILURES as exc:
            print("the main monsterdrops did not answer: %s" % exc)
    known: Dict[int, Dict[str, str]] = {}
    for monsters in main_index.values():
        for row in monsters:
            known.setdefault(int(row["monster_ankama_id"]), row.get("names") or {})
    fetched: Dict[int, Dict[str, str]] = {}

    def names_of(monster_id: int) -> Dict[str, str]:
        if monster_id in known:
            return known[monster_id]
        if not fetched:
            fetched.update(ankama_monster_names(NAME_LANGUAGES, root=root))
        return fetched.get(monster_id, {})

    index, counts = merge_release_drops(main_index, main_lang, lang, names_of)
    if lang is None or main_lang is None:
        retro_release.notice(
            "drops: the %s lang has no monsterdrops to compare (%s %s, main %s), "
            "all %d main rows reused" % (release, release, version, main_version, counts["reused"]))
    else:
        retro_release.notice(
            "drops: monsterdrops %s VERSION %s against main VERSION %s: %d rows read from the %s lang, "
            "%d main rows reused unchanged, %d main rows the lang does not list reused, "
            "%d main rows removed, %d pairs left out as main leaves them, %d at a zero rate; "
            "%d of the reused rows changed only in fields that do not drive the rate, rates on main's scale (t over sr)"
            % (release, version, main_version, counts["read"], release, counts["reused"],
               counts["reused_unlisted"], counts["removed"], counts["left_out_as_main"],
               counts["zero_rate"], counts["reused_other_fields"]))
    return index, counts


# Far below this means the markup moved
MIN_PAIRS = 500


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the Retro item->drops index from Solomonk")
    parser.add_argument("--output", type=Path, default=None,
                        help="default %s, or the beta work folder with --release beta"
                             % DEFAULT_OUTPUT)
    parser.add_argument("--languages", nargs="*", default=list(LANGUAGES))
    parser.add_argument("--delay", type=float, default=0.1,
                        help="seconds between requests (be polite to the source)")
    parser.add_argument("--max-pages", type=int, default=400,
                        help="safety cap on pages fetched per language")
    parser.add_argument("--min-pairs", type=int, default=MIN_PAIRS,
                        help="fail rather than write a suspiciously empty index")
    parser.add_argument("--enrich-only", type=Path, default=None,
                        help="add the languages Solomonk cannot serve to an "
                             "existing index, without rescraping it")
    parser.add_argument("--main-drops", type=Path, default=MAIN_DROPS,
                        help="main's index, which --release beta starts from")
    retro_release.add_release_argument(parser)
    args = parser.parse_args()
    if args.output is None:
        args.output = (retro_release.work_dir(args.release) / BETA_OUTPUT_NAME
                       if retro_release.is_beta(args.release) else DEFAULT_OUTPUT)

    if retro_release.is_beta(args.release):
        if not args.main_drops.exists():
            print("ERROR: %s missing, the beta drops start from main's" % args.main_drops)
            return 1
        index, counts = build_release_drops(args.release, args.main_drops)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", encoding="utf-8") as fh:
            json.dump(index, fh, ensure_ascii=False)
        print("items with drops: %d | item/monster pairs: %d -> %s"
              % (len(index), sum(len(v) for v in index.values()), args.output))
        return 0

    if args.enrich_only:
        with args.enrich_only.open(encoding="utf-8") as fh:
            index = json.load(fh)
        toutes = tuple(args.languages) + tuple(ANKAMA_LANGUAGES)
        avant = count_named(index, toutes)
        merge_ankama_names(index)
        apres = count_named(index, toutes)
        for lang in toutes:
            print("  %s: %d -> %d monsters named"
                  % (lang, avant[lang], apres[lang]))
        if any(apres[lang] <= avant[lang] for lang in ANKAMA_LANGUAGES):
            print("ERROR: no language gained a name; nothing written.")
            return 1
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", encoding="utf-8") as fh:
            json.dump(index, fh, ensure_ascii=False)
        print("enriched -> %s" % args.output)
        return 0

    index = build_drops_index(args.languages, args.delay, args.max_pages)
    total_pairs = sum(len(v) for v in index.values())
    if total_pairs < args.min_pairs:
        print("ERROR: only %d item/monster pairs, expected at least %d. "
              "The source markup has probably changed; %s left untouched."
              % (total_pairs, args.min_pairs, args.output))
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as fh:
        json.dump(index, fh, ensure_ascii=False)
    print("items with drops: %d | item/monster pairs: %d -> %s"
          % (len(index), total_pairs, args.output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
