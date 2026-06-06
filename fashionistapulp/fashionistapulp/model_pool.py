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

from collections import defaultdict
from queue import Empty, Queue

from .model import Model
from .structure import get_current_game_version

# A Model caches a version-specific structure (items / sets / stats) built when it
# is created; setup() only re-applies constraints -- it does NOT rebuild that
# structure. So models MUST be pooled per game version: borrowing a model built
# for another version would solve the request with the wrong version's items,
# producing random broken / incomplete builds across versions. Key the pool by
# the game version each model was built for.
_model_queues = defaultdict(Queue)


def create_model():
    """Pre-build a model for the current game version and add it to its pool."""
    _model_queues[get_current_game_version()].put(Model())


def borrow_model():
    version = get_current_game_version()
    try:
        return _model_queues[version].get_nowait()
    except Empty:
        # No pooled model for this version yet -- build one (captures this
        # version's structure). If a previous borrow was never returned (e.g.
        # an exception), this also avoids blocking forever on an empty queue.
        return Model()


def return_model(borrowed_model):
    _model_queues[borrowed_model.structure.game_version].put(borrowed_model)
