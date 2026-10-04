# Module name: src/wattleflow/concrete/observable.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #
from __future__ import annotations
from threading import RLock
from wattleflow.core.concurrent import IObservableReactive, IObserverReactive
from wattleflow.concrete.base import Wattleflow
from wattleflow.concrete.helpers import Attribute
from wattleflow.enums.event import Event

# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

__author__ = "WattleFlow"
__copyright__ = "© 2022–2026 WattleFlow. All rights reserved"
__license__ = "Apache 2 Licence"


# --------------------------------------------------------------------------- #
# region Clasess                                                              #
# --------------------------------------------------------------------------- #


class ThreadSafeObservable(Wattleflow, IObservableReactive):
    """ThreadSafeObservable - canonical IObservableReactive policy."""

    # Not `_lock`: a slot of that name shadows Audit._lock, which Audit.__init__ takes before this
    # constructor could assign one, so the observable could not be built at all.
    __slots__ = ("_observers", "_observers_lock")

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._observers: list[IObserverReactive] = []
        self._observers_lock = RLock()

    def add_observer(self, observer: IObserverReactive) -> None:
        Attribute.evaluate(self, observer, IObserverReactive)
        with self._observers_lock:
            # Identity, not ==: an observer is subscribed as an object, so two equal ones are two.
            if not any(known is observer for known in self._observers):
                self._observers.append(observer)

    def remove_observer(self, observer: IObserverReactive) -> None:
        with self._observers_lock:
            for index, known in enumerate(self._observers):
                if known is observer:
                    del self._observers[index]
                    break

    def notify_observers(self, *args, **kwargs) -> None:
        with self._observers_lock:
            observers_snapshot = list(self._observers)
        for observer in observers_snapshot:
            try:
                observer.update(self, *args, **kwargs)
            except Exception as e:
                self.exception(
                    msg=Event.Notify,
                    reason="Observer raised during update",
                    observer=observer,
                    error=str(e),
                )


# --------------------------------------------------------------------------- #
# endregion Implementation                                                    #
# --------------------------------------------------------------------------- #


__all__ = ["ThreadSafeObservable"]
