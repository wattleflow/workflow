# Module name: files.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2025 WattleFlow. All rights reserved.
# License: Apache 2 Licence


from __future__ import annotations
import re
from fnmatch import fnmatch
from wattleflow.core import IStrategy


class StrategyFilename(IStrategy):
    def execute(self, value) -> str:
        filtered = re.sub(r"(^[a-zA-Z0-9]+)", "", value)
        filename = filtered.lower()
        return filename


class StrategyFilterFiles(IStrategy):
    def __init__(self, pattern):
        self.pattern = pattern

    def execute(self, filename):
        return fnmatch(filename, self.pattern)
