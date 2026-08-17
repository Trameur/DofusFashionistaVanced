# Copyright (C) 2020 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

"""Does any action endpoint answer 500?

check_pages walks what a crawler can GET. Every 500 a player has reported was a
POST instead, and the last one proves the gap: the weapon picker, ordered by
damage with a search term, reached one of the four Retro weapons the game gives
no AP cost, and no GET on any page could have found it.

This posts the picker and the lock family the way the solution page really does,
once per slot and per version, plus what a stale tab and a fuzzer send. The
project it works on is created and deleted here, so it needs no fixture.

    py fashionsite/manage.py check_actions --settings=fashionsite.settings_dev
    py fashionsite/manage.py check_actions --only retro

Exit code is 1 when anything answered 500 or raised. A 400 is a pass: refusing a
payload is the point.

It sends no mail: it posts as the owner of its own project, and the only endpoint
here that would notify anyone skips a comment left by the build's own owner. The
authentication endpoints are deliberately absent, since a sweep of those would
send real mail and trip the throttles.
"""
import _pickle

from django.core.management.base import BaseCommand, CommandError
from django.test import Client

from fashionistapulp.dofus_constants import SLOTS, SLOT_NAME_TO_TYPE
from fashionistapulp.modelresult import ModelResultMinimal
from fashionistapulp.structure import get_structure, set_current_game_version

VERSIONS = ('dofus3', 'beta', 'dofus2', 'touch', 'retro')

# What the page sends, and what nothing sends on purpose. The search terms are
# the interesting half: a term is what pulls an odd item onto page 1.
SEARCH_TERMS = ('', 'a', 'e', 'ring', 'Mercenary', 'Gelano', 'x' * 300,
                "'; DROP TABLE", '%00', 'Rata')
HOSTILE_PAGES = ('1', '0', '-1', 'abc', '', '99999999')
STAT_FILTERS = ('[]', '[{"stat": "ap", "value": 1}]', 'not json', '{}',
                '[{"stat": "nope", "value": "x"}]')
UNKNOWN_ITEM = 'No Such Item At All'

# The form posts of the workshop, with nothing and with nonsense in them. A form
# that has moved on and a tab that has not send exactly this.
FORM_PATHS = (
    '/statspost/%d/', '/minstatspost/%d/', '/optionspost/%d/',
    '/inclusionspost/%d/', '/exclusionspost/%d/', '/wizardpost/%d/',
    '/wizardgetsliders/%d/', '/setup/%d/', '/save_char/%d/',
    '/initbasestatspost/%d/', '/saveproject/%d/', '/addtag/%d/',
    '/setitemstatoverride/%d/', '/setchargender/%d/', '/setcharcolors/%d/',
    '/setcharhidden/%d/', '/getsharinglink/%d/', '/hidesharinglink/%d/',
    '/duplicatemyproject/%d/', '/workshop/addsolution/%d/',
)
NONSENSE = {'name': 'x' * 400, 'level': 'abc', 'char_level': '-3',
            'value': 'NaN', 'stat': 'no-such-stat', 'weights': '{',
            'gender': '7', 'colors': 'not json', 'hidden': 'maybe',
            'tag': 'x' * 400, 'itemId': 'not-an-id', 'stat_id': '999999',
            'points_str': 'abc', 'scrolled_str': '-1', 'preview_size': 'huge'}


