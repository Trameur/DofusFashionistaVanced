# -*- coding: utf-8 -*-
"""The mutating routes nothing walked, checked against a stranger.

Of the 176 routes in urls.py, twenty-one are named by no test and reached by
neither `check_pages` nor `check_actions`. Four of them change data that
belongs to somebody: they duplicate a build, remove a tag, delete a comment,
drop a follow. Each one reads correctly. This pins that, because reading is
not measuring and these are the routes a change would break unnoticed.

Every case has its opposite here: an owner who *can* do the thing. Without
that, a route that answered 403 to everyone -- including its owner -- would
pass the whole file.
"""
from django.contrib.auth.models import User
from django.test import TestCase

from chardata.encoded_char_id import encode_char_id
from chardata.models import BuildComment, BuildTag, Char, UserFollow


class AStrangerCannotTouchYourThings(TestCase):

    def setUp(self):
        self.owner = User.objects.create_user('owner', 'o@x.test', 'pw')
        self.stranger = User.objects.create_user('stranger', 's@x.test', 'pw')
        self.client.force_login(self.owner)
        self.client.post('/createproject/', {
            'project': 'p', 'charname': 'Perso', 'level': '150',
            'class': 'Iop', 'where_to_go': 'wizard'})
        self.char = Char.objects.order_by('-id').first()
        self.client.get('/solution/%d/' % self.char.id, follow=True)
        self.char.refresh_from_db()

    def share(self):
        self.char.link_shared = True
        self.char.save()

    # -- duplicating someone's build -------------------------------------

    def test_a_build_that_is_not_shared_cannot_be_duplicated(self):
        self.client.force_login(self.stranger)
        before = Char.objects.count()
        response = self.client.get('/duplicatesomeonesproject/%s/'
                                   % encode_char_id(self.char.id))
        self.assertEqual(403, response.status_code)
        self.assertEqual(before, Char.objects.count(), 'a copy was made anyway')

    def test_a_shared_build_can_be_duplicated_and_the_copy_is_private(self):
        """The opposite case, and the fact that explains a whole population.

        The copy carries the original's stored solution -- pk cleared, every
        other field kept. So a build duplicated today holds item ids from the
        day the original was solved, which is why builds created this year can
        carry numbers from an older catalogue.
        """
        self.share()
        self.client.force_login(self.stranger)
        before = Char.objects.count()
        response = self.client.get('/duplicatesomeonesproject/%s/'
                                   % encode_char_id(self.char.id), follow=True)
        self.assertEqual(200, response.status_code)
        self.assertEqual(before + 1, Char.objects.count())
        copy = Char.objects.order_by('-id').first()
        self.assertEqual(self.stranger, copy.owner)
        self.assertFalse(copy.link_shared, 'the copy was published on its own')
        self.assertEqual(self.char.minimal_solution, copy.minimal_solution,
                         'the copy did not carry the solution')

    def test_a_made_up_encoded_id_is_refused(self):
        self.client.force_login(self.stranger)
        self.assertEqual(403, self.client.get(
            '/duplicatesomeonesproject/not-a-real-id/').status_code)

    # -- tags -------------------------------------------------------------

    def a_tag(self):
        self.client.force_login(self.owner)
        self.client.post('/addtag/%d/' % self.char.id, {'tag': 'Klime'})
        tag = BuildTag.objects.filter(char=self.char).first()
        self.assertIsNotNone(tag, 'the owner could not add a tag')
        return tag

    def test_a_stranger_cannot_remove_your_tag(self):
        tag = self.a_tag()
        self.client.force_login(self.stranger)
        self.assertEqual(403, self.client.post('/removetag/%d/' % tag.id).status_code)
        self.assertTrue(BuildTag.objects.filter(id=tag.id).exists())

    def test_the_owner_can_remove_their_own_tag(self):
        tag = self.a_tag()
        self.assertEqual(200, self.client.post('/removetag/%d/' % tag.id).status_code)
        self.assertFalse(BuildTag.objects.filter(id=tag.id).exists())

    # -- comments ---------------------------------------------------------

    def a_comment(self):
        self.share()
        self.client.force_login(self.stranger)
        self.client.post('/postcomment/%d/' % self.char.id,
                         {'content': 'a comment by the stranger'})
        comment = BuildComment.objects.first()
        self.assertIsNotNone(comment)
        return comment

    def test_nobody_else_can_delete_your_comment(self):
        comment = self.a_comment()
        self.client.force_login(self.owner)
        self.assertEqual(403, self.client.post(
            '/deletecomment/%d/' % comment.id).status_code)
        comment.refresh_from_db()
        self.assertFalse(comment.deleted)

    def test_its_author_can_delete_it(self):
        comment = self.a_comment()
        self.assertEqual(200, self.client.post(
            '/deletecomment/%d/' % comment.id).status_code)
        comment.refresh_from_db()
        self.assertTrue(comment.deleted)

    # -- follows ----------------------------------------------------------

    def test_unfollowing_only_drops_your_own_follow(self):
        third = User.objects.create_user('third', 't@x.test', 'pw')
        UserFollow.objects.create(follower=self.owner, followed=third)
        UserFollow.objects.create(follower=self.stranger, followed=third)

        self.client.force_login(self.stranger)
        response = self.client.post('/unfollow/%d/' % third.id)
        self.assertEqual(200, response.status_code)

        self.assertFalse(UserFollow.objects.filter(
            follower=self.stranger, followed=third).exists())
        self.assertTrue(
            UserFollow.objects.filter(follower=self.owner, followed=third).exists(),
            'unfollowing dropped somebody else\'s follow')
