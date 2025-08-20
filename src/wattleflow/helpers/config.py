# Module Name: helpers/config.py
# Description: This modul contains config helper classes.
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2025 WattleFlow
# License: Apache 2 Licence

from enum import Enum
from logging import NOTSET, Handler
from typing import final, Any, Optional, Type, Union
from wattleflow.core import IWattleflow
from wattleflow.concrete import AuditLogger
from wattleflow.constants import Event
from wattleflow.constants.keys import (
    KEY_CLASS_NAME,
    KEY_STRATEGY,
    KEY_SECTION_PROJECT,
    KEY_SSH_KEY_FILENAME,
)
from wattleflow.helpers.attribute import MissingAttribute
from wattleflow.helpers.system import ClassLoader

try:
    import yaml
except Exception:
    from wattleflow.helpers.yaml import yaml  # noqa: E401


PERMITED_TYPES = (bool, dict, list, int, float, str, Enum)


class Preset:
    def configure(
        self,
        caller: IWattleflow,
        permitted: Optional[list] = None,
        permitted_types: tuple = PERMITED_TYPES,
        raise_errors: bool = False,
        **kwargs: Any,
    ) -> None:
        def debug(msg: str, **kwargs):
            if hasattr(caller, "warning"):
                caller.debug(msg, **kwargs)  # type: ignore[attr-defined]

        def warning(msg: str, **kwargs):
            if hasattr(caller, "warning"):
                caller.warning(msg, **kwargs)  # type: ignore[attr-defined]

        debug(
            msg=Event.Configuring.value,
            caller=caller,
            permitted=permitted,
            permitted_types=permitted_types,
            raise_errors=raise_errors,
            **kwargs,
        )

        # no input values
        if not kwargs:
            msg = "No configuration values!"
            warning(msg=msg, **kwargs)  # type: ignore[attr-defined]
            return

        # allowed keys
        has_slots = hasattr(self, "__slots__") and bool(getattr(self, "__slots__"))
        if has_slots:
            allowed_keys = set(getattr(self, "__slots__"))
        elif permitted:
            allowed_keys = set(permitted)
        else:
            # fallback:allow only given keys
            allowed_keys = set(kwargs.keys())

        # setup attributes
        unknown_keys = []
        bad_types = []

        for key, val in kwargs.items():
            if key not in allowed_keys:
                unknown_keys.append(key)
                continue

            if not isinstance(val, permitted_types):
                bad_types.append((key, type(val).__name__))
                continue

            if hasattr(self, "push") and callable(getattr(self, "push")):
                getattr(self, "push")(key, val)  # type: ignore[attr-defined]
            else:
                setattr(self, key, val)

        # opctional raise error if something is not working
        if (unknown_keys or bad_types) and raise_errors:
            parts = []
            if unknown_keys:
                parts.append(f"Unknown keys: {', '.join(sorted(unknown_keys))}")

            if bad_types:
                parts.append(
                    "Restricted types: "
                    + ", ".join(f"{k}={t}" for k, t in bad_types)  # noqa: W503
                    + f". Allowed: {[t.__name__ for t in permitted_types]}"  # noqa: W503
                )
            raise ValueError("; ".join(parts))

        # log messages if not raising error
        if unknown_keys and hasattr(caller, "warning"):
            warning(msg=f"Ignored unknown keys: {', '.join(sorted(unknown_keys))}")

        if bad_types and hasattr(caller, "warning"):
            warning(
                msg=(
                    "Ignored keys with restricted types: "
                    + ", ".join(f"{k}({t})" for k, t in bad_types)  # noqa: W503
                )
            )

    def __getattr__(self, name: str) -> Any:
        # Poziva se samo kad atribut ne postoji; vrati None umjesto iznimke.
        return None

    def to_dict(self) -> dict:
        result = {}
        if hasattr(self, "__slots__") and bool(getattr(self, "__slots__")):
            for key in getattr(self, "__slots__"):
                # getattr w defaultom None, avoiding __getattr__ petlju:
                try:
                    val = object.__getattribute__(self, key)
                except AttributeError:
                    val = None
                result[key] = val
        else:
            result.update(getattr(self, "__dict__", {}) or {})
        return result

    @staticmethod
    def convert(caller: object, name: str, cls: Type[Enum], dict_object: dict):
        if name not in dict_object:
            raise MissingAttribute(
                caller=caller, error="", name=name, cls=cls, dict_object=dict_object
            )

        value = dict_object[name]

        for enum_member in cls:
            if enum_member.name == value:
                dict_object[name] = enum_member
                return

        raise ValueError(f"Invalid enum value '{value}' for {cls.__name__}")


@final
class Config:
    def __init__(
        self,
        config_file: str,
        level: int = NOTSET,
        handler: Optional[Handler] = None,
    ):
        from wattleflow.helpers import check_path

        if not check_path(config_file, True):
            print(f"Config: config_path not provided/valid! [{config_file}]")

        self.config_file: str = config_file
        self._key_filename: Optional[str] = None
        self._data = None
        self._strategy: Any = None
        self._level: int = level
        self._handler: Optional[Handler] = handler

        self.load_settings()

    def decrypt(self, value) -> str:
        if not self._strategy:
            raise RuntimeError("Decryption strategy not initialized.")

        return self._strategy.execute(value)

    def find(self, *keys) -> Any:
        result = self._data
        try:
            for key in keys:
                result = result[key]
            return result
        except (KeyError, TypeError):
            return None

    def get(
        self, section: str, key: str, name=None, default=None
    ) -> Union[dict, str, list]:
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
            # print(f"DEBUG: missing value for [root]. [{section}, {key}, {name}]")
            raise ValueError(f"Config:[root] not found. [{section}, {key}, {name}]")

        branch = find_root(root, key)
        if not branch:
            return root

        root = find_root(branch, name)
        if not root:
            if name:
                # print(f"DEBUG: missing value for [name]. [{section}, {key}, {name}]")
                raise ValueError(f"Config:[name] not found. [{section}, {key}, {name}]")
            return branch

        return root

    def load_settings(self):
        try:
            with open(self.config_file, "r") as file:
                self._data = yaml.safe_load(file)
        except FileNotFoundError:
            raise FileNotFoundError(f"Configuration file not found: {self.config_file}")
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML file: {self.config_file}. Error: {e}")

        self._key_filename = self.find(
            KEY_SECTION_PROJECT, KEY_STRATEGY, KEY_SSH_KEY_FILENAME
        )
        class_name = self.find(KEY_SECTION_PROJECT, KEY_STRATEGY, KEY_CLASS_NAME)

        if not self._key_filename or not class_name:
            return

        # lazy loading (to avoid circular import)
        from wattleflow.helpers import LocalPath

        if not LocalPath(self._key_filename).exists():
            return FileNotFoundError(
                f"Config._key_filename not found: {self._key_filename}"
            )

        self._strategy = ClassLoader(
            class_path=class_name,
            level=self._level,
            handler=self._handler,
            key_filename=self._key_filename,
        ).instance
