# Module Name: concrete/exceptions.py
# Description: This modul contains concrete exception classes.
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2025 WattleFlow
# License: Apache 2 Licence

import inspect
import logging
import traceback
from wattleflow.core import IWattleflow
from wattleflow.concrete import AuditLogger
from wattleflow.constants import Event
from wattleflow.constants.errors import ERROR_PATH_NOT_FOUND, ERROR_UNEXPECTED_TYPE
from wattleflow.helpers.functions import _NC, _NT


# --------------------------------------------------------------------------- #
# Exceptions
# --------------------------------------------------------------------------- #


class AuditException(Exception, AuditLogger):
    """
    AuditException is a custom exception class inheriting from both Exception and AuditLogger.
    It reports and logs application errors, providing context about the caller and cause.

    Key points:
    - Multiple inheritance: combines Exception (base error class)
      and AuditLogger (for event logging).
    - __init__(caller, error, *args, level=logging.DEBUG):
    - Initializes AuditLogger.
    - Logs both creation and error details.
    - Stores caller object, name, reason, and file location.
    - Calls the base Exception with the error reason.
    - _get_call_context():
    - Returns filename and line number where the exception occurred.
    - Falls back to "Unknown Location" if stack trace is unavailable.
    """

    filename: str = ""
    lineno: str = ""

    def __init__(
        self, caller: IWattleflow, error: str, show_path=False, *args, **kwargs
    ):
        level = kwargs.get("level", logging.NOTSET)
        handler = kwargs.get("hanlder", None)

        AuditLogger.__init__(self, level=level, handler=handler, logger=None)

        self.debug(
            msg=Event.Constructor.value,
            caller=caller,
            error=error,
            *args,
            **kwargs,
        )

        self._get_call_context()

        self.caller: IWattleflow = caller
        self.name: str = caller.name
        self.reason: str = error

        if show_path:
            self.reason += f" See {self.filename}:{self.lineno}"

        super().__init__(self.reason)

    def _get_call_context(self):
        try:
            stack = traceback.extract_stack()

            self.filename, self.lineno, _, _ = (
                stack[-4] if len(stack) > 2 else stack[-3]
            )  # Caller frame (-1 is current)
        except Exception as e:
            self.debug(msg=Event.ErrorDetails, error=str(e))

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


class PathException(AuditException):
    def __init__(self, caller, path):
        if not path:
            path = "Unknown Path"
        self.path = path
        super().__init__(caller=caller, error=ERROR_PATH_NOT_FOUND.format(path))


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
            _frame = inspect.currentframe().f_back  # Caller frame
            var_name = next(
                (name for name, value in _frame.f_locals.items() if value is item),
                "Unknown Variable",
            )
        except Exception:
            var_name = "Unknown Variable"

        msg = f"No [{var_name}] found in [{target.__class__.__name__}]"
        super().__init__(msg)


class UnexpectedTypeError(TypeError):
    def __init__(self, caller, found, expected_type):
        try:
            _frame = inspect.currentframe().f_back
            var_name = next(
                (name for name, value in _frame.f_locals.items() if value is found),
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
