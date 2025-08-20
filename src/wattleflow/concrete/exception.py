# Module Name: concrete/exceptions.py
# Description: This modul contains concrete exception classes.
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2025 WattleFlow
# License: Apache 2 Licence

import inspect
import traceback
from logging import DEBUG
from typing import final
from wattleflow.core import IWattleflow
from wattleflow.concrete import AuditLogger
from wattleflow.constants import Event
from wattleflow.constants.errors import ERROR_PATH_NOT_FOUND, ERROR_UNEXPECTED_TYPE
from wattleflow.helpers.functions import _NC, _NT


# --------------------------------------------------------------------------- #
# Exceptions
# --------------------------------------------------------------------------- #


class AuditException(Exception, AuditLogger):
    def __init__(self, caller: IWattleflow, error: str, *args, **kwargs):
        self.debug(
            msg=Event.Constructor.value, caller=caller, error=error, *args, **kwargs
        )
        AuditLogger.__init__(self, level=DEBUG)
        self.caller: IWattleflow = caller
        self.name: str = caller.name
        self.reason: str = error
        self.error(msg=self.reason, caller=caller, **kwargs)
        self.filename = self._get_call_context()
        super().__init__(self.reason)

    def _get_call_context(self):
        """Retrieves calling filename and line number."""
        try:
            stack = traceback.extract_stack()
            filename, lineno, _, _ = stack[-3]  # Caller frame (-1 is current)
            return f"{filename}:({lineno})"
        except Exception:
            return "Unknown Location"


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


@final
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
