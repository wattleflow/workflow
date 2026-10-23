# Module name: audit/audit.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #
from __future__ import annotations

__all__ = ["GenericAudit"]

import logging
from logging import (
    Formatter,
    getLogger,
    Handler,
    Logger,
    StreamHandler,
)
from threading import RLock
from typing import Any
from wattleflow.audit.filters import ContextFilter
from wattleflow.constants.audit import TARGET_ATTRIBUTE
from wattleflow.core import ILogger, IObserver
from wattleflow.enums.event import Event
from wattleflow.enums.log import LogFormat

# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Classes                                                              #
# --------------------------------------------------------------------------- #


_UNIT_CLOSED: str = Event.Processed


class GenericAudit(ILogger, IObserver):
    __slots__ = ("_level", "_logger", "_handler")

    _lock = RLock()
    _instances: set[type] = set()
    _handlers: dict[str, Handler] = {}
    _observer: Any = None

    def __init__(self, **kwargs):
        super().__init__()

        if "fmt" in kwargs:
            kwargs.setdefault("formatting", kwargs.pop("fmt"))

        formatting: str = kwargs.pop("formatting", LogFormat.DEFAULT.value)
        propagate: bool | None = kwargs.pop("propagate", None)
        logger: Logger | None = kwargs.pop("logger", None)

        requested = kwargs.pop("level", None)
        self._level: int = (
            self._resolve_level(requested) if requested is not None else logging.NOTSET
        )
        self._logger: Logger = logger or getLogger(type(self).__name__)
        self._handler: Handler | None = kwargs.pop("handler", None)

        cls = type(self)

        with self._lock:
            key = self._logger.name

            if self._handler is None:
                self._handler = self._handlers.get(key)

            if self._handler is None:
                self._handler = StreamHandler()
                self._handler.addFilter(ContextFilter())
                self._handler.setLevel(self._level)
                self._handler.setFormatter(Formatter(formatting))

            self._handlers.setdefault(key, self._handler)

            if self._handler not in self._logger.handlers:
                self._logger.addHandler(self._handler)

            if requested is not None:
                self._apply_level(self._level)

            if propagate is not None:
                self._logger.propagate = propagate

            if cls not in self._instances:
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
        self._log_msg(logging.ERROR, msg, *args, **kwargs)

    def critical(self, msg: str, *args, **kwargs) -> None:
        kwargs.setdefault("stacklevel", 3)
        self._log_msg(logging.CRITICAL, msg, *args, **kwargs)

    def debug(self, msg: str, *args, **kwargs) -> None:
        kwargs.setdefault("stacklevel", 3)
        self._log_msg(logging.DEBUG, msg, *args, **kwargs)

    def error(self, msg: str, *args, **kwargs) -> None:
        kwargs.setdefault("stacklevel", 3)
        self._log_msg(logging.ERROR, msg, *args, **kwargs)

    def fatal(self, msg: str, *args, **kwargs) -> None:
        kwargs.setdefault("stacklevel", 3)
        self._log_msg(logging.CRITICAL, msg, *args, **kwargs)

    def info(self, msg: str, *args, **kwargs) -> None:
        kwargs.setdefault("stacklevel", 3)
        self._log_msg(logging.INFO, msg, *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs) -> None:
        kwargs.setdefault("stacklevel", 3)
        self._log_msg(logging.WARNING, msg, *args, **kwargs)

    @classmethod
    def observe(cls, observer: Any) -> Any:
        previous, GenericAudit._observer = GenericAudit._observer, observer
        return previous

    def subscribe_handler(self, subscriber: Handler) -> None:
        if not isinstance(subscriber, Handler):
            raise TypeError("subscribe_handler: expected logging.Handler")
        with self._lock:
            if subscriber not in self._logger.handlers:
                self._logger.addHandler(subscriber)

    def update(self, event: Any, **kwargs) -> None:
        self.info(
            msg=Event.Notify,
            event=getattr(event, "name", str(event)),
            stacklevel=kwargs.pop("stacklevel", 4),
            kwargs=kwargs,
        )

    def _apply_level(self, level: int) -> None:
        self._logger.setLevel(level)
        if self._handler is not None:
            self._handler.setLevel(level)

    def set_level(self, level: int | str) -> None:
        self._level = self._resolve_level(level)
        with self._lock:
            self._apply_level(self._level)

    @classmethod
    def resolve_level(cls, level: int | str) -> int:
        return cls._resolve_level(level)

    @staticmethod
    def _resolve_level(level: int | str) -> int:
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

    def _log_msg(self, level: int, msg: str, /, *args, **kwargs) -> None:
        observer = GenericAudit._observer
        if observer is not None:
            step = kwargs.get("step")
            if step is not None or msg == _UNIT_CLOSED:
                try:
                    observer(self, msg, step, kwargs)
                except Exception:
                    self._logger.exception("Audit observer failed.")

        if not self._logger.isEnabledFor(level):
            return

        def is_frame_like(obj: object) -> bool:
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

        target = data.get("target")
        if target is not None:
            extra = dict(pass_through.get("extra") or {})
            extra.setdefault(TARGET_ATTRIBUTE, str(target))
            pass_through["extra"] = extra

        if data:
            parts = []
            for k, v in data.items():
                if v is None or isinstance(v, (bool, int, float, str)):
                    parts.append(f"{k}={v}")
                elif isinstance(v, (list, tuple, set, dict)) and level == logging.INFO:
                    try:
                        n = len(v)
                    except Exception:
                        n = "?"
                    parts.append(f"{k}=<{type(v).__name__}: {n}>")
                else:
                    parts.append(f"{k}={safe_repr(v)}")
            msg = f"{msg} {parts}"

        self._logger.log(level, msg, *args, **pass_through)

    # --------------------------------------------------------------------------- #
    # endregion Private Methods
    # --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# endregion Classes                                                           #
# --------------------------------------------------------------------------- #
