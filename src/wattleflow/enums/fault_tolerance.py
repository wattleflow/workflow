# Module name: enums/fault_tolerance.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #
from __future__ import annotations

__all__ = ["BreakerAction", "BreakerState"]

from enum import Enum

# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Enums                                                                #
# --------------------------------------------------------------------------- #


class BreakerState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class BreakerAction(str, Enum):
    CALL = "call"
    SUCCESS = "success"
    FAILURE = "failure"


# --------------------------------------------------------------------------- #
# endregion Enums                                                             #
# --------------------------------------------------------------------------- #
