# Module Name: concrete/blackboard.py
# Description: This modul contains concrete blackboard classes.
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence

from abc import ABC
from uuid import uuid4
from logging import Handler, NOTSET
from typing import (
    Dict,
    Generic,
    # List,
    Optional,
    # Type,
)
from wattleflow.core import IBlackboard, IPipeline, IRepository, IProcessor, T, C
from wattleflow.concrete import Attribute, AuditLogger
from wattleflow.concrete.strategy import StrategyCreate
from wattleflow.constants import Event


# Generic blackboard with write support to multiple repositories
class GenericBlackboard(IBlackboard, Attribute, AuditLogger, Generic[T], ABC):
    def __init__(
        self,
        strategy_create: Optional[StrategyCreate],
        flush_on_write: bool = True,
        level: int = NOTSET,
        handler: Optional[Handler] = None,
    ):
        IBlackboard.__init__(self)
        AuditLogger.__init__(self, level=level, handler=handler)

        self._strategy_create = strategy_create
        if strategy_create:
            self.evaluate(strategy_create, StrategyCreate)

        self._flush_on_write = flush_on_write
        self._storage: Dict[str, T] = {}
        self._repositories: Dict[str, IRepository] = {}

        self.debug(
            msg=Event.Constructor.value,
            expected_type=getattr(T, "__name__", "Unknown"),
            strategy_create=strategy_create,
        )

    @property
    def canvas(self) -> Dict[str, T]:
        return self._storage

    @property
    def count(self) -> int:
        return len(self._storage)

    def clear(self):
        self.info(msg="clean")
        self._repositories.clear()
        self._storage.clear()

    def create(self, processor: IProcessor, *args, **kwargs) -> Optional[T]:
        self.info(msg=Event.Creating.value, processor=processor, *args, **kwargs)

        if not self._strategy_create:
            self.warning(msg=Event.Audit.value, error="Missing self._strategy_create")
            return None

        self.evaluate(processor, IProcessor)

        return self._strategy_create.create(processor, *args, **kwargs)

    def delete(self, identifier: str) -> None:
        self.info(msg=Event.Deleting.value, identifier=identifier)
        if identifier in self._storage:
            del self._storage[identifier]
        else:
            self.warning(
                msg=Event.Deleting.value,
                reason="not in blackboard",
                identifier=identifier,
            )

    def flush(self, caller: C, *args, **kwargs) -> None:
        self.info(
            msg="Flushing blackboard to repositories",
            caller=caller,
            count=len(self._storage),
            *args,
            **kwargs,
        )

        for identifier, item in self._storage.items():
            for repository in self._repositories.values():
                self.debug(
                    msg=Event.Writting.value, to=repository.name, identifier=identifier
                )
                repository.write(item, caller=caller, *args, **kwargs)

        self._storage.clear()

    def read(self, identifier: str) -> Optional[T]:
        self.info(msg=Event.Reading.value, identifier=identifier)
        return self._storage.get(identifier, None)

    def read_from(
        self, repository_name: str, identifier: str, *args, **kwargs
    ) -> Optional[T]:
        self.info(
            msg=Event.Reading.value, source=repository_name, identifier=identifier
        )

        repository = self._repositories.get(repository_name)
        if not repository:
            msg = "Repository {} not registered".format(repository_name)
            self.warning(msg=msg, id=identifier)
            raise ValueError(msg)

        return repository.read(identifier=identifier, *args, **kwargs)

    def register(self, repository: IRepository) -> None:
        self.info(msg=Event.Registering.value, repository=repository.name)

        self.evaluate(repository, IRepository)

        if repository.name in self._repositories:
            msg = "Repository already registered."
            self.warning(msg=msg, repository=repository.name)
            return

        self._repositories[repository.name] = repository

    def write(self, item: T, pipeline: IPipeline, *args, **kwargs) -> str:
        self.info(
            msg=Event.Writting.value,
            item=item,
            pipeline=pipeline,
            *args,
            **kwargs,
        )

        self.evaluate(item, type(item))
        self.evaluate(pipeline, IPipeline)

        identifier = getattr(item, "identifier", str(uuid4().hex))
        self._storage[identifier] = item

        self.debug(
            msg=Event.Stored.value,
            id=identifier,
            item=item,
            pipeline=pipeline.name,
            flush=self._flush_on_write,
        )

        if not len(self._repositories) > 0:
            self.warning(msg="You have no registered repositories.")

        if self._flush_on_write:
            for repository in self._repositories.values():
                # self.debug(msg=Event.Flushing.value,to=repository.name,identifier=identifier)
                repository.write(item=item, caller=pipeline, *args, **kwargs)

        return identifier
