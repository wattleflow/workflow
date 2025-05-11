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
