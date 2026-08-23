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
from wattleflow.enums.event import Event

# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

__author__ = "WattleFlow"
__copyright__ = "© 2022–2026 WattleFlow. All rights reserved"
__license__ = "Apache 2 Licence"


# --------------------------------------------------------------------------- #
# region Implementation                                                       #
# --------------------------------------------------------------------------- #
class ThreadSafeObservable(Wattleflow, IObservableReactive):
    """
    ThreadSafeObservable - canonical IObservableReactive policy.

    Policy decisions this class fixes (deliberately, as implementation —
    not contract; DR-COR-005):
      * Registration is guarded by an RLock, allowing re-entrant calls if
        observer callbacks interact with the observable.
      * Notifications are delivered to a snapshot of registered observers,
        in registration order, so the list may be mutated mid-notification.
      * An observer that raises is logged and suppressed; remaining
        observers are still notified. NOTE (availability, A in CIA): a
        failing observer becomes invisible to the caller — consumers whose
        observers are delivery-critical need a different policy class.
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._observers: list[IObserverReactive] = []
        self._lock = RLock()

    def add_observer(self, observer: IObserverReactive) -> None:
        with self._lock:
            if observer not in self._observers:
                self._observers.append(observer)

    def remove_observer(self, observer: IObserverReactive) -> None:
        with self._lock:
            if observer in self._observers:
                self._observers.remove(observer)

    def notify_observers(self, *args, **kwargs) -> None:
        with self._lock:
            observers_snapshot = list(self._observers)
        for observer in observers_snapshot:
            try:
                observer.update(self, *args, **kwargs)
            except Exception as e:
                self.exception(
                    msg=Event.Notify.name,
                    reason="Observer raised during update",
                    observer=observer,
                    error=str(e),
                )


# --------------------------------------------------------------------------- #
# endregion Implementation                                                    #
# --------------------------------------------------------------------------- #


__all__ = ["ThreadSafeObservable"]
