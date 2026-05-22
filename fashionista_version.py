"""Centralized version metadata for Dofus Fashionista."""
from __future__ import annotations

FASHIONISTA_VERSION = "3.5.17.21"
FASHIONISTA_BETA_VERSION = "3.5.7.21"


def get_version() -> str:
    """Return the current site/game version string."""
    return FASHIONISTA_VERSION


def get_beta_version() -> str:
    return FASHIONISTA_BETA_VERSION


if __name__ == "__main__":
    print(get_version())
