# Module name: exceptions.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2025 WattleFlow. All rights reserved.
# License: Apache 2 Licence


import inspect
import linecache
import logging
import traceback
import sys
from typing import Iterable, Optional
from wattleflow.concrete import AuditLogger
from wattleflow.constants import Event
from wattleflow.constants.errors import ERROR_UNEXPECTED_TYPE
from wattleflow.helpers.functions import _NC, _NT


# --------------------------------------------------------------------------- #
# Exceptions
# --------------------------------------------------------------------------- #


class AuditException(AuditLogger, Exception):
    filename: str = ""
    lineno: str = ""

    def __init__(self, caller: object, error: str, *args, **kwargs):
        level = kwargs.pop("level", logging.NOTSET)
        handler = kwargs.pop("hanlder", None)

        AuditLogger.__init__(self, level=level, handler=handler, logger=None)

        self._get_call_context(**kwargs)

        self.debug(
            msg=Event.Constructor.value,
            caller=caller,
            error=error,
            *args,
            **kwargs,
        )

        self.caller = caller
        self.name = getattr(caller, "name", caller.__class__.__name__)
        self.reason: str = error

        self.reason += f" See {self.filename}:{self.lineno}"

        Exception.__init__(self, self.reason)

    def _get_call_context(self, **kwargs) -> None:
        try:
            tb = None
            exc = kwargs.get("exc")
            if isinstance(exc, BaseException):
                tb = exc.__traceback__
            else:
                ei = kwargs.get("exc_info")
                if ei is True:
                    tb = sys.exc_info()[2]
                elif isinstance(ei, tuple) and len(ei) == 3:
                    tb = ei[2]

            filename = None
            lineno: Optional[int] = None

            if tb is not None:
                while tb.tb_next:
                    tb = tb.tb_next
                f = tb.tb_frame
                filename = f.f_code.co_filename
                lineno = tb.tb_lineno

            else:
                internal_funcs: Iterable[str] = kwargs.get(
                    "internal_funcs",
                    {
                        "_get_call_context",
                        "__init__",
                        "__getattr__",
                        "__getattribute__",
                        "__repr__",
                    },
                )
                extra_skip = int(kwargs.get("extra_skip", 0))

                f = inspect.currentframe()
                if f:
                    f = f.f_back
                if f:
                    f = f.f_back

                while f and f.f_back and f.f_code.co_name in internal_funcs:
                    f = f.f_back

                for _ in range(extra_skip):
                    if f and f.f_back:
                        f = f.f_back

                if f:
                    info = inspect.getframeinfo(f)
                    filename, lineno = info.filename, info.lineno

            self.filename = filename or "Unknown Location"
            self.lineno = lineno or 0  # type: ignore

            linecache.checkcache(self.filename)
            line = linecache.getline(self.filename, self.lineno)  # type: ignore
            self.code_line = line.strip() if line else None

        except Exception as e:
            self.debug(msg=Event.ErrorDetails.value, error=str(e))

    def _get_call_context2(self):
        try:
            stack = traceback.extract_stack()
            self.filename, self.lineno, _, _ = (
                stack[-4] if len(stack) > 2 else stack[-3]
            )
        except Exception as e:
            self.debug(msg=Event.ErrorDetails.value, error=str(e))

    def __repr__(self) -> str:
        return f"error={self.error} in filename={self.filename}:{self.lineno}"


class AttributeException(AuditException, AuditLogger):
    pass


class AuthenticationException(AuditException):
    pass


class BlackboardException(AuditException):
    pass


class ConstructorException(AuditException):
    pass


class ConfigurationException(AuditException):
    pass


class ConnectionException(AuditException):
    pass


class SFTPConnectionError(ConnectionException):
    pass


class DocumentException(AuditException):
    pass


class EventObserverException(AuditException):
    pass


class ClassificationException(AuditException):
    pass


class ClassInitialisationException(AuditException):
    pass


class ClassLoaderException(AuditException):
    pass


class MissingException(AuditException):
    pass


class OrchestratorException(AuditException):
    pass


class PiplineException(AuditException):
    pass


class ProcessorException(AuditException):
    pass


class PKeyException(AuditException):
    pass


class PrometheusException(AuditException):
    pass


class RepositoryException(AuditException):
    pass


class SaltException(AuditException):
    pass


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #


class NotFoundError(AttributeError):
    def __init__(self, item, target):
        try:
            _frame = inspect.currentframe().f_back  # type: ignore  <== caller frame
            var_name = next(
                (name for name, value in _frame.f_locals.items() if value is item),  # type: ignore
                "Unknown Variable",
            )
        except Exception:
            var_name = "Unknown Variable"

        msg = f"No [{var_name}] found in [{target.__class__.__name__}]"
        super().__init__(msg)


class UnexpectedTypeError(TypeError):
    def __init__(self, caller, found, expected_type):
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
