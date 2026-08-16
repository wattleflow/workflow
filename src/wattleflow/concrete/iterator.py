# Module name: src/wattleflow/concrete/iterator.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #
from __future__ import annotations
from collections.abc import AsyncIterator, Iterator
from wattleflow.core.behavioural import IIterator, IAsyncIterator, Element
from wattleflow.concrete.base import Wattleflow
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
    """
    LazyIterator - canonical lazy IIterator policy.

    Builds the underlying iterator on first __next__ via create_iterator()
    and caches it for the remainder of the traversal (DR-COR-007). Subclasses
    implement create_iterator() only.

    Wattleflow supplies the root identity contract (name); without it every
    subclass would inherit `name` abstract and stay uninstantiable.
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._iterator: Iterator[Element] | None = None

    def __next__(self) -> Element:
        if self._iterator is None:
            self._iterator = self.create_iterator()
        return next(self._iterator)


class LazyAsyncIterator(Wattleflow, IAsyncIterator[Element]):
    """
    LazyAsyncIterator - canonical lazy IAsyncIterator policy.

    create_iterator() is synchronous and returns an AsyncIterator; it is
    invoked on first __anext__ and cached (DR-COR-007).
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._iterator: AsyncIterator[Element] | None = None

    async def __anext__(self) -> Element:
        if self._iterator is None:
            self._iterator = self.create_iterator()
        return await self._iterator.__anext__()


# --------------------------------------------------------------------------- #
# endregion Implementation                                                    #
# --------------------------------------------------------------------------- #


__all__ = ["LazyAsyncIterator", "LazyIterator"]
