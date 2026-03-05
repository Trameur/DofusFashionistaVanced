#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
from typing import Iterable, List, Optional

import requests

try:
    from fashionista_version import FASHIONISTA_VERSION
except ModuleNotFoundError:
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from fashionista_version import FASHIONISTA_VERSION

API_ROOT = "https://api.github.com"
DEFAULT_REPO = "dofusdude/dofus3-main"
DEFAULT_TAG = FASHIONISTA_VERSION
DEFAULT_DEST = "itemscraper/raw"


def _build_headers() -> dict:
    headers = {"Accept": "application/vnd.github+json"}
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _fetch_release_json(repo: str, tag: str) -> dict:
    url = f"{API_ROOT}/repos/{repo}/releases/tags/{tag}"
    response = requests.get(url, headers=_build_headers(), timeout=60)
    response.raise_for_status()
    return response.json()


def _match_filters(name: str, filters: Optional[List[str]]) -> bool:
    if not filters:
        return True
    lowered = name.lower()
    return any(substr.lower() in lowered for substr in filters)


def _human_size(num: int) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if num < 1024 or unit == "TB":
            return f"{num:.1f} {unit}" if unit != "B" else f"{num} {unit}"
        num /= 1024
    return f"{num:.1f} TB"


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, headers=_build_headers(), timeout=60) as r:
        r.raise_for_status()
        total = int(r.headers.get("Content-Length", 0))
        downloaded = 0
        chunk_size = 1024 * 1024  # 1 MB
        with open(dest, "wb") as fh:
            for chunk in r.iter_content(chunk_size=chunk_size):
                if not chunk:
                    continue
                fh.write(chunk)
                downloaded += len(chunk)
                if total:
                    percent = downloaded / total * 100
                    sys.stdout.write(
                        f"\r    -> {dest.name}: {downloaded/1024/1024:7.1f} MB / {total/1024/1024:7.1f} MB ({percent:5.1f}%)"
                    )
                else:
                    sys.stdout.write(f"\r    -> {dest.name}: {downloaded/1024/1024:7.1f} MB downloaded")
                sys.stdout.flush()
        sys.stdout.write("\n")


def download_assets(
    repo: str,
    tag: str,
    dest_root: Path,
    filters: Optional[List[str]] = None,
    skip_existing: bool = True,
    list_only: bool = False,
) -> None:
    release = _fetch_release_json(repo, tag)
    assets = release.get("assets", [])
    if not assets:
        print(f"No assets found for {repo}@{tag}")
        return

    target_dir = dest_root / tag
    for asset in assets:
        name = asset.get("name")
        url = asset.get("browser_download_url")
        size = asset.get("size", 0)
        if not name or not url:
            continue
        if not _match_filters(name, filters):
            continue

        dest_path = target_dir / name
        human = _human_size(size)
        status = "exists" if dest_path.exists() else "missing"
        print(f"- {name} ({human}) -> {dest_path} [{status}]")

        if list_only:
            continue
        if dest_path.exists() and skip_existing:
            continue

        _download(url, dest_path)


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=DEFAULT_REPO, help="GitHub repo in owner/name format")
    parser.add_argument("--tag", default=DEFAULT_TAG, help="Release tag to download")
    parser.add_argument(
        "--dest",
        default=DEFAULT_DEST,
        help="Destination directory root (tag will be appended).",
    )
    parser.add_argument(
        "--filter",
        action="append",
        dest="filters",
        help="Download only assets whose names contain the substring. Repeatable.",
    )
    parser.add_argument(
        "--no-skip-existing",
        action="store_false",
        dest="skip_existing",
        help="Re-download files even if they already exist.",
    )
    parser.add_argument(
        "--list-only",
        action="store_true",
        help="Only list matching assets without downloading them.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv)
    dest_root = Path(args.dest)
    try:
        download_assets(
            repo=args.repo,
            tag=args.tag,
            dest_root=dest_root,
            filters=args.filters,
            skip_existing=args.skip_existing,
            list_only=args.list_only,
        )
        return 0
    except requests.HTTPError as exc:
        print(f"GitHub API error: {exc}", file=sys.stderr)
    except requests.RequestException as exc:
        print(f"Network error: {exc}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
