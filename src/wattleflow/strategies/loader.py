# Module Name: loadwer.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2025 WattleFlow
# License: Apache 2 Licence
# Description: This module defines a concrete strategy loader class within the Wattleflow
# framework. It provides functionality for dynamically loading and managing
# strategy implementations.

"""
Description: This module defines a concrete strategy loader class within the Wattleflow
framework. It provides functionality for dynamically loading and managing
strategy implementations.
"""

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
            return getattr(module, class_name)

        raise ModuleNotFoundError(class_path)
