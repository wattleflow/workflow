# Module Name: strategies/audit.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence
# Description: This modul contains concrete audit classes.

from logging import Handler, NOTSET
from typing import Optional
from wattleflow.core import IWattleflow, ITarget
from wattleflow.concrete.strategy import StrategyGenerate
from wattleflow.concrete.attribute import _NC
from wattleflow.constants import Event
from wattleflow.concrete.logger import AuditLogger
from wattleflow.helpers import TextStream


class StrategyAuditEvent(StrategyGenerate, AuditLogger):
    def __init__(
        self,
        level: int = NOTSET,
        handler: Optional[Handler] = None,
    ):
        StrategyGenerate.__init__(self, expected_type=ITarget)
        AuditLogger.__init__(self, level=level, handler=handler)

    def execute(self, caller: IWattleflow, event: Event, **kwargs) -> Optional[object]:
        def from_dict(obj) -> str:
            return [f"{k}: {v}" for k, v in obj.items() if len(str(v).strip()) > 0]

        msg = ""
        try:
            info = TextStream()
            if isinstance(kwargs, dict):
                for k, v in kwargs.items():
                    info << k
                    info << ":"
                    if isinstance(v, dict):
                        info << from_dict(v)
                    elif isinstance(v, str):
                        info << v
                    elif isinstance(v, int):
                        info << str(v)
                    elif isinstance(v, IWattleflow):
                        info << _NC(v)
                    else:
                        info << v
            else:
                info << kwargs

            name = getattr(caller, "name", caller.__class__.__name__)
            msg = "{} - {} [{}]".format(name, event, str(info))
            self.logger.info(msg=msg)

        except Exception as e:
            print(e)

        return msg
