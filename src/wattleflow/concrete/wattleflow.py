# Module name: src/wattleflow/concrete/wattleflow.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #
from __future__ import annotations
from wattleflow.core.framework import IWattleflow
from wattleflow.concrete.logger import AuditLogger
# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

__author__ = "WattleFlow"
__copyright__ = "© 2022–2026 WattleFlow. All rights reserved"
__license__ = "Apache 2 Licence"


# --------------------------------------------------------------------------- #
# region Implementation                                                       #
# --------------------------------------------------------------------------- #
class Wattleflow(AuditLogger, IWattleflow):
    """
    Wattleflow - canonical root of every framework object: identity plus audit.

    Identity is derived on access from the concrete type and is therefore
    immutable: no code path can rename an object after construction, which
    keeps __str__-based audit records forgery-resistant (DR-COR-002).

    Auditability is not optional. AuditLogger is inherited here, at the single
    declared point, so every descendant carries it by contract rather than by
    picking it up as a side effect of some other base.

    Concrete framework bases (Generic*, managers, ...) inherit this root first,
    ahead of their pattern interfaces, and never name AuditLogger themselves:
        class GenericProcessor(Wattleflow, IProcessor[Item], ABC): ...

    __init__ opens the cooperative chain: keyword arguments travel down the MRO
    to AuditLogger, so subclasses issue a single super().__init__(**kwargs)
    instead of calling each base by hand.

    Interface:
        name -> str      (concrete type name)
        __str__ -> str   (name)
        __repr__ -> str  (TypeName())
    """

    __slots__ = ()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @property
    def name(self) -> str:
        return type(self).__name__

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"{type(self).__name__}()"


# --------------------------------------------------------------------------- #
# endregion Implementation                                                    #
# --------------------------------------------------------------------------- #
