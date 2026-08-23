# Module name: helpers/config.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #

from __future__ import annotations
import json
from pathlib import Path
from abc import abstractmethod
from typing import final, Any, ClassVar
from .audit import Audit
from wattleflow.core import IConfig
from wattleflow.enums.event import Event
from wattleflow.helpers.exception import AuditException
from wattleflow.helpers.validation import SchemaValidator

# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Types                                                                #
# --------------------------------------------------------------------------- #

__all__ = ["Config", "JSONConfig"]

# Distinguishes "no such key" from a key holding a falsy value.
_MISSING: Any = object()

# --------------------------------------------------------------------------- #
# region Classes                                                              #
# --------------------------------------------------------------------------- #


# v0.0.0.97 (DR-WFL-012, DR-COR-016): the search contract is shared and public —
# clean core carries JSON, the YAML variant lives in wattleflow-processors.
class Config(Audit, IConfig):
    """Format-independent lookup; the serialisation format is the only variant."""

    # Serialisation contract of the subclass: label used in errors, decoding of
    # the file, and the parse failures that mean "this document is not valid".
    FORMAT: ClassVar[str] = ""
    ENCODING: ClassVar[str | None] = None
    ERRORS: ClassVar[tuple[type[Exception], ...]] = ()

    __slots__ = (
        "_config_file",
        "_key_filename",
        "_data",
    )

    def __init__(
        self,
        config_file: str | Path,
        **kwargs,
    ):

        super().__init__(**kwargs)

        path = Path(config_file)
        if path.exists() is False:
            self.error(
                msg=Event.Constructor.name,
                error=f"{self}: invalid or missing `config_path` {config_file}!",
                config_file=config_file,
            )

            raise AuditException(
                caller=self,
                error=f"{self}: invalid or missing `config_path` {config_file}!",
                config_file=config_file,
            )

        self._config_file: Path = path
        self._key_filename: str | None = None
        self._data = None
        self._load_settings()

    @property
    def config_file(self) -> Path:
        return self._config_file

    def find(self, *keys: str, default: Any = None) -> Any:
        result = self._data
        try:
            for key in keys:
                result = result[key]  # type: ignore
            return result
        except (KeyError, IndexError, TypeError) as e:
            self.warning(msg=Event.Find.name, missing=str(e))
            return default

    def get(self, section: str, key: str, name=None, default=None) -> dict | str | list:
        # Absence is signalled by _MISSING, never by falsiness: `[]`, `{}`, `0`,
        # `False` and `""` are values a config may legitimately hold, and testing
        # them with `not` reported them as missing and returned the parent node.
        def find_root(branch, name):
            if branch is None:
                return _MISSING

            if name is None:
                return branch

            if isinstance(branch, dict):
                return branch[name] if name in branch else _MISSING

            if isinstance(branch, list):
                for item in branch:
                    if isinstance(item, dict):
                        if name in item:
                            return item[name]
                    elif name == item:
                        return item
                return _MISSING

            if isinstance(branch, str):
                return branch if name in branch else _MISSING

            return _MISSING

        caller = type(self).__name__
        root = find_root(self._data, section)
        if root is _MISSING:
            if default is not None:
                return default
            raise ValueError(f"{caller}:[root] not found. [{section}, {key}, {name}]")

        branch = find_root(root, key)
        if branch is _MISSING:
            return root

        found = find_root(branch, name)
        if found is _MISSING:
            if name is not None:
                if default is not None:
                    return default
                raise ValueError(f"{caller}:[name] not found. [{section}, {key}, {name}]")
            return branch

        return found

    def __repr__(self) -> str:
        name = getattr(self, "name", type(self).__name__)
        config_file = getattr(self, "config_file", "unknown")
        return f"{name}:{config_file}"

    @abstractmethod
    def _parse(self, text: str) -> Any: ...

    def _load_settings(self):
        caller = type(self).__name__
        try:
            self._data = self._parse(self._config_file.read_text(encoding=self.ENCODING))

            try:
                schema = {
                    "type": "object",
                    "properties": {"debug": {"type": "boolean"}},
                }
                SchemaValidator.validate(instance=self._data, schema=schema)
            except Exception as e:
                self.error(
                    msg=Event.Configure.name,
                    reason=f"{caller}._load_settings",
                    error=f"{caller}.validate error: {str(e)}",
                )

        except FileNotFoundError as e:
            raise FileNotFoundError(f"Configuration file not found: {self.config_file}") from e
        except self.ERRORS as e:
            raise ValueError(f"Invalid {self.FORMAT} file: {self.config_file}. Error: {e}") from e

    @classmethod
    def flatten_config(cls, config: dict, parent_key: str = "", sep: str = "_") -> dict:
        items = {}

        for key, value in config.items():
            new_key = f"{parent_key}{sep}{key}" if parent_key else key

            if isinstance(value, dict):
                items.update(cls.flatten_config(value, new_key, sep=sep))
            else:
                items[new_key] = value

        return items

    @staticmethod
    def find_name(config: list, value: str, key: str = "name") -> Any:
        if isinstance(config, dict):
            return config.get(value, None)

        if not isinstance(config, list):
            return {}

        for item in config:
            if not isinstance(item, dict):
                raise ValueError("Unexpeced item type in a list!")
            found = item.get(key, None)
            if found and found == value:
                return item

        return {}


@final
class JSONConfig(Config):
    # RFC 8259 fixes the encoding; the platform default must not decide it.
    FORMAT = "JSON"
    ENCODING = "utf-8"
    ERRORS = (json.JSONDecodeError, UnicodeDecodeError)

    __slots__ = ()

    def _parse(self, text: str) -> Any:
        return json.loads(text)


# --------------------------------------------------------------------------- #
# endregion Classes                                                           #
# --------------------------------------------------------------------------- #
