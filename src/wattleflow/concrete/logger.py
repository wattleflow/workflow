# Module Name: concrete/logger.py
# Description: This modul contains audit logger classes.
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
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

from abc import ABC
from typing import Optional
from logging import Formatter, getLogger, Handler, Logger, StreamHandler, NOTSET
from wattleflow.core import ILogger, ISingleton


"""
from asyncio import Queue
from queue import Queue
from concurrent.futures import ThreadPoolExecutor
from logging.handlers import MemoryHandler # QueueHandler, QueueListener, SysLogHandler
class AuditHandler(Handler):
    def __init__(self, target_handler, capacity=10):
        super().__init__()
        self.memory_handler = MemoryHandler(capacity=capacity, target=target_handler)

    def emit(self, record):
        self.memory_handler.emit(record)

class AuditLogger:
    def __init__(self, name: str, level: int):
        super().__init__(name, level)
        self._observers = []

    def add_observer(self, observer: IObserver):
        self._observers.append(observer)

    def remove_observer(self, observer: IObserver):
        self._observers.remove(observer)

    def notify_observers(self):
        for observer in self._observers:
            observer.update(self)

    def log(self, level, msg, *args, **kwargs):
        super().log(level, msg, *args, **kwargs)
        self.notify_observers()

    def get_message(self):
        return "Log message"
"""


class AsyncHandler(Handler):
    def __init__(self, queue):
        super().__init__()
        self.queue = queue

    def emit(self, record):
        try:
            self.queue.put_nowait(self.format(record))
        except Exception:
            self.handleError(record)


class AuditLogger(ISingleton, ILogger, ABC):
    _logger: Optional[Logger] = None
    _level: int = NOTSET

    def __init__(self, level: int, handler: Optional[Handler] = None):
        ISingleton.__init__(self)
        if (
            hasattr(self, "_instances")
            and self.__class__ in self._instances
            and self._logger
        ):
            return

        self._level = level
        self._logger = getLogger(f"[{self.__class__.__name__}]")
        self._logger.setLevel(self._level)

        if not handler:
            handler = StreamHandler()
            handler.formatter = Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )

        self.subscribe(handler)

    def _log_msg(self, method, msg, **kwargs):
        if not kwargs:
            method(msg=msg)
            return

        formatted_items = []
        for k, v in kwargs.items():
            if isinstance(v, (str, int, dict, list, tuple)):
                formatted_items.append(f"{k}: {v}")
            else:
                formatted_items.append(f"{k}: {type(v).__name__}")

        if len(formatted_items) > 0:
            msg += f" {formatted_items}"

        try:
            method(msg=msg)
        except Exception as e:
            print(f"[ERROR] {e}\nmethod:{method}")
            raise

    def critical(self, msg, *args, **kwargs):
        self._log_msg(self._logger.critical, msg, **kwargs)

    def debug(self, msg, *args, **kwargs):
        self._log_msg(self._logger.debug, msg, **kwargs)

    def exception(self, msg, *args, **kwargs):
        self._log_msg(self._logger.exception, msg, **kwargs)

    def error(self, msg, *args, **kwargs):
        self._log_msg(self._logger.error, msg, **kwargs)

    def fatal(self, msg, *args, **kwargs):
        self._log_msg(self._logger.fatal, msg, **kwargs)

    def info(self, msg, *args, **kwargs):
        self._log_msg(self._logger.info, msg, **kwargs)

    def warning(self, msg, *args, **kwargs):
        self._log_msg(self._logger.warning, msg, **kwargs)

    def subscribe(self, subscriber):
        if not isinstance(subscriber, Handler):
            raise TypeError("Only Hanler can be subscriber.")

        self._logger.addHandler(subscriber)
