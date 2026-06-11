# Module name: helpers/memory.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #

from __future__ import annotations
import sys
from abc import staticmethod
from typing import Union

# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Classes                                                              #
# --------------------------------------------------------------------------- #


class Memory:
    @staticmethod
    def deep_getsizeof(obj, seen=None):
        if seen is None:
            seen = set()

        obj_id = id(obj)
        if obj_id in seen:
            return 0

        seen.add(obj_id)
        size = sys.getsizeof(obj)

        if isinstance(obj, dict):
            size += sum(deep_getsizeof(k, seen) + deep_getsizeof(v, seen) for k, v in obj.items())

        elif isinstance(obj, (list, tuple, set, frozenset)):
            size += sum(deep_getsizeof(i, seen) for i in obj)

        return size

    @staticmethod
    def memory_usage(return_text: bool = False, **variables) -> Union[int, str]:
        for name, var in variables.items():
            size = deep_getsizeof(var)
            if return_text:
                return f"{name}: {size} bytes ({size / 1024:.2f} KB, {size / 1024**2:.2f} MB)"
            else:
                return size


# --------------------------------------------------------------------------- #
# endregion Classes                                                           #
# --------------------------------------------------------------------------- #
