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
    Singleton - concrete base caching one instance per concrete subclass.

    This is an implementation POLICY, not a contract, and therefore lives in
    the workflow distribution's concrete/ layer, not among the core
    interfaces (DR-COR-003): it fixes caching, locking and init-once semantics
    for every subclass. There is no ISingleton — the pattern declares no
    abstract method, so it has no interface to offer.

    Implements the root identity contract (name) the same way as the
    canonical Wattleflow mixin: derived from the concrete type, immutable.

    Abstract subclasses are never cached (see the inspect.isabstract guard in
    __new__). Construction is thread-safe via a per-subclass lock, and each
    subclass's __init__ runs exactly once for its cached instance (init-once
    guard installed in __init_subclass__).

    Interface:
        __new__(cls, *args, **kwargs) -> cached instance per concrete subclass
        name -> str  (concrete type name)

    Design notes:
      * INIT-ONCE: Python calls __init__ after __new__ on every construction.
        The guard wraps each subclass __init__ so it runs only when the cached
        instance is first built; later constructions return the same instance
        without re-running __init__, so state is not clobbered. Validated in
        tools/singleton_audit.py selftest.
      * The guard is installed via __init_subclass__ (no metaclass surgery),
        preserving whatever metaclass the subclass otherwise uses.
      * Each subclass receives its own _lock, so first construction of
        unrelated singletons does not serialise on one shared lock.
      * The init-once flag is stored as an instance attribute
        (_wf_initialized). A concrete singleton using __slots__ must include
        that slot, or omit __slots__, for the guard to work.
      * PROCESS-GLOBAL MUTABLE STATE: _instances is a module-lifetime registry.
        Consumers with zero-trust requirements must treat any Singleton
        subclass as ambient authority and prefer explicit injection (DR-COR-003).
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
