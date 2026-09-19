# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
import re
import sqlite3

from django.test import TestCase

from fashionistapulp.fashionista_config import get_items_db_path
from fashionistapulp.structure import get_structure

BELTEEN = '/encyclopedia/item/equipment/15699-belteen/'
CEINTACE = '/encyclopedia/item/equipment/15699-ceintace/'


class AStaleEncyclopediaUrlMovesForGood(TestCase):

    def _moves_to(self, path, target, **extra):
        response = self.client.get(path, **extra)
        self.assertEqual(response.status_code, 301, path)
        self.assertEqual(response['Location'], target, path)
        return response

    def test_a_trailing_dash_from_the_old_slugs_moves(self):
        self._moves_to('/encyclopedia/item/equipment/15699-belteen-/', BELTEEN)

    def test_a_variant_number_moves_and_the_beta_stays_the_beta(self):
        self._moves_to('/beta/encyclopedia/item/equipment/15699-belteen-1/',
                       '/beta' + BELTEEN)

    def test_a_french_variant_slug_moves_to_the_french_page(self):
        self._moves_to('/encyclopedia/item/equipment/15699-ceintace-1/', CEINTACE)

    def test_a_french_fed_pet_slug_moves_to_the_french_page(self):
        self._moves_to('/touch/encyclopedia/item/equipment/2074-bwak-de-feu-110-vitalite/',
                       '/touch/encyclopedia/item/equipment/2074-bwak-de-feu/')

    def test_a_stale_id_found_by_its_slug_moves_to_the_live_id(self):
        self._moves_to('/encyclopedia/item/equipment/16356-belteen/', BELTEEN)

    def test_a_canonical_french_slug_never_moves(self):
        for header in (None, 'en', 'de'):
            extra = {'HTTP_ACCEPT_LANGUAGE': header} if header else {}
            with self.subTest(header=header):
                response = self.client.get(CEINTACE, **extra)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'Ceintac')

    def test_a_language_prefix_moves_to_the_address_without_it(self):
        self._moves_to('/es/beta/encyclopedia/item/equipment/15699-cintaceo/',
                       '/beta/encyclopedia/item/equipment/15699-cintaceo/')

    def test_an_unknown_slug_follows_the_negotiated_language(self):
        response = self._moves_to('/encyclopedia/item/equipment/15699-zzz/',
                                  CEINTACE, HTTP_ACCEPT_LANGUAGE='fr')
        self.assertIn('cookie', response['Vary'].lower())

    def test_a_slug_that_names_its_language_does_not_vary_on_cookies(self):
        response = self._moves_to('/encyclopedia/item/equipment/15699-belteen-/',
                                  BELTEEN)
        self.assertNotIn('cookie', response.get('Vary', '').lower())

    def test_an_ambiguous_old_slug_is_served_without_moving(self):
        response = self.client.get('/encyclopedia/item/equipment/999999-crocobur/',
                                   HTTP_ACCEPT_LANGUAGE='fr')
        self.assertEqual(response.status_code, 200)

    def test_a_missing_id_stays_a_404(self):
        response = self.client.get(
            '/encyclopedia/item/equipment/999999-zzzz-no-such-item/')
        self.assertEqual(response.status_code, 404)

    def test_a_post_is_not_moved(self):
        response = self.client.post('/encyclopedia/item/equipment/15699-belteen-/')
        self.assertEqual(response.status_code, 200)

    def test_a_head_moves_like_a_get(self):
        response = self.client.head('/encyclopedia/item/equipment/15699-belteen-/')
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response['Location'], BELTEEN)

    def test_the_query_string_is_kept_verbatim(self):
        self._moves_to('/encyclopedia/item/equipment/15699-belteen-/?keeplang=1&q=a%20b',
                       BELTEEN + '?keeplang=1&q=a%20b')

    def test_every_target_is_relative_and_answers_at_once(self):
        stale = ('/encyclopedia/item/equipment/15699-belteen-/',
                 '/beta/encyclopedia/item/equipment/15699-belteen-1/',
                 '/encyclopedia/item/equipment/15699-ceintace-1/',
                 '/encyclopedia/item/equipment/16356-belteen/',
                 '/es/beta/encyclopedia/item/equipment/15699-cintaceo/',
                 '/encyclopedia/set/1/',
                 '/encyclopedia/monster/4960-captain-chafer-1/',
                 '/encyclopedia/resource/resources/287-x/')
        for path in stale:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 301)
                target = response['Location']
                self.assertTrue(target.startswith('/') and not target.startswith('//'),
                                target)
                self.assertEqual(self.client.get(target).status_code, 200, target)

    def test_a_set_without_its_slug_moves_to_the_slugged_address(self):
        response = self.client.get('/encyclopedia/set/1/')
        self.assertEqual(response.status_code, 301)
        self.assertRegex(response['Location'], r'^/encyclopedia/set/1-[a-z0-9-]+/$')

    def test_a_stale_monster_slug_moves(self):
        self._moves_to('/encyclopedia/monster/4960-captain-chafer-1/',
                       '/encyclopedia/monster/4960-captain-chafer/')

    def test_a_stale_resource_slug_moves_to_the_named_page(self):
        conn = sqlite3.connect(get_items_db_path('dofus3'))
        try:
            name = conn.execute(
                "SELECT name FROM item_recipe_ingredient_names WHERE "
                "ingredient_ankama_id = 287 AND ingredient_subtype = 'resources' "
                "AND language = 'en'").fetchone()[0]
        finally:
            conn.close()
        from chardata.official_site import get_resource_link
        self._moves_to('/encyclopedia/resource/resources/287-x/',
                       get_resource_link('resources', 287, name))


