# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The wizard's reset button gives back the weights of the build's boxes and priority together."""
import json
import re

from django.contrib.auth.models import User
from django.test import TestCase

from chardata.models import Char
from fashionistapulp.structure import set_current_game_version

PRIORITY_BOXES = (('damage', {'glasscannon'}), ('defense', {'vit', 'res'}), ('heals', {'heal'}))


def _slider(defaults, key):
    return defaults[key]


class TheWizardResetWeighsThePriorityTooTests(TestCase):

    def setUp(self):
        set_current_game_version('dofus3')
        self.addCleanup(set_current_game_version, 'dofus3')
        owner = User.objects.create_user('wizard-reset', 'wizard-reset@test.local',
                                         'pw-wizard-reset-5')
        self.client.force_login(owner)

    def create(self, aspects, extra=None):
        data = {'project': 'p', 'charname': '', 'class': 'Eniripsa', 'level': '200',
                'wizard': 'wizard'}
        data.update(('check_%s' % aspect, 'on') for aspect in aspects)
        data.update(extra or {})
        self.assertEqual(302, self.client.post('/createproject/', data).status_code)
        return Char.objects.order_by('-id').first()

    def reset(self, char):
        response = self.client.get('/wizard/%d/' % char.id)
        self.assertEqual(200, response.status_code)
        found = re.search(r'<script id="wm-defaults" type="application/json">(.*?)</script>',
                          response.content.decode('utf-8'), re.S)
        self.assertIsNotNone(found)
        return json.loads(found.group(1))

    def test_each_priority_resets_to_the_sliders_of_its_boxes(self):
        plain = self.reset(self.create({'int'}))
        for priority, boxes in PRIORITY_BOXES:
            with self.subTest(priority=priority):
                chosen = self.reset(self.create({'int'}, {'priority': priority}))
                self.assertEqual(self.reset(self.create({'int'} | boxes)), chosen)
                self.assertNotEqual(plain, chosen)

    def test_a_damage_build_resets_to_the_glass_cannon_power(self):
        chosen = self.reset(self.create({'int'}, {'priority': 'damage'}))
        ticked = self.reset(self.create({'int', 'glasscannon'}))
        plain = self.reset(self.create({'int'}))
        self.assertEqual(_slider(ticked, 'pow'), _slider(chosen, 'pow'))
        self.assertGreater(_slider(chosen, 'pow'), _slider(plain, 'pow'))
