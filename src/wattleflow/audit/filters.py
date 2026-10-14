# Module name: audit/filters.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #
from __future__ import annotations

__all__ = ["ContextFilter"]

from logging import Filter
# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #


class ContextFilter(Filter):
    def filter(self, record):
        record.filename = getattr(record, "src_filename", record.filename)
        record.lineno = getattr(record, "src_lineno", record.lineno)
        return True

