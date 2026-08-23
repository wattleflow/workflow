# Module name: helpers/audit.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #
from __future__ import annotations
from enum import Enum
import logging
from logging import (
    Filter,
    Formatter,
    getLogger,
    Handler,
    Logger,
    StreamHandler,
)
from threading import RLock
from typing import Any
from wattleflow.core import ILogger, IObserver
# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Handlers                                                             #
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


# --------------------------------------------------------------------------- #
# endregion Handlers                                                          #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Filters                                                              #
# --------------------------------------------------------------------------- #


class ContextFilter(Filter):
    def filter(self, record):
        record.filename = getattr(record, "src_filename", record.filename)
        record.lineno = getattr(record, "src_lineno", record.lineno)
        return True


# --------------------------------------------------------------------------- #
# endregion Filters                                                           #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Classes                                                              #
# --------------------------------------------------------------------------- #


# Logging format
class LogFormat(Enum):
    DEFAULT = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
    Detailed = "%(asctime)s - %(levelname)s - %(name)s - %(message)s - %(filename)s:%(lineno)d"
    Custom = (
        "%(asctime)s - %(levelname)s - %(name)s - %(message)s - %(src_filename)s:%(src_lineno)d"
    )
    JSON = (
        '{"time": "%(asctime)s", "name": "%(name)s", '
        '"level": "%(levelname)s", "message": "%(message)s"}'
    )


# Terminal link of the cooperative __init__ chain: it consumes the logging
# keywords and swallows the rest, so nothing reaches object.__init__.
class Audit(ILogger, IObserver):
    __slots__ = ("_level", "_logger", "_handler")

    _lock = RLock()
    _instances: set[type] = set()

    def __init__(self, **kwargs):
        super().__init__()

        # `formating` is the original misspelling; still accepted so existing
        # workflow configs and callers keep working.
        legacy: str | None = kwargs.pop("formating", None)
        formatting: str = kwargs.pop("formatting", None) or legacy or LogFormat.DEFAULT.value
        propagate: bool | None = kwargs.pop("propagate", None)
        logger: Logger | None = kwargs.pop("logger", None)

        self._level: int = self._resolve_level(kwargs.pop("level", logging.NOTSET))
        self._logger: Logger = logger or getLogger(type(self).__name__)
        self._handler: Handler | None = kwargs.pop("handler", None)

        cls = type(self)

        with self._lock:
            if cls not in self._instances:
                self._logger.setLevel(self._level)

                if propagate is not None:
                    self._logger.propagate = propagate

                if self._handler is None:
                    self._handler = StreamHandler()
                    self._handler.addFilter(ContextFilter())
                    self._handler.setLevel(self._level)
                    self._handler.setFormatter(Formatter(formatting))

                if self._handler not in self._logger.handlers:
                    self._logger.addHandler(self._handler)

                self._instances.add(cls)
                self._configure_once()

    # Identity lives here, not in the framework root (DR-WFL-009): `subscribe`
    # below formats `name`, and foundation classes need it without importing an
    # upper layer. Derived on access and therefore immutable: nothing can rename
    # an object after construction, which keeps __str__-based audit records
    # forgery-resistant (DR-COR-002).
    @property
    def name(self) -> str:
        return type(self).__name__

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"{type(self).__name__}()"

    @property
    def levelname(self) -> str:
        # Report what actually filters, not what this instance asked for. The
        # logger is configured once per class (see __init__), so a later
        # instance's level never takes effect — reporting it would put a level
        # into audit records that no record was ever filtered by.
        name = logging.getLevelName(self._logger.getEffectiveLevel())
        return name if isinstance(name, str) else "NOTSET"

    def exception(self, msg: str, *args, **kwargs) -> None:
        kwargs.setdefault("exc_info", True)
        kwargs.setdefault("stacklevel", 3)
        self._log_msg(self._logger.error, msg, *args, **kwargs)

    def critical(self, msg: str, *args, **kwargs) -> None:
        kwargs.setdefault("stacklevel", 3)
        self._log_msg(self._logger.critical, msg, *args, **kwargs)

    def debug(self, msg: str, *args, **kwargs) -> None:
        kwargs.setdefault("stacklevel", 3)
        self._log_msg(self._logger.debug, msg, *args, **kwargs)

    def error(self, msg: str, *args, **kwargs) -> None:
        kwargs.setdefault("stacklevel", 3)
        self._log_msg(self._logger.error, msg, *args, **kwargs)

    def fatal(self, msg: str, *args, **kwargs) -> None:
        kwargs.setdefault("stacklevel", 3)
        self._log_msg(self._logger.fatal, msg, *args, **kwargs)

    def info(self, msg: str, *args, **kwargs) -> None:
        kwargs.setdefault("stacklevel", 3)
        self._log_msg(self._logger.info, msg, *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs) -> None:
        kwargs.setdefault("stacklevel", 3)
        self._log_msg(self._logger.warning, msg, *args, **kwargs)

    def subscribe_handler(self, subscriber: Handler) -> None:
        if not isinstance(subscriber, Handler):
            raise TypeError("subscribe_handler: expected logging.Handler")
        with self._lock:
            if subscriber not in self._logger.handlers:
                self._logger.addHandler(subscriber)

    def subscribe(self, observer):
        raise NotImplementedError(f"{self.name}.subscribe is not implemented!")

    def update(self, event: Any, **kwargs) -> None:
        # IObserver end of the sink: an observed event is an audit record.
        # One frame deeper than the level methods, hence stacklevel 4.
        kwargs.setdefault("stacklevel", 4)
        self.info(str(event), **kwargs)

    # --------------------------------------------------------------------------- #
    # region Private Methods
    # --------------------------------------------------------------------------- #

    @staticmethod
    def _resolve_level(level: int | str) -> int:
        # Accept an int directly, or map a name through the public logging API.
        if isinstance(level, int):
            return level
        if isinstance(level, str):
            resolved = logging.getLevelName(level.upper())
            if not isinstance(resolved, int):
                raise ValueError(f"Unknown log level: {level!r}")
            return resolved
        raise TypeError(f"level must be int or str, got {type(level).__name__}")

    def _configure_once(self) -> None:
        pass

    def _log_msg(self, method, msg: str, *args, **kwargs) -> None:
        def is_frame_like(obj: object) -> bool:
            # Frame-like objects (pandas/polars) have huge reprs; show the type
            # name instead. Detected structurally to avoid a third-party import,
            # but the probe must never touch the INSTANCE: hasattr() on a live
            # object runs whatever __getattr__ hook it carries — rdflib
            # namespaces emit a UserWarning for every unknown term, and a lazy
            # proxy would open a connection just to be logged. Scanning the
            # class dicts along the MRO is a plain dict lookup: no descriptor
            # is invoked and no fallback hook fires.
            mro = getattr(type(obj), "__mro__", ())
            return any("shape" in vars(b) for b in mro) and any("columns" in vars(b) for b in mro)

        def safe_repr(obj: object, maxlen: int = 100) -> str:
            try:
                if is_frame_like(obj):
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
                elif isinstance(v, (list, tuple, set, dict)) and (method == self._logger.info):
                    try:
                        n = len(v)
                    except Exception:
                        n = "?"
                    parts.append(f"{k}=<{type(v).__name__}: {n}>")
                else:
                    parts.append(f"{k}={safe_repr(v)}")
            msg = f"{msg} {parts}"

        method(msg, *args, **pass_through)

    # --------------------------------------------------------------------------- #
    # endregion Private Methods
    # --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# endregion Classes                                                           #
# --------------------------------------------------------------------------- #


__all__ = ["AsyncHandler", "Audit", "ContextFilter"]
