# Module Name: helpers/config.py
# Description: This modul contains config helper classes.
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2025 WattleFlow
# License: Apache 2 Licence

from logging import NOTSET, Handler
from typing import final, Any, Optional, Union
from wattleflow.constants.keys import (
    KEY_CLASS_NAME,
    KEY_STRATEGY,
    KEY_SECTION_PROJECT,
    KEY_SSH_KEY_FILENAME,
)
from wattleflow.helpers.system import ClassLoader

try:
    import yaml
except Exception:
    from wattleflow.helpers.yaml import yaml  # noqa: E401


@final
class Config:
    def __init__(
        self,
        config_file: str,
        level: int = NOTSET,
        handler: Optional[Handler] = None,
    ):
        from wattleflow.helpers.system import check_path

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
                result = result[key]  # type: ignore
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
                self._data = yaml.safe_load(file)  # type: ignore
        except FileNotFoundError:
            raise FileNotFoundError(f"Configuration file not found: {self.config_file}")
        except yaml.YAMLError as e:  # type: ignore
            raise ValueError(f"Invalid YAML file: {self.config_file}. Error: {e}")

        self._key_filename = self.find(
            KEY_SECTION_PROJECT,
            KEY_STRATEGY,
            KEY_SSH_KEY_FILENAME,
        )

        class_name = self.find(
            KEY_SECTION_PROJECT,
            KEY_STRATEGY,
            KEY_CLASS_NAME,
        )

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
