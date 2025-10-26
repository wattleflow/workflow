# Module name: __init__.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2025 WattleFlow. All rights reserved.
# License: Apache 2 Licence


from .logger import AuditLogger, AsyncHandler
from .blackboard import GenericBlackboard
from .connection import (
    ConnectionObserverInterface,
    GenericConnection,
)
from .document import Document, DocumentAdapter, DocumentFacade
from .driver import GenericDriverClass
from .exception import (
    AuditException,
    AttributeException,
    AuthenticationException,
    BlackboardException,
    ConstructorException,
    ConfigurationException,
    ConnectionException,
    DocumentException,
    EventObserverException,
    ClassificationException,
    ClassInitialisationException,
    ClassLoaderException,
    MissingException,
    OrchestratorException,
    PiplineException,
    ProcessorException,
    PKeyException,
    PrometheusException,
    RepositoryException,
    SaltException,
    NotFoundError,
    UnexpectedTypeError,
)
from .manager import ConnectionManager
from .memento import MementoClass, ObservableClass
from .orchestrator import Orchestrator
from .pipeline import GenericPipeline
from .processor import GenericProcessor
from .repository import GenericRepository
from .scheduler import Scheduler
from .strategy import (
    Strategy,
    StrategyGenerate,
    StrategyCreate,
    StrategyRead,
    StrategyWrite,
)

__all__ = [
    "AuditLogger",
    "AsyncHandler",
    "AuditException",
    "AttributeException",
    "AuthenticationException",
    "BlackboardException",
    "ConnectionManager",
    "ClassificationException",
    "ClassInitialisationException",
    "ClassLoaderException",
    "ConnectionObserverInterface",
    "ConfigurationException",
    "ConnectionException",
    "ConstructorException",
    "Document",
    "DocumentAdapter",
    "DocumentException",
    "DocumentFacade",
    "EventObserverException",
    "GenericBlackboard",
    "GenericConnection",
    "GenericDriverClass",
    "GenericPipeline",
    "GenericProcessor",
    "GenericRepository",
    "MementoClass",
    "MissingException",
    "NotFoundError",
    "ObservableClass",
    "Orchestrator",
    "OrchestratorException",
    "PiplineException",
    "ProcessorException",
    "PKeyException",
    "PrometheusException",
    "RepositoryException",
    "SaltException",
    "Scheduler",
    "Strategy",
    "StrategyCreate",
    "StrategyGenerate",
    "StrategyRead",
    "StrategyWrite",
    "UnexpectedTypeError",
]
