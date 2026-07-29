# Module name: src/wattleflow/concrete/wattleflow.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #
from __future__ import annotations
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
class Wattleflow(IWattleflow):
    """
    Wattleflow - canonical identity implementation of IWattleflow.

    Identity is derived on access from the concrete type and is therefore
    immutable: no code path can rename an object after construction, which
    keeps __str__-based audit records forgery-resistant (DR-COR-002). Holds no
    state, declares no __init__, imposes no constructor discipline.

    Concrete framework bases (Generic*, managers, ...) inherit this mixin
    alongside their pattern interfaces, e.g.:
        class GenericProcessor(Wattleflow, IProcessor[Item]): ...

    Interface:
        name -> str      (concrete type name)
        __str__ -> str   (name)
        __repr__ -> str  (TypeName())
    """

    __slots__ = ()

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
