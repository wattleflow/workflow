# Module name: logger.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2025 WattleFlow. All rights reserved.
# License: Apache 2 Licence


from __future__ import annotations
from typing import Optional
from logging import Filter, Formatter, getLogger, Handler, Logger, StreamHandler
from threading import RLock
from wattleflow.core import ILogger
from wattleflow.constants import LogFormat


class AsyncHandler(Handler):
    def __init__(self, queue):
        super().__init__()
        self.queue = queue

    def emit(self, record):
        try:
            self.queue.put_nowait(self.format(record))
        except Exception:
            self.handleError(record)


class ContextFilter(Filter):
    def filter(self, record):
        record.filename = getattr(record, "src_filename", record.filename)
        record.lineno = getattr(record, "src_lineno", record.lineno)
        return True


class AuditLogger(ILogger):
    _lock = RLock()
    _instances: set[type] = set()

    def __init__(
        self,
        level: int,
        logger: Optional[Logger] = None,
        handler: Optional[Handler] = None,
        format: str = LogFormat.DEFAULT.value,
        propagate: Optional[bool] = None,
    ):
        ILogger.__init__(self)

        cls = self.__class__
        self._handler = None
        self._level: int = level
        self._logger: Logger = logger or getLogger(self.__class__.__name__)

        with self._lock:
            if cls not in self._instances:
                self._logger.setLevel(self._level)
                self._logger.propagate = bool(propagate)
                handler = self._handler

                if handler is None:
                    handler = StreamHandler()
                    handler.addFilter(ContextFilter())
                    handler.setLevel(self._level)
                    handler.setFormatter(Formatter(format))

                if handler not in self._logger.handlers:
                    self._logger.addHandler(handler)

                self._handler = handler
                self._instances.add(cls)
                self._configure_once()

        # if handler not in self._logger.handlers:
        #     self.subscribe_handler(handler)

    def _configure_once(self) -> None:
        pass

    def _log_msg(self, method, msg: str, *args, **kwargs) -> None:
        def safe_repr(obj: object, maxlen: int = 100) -> str:
            try:
                from pandas import DataFrame

                if isinstance(obj, DataFrame):
                    s = obj.__class__.__name__
                else:
                    s = repr(obj)
            except Exception:
                s = f"<unreprable {obj.__class__.__name__}>"
            return s if len(s) <= maxlen else s[: maxlen - 1] + "…"

        LOG_KW = {"exc_info", "stack_info", "stacklevel", "extra"}
        pass_through = {k: kwargs[k] for k in LOG_KW if k in kwargs}
        data = {k: v for k, v in kwargs.items() if k not in LOG_KW}

        if data:
            parts = []
            for k, v in data.items():
                if v is None or isinstance(v, (bool, int, float, str)):
                    parts.append(f"{k}={v}")
                elif isinstance(v, (list, tuple, set, dict)) and (
                    method == self._logger.info
                ):
                    try:
                        n = len(v)
                    except Exception:
                        n = "?"
                    parts.append(f"{k}=<{type(v).__name__}: {n}>")
                else:
                    parts.append(f"{k}={safe_repr(v)}")
            msg = f"{msg} {parts}"

        method(msg, *args, **pass_through)

    def exception(self, msg: str, *args, **kwargs) -> None:
        kwargs.setdefault("exc_info", True)
        self._log_msg(self._logger.error, msg, *args, **kwargs)

    def critical(self, msg: str, *args, **kwargs) -> None:
        self._log_msg(self._logger.critical, msg, *args, **kwargs)

    def debug(self, msg: str, *args, **kwargs) -> None:
        self._log_msg(self._logger.debug, msg, *args, **kwargs)

    def error(self, msg: str, *args, **kwargs) -> None:
        self._log_msg(self._logger.error, msg, *args, **kwargs)

    def fatal(self, msg: str, *args, **kwargs) -> None:
        self._log_msg(self._logger.fatal, msg, *args, **kwargs)

    def info(self, msg: str, *args, **kwargs) -> None:
        self._log_msg(self._logger.info, msg, *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs) -> None:
        self._log_msg(self._logger.warning, msg, *args, **kwargs)

    def subscribe_handler(self, subscriber: Handler) -> None:
        if not isinstance(subscriber, Handler):
            raise TypeError("subscribe_handler: expected logging.Handler")
        if subscriber not in self._logger.handlers:
            self._logger.addHandler(subscriber)

    def subscribe(self, observer):
        raise NotImplementedError(f"{self.name}.subscribe is not implemented!")
