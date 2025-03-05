# Module Name: core/concrete/audit.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence
# Description: This modul contains concrete audit classes.

from datetime import datetime
from wattleflow.core import IWattleflow
from wattleflow.concrete.strategy import StrategyGenerate
from wattleflow.constants.enums import Event
from wattleflow.helpers.functions import _NC

DEBUG = 3


class DebugAuditStrategyWrite(StrategyGenerate):
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


class StrategyWriteAuditEvent(StrategyGenerate):
    def execute(self, caller: IWattleflow, event: Event, **kwargs) -> str:
        level = kwargs.pop("level", 0)
        if level > DEBUG:
            return None

        timestamp = datetime.now()
        info = (
            [f"{k}:{v}" for k, v in kwargs.items() if len(str(v).strip()) > 0]
            if isinstance(kwargs, dict)
            else kwargs
        )
        info = f"{info}" if len(info) > 0 else info
        name = getattr(caller, "name", caller.__class__.__name__)
        msg = "{} : {} - {} {}".format(timestamp, name, event, info)
        print(msg)
        return msg


class StrategyWriteAuditEventDebug(StrategyWriteAuditEvent):
    def execute(self, caller, owner, event, *args, **kwargs):
        level = kwargs.pop("level", 0)
        if DEBUG > level:
            return super().generate(caller, owner, event, kwargs)
        return None
