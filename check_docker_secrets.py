#!/usr/bin/env python3
"""Refuses to boot a production container that still holds a public default secret."""

import json
import os
import sys

from merge_docker_config import CONFIG_DIR, DEFAULT_CONFIG

GUARDED_KEYS = (
    "SECRET_KEY",
    "PASSWORD_RESET_SALT",
    "EMAIL_CONFIRMATION_SALT",
    "char_id_SECRET_PART_1",
    "char_id_SECRET_PART_2",
)


def configured_dir():
    """The folder the settings read: FASHIONISTA_CONFIG_DIR, else the image default."""
    return os.environ.get("FASHIONISTA_CONFIG_DIR", CONFIG_DIR)


def debug_is_on(config_dir):
    try:
        with open(os.path.join(config_dir, "debug_mode")) as handle:
            return handle.read().strip() == "True"
    except OSError:
        return False


def keys_on_a_public_default(config):
    return [key for key in GUARDED_KEYS
            if key in DEFAULT_CONFIG and key in config and config[key] == DEFAULT_CONFIG[key]]


def main(config_dir=None):
    if config_dir is None:
        config_dir = configured_dir()
    if debug_is_on(config_dir):
        return 0
    try:
        with open(os.path.join(config_dir, "gen_config.json")) as handle:
            config = json.load(handle)
    except (OSError, ValueError):
        print("Cannot read gen_config.json to check the secrets.", file=sys.stderr)
        return 1
    if not isinstance(config, dict):
        print("gen_config.json is not an object.", file=sys.stderr)
        return 1
    names = keys_on_a_public_default(config)
    if names:
        print("Refusing to start: these keys still hold their public default: %s"
              % ", ".join(names), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
