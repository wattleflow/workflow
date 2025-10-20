# Module Name: concrete/blackboard.py
# Description: This modul contains concrete blackboard classes.
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2025 WattleFlow
# License: Apache 2 Licence

"""
GenericBlackboard
    When using GenericBlackboard you must add CreateStrategy and Repository.

    Methods:
        def __init__(
            self,
            strategy_create: StrategyCreate,
            flush_on_write: bool = False,
            level: int = NOTSET,
            handler: Optional[Handler] = None,
            **kwargs,
        ):
        def clear(self)
        def create(self, caller: IWattleflow, *args, **kwargs) -> Optional[ITarget]
        def delete(self, caller: IWattleflow, identifier: str) -> None
        def flush(self, caller: IWattleflow, *args, **kwargs) -> None
        def read(self, identifier: str) -> ITarget
        def read_from(
            self,
            repository_name: str,
            identifier: str,
            *args,
            **kwargs,
        ) -> ITarget
        def register(self, repository: IRepository) -> None
        def write(self, caller: IWattleflow, document: ITarget, *args, **kwargs) -> str

    Properties:
        @property canvas: Mapping[str, ITarget]
        @property count: int
        @property repositories: Mapping[str, IRepository]
"""
from __future__ import annotations
from abc import ABC
from logging import Handler, NOTSET
from types import MappingProxyType
from typing import (
    Any,
    Dict,
    List,
    Mapping,
    Optional,
)
from wattleflow.core import (
    IBlackboard,
    IRepository,
    IProcessor,
    ITarget,
    IWattleflow,
)
from wattleflow.concrete import AuditLogger
from wattleflow.concrete.strategy import StrategyCreate
from wattleflow.constants import Event
from wattleflow.helpers.attribute import Attribute
from wattleflow.decorators.preset import PresetDecorator


