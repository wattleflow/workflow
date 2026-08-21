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
from typing import Any, ClassVar

# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

__all__ = ["ObjectName", "SqlName"]


# --------------------------------------------------------------------------- #
# region Classes                                                              #
# --------------------------------------------------------------------------- #


# v0.0.0.97 (NFR-ORG-05): the naming primitives and the type list they screen
# against belong to the class, not to the module namespace.
# NOTE: concrete/helpers.py carries `NameHelper`, a domain-local copy of the
# same trio; the duplication is deliberate — concrete/ must not import back
# into helpers/ (ORG-01 cycle).
class ObjectName:
    """Object-name primitives and attribute listings."""

    SPECIAL: ClassVar[list[Any]] = [
        None,
        "ABCMeta",
        "function",
        "_Generic",
        "None",
        "NoneType",
        "type",
        "<lambda>",
    ]

    @staticmethod
    def obj_name(o):
        """__name__ of a class/function/module, else None."""
        return getattr(o, "__name__", None)

    @staticmethod
    def cls_name(o):
        """__class__.__name__ if present, else None."""
        return getattr(getattr(o, "__class__", None), "__name__", None)

    @staticmethod
    def typ_name(o) -> str:
        """type(o).__name__ — always a string."""
        return type(o).__name__

    @classmethod
    def name(cls, o):
        return cls.obj_name(o)

    @classmethod
    def nc(cls, o):
        return cls.cls_name(o)

    @classmethod
    def nt(cls, o) -> str:
        return cls.typ_name(o)

    @staticmethod
    def list_all(o):
        """Print every __dict__ entry; returns a list of None (print side effect)."""
        return [print(f"{k}: {v}") for k, v in o.__dict__.items()]

    @staticmethod
    def list_vars(o):
        return [n for n in vars(o) if not (n.startswith("_") and n.endswith("_"))]

    @staticmethod
    def list_dir(o):
        return [n for n in dir(o) if not (n.startswith("_") and n.endswith("_"))]

    @staticmethod
    def list_properties(o):
        """Print non-dunder __dict__ entries; returns a list of None (print side effect)."""
        return [
            print(f"{k}: {v}")
            for k, v in o.__dict__.items()
            if not (k.startswith("_") and k.endswith("_"))
        ]


class SqlName:
    """Short identifier derived from the head of an SQL statement."""

    STATEMENT: ClassVar[re.Pattern] = re.compile(
        r"^(SELECT|INSERT|UPDATE|DELETE)\s+.*?\s+(FROM|INTO|UPDATE|DELETE)?\s+([a-zA-Z0-9_.]+)",
        re.IGNORECASE,
    )
    UNRECOGNISED: ClassVar[str] = "unrecognisable_sql_name"

    @classmethod
    def of(cls, sql: str) -> str:
        """Short `operation_target` identifier; only the head of the statement is read."""
        match = cls.STATEMENT.search(sql)
        if not match:
            return cls.UNRECOGNISED
        operation = match.group(1).strip().lower()
        target = match.group(3).strip().lower()
        return f"{operation}_{target}"


# --------------------------------------------------------------------------- #
# endregion Classes                                                           #
# --------------------------------------------------------------------------- #
