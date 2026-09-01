# Module name: src/wattleflow/concrete/singleton.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #
from __future__ import annotations
import functools
import inspect
import threading
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
    One cached instance per concrete subclass (DR-COR-003).

    Abstract subclasses are never cached; each subclass gets its own lock and
    runs __init__ once, guarded via __init_subclass__ so no metaclass is
    imposed. A subclass using __slots__ must include `_wf_initialized` or the
    init-once guard cannot store its flag. `_instances` is process-global
    mutable state — ambient authority under zero-trust (NFRQ-SEC-01).
    """

    _instances: dict = {}
    _lock = threading.Lock()  # base lock; each subclass gets its own (see below)

    @property
    def name(self) -> str:
        return type(self).__name__

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"{type(self).__name__}()"

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls._lock = threading.Lock()
        original = cls.__dict__.get("__init__")
        if original is None or getattr(original, "_wf_singleton_wrapped", False):
            return

        @functools.wraps(original)
        def guarded(self, *args, **kwargs):
            if getattr(self, "_wf_initialized", False):
                return
            original(self, *args, **kwargs)
            object.__setattr__(self, "_wf_initialized", True)

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


__all__ = ["Singleton"]
