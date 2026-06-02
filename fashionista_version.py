"""Centralized version metadata for Dofus Fashionista."""
from __future__ import annotations

FASHIONISTA_VERSION = "3.5.17.21"
FASHIONISTA_BETA_VERSION = "3.5.7.21"
FASHIONISTA_DOFUS2_VERSION = "2.73.3.14"
# Retro has no version tag to bump in our pipeline; item stats come from the live
# Retro lang CDN, which is currently 1.48 (see itemscraper/get_equipments_retro.py).
FASHIONISTA_RETRO_VERSION = "1.48"


def get_version() -> str:
    """Return the current site/game version string."""
    return FASHIONISTA_VERSION


def get_beta_version() -> str:
    return FASHIONISTA_BETA_VERSION


def get_dofus2_version() -> str:
    return FASHIONISTA_DOFUS2_VERSION


def get_retro_version() -> str:
    return FASHIONISTA_RETRO_VERSION


if __name__ == "__main__":
    print(get_version())
