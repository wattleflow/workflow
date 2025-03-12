# Module Name: strategies/debug.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence
# Description: This modul contains a debug strategies classes.
# NOTE: This is used only for the development.

import datetime
from wattleflow.concrete.attribute import _NC
from wattleflow.concrete.strategy import StrategyWrite

DEBUG = 3


class DebugAuditStrategyWrite(StrategyWrite):
    def __init__(self, *args, **kwargs):
        super().__init__()

    def execute(self, caller, owner, event, *args, **kwargs):
        level = kwargs.get("level", 5)
        if DEBUG >= level:
            __prnt__ = lambda k, v: (
                f"{k}:{v}"
                if isinstance(v, (str, int, bool))
                else f"{k}: {type(v).__name__}"
            )

            print(
                "{} : {} - {} - {} - {}".format(
                    datetime.now(),
                    _NC(caller),
                    _NC(owner),
                    event.value,
                    [__prnt__(k, v) for k, v in kwargs.items()] or None,
                )
            )
        return True
