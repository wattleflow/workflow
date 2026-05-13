# Module name: helpers/functions.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


"""
Description: This module provides a collection of helper functions for object inspection,
attribute management, and SQL query name generation within the Wattleflow
framework. It includes utilities for retrieving object metadata, listing
attributes, and constructing concise SQL operation identifiers.

Usage examples:

    # --- Name introspection -------------------------------------------------
    # _obj_name → __name__ of classes, functions, modules (None for plain
    # instances).
    >>> from wattleflow.helpers.functions import _obj_name, _cls_name, _typ_name
    >>> class Driver: ...
    >>> _obj_name(Driver)
    'Driver'
    >>> _obj_name(Driver())          # instance has no __name__
    >>>
    >>> # _cls_name → class name of an instance (or of a class itself: 'type').
    >>> _cls_name(Driver())
    'Driver'
    >>> _cls_name(42)
    'int'
    >>>
    >>> # _typ_name → type(...).__name__, always returns a string.
    >>> _typ_name(Driver())
    'Driver'
    >>> _typ_name(None)
    'NoneType'

    # Aliases _ON / _NC / _NT exist for short-form logging:
    >>> from wattleflow.helpers.functions import _ON, _NC, _NT
    >>> _ON(Driver), _NC(Driver()), _NT([1, 2])
    ('Driver', 'Driver', 'list')

    # --- Attribute listing --------------------------------------------------
    # list_all → prints every key/value from __dict__ (incl. private).
    # Useful for ad-hoc debugging of processor/blackboard state:
    >>> class Cfg:
    ...     def __init__(self):
    ...         self.host = "localhost"
    ...         self._secret = "x"
    >>> list_all(Cfg())            # doctest: +SKIP
    host: localhost
    _secret: x

    # list_vars → variable names from vars(o), filtering dunder-style
    # names (start *and* end with '_'):
    >>> sorted(list_vars(Cfg()))
    ['_secret', 'host']

    # list_dir → like list_vars but walks dir(o), so it includes methods
    # and inherited attributes:
    >>> 'host' in list_dir(Cfg())
    True

    # list_properties → prints only "public-ish" entries from __dict__:
    >>> list_properties(Cfg())     # doctest: +SKIP
    host: localhost
    _secret: x

    # --- SQL name generation ------------------------------------------------
    # sql_name → builds a short identifier (op_target) for an SQL string.
    # Handy when naming files, log lines or repository keys derived from
    # an SQL statement.
    >>> from wattleflow.helpers.functions import sql_name
    >>> sql_name("SELECT * FROM original.document_pdf")
    'select_original.document_pdf'
    >>> sql_name("INSERT INTO staging.users (id) VALUES (1)")
    'insert_staging.users'
    >>> sql_name("EXPLAIN ANALYZE SELECT 1")
    'unrecognisable_sql_name'

Notes:
    * `list_all` and `list_properties` are side-effecting helpers — they print
      and return a list of None values from `print()`. Prefer `list_vars` /
      `list_dir` when you need a return value to iterate over.
    * `sql_name` only inspects the head of the statement; comments or CTE
      prefixes (e.g. ``WITH ... SELECT``) will fall through to the
      ``unrecognisable_sql_name`` fallback.
"""


# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #

from __future__ import annotations
import re

# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# region Types                                                                #
# --------------------------------------------------------------------------- #

SPECIAL_TYPES = [
    None,
    "ABCMeta",
    "function",
    "_Generic",
    "None",
    "NoneType",
    "type",
    "<lambda>",
]

# --------------------------------------------------------------------------- #
# endregion Types                                                             #
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# region Global methods                                                       #
# --------------------------------------------------------------------------- #


def _obj_name(o):
    """Return the __name__ attribute of object if present, else None."""
    return getattr(o, "__name__", None)


def _cls_name(o):
    """Return the __class__.__name__ of object if __class__ exists, else None."""
    return getattr(getattr(o, "__class__", None), "__name__", None)


def _typ_name(o):
    """Return the type name of object."""
    return type(o).__name__


def list_all(o):
    """
    Print all attributes (including private/protected) from __dict__ of object.
    """
    return [print(f"{k}: {v}") for k, v in o.__dict__.items()]


def list_vars(o):
    """
    Return a list of variable names from vars(o) excluding
    names that start AND end with an underscore.
    """
    return [n for n in vars(o) if not (n.startswith("_") and n.endswith("_"))]


def list_dir(o):
    """
    Return a list of names from dir(o) excluding
    names that start AND end with an underscore.
    """
    return [n for n in dir(o) if not (n.startswith("_") and n.endswith("_"))]


def list_properties(o):
    """
    Print public/protected properties from __dict__ (skip names starting and ending with '_').
    """
    return [
        print(f"{k}: {v}")
        for k, v in o.__dict__.items()
        if not (k.startswith("_") and k.endswith("_"))
    ]


def sql_name(sql):
    """Generates a concise name for the given SQL query."""
    # Extract the operation (e.g., SELECT, INSERT) and the target table/schema
    mask = r"^(SELECT|INSERT|UPDATE|DELETE)\s+.*?\s+(FROM|INTO|UPDATE|DELETE)?\s+([a-zA-Z0-9_.]+)"
    match = re.search(mask, sql, re.IGNORECASE)
    if match:
        operation = match.group(1).strip().lower()
        target = match.group(3).strip().lower()
        return f"{operation}_{target}"
    else:
        return "unrecognisable_sql_name"


# --------------------------------------------------------------------------- #
# endregion Global methods                                                    #
# --------------------------------------------------------------------------- #


_ON = _obj_name
_NC = _cls_name
_NT = _typ_name
