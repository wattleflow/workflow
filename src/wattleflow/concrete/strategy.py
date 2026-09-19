# Module name: strategies.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #

from __future__ import annotations
from abc import abstractmethod, ABC
from wattleflow.core import IWattleflow, IStrategy, ITarget
from wattleflow.concrete.base import Wattleflow
# from wattleflow.decorators.measure import measured  # retired, DR-WFL-031 v3

# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Strategies                                                           #
# --------------------------------------------------------------------------- #


# v0.0.1.14 (DR-WFL-031 v3): retired — measurement now observes audit records; kept for the record.
# @measured()
class Strategy(Wattleflow, IStrategy, ABC):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @abstractmethod
    def execute(self, caller: IWattleflow, **kwargs) -> ITarget | None:
        pass


class StrategyGenerate(Strategy, ABC):
    def generate(self, caller: IWattleflow, **kwargs) -> ITarget | None:
        return self.execute(caller=caller, **kwargs)


class StrategyCreate(Strategy, ABC):
    def create(self, caller: IWattleflow, **kwargs) -> ITarget | None:
        return self.execute(caller=caller, **kwargs)


class StrategyRead(Strategy, ABC):
    def read(
        self,
        caller: IWattleflow,
        identifier: str,
        **kwargs,
    ) -> ITarget | None:
        return self.execute(caller=caller, identifier=identifier, **kwargs)


class StrategyWrite(Strategy, ABC):
    def write(self, caller: IWattleflow, facade: ITarget, **kwargs) -> bool:
        return bool(self.execute(caller=caller, facade=facade, **kwargs))


# --------------------------------------------------------------------------- #
# endregion Strategies                                                        #
# --------------------------------------------------------------------------- #


__all__ = [
    "Strategy",
    "StrategyCreate",
    "StrategyGenerate",
    "StrategyRead",
    "StrategyWrite",
]
