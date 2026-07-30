# Module name: dictionaries.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


"""Attribute-style access over nested dictionaries.

Values are copied by reference and stay mutable; not a MappingProxyType.
"""

# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #

from __future__ import annotations

# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# region Dictionaries                                                         #
# --------------------------------------------------------------------------- #


class AttributeDict:
    def __init__(self, dictionary):
        for key, value in dictionary.items():
            if isinstance(value, dict):
                value = AttributeDict(value)
            self.__dict__[key] = value


class Dictionary:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            if isinstance(value, dict):
                value = Dictionary(**value)
            self.__dict__[key] = value


# --------------------------------------------------------------------------- #
# endregion Dictionaries                                                      #
# --------------------------------------------------------------------------- #
