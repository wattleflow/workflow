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
from wattleflow.concrete.document import DocumentFacade, DummyReadDocument
from wattleflow.concrete.exception import StrategyException
from wattleflow.enums.event import Event
# from wattleflow.decorators.measure import measured  # retired, DR-WFL-031 v3

# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Strategies                                                           #
# --------------------------------------------------------------------------- #


# @measured()
class Strategy(Wattleflow, IStrategy, ABC):
    __slots__ = ("_strict",)

    # def __init__(self, **kwargs):
    #     super().__init__(**kwargs)

    @abstractmethod
    def execute(self, caller: IWattleflow, **kwargs) -> ITarget | None:
        pass


class StrategyGenerate(Strategy, ABC):
    __slots__ = ("_strict",)

    def generate(self, caller: IWattleflow, **kwargs) -> ITarget | None:
        return self.execute(caller=caller, **kwargs)


class StrategyCreate(Strategy, ABC):
    __slots__ = ("_strict",)

    def create(self, caller: IWattleflow, **kwargs) -> ITarget | None:
        return self.execute(caller=caller, **kwargs)


class StrategyRead(Strategy, ABC):
    __slots__ = ("_strict",)

    def read(
        self,
        caller: IWattleflow,
        identifier: str,
        **kwargs,
    ) -> ITarget | None:
        return self.execute(caller=caller, identifier=identifier, **kwargs)


class StrategyWrite(Strategy, ABC):
    __slots__ = ("_strict",)

    def write(self, caller: IWattleflow, facade: ITarget, **kwargs) -> bool:
        return bool(self.execute(caller=caller, facade=facade, **kwargs))


class StrategyReadDummy(StrategyRead):
    __slots__ = ("_document_type", "_strict")

    def __init__(
        self,
        document_type: type | None = None,
        strict: bool = False,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._document_type = document_type
        self._strict = strict

    @property
    def strict(self) -> bool:
        return self._strict

    @property
    def expected(self) -> str:
        return (self._document_type or DummyReadDocument).__name__

    def _build(self, identifier: str) -> object:
        """The configured document type where it accepts the notice, else the placeholder."""
        notice = {
            "notice": DummyReadDocument.NOTICE,
            "identifier": identifier,
            "expected_type": self.expected,
        }
        if self._document_type is not None:
            try:
                return self._document_type(content=notice)
            except (TypeError, ValueError):
                # A document type whose content is not a mapping cannot carry the
                # notice; the placeholder still can, and still declares itself.
                pass
        return DummyReadDocument(identifier=identifier, expected=self.expected)

    def _declare(self, document: object, identifier: str) -> None:
        """Mark the document as a stand-in, whatever type it turned out to be."""
        for key, value in (
            ("implemented", False),
            ("placeholder", DummyReadDocument.NOTICE),
            ("declared_by", type(self).__name__),
            ("expected_type", self.expected),
            ("identifier", identifier),
        ):
            document.update_metadata(key, value)

    def execute(self, caller: IWattleflow, identifier: str = "", **kwargs) -> ITarget:
        # Every call, not once: a stand-in that stops being noticed stops being
        # a declared gap and becomes a silent one.
        self.warning(
            msg=Event.Executing,
            error=DummyReadDocument.NOTICE,
            strategy=type(self).__name__,
            identifier=identifier,
            expected=self.expected,
        )
        document = self._build(identifier)
        self._declare(document, identifier)
        facade = DocumentFacade(document)

        if self._strict:
            failure = StrategyException(
                self, error=f"{DummyReadDocument.NOTICE}: {self.expected}"
            )
            failure.document = facade
            raise failure
        return facade


# --------------------------------------------------------------------------- #
# endregion Strategies                                                        #
# --------------------------------------------------------------------------- #


__all__ = [
    "Strategy",
    "StrategyCreate",
    "StrategyGenerate",
    "StrategyRead",
    "StrategyReadDummy",
    "StrategyWrite",
]
