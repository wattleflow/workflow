# Module name: helpers/functions.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


"""Object introspection helpers and SQL statement naming."""


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
    return getattr(o, "__name__", None)


def _cls_name(o):
    return getattr(getattr(o, "__class__", None), "__name__", None)


def _typ_name(o):
    return type(o).__name__


def list_all(o):
    """Print every __dict__ entry; returns a list of None (print side effect)."""
    return [print(f"{k}: {v}") for k, v in o.__dict__.items()]


def list_vars(o):
    return [n for n in vars(o) if not (n.startswith("_") and n.endswith("_"))]


def list_dir(o):
    return [n for n in dir(o) if not (n.startswith("_") and n.endswith("_"))]


def list_properties(o):
    """Print non-dunder __dict__ entries; returns a list of None (print side effect)."""
    return [
        print(f"{k}: {v}")
        for k, v in o.__dict__.items()
        if not (k.startswith("_") and k.endswith("_"))
    ]


def sql_name(sql):
    """Short `operation_target` identifier; only the head of the statement is read."""
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
