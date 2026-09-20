# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""When the ad setting cannot be read, the admin page says so and the log stays at warning."""
import hashlib
import json
from unittest import mock

from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase

from chardata.context_processors import AD_SETTING_KEY, ad_config


class AFailedAdSettingReadSaysSoTests(TestCase):

    def setUp(self):
        # ad_config() reads a per-worker cache: clear it or a test inherits the previous answer
        cache.delete(AD_SETTING_KEY)

    def _casser(self):
        from chardata.models import SiteSetting
        return mock.patch.object(SiteSetting.objects, 'filter',
                                 side_effect=Exception('no such table'))

    def test_a_failed_read_serves_no_ads_and_marks_itself(self):
        with self._casser():
            with self.assertLogs('chardata.context_processors',
                                 level='WARNING') as journal:
                config = ad_config()
        self.assertFalse(config.get('enabled', True))
        self.assertTrue(config.get('read_failed'),
                        'the failure is invisible to whoever asks why')
        self.assertIn('could not be read', journal.output[0])

    def test_the_failure_stays_a_warning_on_purpose(self):
        with self._casser():
            with self.assertLogs('chardata.context_processors',
                                 level='WARNING') as journal:
                ad_config()
        niveaux = [l.split(':', 1)[0] for l in journal.output]
        self.assertEqual(['WARNING'], niveaux, journal.output)

    def test_a_read_that_works_is_not_marked(self):
        from chardata.models import SiteSetting
        SiteSetting.objects.update_or_create(
            key=AD_SETTING_KEY,
            defaults={'value': json.dumps({'enabled': True, 'slots': {}})})
        cache.delete(AD_SETTING_KEY)
        config = ad_config()
        self.assertFalse(config.get('read_failed', False))
        self.assertTrue(config.get('enabled'))

    def _admin(self):
        call_command('create_local_admin', username='localadmin',
                     email='la@test.local', password='a-solid-pw-42')
        prehash = hashlib.sha256(
            ('dofusfashionista' + 'a-solid-pw-42').encode()).hexdigest()
        reponse = self.client.post('/local_login/',
                                   {'username': 'localadmin',
                                    'password': prehash})
        self.assertEqual(200, reponse.status_code)

    def test_the_admin_page_explains_the_unchecked_box(self):
        self._admin()
        with self._casser():
            page = self.client.get('/admin-tools/').content.decode(
                'utf-8', 'replace')
        self.assertIn('cannot be read', page,
                      'the admin page shows an unchecked box and no reason')
        # The named trap: the box shows unticked, and saving it persists the outage
        self.assertIn('his form would make the outage permanent', page)

    def test_the_admin_page_stays_quiet_when_the_read_works(self):
        self._admin()
        page = self.client.get('/admin-tools/').content.decode(
            'utf-8', 'replace')
        self.assertNotIn('cannot be read', page)
