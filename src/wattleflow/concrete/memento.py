# Module Name: concrete/memento.py
# Description: This modul contains concrete memento classes.
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence

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
