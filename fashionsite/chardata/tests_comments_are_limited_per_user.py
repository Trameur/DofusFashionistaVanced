"""A user posting comments is capped in a short window, and a build's owner gets one notification mail per window."""
from unittest import mock

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase

from chardata import comment_view
from chardata.models import BuildComment, Char, UserAlias


class CommentsAreLimited(TestCase):

    def setUp(self):
        self.owner = User.objects.create_user('owner', 'owner@x.test', 'pw')
        UserAlias.objects.create(user=self.owner, alias='owner', notify_comments=True)
        self.writer = User.objects.create_user('writer', 'writer@x.test', 'pw')
        self.client.force_login(self.owner)
        self.client.post('/createproject/', {
            'project': 'p', 'charname': 'Perso', 'level': '150',
            'class': 'Iop', 'where_to_go': 'wizard'})
        self.char = Char.objects.order_by('-id').first()
        self.char.link_shared = True
        self.char.save()
        self.client.force_login(self.writer)
        mail.outbox = []

    def comment(self, text='a fine build'):
        return self.client.post('/postcomment/%d/' % self.char.id, {'content': text})

    def test_a_user_past_the_ceiling_is_answered_429_and_nothing_is_stored(self):
        with mock.patch.object(comment_view, 'COMMENTS_PER_USER', 2):
            answers = [self.comment('comment %d' % i) for i in range(3)]
        self.assertEqual([200, 200, 429], [a.status_code for a in answers])
        self.assertEqual(2, BuildComment.objects.filter(user=self.writer).count())

    def test_the_ceiling_is_per_user(self):
        with mock.patch.object(comment_view, 'COMMENTS_PER_USER', 1):
            self.comment()
            self.client.force_login(self.owner)
            self.assertEqual(200, self.comment('the owner answers').status_code)

    def test_several_comments_send_the_owner_one_mail(self):
        for i in range(3):
            self.assertEqual(200, self.comment('comment %d' % i).status_code)
        self.assertEqual(3, BuildComment.objects.count())
        self.assertEqual(1, len(mail.outbox))
