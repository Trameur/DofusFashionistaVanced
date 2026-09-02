# -*- coding: utf-8 -*-
"""The header version switcher must never link to a page that does not exist.

On a hub -- /encyclopedia/, /encyclopedia/sets/ -- the same path exists under
every version, so re-prefixing it is right, and VersionSwitcherPathTests (July)
pins that a public encyclopedia path is preserved rather than dumped to home.

On a page ABOUT one entity it is wrong: an item, set, monster or resource id is
not a shared identity across versions, and re-prefixing the path fabricated a
link for every version lacking the entity. Measured on the live site: 63 of
160 header links on a sample of entity pages answered 404, and every monster
page sampled carried at least one. Those are freshly generated 404s on ~40 000
pages, part of what Google keeps re-crawling as "Not found".

The page already knows which versions carry the same entity: the entity block
below the header uses other_versions / monster_version_links, filtered on
existence AND English name. The switcher now reuses that answer and falls
back to the version's encyclopedia hub. The July tests are untouched: the base
path is still preserved; only the href the header emits changes.

The last test has the teeth: it renders the real monster page and demands that
the header link to a version lacking the monster is the hub, while the link to
the version that has it is the entity page. Without it the unit tests could
pass on a template that never calls the tag.
"""
import re

from django.template import Context, Template
from django.test import SimpleTestCase, TestCase

from chardata.context_processors import ACTIVE_GAME_VERSIONS
from chardata.context_processors import game_version as _context


def _render(ctx):
    t = Template('{% load version_url %}'
                 '{% for k, l in active_game_versions %}'
                 '{{ k }}={% version_switch_href k %};{% endfor %}')
    out = t.render(Context(dict({'active_game_versions': ACTIVE_GAME_VERSIONS}, **ctx)))
    return dict(p.split('=', 1) for p in out.split(';') if p)


class _Req(object):
    def __init__(self, path, game_version='dofus3'):
        self.path_info = path
        self.game_version = game_version


class TheSwitcherNeverLinksToNothing(SimpleTestCase):

    def test_the_flag_tells_an_entity_from_a_hub(self):
        entites = ('/encyclopedia/monster/4960-captain-chafer/',
                   '/encyclopedia/item/equipment/44-twiggy-sword/',
                   '/encyclopedia/resource/resources/8772-rotaflor-bark/',
                   '/encyclopedia/set/50-tofu-set/',
                   '/retro/encyclopedia/monster/101-bouftou/')
        carrefours = ('/encyclopedia/', '/encyclopedia/sets/',
                      '/encyclopedia/monsters/', '/encyclopedia/most-used/',
                      '/sharedbuilds/', '/', '/es/encyclopedia/')
        for p in entites:
            self.assertTrue(_context(_Req(p))['version_switch_is_entity'], p)
        for p in carrefours:
            self.assertFalse(_context(_Req(p))['version_switch_is_entity'], p)

    def test_a_hub_keeps_its_path_under_every_version(self):
        ctx = _context(_Req('/encyclopedia/sets/'))
        hrefs = _render(ctx)
        self.assertEqual(hrefs['dofus3'], '/encyclopedia/sets/')
        self.assertEqual(hrefs['retro'], '/retro/encyclopedia/sets/')
        self.assertEqual(hrefs['touch'], '/touch/encyclopedia/sets/')

    def test_an_entity_links_only_where_it_exists_and_the_hub_elsewhere(self):
        ctx = _context(_Req('/encyclopedia/monster/4960-captain-chafer/'))
        ctx['monster_version_links'] = [
            {'game_version': 'beta', 'label': 'Beta',
             'url': '/beta/encyclopedia/monster/4960-captain-chafer/'}]
        hrefs = _render(ctx)
        self.assertEqual(hrefs['dofus3'], '/encyclopedia/monster/4960-captain-chafer/')
        self.assertEqual(hrefs['beta'], '/beta/encyclopedia/monster/4960-captain-chafer/')
        self.assertEqual(hrefs['dofus2'], '/dofus2/encyclopedia/')
        self.assertEqual(hrefs['retro'], '/retro/encyclopedia/')
        self.assertEqual(hrefs['touch'], '/touch/encyclopedia/')

    def test_item_style_links_are_matched_by_label(self):
        """Item, set and resource entries carry a label and no version key."""
        ctx = _context(_Req('/encyclopedia/item/equipment/44-twiggy-sword/'))
        ctx['other_versions'] = [
            {'label': 'Retro', 'url': '/retro/encyclopedia/item/equipment/44-twiggy-sword/'}]
        hrefs = _render(ctx)
        self.assertEqual(hrefs['retro'], '/retro/encyclopedia/item/equipment/44-twiggy-sword/')
        self.assertEqual(hrefs['dofus2'], '/dofus2/encyclopedia/')

    def test_the_language_prefix_survives(self):
        ctx = _context(_Req('/es/encyclopedia/monster/4960-captain-chafer/'))
        ctx['monster_version_links'] = []
        hrefs = _render(ctx)
        self.assertEqual(hrefs['retro'], '/es/retro/encyclopedia/')
        self.assertEqual(hrefs['dofus3'], '/es/encyclopedia/monster/4960-captain-chafer/')

    def test_a_shared_build_still_goes_home(self):
        """The July rule for private and shared builds is untouched."""
        hrefs = _render(_context(_Req('/retro/s/name/AbCdEf_/', 'retro')))
        self.assertEqual(hrefs['dofus3'], '/')
        self.assertEqual(hrefs['touch'], '/touch/')

    def test_the_tag_distinguishes_present_from_absent(self):
        """Control: the same page with and without the link must differ, or
        the assertions above would pass on a tag that always returns the hub."""
        ctx = _context(_Req('/encyclopedia/monster/4960-captain-chafer/'))
        sans = _render(dict(ctx, monster_version_links=[]))
        avec = _render(dict(ctx, monster_version_links=[
            {'game_version': 'retro', 'label': 'Retro',
             'url': '/retro/encyclopedia/monster/4960-captain-chafer/'}]))
        self.assertNotEqual(sans['retro'], avec['retro'])
        self.assertEqual(sans['retro'], '/retro/encyclopedia/')
        self.assertEqual(avec['retro'], '/retro/encyclopedia/monster/4960-captain-chafer/')


class TheRealMonsterPageHasNoDeadHeaderLink(TestCase):

    def test_captain_chafer(self):
        """4960 exists in dofus3 and beta only (the cross-version block says
        so). The header must send retro, dofus2 and touch to their hub."""
        page = self.client.get('/encyclopedia/monster/4960-captain-chafer/')
        self.assertEqual(page.status_code, 200)
        html = page.content.decode('utf-8')
        entete = re.findall(r'<a class="version-link[^"]*" href="([^"]+)"', html)
        self.assertTrue(entete, 'no header switcher rendered: the test is blind')
        self.assertIn('/beta/encyclopedia/monster/4960-captain-chafer/', entete)
        for v in ('retro', 'dofus2', 'touch'):
            self.assertIn('/%s/encyclopedia/' % v, entete, v)
            self.assertNotIn('/%s/encyclopedia/monster/4960-captain-chafer/' % v, entete, v)
