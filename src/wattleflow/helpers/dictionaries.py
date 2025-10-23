# Module Name: dictionaries.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2025 WattleFlow
# License: Apache 2 Licence


"""
Description: This module defines helper classes for working with dictionaries within the
Wattleflow framework. It provides structures that enable attribute-style access
to dictionary keys and support nested dictionary handling.
"""


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
                value = Dictionary(kwargs=value)
            self.__dict__[key] = value
