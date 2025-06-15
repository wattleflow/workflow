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
from wattleflow.core import (
    IBlackboard,
    IPipeline,
    IRepository,
    IProcessor,
    T,
    C
)
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
        if not self._strategy_create:
            self.warning(msg=Event.Audit.value, error="Missing self._strategy_create")
            return None

        self.evaluate(processor, IProcessor)
        self.info(msg=Event.Creating.value, processor=processor.name, **kwargs)
        return self._strategy_create.create(processor, *args, **kwargs)

    def delete(self, identifier: str) -> None:
        self.info(msg=Event.Delete.value, identifier=identifier)
        if identifier in self._storage:
            del self._storage[identifier]
        else:
            self.warning(
                msg=Event.Deleting.value,
                reason="not in blackboard",
                identifier=identifier,
            )

    def flush(self, caller: C, *args, **kwargs) -> None:
        self.info(msg="Flushing blackboard to repositories", count=len(self._storage))

        for identifier, item in self._storage.items():
            for repository in self._repositories.values():
                self.debug(
                    msg=Event.Writting.value, to=repository.name, identifier=identifier
                )
                repository.write(item, caller=caller, *args, **kwargs)

        self._storage.clear()
        self.info(msg="Storage cleared after flush")

    def read(self, identifier: str) -> Optional[T]:
        self.info(msg=Event.Reading.value, identifier=identifier)
        return self._storage.get(identifier, None)

    def read_from(
        self, repository_name: str, identifier: str, *args, **kwargs
    ) -> Optional[T]:
        repository = self._repositories.get(repository_name)
        if not repository:
            self.warning(msg="Repository not found", repository=repository_name)
            raise ValueError(f"Repository '{repository_name}' not registered")

        self.info(
            msg=Event.Reading.value, repository=repository_name, identifier=identifier
        )

        return repository.read(identifier=identifier, *args, **kwargs)

    def register(self, repository: IRepository) -> None:
        self.evaluate(repository, IRepository)

        if repository.name in self._repositories:
            self.warning(
                msg="Overwriting existing repository", repository=repository.name
            )
            return

        self.info(msg=Event.Registered.value, repository=repository.name)
        self._repositories[repository.name] = repository

    def write(self, item: T, pipeline: IPipeline, *args, **kwargs) -> str:
        self.evaluate(item, type(item))
        self.evaluate(pipeline, IPipeline)

        self.debug(
            msg=Event.Write.value,
            pipeline=pipeline.name,
            item=item,
            **kwargs,
        )

        identifier = getattr(item, "identifier", str(uuid4().hex))
        self._storage[identifier] = item

        self.debug(
            msg=Event.Write.value,
            item=item,
            pipeline=pipeline.name,
            flush=self._flush_on_write,
        )

        if self._flush_on_write:
            for repository in self._repositories.values():
                self.debug(
                    msg=Event.Writting.value,
                    to=repository.name,
                    identifier=identifier,
                )
                repository.write(item=item, pipeline=pipeline, *args, **kwargs)

        return identifier
