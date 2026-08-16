# Module name: concrete/exception.py
# Author: (wattleflow@outlook.com)
# Copyright: @ 2022-2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #

from __future__ import annotations
import inspect
from wattleflow.constants.errors import ERROR_UNEXPECTED_TYPE

# Taxonomy root lives one layer down (DR-WFL-009); re-exported so it stays a
# member of this module's public API.
from wattleflow.helpers.exception import AuditException

# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
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

        target_name = target.__name__ if isinstance(target, type) else type(target).__name__
        msg = f"No [{var_name}] found in [{target_name}]"
        super().__init__(msg)


class UnexpectedTypeException(TypeError):
    def __init__(self, caller, found, expected_type):
        # Lazy: concrete.helpers imports AttributeException from this module at
        # module level — a top-level import here would be a circular import.
        from wattleflow.concrete.helpers import NameHelper

        try:
            _frame = inspect.currentframe().f_back  # type: ignore
            var_name = next(
                (name for name, value in _frame.f_locals.items() if value is found),  # type: ignore
                "Unknown Variable",
            )
        except Exception:
            var_name = "Unknown Variable"

        error = ERROR_UNEXPECTED_TYPE.format(
            NameHelper.nc(caller),
            var_name,
            NameHelper.nt(found),
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
# region Workflow exceptions classes                                          #
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
# endregion Workflow exceptions classes                                       #
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


__all__ = [
    "AttributeException",
    "AuditException",
    "AuthenticationException",
    "BlackboardException",
    "ClassificationException",
    "ClassInitialisationException",
    "ClassLoaderException",
    "ConfigurationException",
    "ConnectionException",
    "ConstructorException",
    "DocumentException",
    "DriverException",
    "DriverNotFound",
    "EventObserverException",
    "ManagerException",
    "MissingException",
    "NotFoundException",
    "OrchestratorException",
    "PKeyException",
    "PipelineException",
    "ProcessorException",
    "PrometheusException",
    "RepositoryException",
    "SFTPConnectionError",
    "SaltException",
    "StrategyException",
    "UnexpectedTypeException",
]
