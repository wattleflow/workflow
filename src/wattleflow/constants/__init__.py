# Module name: constants/__init__.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

# What the framework itself uses; the vocabulary that only specialisations read
# lives in `wattleflow.enums` (wattleflow-processors, DR-WFL-016).

from .audit import LogFormat
from .enums import (
    Classification,
    Event,
    Operation,
)

__all__ = [
    "Classification",
    "Event",
    "LogFormat",
    "Operation",
]
