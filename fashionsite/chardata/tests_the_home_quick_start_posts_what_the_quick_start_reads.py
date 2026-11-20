# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The home page offers the quick start: its form posts the fields the quick start reads, preselects no element, and a real post builds a set."""
import re

from django.contrib.auth.models import User
from django.test import TestCase

from chardata.models import Char
from fashionistapulp.structure import set_current_game_version

FORM = re.compile(r'<form[^>]*id="fm-quick-start".*?</form>', re.S)


def _form(page):
    return FORM.search(page).group(0)


class TheHomeQuickStartTests(TestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')

    def test_the_form_posts_to_the_quick_start_with_the_four_fields_and_a_token(self):
        form = _form(self.client.get('/').content.decode())
        self.assertIn('method="post"', form)
        self.assertIn('action="/quickstart/"', form)
        self.assertIn('csrfmiddlewaretoken', form)
        for name in ('char_class', 'char_level', 'element', 'play_style'):
            with self.subTest(name=name):
                self.assertIn('name="%s"' % name, form)

    def test_no_element_and_no_class_is_preselected(self):
        form = _form(self.client.get('/').content.decode())
        self.assertNotIn(' checked', form)

    def test_the_elements_offered_are_the_quick_starts_own_choices(self):
        form = _form(self.client.get('/').content.decode())
        inputs = [tag for tag in re.findall(r'<input[^>]*>', form) if re.search(r'name="?element"?[ >]', tag)]
        values = [re.search(r'value="?(\w+)', tag).group(1) for tag in inputs]
        self.assertEqual(['str', 'int', 'cha', 'agi', 'omni', 'none'], values)

    def test_forgelance_is_offered_on_dofus_3_and_not_on_dofus_2(self):
        self.assertIn('value="Forgelance"', _form(self.client.get('/').content.decode()))
        self.assertNotIn('value="Forgelance"', _form(self.client.get('/dofus2/').content.decode()))

    def test_a_guest_post_builds_a_set_and_goes_to_it(self):
        response = self.client.post('/quickstart/', {'char_class': 'Iop', 'char_level': '150',
                                                      'element': 'str', 'play_style': 'solo_pvm'})
        self.assertEqual(302, response.status_code)
        char = Char.objects.get()
        self.assertEqual(('Iop', 150), (char.char_class, char.level))
        self.assertIn('/%d/' % char.id, response['Location'])

    def test_a_signed_in_post_builds_a_set_for_its_owner(self):
        user = User.objects.create_user('quick', password='x')
        self.client.force_login(user)
        response = self.client.post('/quickstart/', {'char_class': 'Cra', 'char_level': '200',
                                                      'element': 'none', 'play_style': 'pvp'})
        self.assertEqual(302, response.status_code)
        self.assertEqual(user, Char.objects.get().owner)

    def test_a_post_without_an_element_builds_nothing_and_says_so(self):
        response = self.client.post('/quickstart/', {'char_class': 'Iop', 'char_level': '200',
                                                      'play_style': 'solo_pvm'})
        self.assertEqual(400, response.status_code)
        self.assertContains(response, 'Pick an element for this build.', status_code=400)
        self.assertEqual(0, Char.objects.count())
