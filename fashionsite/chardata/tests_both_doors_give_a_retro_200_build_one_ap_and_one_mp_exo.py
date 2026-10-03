# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A new Retro build starts with one AP and one MP exo at level 200, whichever page creates it."""
import re

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from chardata.coaching_view import create_build
from chardata.models import Char
from chardata.options import get_options
from fashionistapulp.structure import set_current_game_version


def _exos(char):
    options = get_options(Char.objects.get(id=char.id))
    return tuple(options.get(option) for option in ('ap_exo', 'mp_exo', 'range_exo'))


class BothDoorsShareTheExoDefaultTests(TestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')
        self.owner = User.objects.create_user('exodoors', 'exodoors@test.local', 'pw-1234')
        self.client.force_login(self.owner)

    def _created(self, version, level):
        prefix = '' if version == 'dofus3' else '/%s' % version
        name = 'exo%s%d' % (version, level)
        response = self.client.post('%s/createproject/' % prefix, {
            'charname': name, 'class': 'Iop', 'level': str(level),
            'project': name, 'byhand': '1'})
        found = re.search(r'/(\d+)/', response.headers.get('Location', ''))
        self.assertIsNotNone(found, 'could not create %s %d' % (version, level))
        char = Char.objects.get(id=int(found.group(1)))
        self.assertEqual((version, level), (char.game_version, char.level))
        return char

    def _coached(self, version, level):
        set_current_game_version(version)
        request = RequestFactory().post('/')
        request.user = self.owner
        return create_build(request, 'Iop', level, {'str'}, version)

    def test_retro_200_gets_one_ap_and_one_mp_exo_at_both_doors(self):
        for door in (self._created, self._coached):
            with self.subTest(door=door.__name__):
                self.assertEqual((1, 1, 0), _exos(door('retro', 200)))

    def test_a_retro_build_under_200_gets_none(self):
        for door in (self._created, self._coached):
            with self.subTest(door=door.__name__):
                self.assertEqual((0, 0, 0), _exos(door('retro', 199)))

    def test_dofus3_keeps_its_yes_and_no(self):
        for door in (self._created, self._coached):
            for level, wanted in ((200, True), (199, False)):
                with self.subTest(door=door.__name__, level=level):
                    ap, mp, range_exo = _exos(door('dofus3', level))
                    self.assertIs(wanted, ap)
                    self.assertIs(wanted, mp)
                    self.assertIsNone(range_exo)
