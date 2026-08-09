"""Centralized version metadata for Dofus Fashionista."""
from __future__ import annotations

FASHIONISTA_VERSION = "3.6.10.10"
FASHIONISTA_BETA_VERSION = "3.6.7.7"
FASHIONISTA_DOFUS2_VERSION = "2.73.3.14"
FASHIONISTA_RETRO_VERSION = "1.48"
FASHIONISTA_TOUCH_VERSION = "1.73"

# What the version watch compares for the two versions whose public number
# never moves. Retro stays "1.48" and Touch "1.73" in the footer while their
# real build changes with every content patch, so those two are watched here
# instead. Update them when the matching pipeline is re-run.
WATCHED_RETRO_BUILD = "1.48.21.5572.434-2106199"
WATCHED_TOUCH_ASSETS = "3.2.11_XmqR,JLRxKAo0jK41tA_EnsXKrTBc47Z"


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
