# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""Switch the WAKFU flag in a test, including the URLconf the include depends on."""

import contextlib
import importlib

from django.conf import settings
from django.test import override_settings
from django.urls import clear_url_caches


def _reload_urlconf():
    clear_url_caches()
    importlib.reload(importlib.import_module(settings.ROOT_URLCONF))
    clear_url_caches()


@contextlib.contextmanager
def wakfu_flag(on):
    experiments = dict(settings.EXPERIMENTS, WAKFU=on)
    try:
        with override_settings(EXPERIMENTS=experiments):
            _reload_urlconf()
            yield
    finally:
        _reload_urlconf()
