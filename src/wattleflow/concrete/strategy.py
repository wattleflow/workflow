# Module name: strategies.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #

from __future__ import annotations

__all__ = [
    "Strategy",
    "StrategyCreate",
    "StrategyGenerate",
    "StrategyRead",
    "StrategyWrite",
]

from abc import abstractmethod, ABC
from wattleflow.core import IWattleflow, IStrategy, ITarget
from wattleflow.concrete.base import Wattleflow
from wattleflow.concrete.exception import StrategyException
from wattleflow.enums.event import Event

# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Strategies                                                           #
# --------------------------------------------------------------------------- #


class Strategy(Wattleflow, IStrategy, ABC):
    __slots__ = ()

    @abstractmethod
    def algorithm(self, caller: IWattleflow, **kwargs) -> ITarget | None:
        pass

    def _run(self, operation: str, **kwargs):
        """BR-05: ../../../../../documentation/requirements/02-SyRS/SyRS-PTR-root-base.md#7-business-rules"""
        try:
            return self.algorithm(**kwargs)
        except StrategyException:
            raise
        except Exception as e:
            error = "%s.%s error: %s: %s" % (type(self).__name__, operation, type(e).__name__, e)
            self.debug(msg=Event.Executing, step=Event.Failed, operation=operation, error=error)
            raise StrategyException(caller=self, error=error) from None


class StrategyGenerate(Strategy, ABC):
    __slots__ = ()

    def generate(self, caller: IWattleflow, **kwargs) -> ITarget | None:
        return self._run("generate", caller=caller, **kwargs)


class StrategyCreate(Strategy, ABC):
    __slots__ = ()

    def create(self, caller: IWattleflow, **kwargs) -> ITarget | None:
        return self._run("create", caller=caller, **kwargs)


class StrategyRead(Strategy, ABC):
    __slots__ = ()

    def read(
        self,
        caller: IWattleflow,
        identifier: str,
        **kwargs,
    ) -> ITarget | None:
        return self._run("read", caller=caller, identifier=identifier, **kwargs)


class StrategyWrite(Strategy, ABC):
    __slots__ = ()

    def write(self, caller: IWattleflow, facade: ITarget, **kwargs) -> bool:
        return bool(self._run("write", caller=caller, facade=facade, **kwargs))


# --------------------------------------------------------------------------- #
# endregion Strategies                                                        #
# --------------------------------------------------------------------------- #
