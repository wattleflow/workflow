# Module name: src/wattleflow/concrete/iterator.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #
from __future__ import annotations

__all__ = ["LazyAsyncIterator", "LazyIterator", "ThreadSafeLazyIterator"]

import threading
from collections.abc import AsyncIterator, Iterator
from wattleflow.core.behavioural import IIterator, IAsyncIterator, Element
from wattleflow.concrete.base import Wattleflow
from wattleflow.concrete.helper import Attribute
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
class LazyIterator(Wattleflow, IIterator[Element]):
    """LazyIterator - canonical lazy IIterator policy."""

    __slots__ = ("_iterator",)

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._iterator: Iterator[Element] | None = None

    def _build(self) -> Iterator[Element]:
        self.debug(msg=Event.Create, step=Event.Started)
        try:
            source = self.create_iterator()
            Attribute.evaluate(self, source, Iterator)
        except Exception as error:
            self.debug(msg=Event.Create, step=Event.Failed, error=str(error))
            raise
        self.debug(msg=Event.Create, step=Event.Completed)
        return source

    def __next__(self) -> Element:
        if self._iterator is None:
            self._iterator = self._build()
        return next(self._iterator)


class ThreadSafeLazyIterator(LazyIterator[Element]):
    """ThreadSafeLazyIterator - LazyIterator whose source is built once under concurrent first fetches."""

    # The lock is not named _lock: a slot of that name would shadow Audit._lock.
    __slots__ = ("_build_lock",)

    def __init__(self, **kwargs) -> None:
        self._build_lock = threading.Lock()
        super().__init__(**kwargs)

    def __next__(self) -> Element:
        if self._iterator is None:
            with self._build_lock:
                if self._iterator is None:
                    self._iterator = self._build()
        return next(self._iterator)


class LazyAsyncIterator(Wattleflow, IAsyncIterator[Element]):
    """
    LazyAsyncIterator - canonical lazy IAsyncIterator policy.
    """

    __slots__ = ("_iterator",)

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._iterator: AsyncIterator[Element] | None = None

    def _build(self) -> AsyncIterator[Element]:
        self.debug(msg=Event.Create, step=Event.Started)
        try:
            source = self.create_iterator()
            Attribute.evaluate(self, source, AsyncIterator)
        except Exception as error:
            self.debug(msg=Event.Create, step=Event.Failed, error=str(error))
            raise
        self.debug(msg=Event.Create, step=Event.Completed)
        return source

    async def __anext__(self) -> Element:
        if self._iterator is None:
            self._iterator = self._build()
        return await self._iterator.__anext__()


# --------------------------------------------------------------------------- #
# endregion Implementation                                                    #
# --------------------------------------------------------------------------- #
