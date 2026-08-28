# -*- coding: utf-8 -*-
"""A comment is the only stranger's text that lands on a public page.

Everything else a visitor reads on `/s/…/` comes from the catalogue or from
the build's owner. Comments come from a third party, they are rendered on a
page Google indexes, and `validate_comment` only refuses external links and
profanity -- never a tag. So the escaping is the whole defence, and it lives
in two places that a later edit could quietly undo: `linebreaksbr` in
`solution.html`, and `.text()` in the script that appends a new comment.

The positive control matters as much as the payloads: without asserting that
the escaped form is present, a page that simply stopped showing comments would
pass every "no raw tag" check.
"""
from django.contrib.auth.models import User
from django.test import TestCase

from chardata.models import BuildComment, Char
from chardata.util import shared_build_path

#: Payloads chosen to survive moderation: none carries an external link.
PAYLOADS = [
    '<script>alert(1)</script>',
    '<img src=x onerror=alert(1)>',
    '"><svg onload=alert(1)>',
    '<a href="/s/x/">an internal link</a>',
]


class ACommentOnAPublicPage(TestCase):

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
        self.char.link_shared = True
        self.char.save()
        self.client.logout()

    def post_comment(self, content):
        return self.client.post('/postcomment/%d/' % self.char.id,
                                {'content': content})

    def public_page(self):
        response = self.client.get(shared_build_path(self.char), follow=True)
        self.assertEqual(200, response.status_code)
        return response.content.decode('utf-8', 'replace')

    def test_a_hostile_comment_reaches_the_page_escaped(self):
        self.client.force_login(self.stranger)
        accepted = [p for p in PAYLOADS if self.post_comment(p).status_code == 200]
        self.assertEqual(
            len(PAYLOADS), len(accepted),
            'moderation refused a payload, so the page is no longer the thing '
            'under test: %s' % [p for p in PAYLOADS if p not in accepted])
        self.client.logout()

        page = self.public_page()
        self.assertEqual(
            [], [p for p in accepted if p in page],
            'a comment is rendered as markup on a public page')
        self.assertIn(
            '&lt;script&gt;', page,
            'no escaped form on the page: the comments may not be displayed at '
            'all, and the check above would pass on an empty page')

    def test_an_anonymous_visitor_cannot_comment(self):
        response = self.post_comment('hello')
        self.assertIn(response.status_code, (302, 401, 403))
        self.assertEqual(0, BuildComment.objects.count())

    def test_a_build_that_is_not_shared_takes_no_comment(self):
        self.char.link_shared = False
        self.char.save()
        self.client.force_login(self.stranger)
        self.assertEqual(404, self.post_comment('hello').status_code)
        self.assertEqual(0, BuildComment.objects.count())

    def test_three_reports_hide_the_comment(self):
        self.client.force_login(self.stranger)
        self.post_comment('an ordinary comment')
        comment = BuildComment.objects.get()
        for i in range(3):
            self.client.force_login(User.objects.create_user(
                'reporter%d' % i, 'r%d@x.test' % i, 'pw'))
            self.assertEqual(200, self.client.post(
                '/reportcomment/%d/' % comment.id, {'reason': 'spam'}).status_code)
        comment.refresh_from_db()
        self.assertTrue(comment.deleted,
                        'three distinct reports left the comment visible')
