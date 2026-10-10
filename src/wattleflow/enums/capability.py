# Module name: enums/capability.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #
from __future__ import annotations

__all__ = ["DriverCapability"]

from enum import Enum

# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Enums                                                                #
# --------------------------------------------------------------------------- #


class DriverCapability(str, Enum):
    """What a driver may declare it can do (`DriverMetadata.capabilities`).

    A new capability is a documented change to this vocabulary (D-12), not a literal at the point
    of use (NFRQ-ORG-12).
    """

    READ = "read"
    WRITE = "write"
    SEARCH = "search"
    FIND = "find"
    STREAM = "stream"
    COMPLETE = "complete"
    DOWNLOAD = "download"
    UPDATE = "update"
    VALIDATE = "validate"
    QUERY = "query"
    QUERY_RANGE = "query_range"
    PUSH = "push"
    ANNOTATION_CREATE = "annotation:create"
    ANNOTATION_UPDATE = "annotation:update"
    ANNOTATION_DELETE = "annotation:delete"


# --------------------------------------------------------------------------- #
# endregion Enums                                                             #
# --------------------------------------------------------------------------- #
