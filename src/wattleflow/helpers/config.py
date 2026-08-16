# Module name: helpers/config.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #

from __future__ import annotations
import logging
from pathlib import Path
from typing import final, Any
from wattleflow.helpers.exception import AuditException
from wattleflow.core import IWattleflow
from wattleflow.helpers.audit import Audit
from wattleflow.constants.enums import Event
from wattleflow.helpers.yaml import yaml, validate

# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Config                                                               #
# --------------------------------------------------------------------------- #

# Distinguishes "no such key" from a key holding a falsy value.
_MISSING: Any = object()


@final
# Bases are composed rather than inherited from the framework root: helpers/ may
# not import concrete/ (DR-WFL-009).
class Config(Audit, IWattleflow):
    __slots__ = (
        "_config_file",
        "_key_filename",
        "_data",
    )

    def __init__(
        self,
        config_file: str,
        **kwargs,
    ):
        level: str | int = kwargs.get("level", "NOTSET")
        handler: logging.Handler | None = kwargs.get("handler", None)

        super().__init__(level=level, handler=handler)

        if Path(config_file).exists() is False:
            self.error(
                msg=Event.Constructor.value,
                error=f"{self}: invalid or missing `config_path` {config_file}!",
                config_file=config_file,
            )

            raise AuditException(
                caller=self,
                error=f"{self}: invalid or missing `config_path` {config_file}!",
                config_file=config_file,
            )

        self._config_file: str = config_file
        self._key_filename: str | None = None
        self._data = None
        self._load_settings()

    @property
    def config_file(self) -> str:
        return self._config_file

    def find(self, *keys) -> Any:
        result = self._data
        try:
            for key in keys:
                result = result[key]  # type: ignore
            return result
        except (KeyError, IndexError, TypeError) as e:
            self.warning(Event.Find.value, missing=str(e))
            return None

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

        root = find_root(self._data, section)
        if root is _MISSING:
            if default is not None:
                return default
            raise ValueError(f"Config:[root] not found. [{section}, {key}, {name}]")

        branch = find_root(root, key)
        if branch is _MISSING:
            return root

        found = find_root(branch, name)
        if found is _MISSING:
            if name is not None:
                if default is not None:
                    return default
                raise ValueError(f"Config:[name] not found. [{section}, {key}, {name}]")
            return branch

        return found

    def __repr__(self) -> str:
        name = getattr(self, "name", "Config")
        config_file = getattr(self, "config_file", "unknown")
        return f"{name}:{config_file}"

    def _load_settings(self):
        try:
            with open(self.config_file, "r") as file:
                self._data = yaml.safe_load(file)  # type: ignore

            try:
                schema = {
                    "type": "object",
                    "properties": {"debug": {"type": "boolean"}},
                }
                validate(instance=self._data, schema=schema)
            except Exception as e:
                self.error(
                    msg="Config._load_settings",
                    error=f"Config.validate error: {str(e)}",
                )

        except FileNotFoundError as e:
            raise FileNotFoundError(f"Configuration file not found: {self.config_file}") from e
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML file: {self.config_file}. Error: {e}") from e

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


# --------------------------------------------------------------------------- #
# endregion Config                                                            #
# --------------------------------------------------------------------------- #
