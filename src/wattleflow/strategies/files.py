# Module Name: strategies/files.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence
# Description: This modul contains concrete name filter classes.

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
