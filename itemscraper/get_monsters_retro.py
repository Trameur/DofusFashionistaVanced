#!/usr/bin/env python3
"""get_monsters_retro.py - build the item -> monster drops index for Dofus Retro.

Unlike the other versions, Retro has no automatable first-party drop source: the
1.29 client / lang files carry monster names and stats but not the drop tables
(those are server-side), and Ankama publishes no Retro monster encyclopedia. The
only maintained, current (1.48) and automatable source is the community reference
Solomonk.fr, which tracks the live game.

Solomonk renders its bestiary through a paginated AJAX endpoint that returns
monster cards keyed by Ankama monster and item ids, in Retro's three official
languages (fr, en, es). This scrapes every monster across those languages and
emits the exact same index shape as the dofusdude-based get_monsters.py:

    {item_ankama_id: [{monster_ankama_id, names{lang}, rates}]}

so store_drops.py loads it unchanged. Item/monster ids are Ankama ids, so they map
straight onto items_retro.db (ankama_id) and the encyclopedia's per-language names.

Usage (from repo root):
    python itemscraper/get_monsters_retro.py --output itemscraper/transformed_drops_retro.json
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

# Dofus Retro's three official languages. pt/de do not exist for Retro, so those
# users fall back to the English monster name (handled by the encyclopedia query).
LANGUAGES: Sequence[str] = ("fr", "en", "es")
DEFAULT_OUTPUT = Path("itemscraper/transformed_drops_retro.json")

BASE = "https://solomonk.fr"
AJAX = BASE + "/ajax/select_monster.php"
REFERER = BASE + "/fr/monstres/chercher"
BATCH = 10  # the endpoint only honours Q=10; larger values return an empty body
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
# Collapse settings the site sends; required for the endpoint to answer. The data
# is present in the HTML regardless of collapse state.
COLLAPSE = {
    "CS[bestiaryCollapseSpells]": "true",
    "CS[bestiaryCollapseSubareas]": "true",
    "CS[bestiaryCollapseDrops]": "true",
    "CS[bestiaryCollapseDropsTemporis]": "true",
}

# The monster title anchor: `card-solo-monster-title"><a ... href=".../<ankama_id>/<slug>">Name</a>`.
# The class marker also appears on a decorative div (followed by <div, not <a>), so we
# require the <a> to pin only real titles; each card spans from one title to the next.
TITLE_RE = re.compile(
    r'card-solo-monster-title"><a[^>]*href="[^"]*?/(\d+)/[^"/]+"[^>]*>([^<]+)</a>')
# One drop: an item link (Ankama id in the path) followed by its ( <rate>% ...).
DROP_RE = re.compile(
    r'href="[^"]*?/(\d+)/[^"/]+"[^>]*>.*?</a>\s*\(\s*([\d.,]+)\s*%', re.S)


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
    # Bound the region to the regular-drops block: stop before the seasonal Temporis
    # drops (a different server's table) if that block follows.
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
    """Parse one page into [(monster_id, monster_name, [(item_id, rate), ...])].

    Each card spans from its title anchor to the next title anchor (or page end)."""
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
    for _ in range(max_pages):
        query = urlencode({"lang": lang, "Q": BATCH, "O": offset, "T": "all", **COLLAPSE})
        data = _http_get_json("%s?%s" % (AJAX, query))
        if not data:
            break
        cards = _parse_cards(data.get("html") or "")
        if not cards:
            break
        for monster_id, name, drops in cards:
            monsters[monster_id] = {"name": name, "drops": drops}
        next_offset = data.get("offset")
        if next_offset is None or next_offset <= offset:
            break
        offset = next_offset
        if delay:
            time.sleep(delay)
    return monsters


def build_drops_index(languages: Sequence[str] = LANGUAGES,
                      delay: float = 0.1, max_pages: int = 400) -> Dict[str, Any]:
    per_lang = {lang: _fetch_language(lang, delay, max_pages) for lang in languages}
    primary = languages[0]  # fr: authoritative for the drop tables

    names_by_monster: Dict[int, Dict[str, str]] = {}
    for lang in languages:
        for monster_id, info in per_lang[lang].items():
            names_by_monster.setdefault(monster_id, {})[lang] = info["name"]

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


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the Retro item->drops index from Solomonk")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--languages", nargs="*", default=list(LANGUAGES))
    parser.add_argument("--delay", type=float, default=0.1,
                        help="seconds between requests (be polite to the source)")
    parser.add_argument("--max-pages", type=int, default=400,
                        help="safety cap on pages fetched per language")
    args = parser.parse_args()

    index = build_drops_index(args.languages, args.delay, args.max_pages)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as fh:
        json.dump(index, fh, ensure_ascii=False)
    total_pairs = sum(len(v) for v in index.values())
    print("items with drops: %d | item/monster pairs: %d -> %s"
          % (len(index), total_pairs, args.output))


if __name__ == "__main__":
    main()
