# Module Name: concrete/blackboard.py
# Description: This modul contains concrete blackboard classes.
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2025 WattleFlow
# License: Apache 2 Licence

from abc import ABC
from logging import Handler, NOTSET
from types import MappingProxyType
from typing import (
    Dict,
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


class GenericBlackboard(IBlackboard, AuditLogger, ABC):
    __slots__ = (
        "_canvas",
        "_repositories",
        "_strategy_create",
        "_write_on_flush_only",
    )

    def __init__(
        self,
        strategy_create: StrategyCreate,
        write_on_flush_only: bool = False,
        level: int = NOTSET,
        handler: Optional[Handler] = None,
    ):
        IBlackboard.__init__(self)
        AuditLogger.__init__(self, level=level, handler=handler)

        self.debug(
            msg=Event.Constructor.value,
            strategy_create=strategy_create,
            write_on_flush_only=write_on_flush_only,
            level=level,
            handler=handler,
            # expected_type=getattr(T, "__name__", "Unknown"),
        )

        Attribute.evaluate(self, strategy_create, StrategyCreate)

        self._strategy_create = strategy_create
        self._canvas: Dict[str, ITarget] = {}
        self._repositories: Dict[str, IRepository] = {}
        self._write_on_flush_only = write_on_flush_only

    @property
    def canvas(self) -> Mapping[str, ITarget]:
        return MappingProxyType(self._canvas)  # Read only

    @property
    def count(self) -> int:
        return len(self._canvas)

    @property
    def repositories(self) -> Mapping[str, IRepository]:
        return MappingProxyType(self._repositories)  # Read only

    def _send_to_all_repositories(
        self,
        caller: IWattleflow,
        document: ITarget,
        *args,
        **kwargs,
    ) -> None:
        self.debug(
            msg=Event.Writing.name,
            fnc="_send_to_all_repositories",
            caller=repr(caller.name),
            document=repr(document),
            *args,
            **kwargs,
        )

        for repository in self._repositories.values():
            repository.write(caller=caller, document=document, *args, **kwargs)

    def clear(self):
        self.info(msg="clean")
        self._repositories.clear()
        self._canvas.clear()

    def create(self, caller: IWattleflow, *args, **kwargs) -> Optional[ITarget]:
        self.debug(msg=Event.Creating.value, caller=caller.name, *args, **kwargs)

        Attribute.evaluate(caller=self, target=caller, expected_type=IProcessor)

        if not self._strategy_create:
            self.warning(
                msg=Event.Audit.value, error=f"{self.name}._strategy_create is missing!"
            )
            return None

        return self._strategy_create.create(
            caller=caller, blackboard=self, *args, **kwargs
        )

    def delete(self, caller: IWattleflow, identifier: str) -> None:
        self.debug(msg=Event.Deleting.value, caller=caller.name, identifier=identifier)

        if identifier in self._canvas:
            del self._canvas[identifier]
            self.info(msg=Event.Delete.value, identifier=identifier)
        else:
            self.warning(
                msg=Event.Deleting.value,
                caller=caller.name,
                reason="not in blackboard",
                identifier=identifier,
            )

    def flush(self, caller: IWattleflow, *args, **kwargs) -> None:
        self.debug(
            msg="Flushing canvas to repositories",
            caller=caller,
            count=len(self._canvas),
            *args,
            **kwargs,
        )

        if self._write_on_flush_only:
            for document in self._canvas.values():
                self._send_to_all_repositories(
                    document=document,
                    caller=caller,
                    *args,
                    **kwargs,
                )

        self._canvas.clear()

    def read(self, identifier: str) -> ITarget:
        self.debug(msg=Event.Reading.value, identifier=identifier)

        if identifier not in self._canvas:
            raise ValueError(f"Document {identifier} not found!")

        document: ITarget = self._canvas[identifier]

        return document

    def read_from(
        self,
        repository_name: str,
        identifier: str,
        *args,
        **kwargs,
    ) -> ITarget:
        self.debug(
            msg=Event.Reading.value,
            source=repository_name,
            identifier=identifier,
        )

        repository = self._repositories.get(repository_name)

        if not repository:
            msg = f"Repository {repository_name} not registered!"
            raise ValueError(msg)

        return repository.read(identifier=identifier, *args, **kwargs)

    def register(self, repository: IRepository) -> None:
        self.info(msg=Event.Registering.value, repository=repository.name)

        Attribute.evaluate(self, repository, IRepository)

        if repository.name in self._repositories:
            self.warning(
                msg="Repository already registered!", repository=repository.name
            )
            return

        self._repositories[repository.name] = repository

    def write(self, caller: IWattleflow, document: ITarget, *args, **kwargs) -> str:
        doc = document.request()

        self.debug(
            msg=Event.Writing.value,
            caller=caller.name,
            document=repr(document),
            doc=repr(doc),
            *args,
            **kwargs,
        )

        identifier: str = str(document.request())

        self._canvas[identifier] = document

        self.debug(
            msg=Event.Stored.value,
            document=repr(document),
            flush=self._write_on_flush_only,
        )

        if not self._repositories:
            self.warning(msg="You have no registered repositories.")

        if not self._write_on_flush_only:
            self._send_to_all_repositories(
                caller=caller,
                document=document,
                *args,
                **kwargs,
            )

        return identifier

    def __repr__(self) -> str:
        return f"{self.name}: {self.count}"
