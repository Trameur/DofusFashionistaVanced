# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Builds a character through each /setup/ creation door, with fields the player touched, for the tests that compare the stored result."""
import json

from django.test import RequestFactory

from chardata.models import Char
from chardata.setup_preview import panel_context
from chardata.stats_weights_view import weights_mins_post
from chardata.tests_the_hand_door_saves_no_minimum_as_the_setup_panel_says import one_element_box
from chardata.tests_the_setup_preview_matches_the_build_the_door_creates import (
    _DoorBuilds, classes_of, form_fields)
from chardata.weights_minimums import page_state
from fashionistapulp.structure import set_current_game_version

DOORS = ('wizard', 'optimize', 'byhand')


def door_fields(door, char_class, level, aspects, touched=()):
    fields = [(key, value) for key, value in form_fields(char_class, level, aspects)
              if key != 'wizard']
    return fields + [(door, door)] + list(touched)


def panel_rows(version):
    """(weight keys, minimum keys) of the rows the panel lets a player edit, aggregates and the derived row left out."""
    rows = [row for section in panel_context(version)['sections'] for row in section['rows']]
    weights = [row['key'] for row in rows
               if row['weight'] and not row['aggregate'] and not row['derived']]
    minimums = [row['key'] for row in rows if row['minimum'] and not row['aggregate']]
    minimums += [adv['key'] for adv in panel_context(version)['combined']]
    return weights, minimums


class TouchedDoors(_DoorBuilds):

    def build(self, version, door, touched=(), level=200):
        char_class = sorted(classes_of(version))[0]
        fields = door_fields(door, char_class, level, one_element_box(version), touched)
        built = self.door_build(version, fields)
        set_current_game_version(version)
        return Char.objects.get(pk=built.pk)

    def state(self, version, char):
        set_current_game_version(version)
        return json.loads(json.dumps(page_state(Char.objects.get(pk=char.pk))))

    def weights_page(self, version, char, fields):
        """The state the weights page answers when it is posted these fields for this build."""
        set_current_game_version(version)
        request = RequestFactory().post('/', dict(fields))
        request.user = self.owner
        request.game_version = version
        response = weights_mins_post(request, char.pk)
        self.assertEqual(200, response.status_code)
        return json.loads(response.content)
