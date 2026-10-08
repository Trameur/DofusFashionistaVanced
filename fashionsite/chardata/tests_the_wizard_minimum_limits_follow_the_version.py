# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The wizard's AP, MP and Range boxes stop at the version's own limit, and Retro has none."""
from html.parser import HTMLParser

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from chardata.coaching_view import create_build
from fashionistapulp.dofus_constants import get_stat_maximum
from fashionistapulp.structure import set_current_game_version

PREFIX = {'dofus3': '', 'beta': '/beta', 'dofus2': '/dofus2', 'touch': '/touch',
          'retro': '/retro'}
FIELDS = (('min_ap', 'AP'), ('min_mp', 'MP'), ('min_range', 'Range'))


class _Inputs(HTMLParser):
    def __init__(self):
        super().__init__()
        self.found = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'input' and attrs.get('id', '').startswith('min_'):
            self.found[attrs['id']] = attrs


class TheWizardMinimumLimitsFollowTheVersionTests(TestCase):

    def setUp(self):
        self.owner = User.objects.create_user('wizard', 'wz@test.local', 'pw-42-solid')
        self.client.force_login(self.owner)

    def tearDown(self):
        set_current_game_version('dofus3')

    def inputs(self, version, level):
        set_current_game_version(version)
        request = RequestFactory().post('/')
        request.user = self.owner
        char = create_build(request, 'Iop', level, {'str'}, version)
        response = self.client.get('%s/wizard/%d/' % (PREFIX[version], char.pk))
        self.assertEqual(200, response.status_code)
        parser = _Inputs()
        parser.feed(response.content.decode('utf-8'))
        return parser.found

    def test_each_box_carries_the_cap_of_its_version(self):
        for version in PREFIX:
            caps = get_stat_maximum(version)
            for level in (20, 200):
                inputs = self.inputs(version, level)
                for field, name in FIELDS:
                    with self.subTest(version=version, level=level, field=field):
                        if name in caps:
                            self.assertEqual(str(caps[name]), inputs[field]['max'])
                        else:
                            self.assertNotIn('max', inputs[field])

    def test_retro_puts_no_limit_on_ap(self):
        self.assertNotIn('max', self.inputs('retro', 200)['min_ap'])
