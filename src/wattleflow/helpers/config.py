# Module Name: helpers/config.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence
# Description: This modul contains config class.

import yaml
from enum import Enum
from typing import Type
from wattleflow.concrete.attribute import ClassLoader
from wattleflow.constants.errors import ERROR_MISSING_ATTRIBUTE
from wattleflow.constants.keys import (
    CONFIG_FILE,
    KEY_CLASS_NAME,
    KEY_STRATEGY,
    KEY_SECTION_PROJECT,
    KEY_SSH_KEY_FILENAME,
)
from wattleflow.helpers.system import Project, CheckPath


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


class Config:
    def __init__(self, project_path:str, level_up:int=2):
        self.file_path = CheckPath("{}/{}".format(
            Project(project_path, level_up).root_path,
            CONFIG_FILE,
        )).file_path
        self.key_filename = None
        self.data = None
        self.decrypt = None
        self.load_settings()
        CheckPath(file_path=self.key_filename, owner=self)

    def load_settings(self):
        with open(self.file_path, "r") as file:
            self.data = yaml.safe_load(file)

        self.key_filename = self.find(
            section=KEY_SECTION_PROJECT, key=KEY_STRATEGY, name=KEY_SSH_KEY_FILENAME
        )

        CheckPath(self.key_filename, self)
        class_name = self.find(
            section=KEY_SECTION_PROJECT, key=KEY_STRATEGY, name=KEY_CLASS_NAME
        )
        # self.decrypt = ClassLoader(
        #     class_path=class_name, key_filename=self.key_filename
        # ).instance

    def get(self, section, key, name=None, default=None):
        self.find(section, key, name=None, default=None)

    def find(self, section, key, name=None, default=None):
        def find_root(branch, name):
            if not branch:
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

        root = find_root(self.data, section)
        if not root:
            return None

        branch = find_root(root, key)
        if not branch:
            return root

        root = find_root(branch, name)
        if not root:
            if name:
                raise AttributeError(ERROR_MISSING_ATTRIBUTE.format(name), name, self)
            return branch

        return root

    def decrypt(self, section, key, name=None, default=None):
        value = self.find(section, key, name, default)
        return self.decrypt.execute(value)
