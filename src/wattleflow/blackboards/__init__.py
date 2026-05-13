# Module name: blackboards/__init__.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


from .large import LargeBlackboard
from .small import SmallBlackboard

__all__ = [
    "SmallBlackboard",
    "LargeBlackboard",
]
