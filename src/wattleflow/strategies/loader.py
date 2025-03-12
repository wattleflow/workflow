# Module Name: strategies/loadwer.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence
# Description: This modul contains concrete strategy loader class.

import os
from importlib import import_module
from wattleflow.core import IStrategy


class StrategyClassLoader(IStrategy):
    def execute(self, class_path, root_path):
        class_path, class_name = class_path.rsplit(".", 1)
        module_path = class_path.replace(".", os.path.sep)
        module_path = os.path.join(root_path, "{}.py".format(module_path))

        if not os.path.exists(module_path):
            raise ModuleNotFoundError(module_path)

        module = import_module(class_path)

        if class_name in module.__dict__:
            return module.__dict__[class_name]

        raise ModuleNotFoundError(class_path)