class Command(BaseCommand):
    help = 'Post every action endpoint and report anything that answers 500.'

    def add_arguments(self, parser):
        parser.add_argument('--only', help='one game version')

    def handle(self, *args, **options):
        versions = [v for v in VERSIONS
                    if not options['only'] or v == options['only']]
        if not versions:
            raise CommandError('unknown version %r' % options['only'])

        posted = 0
        findings = []
        for version in versions:
            set_current_game_version(version)
            char, user = self._make_project(version)
            client = Client()
            client.force_login(user)
            prefix = '' if version == 'dofus3' else '/' + version
            try:
                for path, payload in self._payloads(version, char.pk):
                    posted += 1
                    url = '%s%s' % (prefix, path)
                    try:
                        response = client.post(url, payload)
                    except Exception as error:            # noqa: BLE001
                        findings.append((url, payload, '%s: %s'
                                         % (type(error).__name__,
                                            str(error)[:90])))
                        continue
                    if response.status_code >= 500:
                        findings.append((url, payload, response.status_code))
            finally:
                # The chars cascade off the user, including any the sweep
                # duplicated on the way.
                user.delete()
        set_current_game_version('dofus3')

        self.stdout.write('posts made: %d' % posted)
        if findings:
            self.stdout.write('answered 500 or raised:')
            for url, payload, what in findings:
                self.stdout.write('   %-34s %-58s %s'
                                  % (url, str(payload)[:58], what))
            raise SystemExit(1)
        self.stdout.write('no action endpoint answered 500')

    def _make_project(self, version):
        from django.contrib.auth.models import User
        from chardata.models import Char
        username = 'check-actions-%s' % version
        # A run stopped with Ctrl-C never reaches its own cleanup, and the name
        # is fixed, so start by taking the previous one away.
        User.objects.filter(username=username).delete()
        user = User.objects.create_user(
            username, 'check-actions-%s@invalid.local' % version, 'pw-42-solid')
        model_input = {
            'char_class': 'Iop', 'char_level': 200, 'origin': 'generated',
            'options': {'ap_exo': False, 'mp_exo': False},
            'base_stats_by_attr': {'Vitality': 0, 'Wisdom': 0, 'Strength': 0,
                                   'Intelligence': 0, 'Chance': 0,
                                   'Agility': 0},
            'locked_equips': {}}
        char = Char.objects.create(
            name='Action Check', char_name='action-check', char_class='Iop',
            char_build='Damage', level=200, minimum_stats=b'',
            minimum_crits=b'', stats_weight=b'', options=b'', inclusions=b'',
            exclusions=b'',
            minimal_solution=_pickle.dumps(
                ModelResultMinimal({}, model_input, {})),
            owner=user, link_shared=False, game_version=version)
        return char, user

    def _payloads(self, version, char_id):
        """(path, POST dict) pairs, in the order the page would send them."""
        structure = get_structure(version)
        for slot in SLOTS:
            # What the page sends when you open the picker on a slot, both ways
            # round: ordered by damage and ordered by the stats you weighted.
            for order in ('true', 'false'):
                yield ('/itemexchange/%d/' % char_id,
                       {'slot': slot, 'page': '1', 'order_by_stat': order,
                        'search_term': '', 'stat_filters_json': '[]',
                        'inventory_only': 'false', 'source_filter': ''})
            yield ('/itemadd/%d/' % char_id,
                   {'slot': slot, 'page': '1', 'search_term': '',
                    'stat_filters_json': '[]', 'inventory_only': 'false'})

        # A search term is what pulls an odd item onto the first page, which is
        # how the Retro weapons with no AP cost were reached.
        for slot in ('weapon', 'ring1', 'amulet', 'pet', 'dofus1'):
            for term in SEARCH_TERMS:
                yield ('/itemexchange/%d/' % char_id,
                       {'slot': slot, 'page': '1', 'order_by_stat': 'true',
                        'search_term': term, 'stat_filters_json': '[]',
                        'inventory_only': 'false', 'source_filter': ''})

        for page in HOSTILE_PAGES:
            yield ('/itemexchange/%d/' % char_id,
                   {'slot': 'weapon', 'page': page, 'order_by_stat': 'true',
                    'search_term': '', 'stat_filters_json': '[]'})
        for filters in STAT_FILTERS:
            yield ('/itemexchange/%d/' % char_id,
                   {'slot': 'boots', 'page': '1', 'order_by_stat': 'true',
                    'search_term': '', 'stat_filters_json': filters})
        yield ('/itemexchange/%d/' % char_id, {})
        yield ('/itemexchange/%d/' % char_id, {'slot': 'not-a-slot'})
        yield ('/itemadd/%d/' % char_id, {'slot': 'not-a-slot'})

        # The lock and forbid buttons, named by item: a real one, a group whose
        # branches are only known under the group name, and a name this version
        # does not have, which is what a tab left open across a rebuild sends.
        names = []
        for slot in ('boots', 'ring1', 'weapon'):
            type_name = SLOT_NAME_TO_TYPE[slot]
            type_id = structure.get_type_id_by_name(type_name)
            for item in structure.get_concatenated_items_lists():
                if item.type == type_id and not item.removed:
                    names.append((slot, item.localized_names.get('en')
                                  or item.name))
                    break
        for group_name in list(structure.or_items)[:2]:
            names.append(('ring1', group_name))
        names.append(('boots', UNKNOWN_ITEM))
        names.append(('boots', ''))
        for slot, name in names:
            for flag in ('true', 'false'):
                yield ('/setitemlocked/%d/' % char_id,
                       {'slot': slot, 'equip': name, 'locked': flag})
                yield ('/setitemforbidden/%d/' % char_id,
                       {'slot': slot, 'equip': name, 'forbidden': flag})

        for slot in ('boots', 'weapon', 'dofus1'):
            yield ('/setslotlockempty/%d/' % char_id,
                   {'slot': slot, 'empty': 'true'})
            yield ('/setslotlockempty/%d/' % char_id,
                   {'slot': slot, 'empty': 'false'})

        for path in FORM_PATHS:
            yield (path % char_id, {})
            yield (path % char_id, dict(NONSENSE))

        # The exclusion list arrives as a JSON string, so it has its own ways of
        # not being one.
        for raw in ('[]', '[1, 2]', 'not json', '{"a": 1}', '5', 'null',
                    '[1, "x"]', '["' + 'x' * 300 + '"]'):
            yield ('/exclusionspost/%d/' % char_id, {'exclusions': raw})
        for slot in ('boots', 'weapon'):
            yield ('/inclusionspost/%d/' % char_id, {slot: UNKNOWN_ITEM})
            yield ('/inclusionspost/%d/' % char_id, {slot: 'x' * 400})

        # The turn panel posts two JSON objects, and what is inside them reaches
        # the combo simulator.
        for buffs in ('{}', 'not json', '[]', '{"x": "y"}', '{"1": -5}',
                      '{"power": 99999}', 'null'):
            yield ('/best_combo/%d/' % char_id,
                   {'buff_state': buffs, 'spell_levels': buffs})
        yield ('/spells/%d/' % char_id, {})
        for content in ('', 'x' * 5000, '<script>alert(1)</script>'):
            yield ('/postcomment/%d/' % char_id, {'content': content})

        # The inventory: folders and rolls, keyed by ids the page sends back.
        yield ('/inventory/folder/add/', {'name': 'sweep'})
        yield ('/inventory/folder/add/', {'name': 'x' * 400})
        yield ('/inventory/folder/add/', {})
        for folder_id in ('abc', '-1', '0', '99999999', ''):
            yield ('/inventory/folder/delete/', {'folder_id': folder_id})
            yield ('/inventory/add/', {'folder_id': folder_id, 'item_id': '1'})
        for item_id in ('abc', '-1', '99999999', ''):
            yield ('/inventory/add/', {'folder_id': '1', 'item_id': item_id})
        for custom in ('', '{}', 'not json', '{"mp": "x"}', '{"nope": 3}',
                       '[1, 2]'):
            yield ('/inventory/update/', {'id': '1', 'custom_stats': custom})
        for inv_id in ('abc', '-1', '99999999', ''):
            yield ('/inventory/remove/', {'id': inv_id})
            yield ('/inventory/update/', {'id': inv_id, 'custom_stats': '{}'})

        yield ('/choose_compare_sets_post/', {})
        yield ('/choose_compare_sets_post/',
               {'char1': str(char_id), 'char2': 'abc'})

        # Switching an item writes the solution back, so it goes last.
        for slot in ('boots', 'weapon', 'ring1'):
            type_id = structure.get_type_id_by_name(SLOT_NAME_TO_TYPE[slot])
            item = next((i for i in structure.get_concatenated_items_lists()
                         if i.type == type_id and not i.removed), None)
            if item is not None:
                yield ('/exchange/%d/' % char_id,
                       {'slot': slot, 'itemName': str(item.id)})
            yield ('/exchange/%d/' % char_id,
                   {'slot': slot, 'itemName': 'not-an-id'})
            yield ('/remove/%d/' % char_id, {'slot': slot})
