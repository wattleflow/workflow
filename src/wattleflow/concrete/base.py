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
    """See documentation for `IWattleflow` and `Audit`."""

    __slots__ = ()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


# --------------------------------------------------------------------------- #
# endregion Implementation                                                    #
# --------------------------------------------------------------------------- #


__all__ = ["Wattleflow"]
