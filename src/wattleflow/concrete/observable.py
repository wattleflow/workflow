# Module name: src/wattleflow/concrete/observable.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #
from __future__ import annotations
import logging
from threading import RLock
from typing import List
from wattleflow.core.concurrent import IObservableReactive, IObserverReactive
from wattleflow.concrete.wattleflow import Wattleflow
# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

__author__ = "WattleFlow"
__copyright__ = "© 2022–2026 WattleFlow. All rights reserved"
__license__ = "Apache 2 Licence"

logger = logging.getLogger(__name__)


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

    def __init__(self) -> None:
        super().__init__()
        self._observers: List[IObserverReactive] = []
        self._lock = RLock()

    def add_observer(self, observer: IObserverReactive) -> None:
        """Register an observer if not already present (thread-safe)."""
        with self._lock:
            if observer not in self._observers:
                self._observers.append(observer)

    def remove_observer(self, observer: IObserverReactive) -> None:
        """Unregister an observer (thread-safe)."""
        with self._lock:
            if observer in self._observers:
                self._observers.remove(observer)

    def notify_observers(self, *args, **kwargs) -> None:
        """Notify all registered observers (snapshot; failures suppressed)."""
        with self._lock:
            observers_snapshot = list(self._observers)
        for observer in observers_snapshot:
            try:
                observer.update(self, *args, **kwargs)
            except Exception as exc:
                logger.exception(
                    "Observer %r raised exception during update: %s", observer, exc
                )


# --------------------------------------------------------------------------- #
# endregion Implementation                                                    #
# --------------------------------------------------------------------------- #
