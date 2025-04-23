# Module Name: helpers/config.py
# Description: This modul contains config class.
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence


import yaml
from typing import Any, final, Union
from enum import Enum
from typing import Type
from wattleflow.concrete import ClassLoader
from wattleflow.constants.errors import ERROR_MISSING_ATTRIBUTE
from wattleflow.constants.keys import (
    KEY_CLASS_NAME,
    KEY_STRATEGY,
    KEY_SECTION_PROJECT,
    KEY_SSH_KEY_FILENAME,
)


@final
class Mapper:
    @staticmethod
    def convert(name: str, cls: Type[Enum], dict_object: dict):
        if name not in dict_object:
            raise ValueError(ERROR_MISSING_ATTRIBUTE.format(name))

        value = dict_object[name]

        for enum_member in cls:
            if enum_member.name == value:
                dict_object[name] = enum_member
                return

        raise ValueError(f"Invalid enum value '{value}' for {cls.__name__}")


@final
class Config:
    def __init__(self, config_file: str):
        self.config_file = config_file
        self._key_filename = None
        self._data = None
        self._strategy = None
        self.load_settings()

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

        if not self._key_filename or not self.class_name:
            return

        # lazy loading (to avoid circular import)
        from wattleflow.helpers import LocalPath

        if not LocalPath(self._key_filename).exists():
            return FileNotFoundError(
                f"Config._key_filename not found: {self._key_filename}"
            )

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

    def decrypt(self, value) -> str:
        if not self._strategy:
            raise RuntimeError("Decryption strategy not initialized.")

        return self._strategy.execute(value)
