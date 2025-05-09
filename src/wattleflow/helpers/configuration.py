# Module Name: helpers/configuration.py
# Description: This modul contains Configuration and Preset classes.
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence


import os
import yaml
from typing import Any, final, Union
from wattleflow.core import IWattleflow


@final
class Configuration:
    def __init__(self, config_file: str = None):
        self.config_file = config_file
        self._key_filename = None
        self._data = None
        self._strategy = None

        if not os.path.exists(self.config_file):
            raise FileNotFoundError(self.config_file)

        if os.path.isdir(self.config_file):
            raise FileNotFoundError(
                f"Directory given instead of file: {self.config_file}"
            )

        self.load_settings()

    def load_settings(self):
        try:
            with open(self.config_file, "r") as file:
                self._data = yaml.safe_load(file)
        except FileNotFoundError:
            raise FileNotFoundError(f"Configuration file not found: {self.config_file}")
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML file: {self.config_file}. Error: {e}")

        self._key_filename = self.find("project", "strategy", "ssh_key_filename")
        class_name = self.find("project", "strategy", "class_name")

        if not self._key_filename or not class_name:
            return

        from wattleflow.helpers import LocalPath

        if not LocalPath(self._key_filename).exists():
            raise FileNotFoundError(
                f"Configuration._key_filename not found: {self._key_filename}"
            )

        from wattleflow.helpers import ClassLoader

        self._strategy = ClassLoader(
            class_path=class_name, key_filename=self._key_filename
        ).instance

    def find(self, *keys) -> Any:
        result = self._data
        try:
            for key in keys:
                result = result[key]
            return result
        except (KeyError, TypeError):
            return None

    def get(self, section, key, name=None, default=None) -> Union[dict, str, list]:
        def find_root(branch, name):
            if branch is None:
                return None
            if isinstance(branch, dict):
                return branch.get(name)
            if isinstance(branch, list):
                for item in branch:
                    if isinstance(item, dict) and name in item:
                        return item[name]
                    elif item == name:
                        return item
            elif isinstance(branch, str) and name in branch:
                return branch
            return None

        root = find_root(self._data, section)
        if not root:
            raise ValueError(
                f"Configuration: Section not found. [{section}, {key}, {name}]"
            )

        branch = find_root(root, key)
        if name:
            final_value = find_root(branch, name)
            if final_value is None:
                raise ValueError(
                    f"Configuration: Key not found. [{section}, {key}, {name}]"
                )
            return final_value
        return branch or root

    def decrypt(self, value) -> str:
        if not self._strategy:
            raise RuntimeError("Decryption strategy not initialized.")
        return self._strategy.execute(value)

    def export_preset(self, cls: type) -> dict:
        """Export configuration preset for given class, using lowercased class name as key."""
        key = cls.__name__.lower()
        return self._data.get("presets", {}).get(key, {})


@final
class Preset:
    __slots__ = ()  # Reduce memory footprint and eliminate __dict__ i __weakref__

    def configure(self, allowed: list = None, *args, **kwargs):  # config: dict = None):
        if kwargs is None:
            return

        if isinstance(self, IWattleflow):
            name = self.name.lower()
            self._allowed = allowed if allowed else []
            if name not in self._allowed:
                self._allowed.append(name)

        for preset in self._allowed:
            if preset in kwargs:
                for key, val in kwargs[preset].items():
                    if isinstance(val, (bool, dict, list, int, float, str)):
                        self.push(key, val)
                    else:
                        error = "Restricted type: {}.{}. Allowed: bool, dict, list, int, float, str"
                        raise AttributeError(error.format(type(val).__name__, key,))
