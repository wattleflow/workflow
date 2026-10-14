# Module name: constants/fault_tolerance.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

__all__ = [
    "CIRCUIT_REJECTED",
    "CIRCUIT_STATE_CHANGED",
    "RETRY_GAVE_UP",
    "RETRY_SCHEDULED",
]

# --------------------------------------------------------------------------- #
# region Constants                                                            #
# --------------------------------------------------------------------------- #
# Fault tolerance event types.
RETRY_SCHEDULED = "retry.scheduled"
RETRY_GAVE_UP = "retry.gave_up"
CIRCUIT_STATE_CHANGED = "circuit.state_changed"
CIRCUIT_REJECTED = "circuit.rejected"
# --------------------------------------------------------------------------- #
# endregion Constants                                                         #
# --------------------------------------------------------------------------- #
