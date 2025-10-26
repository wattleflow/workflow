# Module name: memento.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2025 WattleFlow. All rights reserved.
# License: Apache 2 Licence


from __future__ import annotations
import copy
from wattleflow.core import IMemento, IObservable


class MementoClass(IMemento):
    def __init__(self, state):
        # self._state = state
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
