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

"""The project a signed-out visitor is working on, one per game version."""

SESSION_KEY = 'char_ids'
LEGACY_SESSION_KEY = 'char_id'


def _char_version(char_id):
    from chardata.models import Char
    char = Char.objects.filter(pk=char_id).only('game_version').first()
    return char.game_version if char is not None else None


def get_anon_char_ids(request):
    """{game_version: char id} for this visitor, migrating the old single key."""
    ids = request.session.get(SESSION_KEY)
    if not isinstance(ids, dict):
        ids = {}
    legacy_id = request.session.get(LEGACY_SESSION_KEY)
    if legacy_id is not None:
        version = _char_version(legacy_id)
        if version is not None and version not in ids:
            ids[version] = legacy_id
            request.session[SESSION_KEY] = ids
            request.session.modified = True
    return ids


def get_anon_char_id(request, game_version):
    return get_anon_char_ids(request).get(game_version)


def owns_anon_char(request, char_id):
    """True for a project of any game version, not only the current one."""
    try:
        char_id = int(char_id)
    except (TypeError, ValueError):
        return False
    return char_id in set(get_anon_char_ids(request).values())


def remember_anon_char(request, char):
    ids = dict(get_anon_char_ids(request))
    ids[char.game_version] = char.pk
    request.session[SESSION_KEY] = ids
    # Legacy readers expect the last project created.
    request.session[LEGACY_SESSION_KEY] = char.pk
    request.session.modified = True


def forget_anon_char(request, char_id=None):
    """Drop one project, or all of them when no id is given (sign-in, sign-out)."""
    ids = dict(get_anon_char_ids(request))
    if char_id is None:
        ids = {}
    else:
        try:
            char_id = int(char_id)
        except (TypeError, ValueError):
            return
        ids = {version: pk for version, pk in ids.items() if pk != char_id}
    if ids:
        request.session[SESSION_KEY] = ids
    else:
        request.session.pop(SESSION_KEY, None)
    legacy_id = request.session.get(LEGACY_SESSION_KEY)
    if legacy_id is not None and (char_id is None or int(legacy_id) == char_id):
        request.session.pop(LEGACY_SESSION_KEY, None)
    request.session.modified = True
