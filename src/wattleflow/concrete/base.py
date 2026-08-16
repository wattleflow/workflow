# Module name: src/wattleflow/concrete/base.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #
from __future__ import annotations
from wattleflow.core import IWattleflow
from wattleflow.helpers.audit import Audit
# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

__author__ = "WattleFlow"
__copyright__ = "© 2022–2026 WattleFlow. All rights reserved"
__license__ = "Apache 2 Licence"


# --------------------------------------------------------------------------- #
# region Implementation                                                       #
# --------------------------------------------------------------------------- #
class Wattleflow(Audit, IWattleflow):
    """
    Wattleflow - canonical root of every framework object: identity plus audit.

    Identity is derived on access from the concrete type and is therefore
    immutable: no code path can rename an object after construction, which
    keeps __str__-based audit records forgery-resistant (DR-COR-002).

    Auditability is not optional. Audit is inherited here, at the single
    declared point, so every descendant carries it by contract rather than by
    picking it up as a side effect of some other base.

    Concrete framework bases (Generic*, managers, ...) inherit this root first,
    ahead of their pattern interfaces, and never name Audit themselves:
        class GenericProcessor(Wattleflow, IProcessor[Item], ABC): ...

    __init__ opens the cooperative chain and is the single place that splits a
    constructor's keywords: the logging ones go to Audit, the rest stop
    here. Subclasses therefore forward their whole **kwargs unchanged and keep
    the remainder for their own use (PresetDecorator, strategies, ...):

        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self._preset = PresetDecorator(self, **kwargs)

    No subclass pops the logging keywords itself — doing so duplicates the
    split and drifts the moment a logging keyword is added.

    Interface (inherited from Audit, which owns identity — DR-WFL-009):
        name -> str      (concrete type name)
        __str__ -> str   (name)
        __repr__ -> str  (TypeName())
    """

    __slots__ = ()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


# --------------------------------------------------------------------------- #
# endregion Implementation                                                    #
# --------------------------------------------------------------------------- #


__all__ = ["Wattleflow"]
