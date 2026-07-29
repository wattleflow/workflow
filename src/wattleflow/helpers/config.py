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
from typing import final, Any, Optional, Union
from wattleflow.concrete.exception import AuditException
from wattleflow.concrete.wattleflow import Wattleflow
from wattleflow.constants.enums import Event

# NOTE: Guarded optional dependency (DR-WFL-003) — PyYAML/jsonschema only accelerate
# and extend; `helpers/yaml.py` is a functionally complete stdlib fallback, so this
# module's effective closure stays stdlib and it belongs in the clean core (DR-WFL-002
# §2.1 exception). Verified by the masking test: mask both packages and this must still
# import and parse. Keep the fallback at parity — a silently divergent shim is worse
# than an ImportError.
try:
    import yaml
    from jsonschema import validate
except Exception:
    from wattleflow.helpers.yaml import yaml, validate  # noqa: F401


# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Config                                                               #
# --------------------------------------------------------------------------- #


@final
class Config(Wattleflow):
    __slots__ = (
        "_config_file",
        "_key_filename",
        "_data",
        # "_strategy",
        # "_level",
        # "_handler",
    )

    def __init__(
        self,
        config_file: str,
        **kwargs,
    ):
        level: Union[str, int] = kwargs.get("level", "NOTSET")
        handler: Optional[logging.Handler] = kwargs.get("handler", None)

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
        self._key_filename: Optional[str] = None
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
        except (KeyError, TypeError) as e:
            self.warning(Event.Find.value, missing=str(e))
            return None

    def get(self, section: str, key: str, name=None, default=None) -> Union[dict, str, list]:
        def find_root(branch, name):
            if branch is None:
                return None

            if name is None:
                return branch

            if isinstance(branch, dict):
                if name in branch:
                    return branch[name]
            elif isinstance(branch, list):
                for item in branch:
                    if isinstance(item, dict):
                        if name in item:
                            return item[name]
                    else:
                        if name == item:
                            return item
            elif isinstance(branch, str):
                if name in branch:
                    return branch
            else:
                return None

        root = find_root(self._data, section)
        if not root:
            raise ValueError(f"Config:[root] not found. [{section}, {key}, {name}]")

        branch = find_root(root, key)
        if not branch:
            return root

        root = find_root(branch, name)
        if not root:
            if name:
                raise ValueError(f"Config:[name] not found. [{section}, {key}, {name}]")
            return branch

        return root

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
