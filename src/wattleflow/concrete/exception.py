# Module name: concrete/exceptions.py
# Author: (wattleflow@outlook.com)
# Copyright: @ 2022-2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #

from __future__ import annotations
import inspect
import linecache
import logging
import sys
import traceback
from typing import Optional
from wattleflow.constants.errors import ERROR_UNEXPECTED_TYPE

# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

_logger = logging.getLogger("wattleflow.exception")

# --------------------------------------------------------------------------- #
# region hide
# --------------------------------------------------------------------------- #
# class MyError(Exception):
#     def __init__(self, msg: str, **context):
#         super().__init__(msg)
#         self.context = context

#     def __str__(self):
#         if self.context:
#             ctx = ", ".join(f"{k}={v!r}" for k, v in self.context.items())
#             return f"{self.args[0]} [{ctx}]"
#         return self.args[0]

# def operation():
#     try:
#         risky_call()
#     except (IOError, ValueError) as e:
#         raise MyError(
#             "operation failed",
#             stage="parsing",
#             input_file=path,
#         ) from e
# --------------------------------------------------------------------------- #
# endregion hide
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Audit base class                                                     #
# --------------------------------------------------------------------------- #


class AuditException(Exception):
    """Base exception with rich location context.

    Attributes:
        reason:     original error message (alias: error)
        error:      same as reason, kept for legacy callers
        filename:   source file where the error originated
        lineno:     source line number
        code_line:  the source line text (stripped)
        caller:     object that raised the exception
        name:       caller's name attribute, falling back to class name

    Backward-compat kwargs (silently consumed):
        level, handler, exc, exc_info, internal_funcs, extra_skip

    Idiomatic use - propagate the original cause via `from`:

        try:
            risky()
        except ValueError as e:
            raise DriverException(self, "driver failed") from e

    Legacy `exc=e` kwarg also auto-chains __cause__ for backward compat.
    """

    filename: str = ""
    lineno: int = 0
    code_line: Optional[str] = None

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
        exc: Optional[BaseException],
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
        return (_rebuild_audit_exception, (type(self), self.reason))


def _rebuild_audit_exception(cls, reason):
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

# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Validation                                                           #
# --------------------------------------------------------------------------- #


class AttributeException(AuditException):
    pass


class MissingException(AuditException):
    pass


class AuthenticationException(AuditException):
    pass


class EventObserverException(AuditException):
    pass


class ClassificationException(AuditException):
    pass


class PKeyException(AuditException):
    pass


class SaltException(AuditException):
    pass


class NotFoundException(AttributeError):
    def __init__(self, item, target):
        try:
            _frame = inspect.currentframe().f_back  # type: ignore  <== caller frame
            var_name = next(
                (name for name, value in _frame.f_locals.items() if value is item),  # type: ignore
                "Unknown Variable",
            )
        except Exception:
            var_name = "Unknown Variable"

        target_name = (
            target.__name__ if isinstance(target, type) else type(target).__name__
        )
        msg = f"No [{var_name}] found in [{target_name}]"
        super().__init__(msg)


class UnexpectedTypeException(TypeError):
    def __init__(self, caller, found, expected_type):
        # Deferred import - wattleflow.helpers triggers helpers/__init__.py
        # which loads helpers.attribute, which imports AttributeException from
        # this module. Importing at module level creates a circular import.
        from wattleflow.helpers.functions import _NC, _NT

        try:
            _frame = inspect.currentframe().f_back  # type: ignore
            var_name = next(
                (name for name, value in _frame.f_locals.items() if value is found),  # type: ignore
                "Unknown Variable",
            )
        except Exception:
            var_name = "Unknown Variable"

        error = ERROR_UNEXPECTED_TYPE.format(
            _NC(caller) if callable(_NC) else str(caller),
            var_name,
            _NT(found) if callable(_NT) else type(found).__name__,
            expected_type.__name__,
        )
        super().__init__(error)


# --------------------------------------------------------------------------- #
# endregion Validation                                                        #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Class handling exceptions                                            #
# --------------------------------------------------------------------------- #


class ConstructorException(AuditException):
    pass


class ClassInitialisationException(AuditException):
    pass


class ClassLoaderException(AuditException):
    pass


# --------------------------------------------------------------------------- #
# endregion Class handling exceptions                                         #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Workflow classes exceptions                                          #
# --------------------------------------------------------------------------- #


class BlackboardException(AuditException):
    pass


class ConfigurationException(AuditException):
    pass


class DocumentException(AuditException):
    pass


class DriverException(AuditException):
    pass


class DriverNotFound(AuditException):
    pass


class ManagerException(AuditException):
    pass


class OrchestratorException(AuditException):
    pass


class PipelineException(AuditException):
    pass


class ProcessorException(AuditException):
    pass


class RepositoryException(AuditException):
    pass


class StrategyException(AuditException):
    pass


# --------------------------------------------------------------------------- #
# endregion Workflow classes exceptions                                       #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Connection exceptions                                                #
# --------------------------------------------------------------------------- #


class ConnectionException(AuditException):
    pass


class SFTPConnectionError(ConnectionException):
    pass


class PrometheusException(AuditException):
    pass


# --------------------------------------------------------------------------- #
# endregion Connection exceptions                                             #
# --------------------------------------------------------------------------- #
