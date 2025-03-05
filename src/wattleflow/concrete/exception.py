# Module Name: core/concrete/exceptions.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence
# Description: This modul contains concrete exception classes.

import inspect
from typing import final
from sys import _getframe as frame

from wattleflow.constants.enums import Event
from wattleflow.constants.errors import ERROR_PATH_NOT_FOUND, ERROR_UNEXPECTED_TYPE
from wattleflow.helpers.functions import _NC, _NT
from wattleflow.strategies.audit import StrategyWriteAuditEvent


# --------------------------------------------------------------------------- #
# Exceptions
# --------------------------------------------------------------------------- #


class ManagedException(Exception):
    def __init__(self, caller, error, **kwargs):
        self.name = _NC(caller)
        self.caller = caller
        self.error = error
        self.frame = frame
        self.filename = (
            f"{frame(2).f_code.co_filename}:({frame(2).f_code.co_firstlineno})"
        )
        self.audit_strategy = StrategyWriteAuditEvent()
        self.audit_strategy.generate(
            owner=caller,
            caller=self,
            event=Event.ErrorDetails,
            error=error,
            **kwargs,
        )
        super().__init__(self.error)


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
        self.path = path
        super().__init__(caller=caller, error=ERROR_PATH_NOT_FOUND.format(path))


class PiplineException(ManagedException):
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
    def __init__(self, item, target):  # TODO: make a function
        frame = inspect.currentframe().f_back  # Okvir pozivatelja
        local_vars = frame.f_locals  # Lokalne varijable unutar metode koja je pozvala
        var_name = None
        for name, value in local_vars.items():
            if value is item:
                var_name = name
                break
        msg = f"No [{var_name}] found in [{target.__class__.__name__}]"
        super().__init__(msg)


class UnexpectedTypeError(TypeError):
    def __init__(self, caller, found, expected_type):
        frame = inspect.currentframe().f_back  # Okvir pozivatelja
        local_vars = frame.f_locals  # Lokalne varijable unutar metode koja je pozvala
        var_name = None
        for name, value in local_vars.items():
            if value is found:
                var_name = name
                break

        error = ERROR_UNEXPECTED_TYPE.format(
            _NC(caller),
            var_name,
            _NT(found),
            expected_type.__name__,
        )
        super().__init__(error)
