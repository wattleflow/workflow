# Module Name: helpers/handlers.py
# Description: This modul contains trace handler class.
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2025 WattleFlow
# License: Apache 2 Licence


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
