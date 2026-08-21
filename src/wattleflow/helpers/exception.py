# Module name: helpers/exception.py
# Author: (wattleflow@outlook.com)
# Copyright: @ 2022-2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

# Root of the framework's exception taxonomy. It sits in the foundation layer
# because helpers raise it and helpers may not import an upper one (DR-WFL-009);
# concrete/exception.py re-exports it, so the taxonomy reads as one unit.


# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #

from __future__ import annotations
import inspect
import linecache
import logging
import sys
import traceback

# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

_logger = logging.getLogger("wattleflow.exception")

# --------------------------------------------------------------------------- #
# region Audit base class                                                     #
# --------------------------------------------------------------------------- #


class AuditException(Exception):
    """Base exception carrying the caller and source location of the failure.

    `error` aliases `reason`; the legacy kwargs level, handler, exc, exc_info,
    internal_funcs and extra_skip are consumed silently, and `exc=` chains
    __cause__ as `raise ... from` would.
    """

    filename: str = ""
    lineno: int = 0
    code_line: str | None = None

    def __init__(self, caller: object, error: str, *args, **kwargs):
        kwargs.pop("level", None)
        kwargs.pop("handler", None)
        kwargs.pop("hanlder", None)

        exc = kwargs.pop("exc", None)
        exc_info = kwargs.pop("exc_info", None)
        kwargs.pop("internal_funcs", None)
        kwargs.pop("extra_skip", None)

        self._extract_location(exc, exc_info)

        if isinstance(exc, BaseException) and self.__cause__ is None:
            self.__cause__ = exc

        self.caller = caller
        self.name = (
            caller.__name__
            if isinstance(caller, type)
            else getattr(caller, "name", type(caller).__name__)
        )
        self.reason: str = error
        self.error: str = error

        Exception.__init__(self, self.reason)

    def _extract_location(
        self,
        exc: BaseException | None,
        exc_info,
    ) -> None:
        try:
            tb = None
            if isinstance(exc, BaseException):
                tb = exc.__traceback__
            elif exc_info is True:
                tb = sys.exc_info()[2]
            elif isinstance(exc_info, tuple) and len(exc_info) == 3:
                tb = exc_info[2]
            else:
                tb = sys.exc_info()[2]

            if tb is not None:
                frames = traceback.extract_tb(tb)
                if frames:
                    last = frames[-1]
                    self.filename = last.filename
                    self.lineno = last.lineno
                    self.code_line = last.line
                    return

            f = inspect.currentframe()
            for _ in range(2):
                if f and f.f_back:
                    f = f.f_back
            if f:
                self.filename = f.f_code.co_filename
                self.lineno = f.f_lineno
                linecache.checkcache(self.filename)
                line = linecache.getline(self.filename, self.lineno)
                self.code_line = line.strip() if line else None
        except Exception as e:
            _logger.debug("AuditException._extract_location failed: %s", e)

    def add_context(self, **ctx) -> "AuditException":
        for k, v in ctx.items():
            try:
                self.add_note(f"{k}={v!r}")
            except AttributeError:
                pass
        return self

    def __repr__(self) -> str:
        return f"{type(self).__name__}(reason={self.reason!r}, at={self.filename}:{self.lineno})"

    def __str__(self) -> str:
        if self.filename:
            return f"{self.reason} (at {self.filename}:{self.lineno})"
        return self.reason

    def __reduce__(self):
        return (type(self)._rebuild, (self.reason,))

    # v0.0.0.97 (NFR-ORG-05): unpickling callable is a member of the class it
    # rebuilds; `cls` carries the concrete subclass, so no type argument is
    # threaded through the reduce tuple.
    @classmethod
    def _rebuild(cls, reason):
        obj = cls.__new__(cls)
        obj.reason = reason
        obj.error = reason
        obj.caller = None
        obj.name = cls.__name__
        obj.filename = ""
        obj.lineno = 0
        obj.code_line = None
        Exception.__init__(obj, reason)
        return obj


# --------------------------------------------------------------------------- #
# endregion Audit base class                                                  #
# --------------------------------------------------------------------------- #


__all__ = ["AuditException"]
