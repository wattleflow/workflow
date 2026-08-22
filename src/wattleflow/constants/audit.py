# Module name: audit.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #
from __future__ import annotations
from enum import Enum
# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# region Constants                                                            #
# --------------------------------------------------------------------------- #


# Logging format
class LogFormat(Enum):
    DEFAULT = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
    Detailed = "%(asctime)s - %(levelname)s - %(name)s - %(message)s - %(filename)s:%(lineno)d"
    Custom = (
        "%(asctime)s - %(levelname)s - %(name)s - %(message)s - %(src_filename)s:%(src_lineno)d"
    )
    JSON = '{"time": "%(asctime)s", "name": "%(name)s", "level": "%(levelname)s", "message": "%(message)s"}'


# --------------------------------------------------------------------------- #
# endregion Constants                                                         #
# --------------------------------------------------------------------------- #
