# Module name: strategies.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #

from __future__ import annotations
from abc import abstractmethod, ABC
from typing import Optional
from wattleflow.core import IWattleflow, IStrategy, ITarget
from wattleflow.concrete.wattleflow import Wattleflow

# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Strategies                                                           #
# --------------------------------------------------------------------------- #


class Strategy(Wattleflow, IStrategy, ABC):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @abstractmethod
    def execute(self, caller: IWattleflow, **kwargs) -> Optional[ITarget]:
        pass


class StrategyGenerate(Strategy, ABC):
    def generate(self, caller: IWattleflow, **kwargs) -> Optional[ITarget]:
        return self.execute(caller=caller, **kwargs)


class StrategyCreate(Strategy, ABC):
    def create(self, caller: IWattleflow, **kwargs) -> Optional[ITarget]:
        return self.execute(caller=caller, **kwargs)


class StrategyRead(Strategy, ABC):
    def read(
        self,
        caller: IWattleflow,
        identifier: str,
        **kwargs,
    ) -> Optional[ITarget]:
        return self.execute(caller=caller, identifier=identifier, **kwargs)


class StrategyWrite(Strategy, ABC):
    def write(self, caller: IWattleflow, facade: ITarget, **kwargs) -> bool:
        return self.execute(caller=caller, facade=facade, **kwargs) is not None


# --------------------------------------------------------------------------- #
# endregion Strategies                                                        #
# --------------------------------------------------------------------------- #
