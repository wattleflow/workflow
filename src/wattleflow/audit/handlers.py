# Module name: audit/handlers.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #
from __future__ import annotations

__all__ = ["TraceHandler", "AsyncHandler"]

import logging
import traceback
from logging import Handler
# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #


class AsyncHandler(Handler):
    def __init__(self, queue):
        super().__init__()
        self.queue = queue

    def emit(self, record):
        try:
            self.queue.put_nowait(self.format(record))
        except Exception:
            self.handleError(record)


class TraceHandler(logging.StreamHandler):
    def emit(self, record):
        error = getattr(record, "error", None)

        if error and isinstance(error, Exception):
            record.msg += "\n" + "".join(
                traceback.format_exception(type(error), error, error.__traceback__)
            )

        super().emit(record)
