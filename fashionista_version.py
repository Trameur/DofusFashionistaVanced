"""Centralized version metadata for Dofus Fashionista."""
from __future__ import annotations

FASHIONISTA_VERSION = "3.5.17.26"
FASHIONISTA_BETA_VERSION = "3.6.7.6"
FASHIONISTA_DOFUS2_VERSION = "2.73.3.14"
FASHIONISTA_RETRO_VERSION = "1.48"
FASHIONISTA_TOUCH_VERSION = "1.72"


def get_version() -> str:
    """Return the current site/game version string."""
    return FASHIONISTA_VERSION


def get_beta_version() -> str:
    return FASHIONISTA_BETA_VERSION


def get_dofus2_version() -> str:
    return FASHIONISTA_DOFUS2_VERSION


def get_retro_version() -> str:
    return FASHIONISTA_RETRO_VERSION


def get_touch_version() -> str:
    return FASHIONISTA_TOUCH_VERSION


if __name__ == "__main__":
    print(get_version())
