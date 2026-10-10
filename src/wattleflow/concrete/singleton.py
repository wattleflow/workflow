# Module name: src/wattleflow/concrete/singleton.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #
from __future__ import annotations

__all__ = ["Singleton"]

import functools
import inspect
import threading
import warnings
from wattleflow.core.framework import IWattleflow
# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

__author__ = "WattleFlow"
__copyright__ = "© 2022–2026 WattleFlow. All rights reserved"
__license__ = "Apache 2 Licence"

# --------------------------------------------------------------------------- #
# region Implementation                                                       #
# --------------------------------------------------------------------------- #


class Singleton(IWattleflow):
    """
    One cached instance per concrete subclass.

    Abstract subclasses are never cached; each subclass gets its own lock and
    runs __init__ once, guarded via __init_subclass__ so no metaclass is
    imposed. The guard holds the subclass's init lock for the whole of
    __init__, so a second thread waits for a fully built object instead of
    receiving a half-built one, and an __init__ that raises is retried on the
    next call. Arguments of later calls are ignored, with a RuntimeWarning when
    they differ from the call that initialised the instance. `_instances` is
    process-global mutable state — ambient authority under zero-trust
    (NFRQ-SEC-01).
    """

    # The base declares the init flag, so a subclass with __slots__ needs no extra slot.
    __slots__ = ("_wf_initialized",)

    _instances: dict = {}
    _lock = threading.Lock()  # base lock; each subclass gets its own (see below)
    _init_lock = threading.RLock()  # held for the whole of __init__; each subclass gets its own
    _init_calls: dict = {}  # class -> (args, kwargs) of the call that initialised it
    _initialising = threading.local()  # ids of the instances whose __init__ this thread is in

    @property
    def name(self) -> str:
        return type(self).__name__

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"{type(self).__name__}()"

    @classmethod
    def _note_repeat(cls, args: tuple, kwargs: dict) -> None:
        """A later call carried arguments the first one did not: say so, they are not applied."""
        if not args and not kwargs:
            return
        try:
            same = cls._init_calls.get(cls) == (args, kwargs)
        except Exception:
            same = False  # arguments that cannot be compared are reported, not trusted
        if not same:
            warnings.warn(
                f"{cls.__name__} is already initialised; the arguments of this call are ignored",
                RuntimeWarning,
                stacklevel=4,
            )

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls._lock = threading.Lock()
        cls._init_lock = threading.RLock()
        original = cls.__dict__.get("__init__")
        if original is None or getattr(original, "_wf_singleton_wrapped", False):
            return

        @functools.wraps(original)
        def guarded(self, *args, **kwargs):
            owner = type(self)
            active = Singleton._initialising.__dict__.setdefault("ids", set())
            if id(self) in active:
                # a parent's guarded __init__ reached through super() inside this one:
                # still the same initialisation, so it runs and the outermost call sets the flag
                original(self, *args, **kwargs)
                return
            with owner._init_lock:
                if getattr(self, "_wf_initialized", False):
                    owner._note_repeat(args, kwargs)
                    return
                active.add(id(self))
                try:
                    original(self, *args, **kwargs)
                finally:
                    active.discard(id(self))
                object.__setattr__(self, "_wf_initialized", True)
                Singleton._init_calls[owner] = (args, kwargs)

        guarded._wf_singleton_wrapped = True
        cls.__init__ = guarded

    def __new__(cls, *args, **kwargs):
        if inspect.isabstract(cls):
            return super().__new__(cls)
        if cls not in cls._instances:
            with cls._lock:
                if cls not in cls._instances:
                    cls._instances[cls] = super().__new__(cls)
        return cls._instances[cls]


# --------------------------------------------------------------------------- #
# endregion Implementation                                                    #
# --------------------------------------------------------------------------- #
