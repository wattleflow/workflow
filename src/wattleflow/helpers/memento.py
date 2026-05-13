# Module name: memento.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2025 WattleFlow. All rights reserved.
# License: Apache 2 Licence


"""
This module provides reusable Memento and Observable building blocks for
Wattleflow components that need to snapshot internal state or broadcast
change events to subscribed listeners.
"""

# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #

from __future__ import annotations
import copy
from wattleflow.core import IMemento, IObservable

# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# region Classes                                                              #
# --------------------------------------------------------------------------- #


class MementoClass(IMemento):
    # FIX: previously kept a shallow reference to the caller's state via the
    # commented `self._state = state` line. Snapshotting must be defensive,
    # otherwise later mutation of the originator leaks into the memento and
    # breaks restore semantics — always deep-copy.
    def __init__(self, state):
        self._state = copy.deepcopy(state)

    def get_state(self):
        return self._state


class ObservableClass(IObservable):
    def __init__(self):
        self._listeners = []

    def notify(self, **kwargs):
        for listener in self._listeners:
            listener.update(**kwargs)

    def subscribe(self, listener):
        self._listeners.append(listener)


# --------------------------------------------------------------------------- #
# endregion Classes                                                           #
# --------------------------------------------------------------------------- #