class GenericBlackboard(IBlackboard, AuditLogger, ABC):
    __slots__ = (
        "_canvas",
        "_flushed",
        "_preset",
        "_repositories",
        "_strategy_create",
        "_defer_write_until_flush",
    )

    def __init__(
        self,
        strategy_create: StrategyCreate,
        defer_flush: bool = False,
        level: int = NOTSET,
        handler: Optional[Handler] = None,
        **kwargs,
    ):
        IBlackboard.__init__(self)
        AuditLogger.__init__(self, level=level, handler=handler)

        self.debug(
            msg=Event.Constructor.value,
            step=Event.Started.value,
            strategy_create=strategy_create,
            defer_flush=defer_flush,
            level=level,
            handler=handler,
        )

        Attribute.evaluate(
            caller=self, target=strategy_create, expected_type=StrategyCreate
        )

        self._flushed = False
        self._preset: PresetDecorator = PresetDecorator(self, **kwargs)
        self._strategy_create = strategy_create
        self._canvas: Dict[str, ITarget] = {}
        self._repositories: List[IRepository] = []
        self._defer_write_until_flush = defer_flush

        self.debug(
            msg=Event.Constructor.value,
            step=Event.Completed.value,
            preset=self._preset,
            canvas=self._canvas,
            repositories=self._repositories,
        )

    @property
    def canvas(self) -> Mapping[str, ITarget]:
        return MappingProxyType(self._canvas)  # Read only

    @property
    def count(self) -> int:
        return len(self._canvas)

    @property
    def repositories(self) -> List[IRepository]:
        return self._repositories

    def _emit(
        self,
        caller: IWattleflow,
        document: ITarget,
        *args,
        **kwargs,
    ) -> None:
        """
        Broadcast document to the registered repositories.
        """
        self.debug(
            msg=Event.Emit.value,
            step=Event.Started.value,
            caller=repr(caller.name),
            document=repr(document),
            *args,
            **kwargs,
        )

        for repository in self._repositories:
            repository.write(caller=caller, document=document, *args, **kwargs)
            self._flushed = True

        self.debug(
            msg=Event.Emit.name,
            step=Event.Completed.value,
            broadcasted=True,
            *args,
            **kwargs,
        )

    def clean(self):
        self.debug(
            msg=Event.Clean.value,
            step=Event.Started.value,
            repositories=len(self._repositories),
            canvases=len(self._canvas),
        )
        self._repositories.clear()
        self._canvas.clear()
        self.debug(
            msg=Event.Clean.value,
            step=Event.Completed.value,
            repositories=len(self._repositories),
            canvases=len(self._canvas),
        )

    def create(self, caller: IWattleflow, *args, **kwargs) -> Optional[ITarget]:
        self.debug(
            msg=Event.Create.value,
            step=Event.Started.value,
            caller=caller.name,
            *args,
            **kwargs,
        )

        Attribute.evaluate(caller=self, target=caller, expected_type=IProcessor)

        if not self._strategy_create:
            self.warning(
                msg=Event.Create.value,
                error=f"{self.name}._strategy_create is missing!",
            )
            return None

        self.debug(
            msg=Event.Create.value,
            step=Event.Completed.value,
        )

        return self._strategy_create.create(
            caller=caller, blackboard=self, *args, **kwargs
        )

    def delete(self, caller: IWattleflow, identifier: str) -> None:
        self.debug(
            msg=Event.Delete.value,
            step=Event.Started.value,
            caller=caller.name,
            id=identifier,
        )

        if identifier in self._canvas:
            del self._canvas[identifier]
            self.info(
                msg=Event.Deleted.value,
                identifier=identifier,
            )
        else:
            self.warning(
                msg=Event.Delete.value,
                caller=caller.name,
                reason="The blackboard neither confirms nor denies the existance!",
                identifier=identifier,
            )
        self.debug(
            msg=Event.Delete.value,
            step=Event.Completed.value,
            caller=caller.name,
            id=identifier,
        )

    def flush(self, caller: IWattleflow, *args, **kwargs) -> None:
        self.debug(
            msg=Event.Flush.value,
            step=Event.Started.value,
            caller=caller.name,
            count=len(self._canvas),
            *args,
            **kwargs,
        )

        if self._defer_write_until_flush and not self._flushed:
            for document in self._canvas.values():
                self._emit(
                    document=document,
                    caller=caller,
                    *args,
                    **kwargs,
                )

        self._canvas.clear()
        self.debug(
            msg=Event.Flush.value,
            step=Event.Completed.value,
            caller=caller.name,
            count=len(self._canvas),
            *args,
            **kwargs,
        )

    def read(self, identifier: str) -> ITarget:
        self.debug(
            msg=Event.Read.value,
            step=Event.Started.value,
            identifier=identifier,
        )

        if identifier not in self._canvas:
            raise ValueError(f"Document {identifier} not found!")

        document: ITarget = self._canvas[identifier]

        self.debug(
            msg=Event.Read.value,
            step=Event.Completed.value,
            identifier=identifier,
        )
        return document

    def read_from(
        self,
        repository_name: str,
        identifier: str,
        *args,
        **kwargs,
    ) -> ITarget:
        self.debug(
            msg=Event.Read.value,
            step=Event.Started.value,
            source=repository_name,
            identifier=identifier,
        )

        # repository = self._repositories.get(repository_name)
        repository = None
        for obj in self._repositories:
            if hash(repository) == identifier:
                repository = obj

        if not repository:
            msg = f"Repository {repository_name} not registered!"
            raise ValueError(msg)

        self.debug(
            msg=Event.Read.value,
            step=Event.Completed.value,
            repository=repository,
            identifier=identifier,
        )

        return repository.read(identifier=identifier, *args, **kwargs)

    def register(self, repository: IRepository) -> None:
        self.debug(
            msg=Event.Register.value,
            step=Event.Started.value,
            registering=repository,
        )

        Attribute.evaluate(self, repository, IRepository)

        if repository in self._repositories:
            self.warning(
                msg=Event.Register.value,
                repository=repository,
                error="Repository already registered!",
            )
            return

        self._repositories.append(repository)

        self.debug(
            msg=Event.Register.value,
            step=Event.Completed.value,
            added=repository,
        )

    def write(self, caller: IWattleflow, document: ITarget, *args, **kwargs) -> str:
        self.debug(
            msg=Event.Write.value,
            step=Event.Started.value,
            caller=caller.name,
            document=document,
            *args,
            **kwargs,
        )

        if not getattr(document, "identifier", None):
            raise ValueError(f"Document:{document} is missing identifier!")

        item = document.request()
        self._canvas[item.identifier] = document  # type: ignore

        self.debug(
            msg=Event.Write.value,
            action=Event.Stored.value,
            document=item,
            flush=self._defer_write_until_flush,
        )

        if not self._repositories:
            self.warning(
                msg=Event.Write.value,
                error="No repositories have been registered.",
            )
            return ""

        if not self._defer_write_until_flush:
            self._emit(
                caller=caller,
                document=document,
                *args,
                **kwargs,
            )

        self.debug(
            msg=Event.Write.value,
            step=Event.Completed.value,
            id=item.identifier,  # type: ignore
        )

        return item.identifier  # type: ignore

    # Must be implemented if using PresetDecorator
    def __getattr__(self, name: str) -> Any:
        preset: PresetDecorator = object.__getattribute__(self, "_preset")
        return preset.__getattr__(name)

    def __del__(self):
        self.clean()

    def __repr__(self) -> str:
        return f"{self.name}: {self.count}"
