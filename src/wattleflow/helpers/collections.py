# Module name: helpers/collections.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


"""
Description: This module defines collection helper classes for use within the Wattleflow
framework. It provides an extended deque implementation with advanced search,
update, and removal functionality, enabling efficient management of dynamic
collections.
"""


# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #

from __future__ import annotations
from collections import deque
from typing import Any, Iterable
from wattleflow.constants.errors import ERROR_NOT_FOUND


# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

REPLACE_ALL = "all"

# --------------------------------------------------------------------------- #
# region DequeList                                                            #
# --------------------------------------------------------------------------- #


# Subclasses deque only: IWattleflow's non-empty __slots__ ("name") is a solid
# C-layout base that cannot be combined with the deque builtin (layout conflict).
# We replicate the IWattleflow identity surface (name / __str__ / __repr__) inline.
class DequeList(deque):
    """
    Extended deque s simplified search and crud over elements.
    - find(*args, **kwargs)
    - remove_match(...):
    - update(new_object, ...)
    """

    def __init__(self, iterable: Iterable[Any] | None = None):
        super().__init__(iterable or ())
        self.name = type(self).__name__

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"{type(self).__name__}(name={self.name!r})"

    @staticmethod
    def _matches(item: Any, args: tuple, kwargs: dict) -> bool:
        # Podudaranje po vrijednosti (int/str) ili po atributima
        if isinstance(item, (int, str)):
            return item in args if args else False
        return all(hasattr(item, k) and getattr(item, k) == v for k, v in kwargs.items())

    def find(self, *args, **kwargs) -> list[Any]:
        return [x for x in self if self._matches(x, args, kwargs)]

    def remove_match(self, *args, remove_all: bool = False, **kwargs) -> int:
        matches = self.find(*args, **kwargs)
        if not matches:
            crit = ", ".join([*(map(str, args)), *[f"{k}={v}" for k, v in kwargs.items()]]) or "N/A"
            raise ValueError(ERROR_NOT_FOUND % ("Item", crit))

        removed = 0
        if remove_all:
            to_keep = [x for x in self if x not in matches]
            removed = len(self) - len(to_keep)
            self.clear()
            self.extend(to_keep)
        else:
            super().remove(matches[0])
            removed = 1
        return removed

    def update(self, new_object: Any, *args, **kwargs) -> int:
        replace_all: bool = kwargs.pop(REPLACE_ALL, False)
        matches = self.find(*args, **kwargs)
        if not matches:
            crit = ", ".join([*(map(str, args)), *[f"{k}={v}" for k, v in kwargs.items()]]) or "N/A"
            raise ValueError(ERROR_NOT_FOUND % ("Item", crit))

        if replace_all:
            # Zamijeni svaki podudarni element novim objektom (isti broj ponavljanja)
            to_keep = [x for x in self if x not in matches]
            self.clear()
            self.extend(to_keep)
            self.extend(new_object for _ in matches)
            return len(matches)

        # Zamijeni samo prvi podudarni element
        super().remove(matches[0])
        self.append(new_object)
        return 1


# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #
