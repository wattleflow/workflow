# Module name: helpers/__init__.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

# NOTE: this package re-exports only clean-core helpers (stdlib + wattleflow
# core). Helpers that rely on additionally-installed third-party libraries are
# NOT re-exported here — import them explicitly by their sub-module path so a
# missing optional dependency never breaks ``import wattleflow.helpers``:
#     from wattleflow.helpers.config import Config                # yaml/jsonschema
#     from wattleflow.helpers.config_adapter import SecretResolverChain, ...
#     from wattleflow.helpers.config_validator import ConfigValidator, ...
#     from wattleflow.helpers.localmodels import StoredModels, ...  # transformers
from .attribute import Attribute
from .collections import DequeList
from .datetime import CreatedVerdict, CreatedWithin, Now
from .dictionaries import AttributeDict, Dictionary
from .dotenv import DotEnvParser, DotEnvResolver, find_env_file
from .files import FileScanner
from .handlers import TraceHandler
from .macros import TextMacros
from .normaliser import CaseText, Normaliser
from .pathadder import show_paths, override_paths
from .sanitiser import sanitised_uri
from .streams import TextStream, TextFileStream
from .system import (
    decorator,
    ClassLoader,
    FileStorage,
    Proxy,
    Project,
    ShellExecutor,
    TempPathHelper,
)

__all__ = [
    "decorator",
    "sanitised_uri",
    "show_paths",
    "Attribute",
    "AttributeDict",
    "CaseText",
    "Now",
    "CreatedWithin",
    "CreatedVerdict",
    "ClassLoader",
    "DequeList",
    "DotEnvParser",
    "DotEnvResolver",
    "find_env_file",
    "FileScanner",
    "FileStorage",
    "Dictionary",
    "override_paths",
    "Project",
    "Proxy",
    "ShellExecutor",
    "TempPathHelper",
    "TextFileStream",
    "Normaliser",
    "TextMacros",
    "TextStream",
    "TraceHandler",
]
