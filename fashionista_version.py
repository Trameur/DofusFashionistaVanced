"""Centralized version metadata for Dofus Fashionista."""
from __future__ import annotations

FASHIONISTA_VERSION = "3.4.15.16"


def get_version() -> str:
    """Return the current site/game version string."""
    return FASHIONISTA_VERSION


if __name__ == "__main__":
    print(get_version())
