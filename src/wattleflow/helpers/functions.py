# Module name: functions.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2025 WattleFlow. All rights reserved.
# License: Apache 2 Licence


"""
Description: This module provides a collection of helper functions for object inspection,
attribute management, and SQL query name generation within the Wattleflow
framework. It includes utilities for retrieving object metadata, listing
attributes, and constructing concise SQL operation identifiers.
"""


from __future__ import annotations
import re

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


_ON = _obj_name
_NC = _cls_name
_NT = _typ_name
