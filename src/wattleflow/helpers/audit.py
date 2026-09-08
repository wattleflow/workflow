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
from wattleflow.enums.event import Event
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
    Detailed = (
        "%(asctime)s - %(levelname)s - %(name)s - %(message)s - %(filename)s:%(lineno)d"
    )
    Custom = "%(asctime)s - %(levelname)s - %(name)s - %(message)s - %(src_filename)s:%(src_lineno)d"
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

        formatting: str = kwargs.pop("formatting", LogFormat.DEFAULT.value)
        propagate: bool | None = kwargs.pop("propagate", None)
        logger: Logger | None = kwargs.pop("logger", None)

        # `None` means the caller said nothing about the level, which is not the
        # same as asking for NOTSET: an instantiation that omits `level=` must not
        # reset a level someone else configured for this class.
        requested = kwargs.pop("level", None)
        self._level: int = (
            self._resolve_level(requested) if requested is not None else logging.NOTSET
        )
        self._logger: Logger = logger or getLogger(type(self).__name__)
        self._handler: Handler | None = kwargs.pop("handler", None)

        cls = type(self)

        with self._lock:
            first = cls not in self._instances

            # An explicit level applies whenever it arrives, not only on the first
            # instance of the class. The logger is shared per class, so keeping the
            # first value made every later `level=` a silent no-op — a setting the
            # caller could pass and the YAML could carry while nothing honoured it.
            # Last explicit writer wins; that is a property of sharing one logger
            # per class, not a defect of the caller.
            if requested is not None:
                self._apply_level(self._level)

            if propagate is not None:
                self._logger.propagate = propagate

            # The default stream handler is built once per class: one per instance
            # would attach a handler per object and multiply every record.
            if self._handler is None and first:
                self._handler = StreamHandler()
                self._handler.addFilter(ContextFilter())
                self._handler.setLevel(self._level)
                self._handler.setFormatter(Formatter(formatting))

            if self._handler is not None and self._handler not in self._logger.handlers:
                self._logger.addHandler(self._handler)

            if first:
                self._instances.add(cls)
                self._configure_once()

    @property
    def name(self) -> str:
        return type(self).__name__

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"{type(self).__name__}()"

    @property
    def levelname(self) -> str:
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
        # IObserver end of the sink: an observed event is an audit record. One
        # frame deeper than the level methods, hence stacklevel 4.
        # v0.0.1.10 (DR-WFL-018 t.3): the observed value is a named field, so a
        # caller key can no longer land in this call's own namespace.
        self.info(
            msg=Event.Notify.name,
            event=getattr(event, "name", str(event)),
            stacklevel=kwargs.pop("stacklevel", 4),
            kwargs=kwargs,
        )

    # --------------------------------------------------------------------------- #
    # region Private Methods
    # --------------------------------------------------------------------------- #

    def _apply_level(self, level: int) -> None:
        """Put `level` on the logger AND on the handlers already attached to it.

        A handler is built once per class, with the level of the FIRST instance,
        and a handler filters independently of its logger. Setting only the
        logger therefore left the first instance's threshold in force, so a
        later `level=` (or a level raised after construction) silently changed
        nothing.
        """
        self._logger.setLevel(level)
        for handler in self._logger.handlers:
            handler.setLevel(level)

    def set_level(self, level: int | str) -> None:
        """Change this component's level after construction.

        Used by a caller that learns the level later than the object — the
        factory reads it from the YAML after its own logger already exists.
        """
        self._level = self._resolve_level(level)
        with self._lock:
            self._apply_level(self._level)

    @classmethod
    def resolve_level(cls, level: int | str) -> int:
        """The level lookup, for a caller configuring a logger it does not own.

        The factory sets the workflow default on the root logger and needs the
        same mapping the constructor applies to `level=`.
        """
        return cls._resolve_level(level)

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
            return any("shape" in vars(b) for b in mro) and any(
                "columns" in vars(b) for b in mro
            )

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

    # --------------------------------------------------------------------------- #
    # endregion Private Methods
    # --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# endregion Classes                                                           #
# --------------------------------------------------------------------------- #


__all__ = ["AsyncHandler", "Audit", "ContextFilter"]