class TheSiteLinksNoAddressThatMoves(TestCase):

    def _answers_at_once(self, links):
        self.assertTrue(links, 'no link found: the test is blind')
        for link in sorted(set(links)):
            with self.subTest(link=link):
                self.assertEqual(self.client.get(link).status_code, 200, link)

    def test_the_version_links_of_an_item_page(self):
        response = self.client.get(
            '/encyclopedia/item/equipment/16314-carapace-terre-mineur/')
        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8')
        switcher = re.findall(r'<a class="version-link[^"]*" href="([^"]+)"', html)
        block = re.search(r'encyclopedia-other-versions.*?</div>', html, re.S)
        self.assertIsNotNone(block, 'no other versions block')
        also_in = re.findall(r'href="([^"]+)"', block.group(0))
        self.assertIn('/beta/encyclopedia/item/equipment/16314-carapace-terre-mineure/',
                      also_in)
        self._answers_at_once(switcher + also_in)

    def test_the_drop_links_of_a_touch_monster(self):
        conn = sqlite3.connect(get_items_db_path('touch'))
        try:
            name = conn.execute(
                "SELECT name FROM monster_names WHERE monster_ankama_id = 265 "
                "AND language = 'en'").fetchone()[0]
        finally:
            conn.close()
        from chardata.official_site import get_monster_link
        response = self.client.get(get_monster_link(265, name, 'touch'))
        self.assertEqual(response.status_code, 200)
        links = re.findall(r'href="(/touch/encyclopedia/item/[^"]+)"',
                           response.content.decode('utf-8'))
        structure = get_structure('touch')
        variants = [item for item in structure.get_concatenated_items_lists()
                    if item.ankama_id == 2074]
        self.assertGreater(len(variants), 1, 'the fed variants are gone')
        self._answers_at_once(links)

    def test_the_drop_previews_of_the_monster_lists(self):
        links = []
        for page in ('/touch/encyclopedia/monsters/?q=bwak',
                     '/retro/encyclopedia/monsters/?q=bwak'):
            response = self.client.get(page)
            self.assertEqual(response.status_code, 200, page)
            for tag in re.findall(r'<a [^>]*encyclopedia-monster-drop-link[^>]*>',
                                  response.content.decode('utf-8')):
                href = re.search(r'href="([^"]+)"', tag).group(1)
                if '/encyclopedia/item/' in href:
                    links.append(href)
        self._answers_at_once(links)

    def test_the_item_link_of_a_fed_pet_on_a_build_page(self):
        from chardata.solution_result import evolve_result_item
        from fashionistapulp.modelresult import ModelResult
        from fashionistapulp.structure import set_current_game_version
        set_current_game_version('touch')
        self.addCleanup(set_current_game_version, 'dofus3')
        structure = get_structure('touch')
        fed = next(item for item in structure.get_concatenated_items_lists()
                   if item.ankama_id == 2074 and '(+' in item.name)
        result = ModelResult({'options': {}, 'base_stats_by_attr': {},
                              'char_level': 200})
        result.add_item_at_slot(fed, 'pet')
        item = result.item_list[0]
        evolve_result_item(item, result)
        self.assertEqual('/touch/encyclopedia/item/equipment/2074-fire-bwak/',
                         item.link)
        self._answers_at_once([item.link])


class AMoveStaysOnTheSiteTests(TestCase):

    def test_a_target_naming_another_host_is_not_followed(self):
        from django.test import RequestFactory
        from chardata.url_language import redirect_to_own_address
        request = RequestFactory().get('/encyclopedia/item/equipment/15699-belteen-/')
        for target in ('//evil.example/x/', 'https://evil.example/x/'):
            with self.subTest(target=target):
                self.assertIsNone(redirect_to_own_address(
                    request, lambda: target, 'en', False))
