# -*- coding: utf-8 -*-
"""A reader who lost their password gets it back, and nobody else does.

Nothing walked this. `check_pages` follows links a crawler can GET and
`check_actions` posts to the endpoints it knows; neither can read the mail that
carries the link, so the chain from "I forgot it" to "I am logged in again"
was never joined end to end. It is also the flow that never gets reported when
it breaks: a reader who cannot get back in does not write, they leave.

The design being pinned here is careful and worth keeping that way. The token
is a TimestampSigner over an HMAC of the username **and the current password
hash**, so it expires on its own and a completed reset kills every older link
in the same instant. The four security properties below are that design.

The browser's login.js posts SHA256('dofusfashionista' + password), so a login
here has to send the same thing; the reset form posts the raw password and the
view hashes it. Getting that backwards fails in a way that looks like a bug in
the site.
"""
import hashlib
import re

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase

EMAIL = 'lost@example.test'
OLD = 'the-old-one'
NEW = 'the-new-one'


def as_the_browser_sends_it(password):
    return hashlib.sha256(('dofusfashionista' + password).encode('utf-8')).hexdigest()


class APasswordRecoveryWalk(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            'lost-user', EMAIL, as_the_browser_sends_it(OLD))
        self.user.is_active = True
        self.user.save()
        mail.outbox = []

    def ask_for_a_reset(self, email=EMAIL):
        response = self.client.post('/recover_password/', {'email': email})
        self.assertEqual(200, response.status_code)
        return response

    def link_from_the_mail(self):
        self.assertEqual(1, len(mail.outbox), 'no reset mail was sent')
        found = re.search(r'(/do_recover_password/\S+/)', mail.outbox[0].body)
        self.assertIsNotNone(found, 'the mail carries no reset link:\n%s'
                             % mail.outbox[0].body)
        return found.group(1)

    def log_in(self, password):
        return self.client.post('/local_login/',
                                {'username': 'lost-user',
                                 'password': as_the_browser_sends_it(password)}
                                ).content.decode('utf-8')

    def test_the_whole_walk(self):
        self.ask_for_a_reset()
        link = self.link_from_the_mail()

        form = self.client.get(link)
        self.assertEqual(200, form.status_code, 'the reset link does not open')

        mismatched = self.client.post(link, {'new_password': NEW,
                                             'confirm_password': 'something else'})
        self.assertEqual(200, mismatched.status_code)
        self.assertEqual('ok', self.log_in(OLD),
                         'a mismatched pair changed the password anyway')

        done = self.client.post(link, {'new_password': NEW,
                                       'confirm_password': NEW})
        self.assertEqual(200, done.status_code)

        self.client.post('/logout/')
        self.assertEqual('ok', self.log_in(NEW), 'the new password does not work')
        self.client.post('/logout/')
        self.assertEqual('invalid', self.log_in(OLD),
                         'the old password still opens the account')

    def test_the_link_dies_with_the_password_it_was_made_for(self):
        """A reset mail left in an old inbox must not be a second key."""
        self.ask_for_a_reset()
        link = self.link_from_the_mail()
        self.client.post(link, {'new_password': NEW, 'confirm_password': NEW})
        self.client.post('/logout/')
        self.assertEqual(403, self.client.get(link).status_code,
                         'the used link still opens the reset form')

    def test_a_tampered_token_is_refused(self):
        self.ask_for_a_reset()
        link = self.link_from_the_mail()
        head, token = link.rstrip('/').rsplit('/', 1)
        forged = '%s/%s/' % (head, token[:-1] + ('a' if token[-1] != 'a' else 'b'))
        self.assertEqual(403, self.client.get(forged).status_code)

    def comparable(self, content, address):
        """The page minus what has to differ between two requests.

        The csrf token is new on every response and the address is echoed
        back; neither says anything about whether an account exists.
        """
        text = content.decode('utf-8', 'replace').replace(address, '')
        # The token appears both as an attribute and inside a script, so blank
        # every long opaque run rather than one shape of it.
        return re.sub(r'[A-Za-z0-9]{32,}', 'TOKEN', text)

    def test_an_unknown_address_is_answered_the_same_way(self):
        """The page must not tell a stranger which addresses have an account."""
        known = self.comparable(self.ask_for_a_reset().content, EMAIL)
        mail.outbox = []
        unknown = self.comparable(
            self.ask_for_a_reset('nobody@example.test').content,
            'nobody@example.test')
        self.assertEqual(0, len(mail.outbox), 'a mail went to an unknown address')
        self.assertEqual(known, unknown,
                         'the two answers differ, so the page tells a stranger '
                         'whether an address has an account')

    def test_that_comparison_can_still_see_a_difference(self):
        """Blanking the csrf token must not blank everything else with it."""
        a = self.comparable(b'<p>hello</p><input value="%s">' % (b'x' * 40),
                            'nobody@example.test')
        b = self.comparable(b'<p>goodbye</p><input value="%s">' % (b'y' * 40),
                            'nobody@example.test')
        self.assertNotEqual(a, b)

    def test_the_reset_mail_is_throttled(self):
        for _ in range(12):
            self.ask_for_a_reset()
        self.assertLess(len(mail.outbox), 12,
                        'an address can be mailed as often as anyone asks')
