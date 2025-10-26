# Module name: collections.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2025 WattleFlow. All rights reserved.
# License: Apache 2 Licence


"""
Description: This module defines collection helper classes for use within the Wattleflow
framework. It provides an extended deque implementation with advanced search,
update, and removal functionality, enabling efficient management of dynamic
collections.
"""


from __future__ import annotations
from collections import deque
from typing import Any, Iterable
from wattleflow.core import IWattleflow
from wattleflow.constants.errors import ERROR_NOT_FOUND


REPLACE_ALL = "all"


class DequeList(IWattleflow, deque):
    """
    Extended deque s simplified search and crud over elements.
    - find(*args, **kwargs)
    - remove_match(...):
    - update(new_object, ...)
    """

    def __init__(self, iterable: Iterable[Any] | None = None):
        super().__init__(iterable or ())

    @staticmethod
    def _matches(item: Any, args: tuple, kwargs: dict) -> bool:
        # Podudaranje po vrijednosti (int/str) ili po atributima
        if isinstance(item, (int, str)):
            return item in args if args else False
        return all(
            hasattr(item, k) and getattr(item, k) == v for k, v in kwargs.items()
        )

    def find(self, *args, **kwargs) -> list[Any]:
        return [x for x in self if self._matches(x, args, kwargs)]

    def remove_match(self, *args, remove_all: bool = False, **kwargs) -> int:
        matches = self.find(*args, **kwargs)
        if not matches:
            crit = (
                ", ".join([*(map(str, args)), *[f"{k}={v}" for k, v in kwargs.items()]])
                or "N/A"  # noqa: E501 W503
            )
            raise ValueError(ERROR_NOT_FOUND.format("Item", crit))

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
            raise ValueError(ERROR_NOT_FOUND.format("Nothing to match."))

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
