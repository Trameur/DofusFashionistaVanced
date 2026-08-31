# -*- coding: utf-8 -*-
"""The stat table's icons load late; the gear does not.

Measured on production at 375x812 before changing anything: a shared build page
holds 246 images and **three** of them are in the first screen -- the banner,
the language flag, the class picture. The stat summary table starts at 978 px,
and 84 of its 137 icons sit inside panels that are collapsed to nothing.

Those icons are 56 % of the page's image bytes, and each is a 120x113 file
drawn at about seven pixels. Deferring them costs the reader nothing.

The opposite half matters as much: `loading="lazy"` on the equipment would
delay the one thing the page exists for. This file pins both, so a later sweep
that adds the attribute everywhere fails here instead of shipping.
"""
import re

from django.contrib.auth.models import User
from django.test import TestCase

from chardata.models import Char
from chardata.util import shared_build_path

STAT_ICON = re.compile(r'<img[^>]*solution-stat-summary-icon[^>]*>')
ITEM_IMAGE = re.compile(r'<img[^>]*solution-items-icon[^>]*>')


class TheStatIconsLoadLate(TestCase):

    def setUp(self):
        owner = User.objects.create_user('owner', 'o@x.test', 'pw')
        self.client.force_login(owner)
        self.client.post('/createproject/', {
            'project': 'p', 'charname': 'Perso', 'level': '150',
            'class': 'Iop', 'where_to_go': 'wizard'})
        self.char = Char.objects.order_by('-id').first()
        self.client.get('/solution/%d/' % self.char.id, follow=True)
        self.char.refresh_from_db()
        self.char.link_shared = True
        self.char.save()
        self.client.logout()

    def page(self):
        response = self.client.get(shared_build_path(self.char), follow=True)
        self.assertEqual(200, response.status_code)
        return response.content.decode('utf-8', 'replace')

    def test_every_stat_icon_waits(self):
        icons = STAT_ICON.findall(self.page())
        self.assertGreaterEqual(
            len(icons), 20,
            'only %d stat icons on the page: this test is measuring nothing'
            % len(icons))
        eager = [i for i in icons if 'loading="lazy"' not in i]
        self.assertEqual([], eager[:5],
                         '%d of %d stat icons still load with the page'
                         % (len(eager), len(icons)))

    def test_the_comment_explaining_it_stays_out_of_the_page(self):
        """A `{# #}` spanning several lines leaks into the html. The note above
        those tags is a {% comment %} block for that reason."""
        self.assertNotIn('375x812', self.page())

    def test_the_gear_is_not_deferred(self):
        """The half that keeps the other honest.

        The equipment starts at 935 px on a phone but it is what the reader
        came for, and on a desktop screen it is the first thing visible.
        """
        images = ITEM_IMAGE.findall(self.page())
        self.assertGreaterEqual(
            len(images), 10,
            'only %d equipment images found: the pattern matches nothing, so '
            'this test would pass whatever the page did' % len(images))
        deferred = [i for i in images if 'loading="lazy"' in i]
        self.assertEqual([], deferred[:5],
                         'the equipment images were made lazy, which delays '
                         'the one thing this page exists to show')
