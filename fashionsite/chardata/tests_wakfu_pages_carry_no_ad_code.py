# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""No Wakfu page carries ad code, while the same configuration ads a Dofus page."""
import inspect
import os
import re

from django.conf import settings
from django.core.cache import cache
from django.test import RequestFactory, TestCase, override_settings

from chardata.context_processors import DEFAULT_AD_CLIENT, OPTIONAL_AD_PATHS, ads
from chardata.templatetags import ads as ads_tags
from chardata.wakfu_flag_for_tests import wakfu_flag

LANDINGS = ('/wakfu/', '/fr/wakfu/', '/es/wakfu/', '/pt/wakfu/', '/de/wakfu/')
LIST_PAGES = ('/wakfu/encyclopedia/', '/fr/wakfu/encyclopedia/', '/de/wakfu/encyclopedia/',
              '/wakfu/encyclopedia/?q=ring&page=2')
ITEM_PAGE = '/wakfu/encyclopedia/item/equipment/2021-gobball-amulet/'
AD_MARKERS = ('pagead2.googlesyndication.com', 'adsbygoogle', 'google-adsense-account',
              'fundingchoices')
TEMPLATES = os.path.join(os.path.dirname(__file__), 'templates')


def _slot_keys():
    """Every slot key a template, the ad tags or the ads context reads."""
    keys = set(OPTIONAL_AD_PATHS.values())
    keys.update(re.findall(r"slot_name='(\w+)'", inspect.getsource(ads_tags)))
    for folder, _dirs, names in os.walk(TEMPLATES):
        for name in names:
            with open(os.path.join(folder, name), encoding='utf-8') as source:
                text = source.read()
            keys.update(re.findall(r"ad_(?:unit|feed|rails)\s+'(\w+)'", text))
            keys.update(re.findall(r"ad_slots\.(\w+)", text))
    return keys


def _every_slot_configured():
    gen = dict(getattr(settings, 'GEN_CONFIGS', {}))
    gen['adsense'] = {'enabled': True, 'auto': True, 'client': DEFAULT_AD_CLIENT,
                      'slots': {key: '1234567890' for key in _slot_keys()}}
    return override_settings(GEN_CONFIGS=gen)


class WakfuPagesCarryNoAdCodeTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_the_slot_keys_cover_what_the_templates_read(self):
        self.assertTrue({'content_top', 'footer', 'solution', 'rail'} <= _slot_keys())

    def test_a_dofus_page_carries_ad_code_under_the_same_configuration(self):
        with _every_slot_configured(), wakfu_flag(True):
            html = self.client.get('/').content.decode('utf-8')
        self.assertIn('pagead2.googlesyndication.com', html)

    def test_no_wakfu_landing_carries_any_ad_code(self):
        with _every_slot_configured(), wakfu_flag(True):
            for path in LANDINGS:
                with self.subTest(path=path):
                    response = self.client.get(path)
                    self.assertEqual(200, response.status_code)
                    html = response.content.decode('utf-8')
                    for marker in AD_MARKERS:
                        self.assertNotIn(marker, html)

    def test_a_wakfu_item_list_carries_no_ad_code(self):
        with _every_slot_configured(), wakfu_flag(True):
            for path in LIST_PAGES:
                with self.subTest(path=path):
                    response = self.client.get(path)
                    self.assertEqual(200, response.status_code)
                    html = response.content.decode('utf-8')
                    for marker in AD_MARKERS:
                        self.assertNotIn(marker, html)

    def test_a_wakfu_item_page_carries_no_ad_code(self):
        with _every_slot_configured(), wakfu_flag(True):
            response = self.client.get(ITEM_PAGE)
            self.assertEqual(200, response.status_code)
            html = response.content.decode('utf-8')
        for marker in AD_MARKERS:
            self.assertNotIn(marker, html)

    def test_the_ad_context_of_a_wakfu_request_is_off(self):
        request = RequestFactory().get('/wakfu/')
        request.game_version = 'wakfu'
        with _every_slot_configured():
            answer = ads(request)
        self.assertFalse(answer['ads_allowed'])
        self.assertFalse(answer['ads_enabled'])
        self.assertEqual({}, answer['ad_slots'])

    def test_the_same_request_under_dofus_3_may_carry_ads(self):
        request = RequestFactory().get('/')
        request.game_version = 'dofus3'
        with _every_slot_configured():
            self.assertTrue(ads(request)['ads_allowed'])
