# Module Name: concrete/collections.py
# Description: This modul contains concrete collection classes.
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence

from collections import deque
from wattleflow.core import IWattleflow
from wattleflow.constants.errors import ERROR_NOT_FOUND


REPLACE_ALL = "all"


class DequeList(IWattleflow, deque):
    def __init__(self):
        super().__init__()

    def find(self, *args, **kwargs):
        results = []
        for item in self:
            if isinstance(item, (int, str)):
                if item in args:
                    results.append(item)
            else:
                match = True
                for key, value in kwargs.items():
                    if not (hasattr(item, key) and getattr(item, key) == value):
                        match = False
                        break
                if match:
                    results.append(item)
        return results

    def remove(self, *args, **kwargs):
        item = self.find(*args, **kwargs)
        if len(item) == 0:
            value = ", ".join(f"{key}={value}" for key, value in kwargs.items())
            raise ValueError(ERROR_NOT_FOUND.format("Item", value))
        else:
            super().remove(item)

    def update(self, new_object, *args, **kwargs):
        replace_all = kwargs.pop(REPLACE_ALL, False)
        results = self.find(*args, **kwargs)
        if len(results) == 0:
            raise ValueError(ERROR_NOT_FOUND.format("Nothing to match."))

        for item in results:
            super().remove(item)
            if replace_all:
                self.append(new_object)

        if not replace_all:
            self.append(new_object)
