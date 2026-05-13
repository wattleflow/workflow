# Module name: dictionaries.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


"""
Description: This module defines helper classes for working with dictionaries within the
Wattleflow framework. It provides structures that enable attribute-style access
to dictionary keys and support nested dictionary handling.

Usage examples:

    # AttributeDict — wrap an existing dict (e.g. parsed YAML/JSON config) and
    # access its keys as attributes. Nested dicts are wrapped recursively.
    >>> from wattleflow.helpers.dictionaries import AttributeDict
    >>> cfg = AttributeDict({
    ...     "host": "localhost",
    ...     "port": 5601,
    ...     "auth": {"user": "admin", "password": "wattleflow"},
    ... })
    >>> cfg.host
    'localhost'
    >>> cfg.auth.user
    'admin'

    # Typical use: load a YAML config and walk it without dict subscripts.
    >>> import yaml
    >>> raw = yaml.safe_load(open("config.yaml"))
    >>> kb = AttributeDict(raw["kibana"])
    >>> kb.base_url, kb.request_timeout
    ('http://localhost:5601', 30)

    # Dictionary — same idea but built from keyword arguments. Handy for
    # constructing lightweight, immutable-looking config objects inline.
    >>> from wattleflow.helpers.dictionaries import Dictionary
    >>> driver = Dictionary(
    ...     name="driver-kibana",
    ...     base_url="http://localhost:5601",
    ...     retry={"max": 3, "backoff": 0.5},
    ... )
    >>> driver.name
    'driver-kibana'
    >>> driver.retry.backoff
    0.5

    # Useful inside processor/pipeline kwargs where you want dotted access
    # without forcing every caller to unpack the dict:
    >>> opts = Dictionary(read_path="/tmp/in", write_path="/tmp/out")
    >>> opts.read_path
    '/tmp/in'

Notes:
    * Both classes copy values by reference; they do not deep-copy lists or
      arbitrary objects, only nested dicts.
    * Neither class enforces immutability — attributes can still be reassigned
      via ``cfg.host = "..."``. Use them for read-mostly config, not as a
      replacement for ``types.MappingProxyType``.
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
