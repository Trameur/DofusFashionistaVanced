# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The Touch shared builds gallery filters on the TemporiX mode."""

import pickle
import re

from django.core.cache import cache
from django.test import TestCase

from chardata.models import Char
from fashionistapulp.modelresult import ModelResultMinimal

SITE = 'https://dofusfashionista.gg'


def _solution(temporix):
    entree = {
        'options': {'ap_exo': False, 'mp_exo': False, 'temporix': temporix},
        'origin': 'generated',
        'char_level': 200,
        'base_stats_by_attr': {'Vitality': 0, 'Wisdom': 0, 'Strength': 0,
                               'Intelligence': 0, 'Chance': 0, 'Agility': 0},
        'locked_equips': {},
    }
    return pickle.dumps(ModelResultMinimal({}, entree, {}))


def _builds(nombre, temporix, prefix, char_class='Cra', game_version='touch'):
    solution = _solution(temporix)
    Char.objects.bulk_create([
        Char(name='%s %d' % (prefix, i), char_name='%s%d' % (prefix.lower(), i),
             char_class=char_class, char_build='Str', level=200,
             minimum_stats=b'', minimum_crits=b'', stats_weight=b'',
             options=b'', inclusions=b'', exclusions=b'',
             minimal_solution=solution, link_shared=True,
             game_version=game_version)
        for i in range(nombre)])


def _canonical(html):
    tag = re.search(r'<link[^>]*rel="canonical"[^>]*>', html)
    return re.search(r'href="([^"]*)"', tag.group(0)).group(1) if tag else None


class TheGalleryFiltersOnTemporixTests(TestCase):

    def _count(self, chemin):
        reponse = self.client.get(chemin)
        self.assertEqual(200, reponse.status_code, chemin)
        return reponse.context['page_obj'].paginator.count

    def test_by_default_every_server_is_shown(self):
        _builds(2, True, 'Rayonnant')
        _builds(3, False, 'Normal')
        self.assertEqual(5, self._count('/touch/sharedbuilds/'))

    def test_only_keeps_the_temporix_builds(self):
        _builds(2, True, 'Rayonnant')
        _builds(3, False, 'Normal')
        self.assertEqual(2, self._count('/touch/sharedbuilds/?temporix=only'))

    def test_hide_drops_the_temporix_builds(self):
        _builds(2, True, 'Rayonnant')
        _builds(3, False, 'Normal')
        self.assertEqual(3, self._count('/touch/sharedbuilds/?temporix=hide'))

    def test_an_unrecognised_value_behaves_as_the_default(self):
        _builds(2, True, 'Rayonnant')
        _builds(3, False, 'Normal')
        self.assertEqual(5, self._count('/touch/sharedbuilds/?temporix=nonsense'))

    def test_it_combines_with_hide_invalid(self):
        from chardata import shared_builds_view as vue
        _builds(1, True, 'InvalideRayonnant')
        _builds(1, True, 'ValideRayonnant')
        _builds(1, False, 'ValideNormal')

        invalide = Char.objects.get(char_name='invaliderayonnant0')
        meta = dict(vue._get_shared_build_meta(invalide))
        meta['is_invalid'] = True
        cache.set(vue._get_shared_build_meta_cache_key(invalide), meta, 600)

        reponse = self.client.get(
            '/touch/sharedbuilds/?temporix=only&hide_invalid=1')
        noms = {b['char'].char_name for b in reponse.context['builds']}
        self.assertEqual({'validerayonnant0'}, noms)

    def test_the_control_is_absent_and_the_parameter_ignored_on_dofus3(self):
        _builds(2, True, 'Rayonnant', game_version='dofus3')
        _builds(3, False, 'Normal', game_version='dofus3')
        html = self.client.get('/sharedbuilds/').content.decode('utf-8')
        self.assertNotIn('name="temporix"', html)
        self.assertEqual(5, self._count('/sharedbuilds/?temporix=only'))
        self.assertEqual(5, self._count('/sharedbuilds/?temporix=hide'))

    def test_the_control_is_shown_on_touch(self):
        _builds(1, True, 'Rayonnant')
        html = self.client.get('/touch/sharedbuilds/').content.decode('utf-8')
        self.assertIn('name="temporix"', html)

    def test_a_temporix_filter_collapses_to_the_plain_canonical(self):
        _builds(30, True, 'Rayonnant')
        html = self.client.get(
            '/touch/sharedbuilds/?temporix=only&page=2').content.decode('utf-8')
        self.assertEqual(SITE + '/touch/sharedbuilds/', _canonical(html))

    def test_without_the_filter_page_two_keeps_its_own_canonical(self):
        _builds(30, False, 'Normal')
        html = self.client.get(
            '/touch/sharedbuilds/?page=2').content.decode('utf-8')
        self.assertEqual(SITE + '/touch/sharedbuilds/?page=2', _canonical(html))

    def test_pagination_links_carry_the_filter(self):
        _builds(30, True, 'Rayonnant')
        html = self.client.get(
            '/touch/sharedbuilds/?temporix=only').content.decode('utf-8')
        pagination = re.search(r'<div class="pagination">(.*?)</div>',
                               html, re.S)
        self.assertIsNotNone(pagination)
        self.assertIn('temporix=only', pagination.group(1))

    def test_the_select_keeps_the_chosen_value_after_submit(self):
        # Minified markup sorts and quotes attributes, order not guaranteed.
        _builds(1, True, 'Rayonnant')
        html = self.client.get(
            '/touch/sharedbuilds/?temporix=hide').content.decode('utf-8')
        select = re.search(r'<select[^>]*name="temporix"[^>]*>(.*?)</select>',
                           html, re.S)
        self.assertIsNotNone(select)
        hide_option = re.search(r'<option[^>]*value="hide"[^>]*>',
                                select.group(1))
        only_option = re.search(r'<option[^>]*value="only"[^>]*>',
                                select.group(1))
        self.assertIn('selected', hide_option.group(0))
        self.assertNotIn('selected', only_option.group(0))
