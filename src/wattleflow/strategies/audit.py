# Module Name: strategies/audit.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence
# Description: This modul contains concrete audit classes.

from datetime import datetime
from wattleflow.core import IWattleflow
from wattleflow.concrete.strategy import StrategyGenerate
from wattleflow.constants.enums import Event

DEBUG = 4


class StrategyAuditEvent(StrategyGenerate):
    def execute(self, caller: IWattleflow, event: Event, **kwargs) -> None:
        level = kwargs.pop("level", 0)
        if level > DEBUG:
            return None

        timestamp = datetime.now()
        info = (
            [f"{k}: {v}" for k, v in kwargs.items() if len(str(v).strip()) > 0]
            if isinstance(kwargs, dict)
            else kwargs
        )
        info = f"{info}" if len(info) > 0 else info
        name = getattr(caller, "name", caller.__class__.__name__)
        msg = "{} : {} - {} {}".format(timestamp, name, event, info)
        print(msg)


class DebugAuditEvent(StrategyAuditEvent):
    def execute(self, caller, owner, event, *args, **kwargs) -> None:
        level = kwargs.pop("level", 0)
        if DEBUG >= level:
            owner_name = getattr(owner, "__class__", type(owner)).__name__ if owner else "unknown"
            super().execute(caller, event, owner=owner_name, **kwargs)
