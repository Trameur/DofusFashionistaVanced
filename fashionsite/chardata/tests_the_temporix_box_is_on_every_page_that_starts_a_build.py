# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The TemporiX box is on every page where a Touch build gets its options.

Thibaud, 2026-09-18, on /fr/touch/setup/: "je vois pas de coche temporiX".
The mode shipped with its box on the options page only, so a player creating
a Touch build, on the create page and then in the wizard, never met it. The
wizard also saved the minimums BEFORE the options, and set_min_stats clamps
AP, MP and Range to the limits of the mode already stored: a first TemporiX
wizard asking for 14 AP would have kept 12.
"""
from django.test import TestCase

from chardata.min_stats import get_min_stats
from chardata.models import Char
from chardata.options import get_options
from fashionistapulp.dofus_constants import get_stat_maximum
from fashionistapulp.structure import set_current_game_version


class TheTemporixBoxIsOnEveryPageThatStartsABuildTests(TestCase):

    def tearDown(self):
        set_current_game_version('dofus3')

    def _create(self, prefix, **extra):
        post = {'project': 'Temporix', 'charname': 'Temporix', 'level': '200',
                'class': 'Iop', 'wizard': 'wizard'}
        post.update(extra)
        response = self.client.post('%s/createproject/' % prefix, post)
        self.assertEqual(302, response.status_code)
        return Char.objects.latest('pk')

    def test_the_create_page_shows_the_box_on_touch_only(self):
        touch = self.client.get('/touch/setup/').content.decode('utf-8')
        self.assertIn('name="temporix"', touch)
        french = self.client.get('/touch/setup/', HTTP_ACCEPT_LANGUAGE='fr')
        self.assertIn('Pour les serveurs TemporiX', french.content.decode('utf-8'))
        for prefix in ('', '/retro', '/dofus2'):
            with self.subTest(prefix=prefix or '/'):
                page = self.client.get('%s/setup/' % prefix).content.decode('utf-8')
                self.assertNotIn('name="temporix"', page)

    def test_a_ticked_box_creates_a_temporix_build(self):
        char = self._create('/touch', temporix='on')
        self.assertTrue(get_options(char)['temporix'])

    def test_an_unticked_box_creates_a_classic_build(self):
        char = self._create('/touch')
        self.assertFalse(get_options(char)['temporix'])

    def test_the_box_means_nothing_off_touch(self):
        char = self._create('', temporix='on')
        self.assertFalse(get_options(char)['temporix'])

    def test_the_wizard_shows_the_box_ticked_as_the_build_is(self):
        char = self._create('/touch', temporix='on')
        page = self.client.get('/touch/wizard/%d/' % char.pk).content.decode('utf-8')
        self.assertIn('name="temporix"', page)
        self.assertIn('"temporix": true', page)

    def test_the_wizard_keeps_a_temporix_minimum_above_the_classic_limit(self):
        char = self._create('/touch')
        self.client.post('/touch/wizardpost/%d/' % char.pk,
                         {'min_AP': '14', 'temporix': 'on', 'ap_exo': 'no',
                          'mp_exo': 'no'})
        char.refresh_from_db()
        self.assertTrue(get_options(char)['temporix'])
        self.assertEqual(14, get_min_stats(char)['AP'])

    def test_the_wizard_unticked_clamps_to_the_classic_limit(self):
        char = self._create('/touch', temporix='on')
        self.client.post('/touch/wizardpost/%d/' % char.pk,
                         {'min_AP': '14', 'ap_exo': 'no', 'mp_exo': 'no'})
        char.refresh_from_db()
        self.assertFalse(get_options(char)['temporix'])
        self.assertEqual(get_stat_maximum('touch')['AP'],
                         get_min_stats(char)['AP'])
