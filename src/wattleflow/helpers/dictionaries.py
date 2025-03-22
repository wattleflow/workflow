# Module Name: concrete/dictionaries.py
# Description: This modul contains dictionary helper classes.
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence


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
