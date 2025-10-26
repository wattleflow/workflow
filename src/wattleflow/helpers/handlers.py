# Module name: handlers.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2025 WattleFlow. All rights reserved.
# License: Apache 2 Licence


"""
This module implements a trace handler for enhanced logging within the
Wattleflow framework. It extends the standard logging handler to include
detailed stack traces for captured exceptions, improving error visibility
and debugging efficiency.
"""


from __future__ import annotations
import logging
import traceback


class TraceHandler(logging.StreamHandler):
    def emit(self, record):
        if isinstance(record, BaseException):
            error = record
        else:
            error = getattr(record, "error", None)

        if error and isinstance(error, Exception):
            record.msg += "\n" + "".join(
                traceback.format_exception(type(error), error, error.__traceback__)
            )

        super().emit(record)
