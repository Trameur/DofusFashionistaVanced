"""A run of thousands of digits in a form value answers something other than a server error."""
from django.contrib.auth.models import User
from django.test import Client, RequestFactory, TestCase

from chardata.coaching_view import create_build
from chardata.lock_forbid import get_inclusions_dict

BIG = '9' * 4400


class AHugeNumberInAForm(TestCase):

    def setUp(self):
        self.client = Client(raise_request_exception=False)

    def test_a_pasted_stat_line_with_thousands_of_digits_is_ignored(self):
        line = '+%s Strength' % BIG
        response = self.client.post('/import/text/', {'text': line + chr(10) + '+50 Vitality'})
        self.assertEqual(200, response.status_code)
        self.assertIn(line, response.context['ignored'])

    def test_a_posted_weapon_id_with_thousands_of_digits_is_not_locked(self):
        owner = User.objects.create_user('wizard', 'wizard@test.local', 'pw-1234')
        self.client.force_login(owner)
        request = RequestFactory().post('/')
        request.user = owner
        char = create_build(request, 'Iop', 200, {'str'}, 'dofus3')
        response = self.client.post('/wizardpost/%d/' % char.id, {'weapon': BIG})
        self.assertLess(response.status_code, 500)
        self.assertFalse(get_inclusions_dict(char).get('weapon'))
