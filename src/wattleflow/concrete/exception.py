# Module Name: core/concrete/exceptions.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence
# Description: This modul contains concrete exception classes.

import inspect
from typing import final
from wattleflow.constants.enums import Event
from wattleflow.constants.errors import ERROR_PATH_NOT_FOUND, ERROR_UNEXPECTED_TYPE
from wattleflow.helpers.functions import _NC, _NT
from wattleflow.strategies.audit import StrategyWriteAuditEvent


# --------------------------------------------------------------------------- #
# Exceptions
# --------------------------------------------------------------------------- #


import traceback


class ManagedException(Exception):
    def __init__(self, caller, error, **kwargs):
        self.name = _NC(caller)
        self.caller = caller
        self.error = error
        self.filename = self._get_call_context()

        self.audit_strategy = StrategyWriteAuditEvent()
        if self.audit_strategy:
            self.audit_strategy.generate(
                owner=caller,
                caller=self,
                event=Event.ErrorDetails,
                error=error,
                **kwargs,
            )
        super().__init__(self.error)

    def _get_call_context(self):
        """Retrieves calling filename and line number."""
        try:
            stack = traceback.extract_stack()
            filename, lineno, _, _ = stack[-3]  # Caller frame (-1 is current)
            return f"{filename}:({lineno})"
        except Exception:
            return "Unknown Location"


class AuthenticationException(ManagedException):
    pass


class BlackboardException(ManagedException):
    pass


class ConnectionException(ManagedException):
    pass


class SFTPConnection(ConnectionException):
    pass


class DocumentException(ManagedException):
    pass


class EventObserverException(ManagedException):
    pass


class ClassificationException(ManagedException):
    pass


class ClassInitialisationException(ManagedException):
    pass


class ClassLoaderException(ManagedException):
    pass


@final
class MissingException(ManagedException):
    pass


class PathException(ManagedException):
    def __init__(self, caller, path):
        if not path:
            path = "Unknown Path"
        self.path = path
        super().__init__(caller=caller, error=ERROR_PATH_NOT_FOUND.format(path))


class PiplineException(ManagedException):
    pass


class OrchestratorException(ManagedException):
    error = "Unknown operation error."
    pass


class ProcessorException(ManagedException):
    pass


class PKeyException(ManagedException):
    pass


class PrometheusException(ManagedException):
    pass


class RepositoryException(ManagedException):
    pass


class SaltException(ManagedException):
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
