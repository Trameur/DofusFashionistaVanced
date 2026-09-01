# -*- coding: utf-8 -*-
"""A build's own name must not be what hides its page from Google.

robots.txt refuses internal endpoints with `Disallow: */word/`. That form
matches the word at any depth, and a shared build's address carries its name as
a path segment, so a build called `fashion` asks Google to skip a rule written
for /fashion/ -- and skips /s/fashion/<id>/ with it. One live build was in that
state when this was written.

The two files know nothing of each other, so the drift test below is what keeps
them level: a new `Disallow: */word/` with no matching entry turns this red.
"""
import io
import os
import re

from django.test import TestCase

from chardata.solution_view import RESERVED_PATH_WORDS, shared_build_path

ROBOTS = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      'templates', 'chardata', 'robots.txt')


class _Char(object):
    """Enough of a Char for shared_build_path: it reads four fields."""

    def __init__(self, char_name, game_version='dofus3', char_id=102131):
        self.char_name = char_name
        self.char_class = 'Cra'
        self.level = 200
        self.game_version = game_version
        self.id = char_id


def _rules():
    """The Allow/Disallow of the `User-agent: *` group, in order."""
    out, inside = [], False
    for line in io.open(ROBOTS, encoding='utf-8').read().splitlines():
        line = line.split('#', 1)[0].strip()
        if not line or ':' not in line:
            continue
        key, value = (p.strip() for p in line.split(':', 1))
        key = key.lower()
        if key == 'user-agent':
            inside = (value == '*')
        elif inside and key in ('allow', 'disallow') and value:
            out.append((key, value))
    return out


def _as_pattern(path):
    anchored = path.endswith('$')
    if anchored:
        path = path[:-1]
    body = ''.join('.*' if c == '*' else re.escape(c) for c in path)
    return re.compile('^' + body + ('$' if anchored else ''))


def _allows(rules, path):
    """Google's rule: the longest matching pattern wins, ties go to Allow.

    The length is the pattern as written, `$` and `*` included -- measuring it
    without the `$` loses `Allow: /setup/$` against `Disallow: */setup/`.
    """
    winner, length = None, -1
    for key, value in rules:
        if _as_pattern(value).match(path):
            n = len(value)
            if n > length or (n == length and key == 'allow'):
                winner, length = key, n
    return winner != 'disallow'


class BuildNameCannotHideItself(TestCase):

    def setUp(self):
        self.rules = _rules()

    def test_the_word_list_matches_the_file(self):
        written = set()
        for key, value in self.rules:
            match = re.fullmatch(r'\*/([A-Za-z0-9_-]+)/', value)
            if key == 'disallow' and match:
                written.add(match.group(1))
        self.assertTrue(written, 'no */word/ rule found: the reader is broken')
        self.assertEqual(written, set(RESERVED_PATH_WORDS))

    def test_a_build_named_after_an_endpoint_stays_crawlable(self):
        blocked = [w for w in sorted(RESERVED_PATH_WORDS)
                   if not _allows(self.rules, shared_build_path(_Char(w)))]
        self.assertEqual(blocked, [])

    def test_without_the_fix_every_one_of_them_would_be_blocked(self):
        """The control: the matcher above must actually be able to say no.

        It reproduces the address the site used to build -- the name verbatim --
        and demands a refusal for every reserved word. A matcher that allowed
        everything would make the test above pass while proving nothing.
        """
        allowed = [w for w in sorted(RESERVED_PATH_WORDS)
                   if _allows(self.rules, '/s/%s/MTAyMTMx/' % w)]
        self.assertEqual(allowed, [])

    def test_an_ordinary_name_is_left_alone(self):
        path = shared_build_path(_Char('yasu'))
        self.assertEqual(path, '/s/yasu/%s/' % path.rstrip('/').rsplit('/', 1)[-1])
        self.assertTrue(_allows(self.rules, path))

    def test_a_version_prefixed_build_is_crawlable_too(self):
        path = shared_build_path(_Char('fashion', game_version='retro'))
        self.assertTrue(path.startswith('/retro/s/'))
        self.assertTrue(_allows(self.rules, path))
