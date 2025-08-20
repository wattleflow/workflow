# Module Name: concrete/logger.py
# Description: This modul contains audit logger classes.
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2025 WattleFlow
# License: Apache 2 Licence

# ---------------------------------------------------------------------------------------
# Logging module in Python utilises the design patterns 'Observer' and 'Observable'
# ---------------------------------------------------------------------------------------
# Observable (Logger)
#    Logger is an object that generates logging messages.
#    It's 'Observable', as it notifies all its handlers ("listeners")
#    with every new message created by the logger.
# ---------------------------------------------------------------------------------------
# Observer (Handler):
#    Handlers, such as StreamHandler, FileHandler, and RotatingFileHandler, are
#    objects that attach themselves to the 'Observable' object (Logger) in Python.
#    They act as observers responding to changes made by the logger object itself.
#    Handlers are responsible for processing and sending logs to different
#    destinations like screens, files, or remote servers.
# ---------------------------------------------------------------------------------------
# Handlers are registered to the Logger and act as 'listeners'.
# When a logger generates a log message, all associated handlers process it accordingly.
#
# Handlers can handle logs in various ways such as displaying on a console,
# storing them into files or sending via network connections.
#
# Decentralization of logging means the Logger is solely responsible for generating and
# distributing log messages to handlers. Handlers are then appropriate for different
# strategies of processing logs (display on screen, storage in files, sending emails etc.).
#
# This approach allows each part—the logger or handler—to be optimised independently
# according to its specific responsibilities, leading to a flexible and scalable
# logging system that can handle diverse requirements
# ---------------------------------------------------------------------------------------

from typing import Optional
from logging import Formatter, getLogger, Handler, Logger, StreamHandler, NOTSET
from wattleflow.core import ILogger, ISingleton


class AsyncHandler(Handler):
    def __init__(self, queue):
        super().__init__()
        self.queue = queue

    def emit(self, record):
        try:
            self.queue.put_nowait(self.format(record))
        except Exception:
            self.handleError(record)


class AuditLogger(ISingleton, ILogger):
    def __init__(
        self,
        level: int,
        logger: Optional[Logger] = None,
        handler: Optional[Handler] = None,
    ):
        ISingleton.__init__(self)
        ILogger.__init__(self)

        if getattr(self, "_initialized", False):
            return

        self._level: int = level
        self._logger: Logger = logger or getLogger(self.__class__.__name__)
        self._logger.setLevel(self._level)
        # self._logger.propagate = False

        if handler is None:
            handler = StreamHandler()
            handler.setLevel(self._level)
            handler.setFormatter(
                Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
            )

        self.subscribe_handler(handler)
        self._initialized = True

    def _log_msg(self, method, msg: str, *args, **kwargs) -> None:
        # logging-specific keys
        LOG_KW = {"exc_info", "stack_info", "stacklevel", "extra"}
        pass_through = {k: v for k, v in kwargs.items() if k in LOG_KW}
        data = {k: v for k, v in kwargs.items() if k not in LOG_KW}

        if data:
            # key=value; repr
            suffix = ", ".join(f"{k}={repr(v)}" for k, v in data.items())
            msg = f"{msg} | {suffix}"

        method(msg, *args, **pass_through)

    def exception(self, msg: str, *args, **kwargs) -> None:
        kwargs.setdefault("exc_info", True)
        self._log_msg(self._logger.error, msg, *args, **kwargs)

    def critical(self, msg: str, *args, **kwargs) -> None:
        self._log_msg(self._logger.critical, msg, *args, **kwargs)

    def debug(self, msg: str, *args, **kwargs) -> None:
        self._log_msg(self._logger.debug, msg, *args, **kwargs)  # alias

    def error(self, msg: str, *args, **kwargs) -> None:
        self._log_msg(self._logger.error, msg, *args, **kwargs)  # alias

    def fatal(self, msg: str, *args, **kwargs) -> None:
        self._log_msg(self._logger.fatal, msg, *args, **kwargs)  # alias

    def info(self, msg: str, *args, **kwargs) -> None:
        self._log_msg(self._logger.info, msg, *args, **kwargs)  # alias

    def warning(self, msg: str, *args, **kwargs) -> None:
        self._log_msg(self._logger.warning, msg, *args, **kwargs)  # alias

    def subscribe_handler(self, subscriber: Handler) -> None:
        if not isinstance(subscriber, Handler):
            raise TypeError("subscribe_handler: expected logging.Handler")

        # avoid duplicte from same handler
        if subscriber not in self._logger.handlers:
            self._logger.addHandler(subscriber)

    def subscribe(self, observer: Handler) -> None:
        self.subscribe_handler(observer)
