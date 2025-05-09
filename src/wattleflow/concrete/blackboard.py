# Module Name: concrete/blackboard.py
# Description: This modul contains concrete blackboard classes.
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence


from uuid import uuid4
from logging import Handler, NOTSET
from typing import (
    Dict,
    Generic,
    List,
    Optional,
    Type,
)
from wattleflow.core import (
    IBlackboard,
    IPipeline,
    IRepository,
    IProcessor,
    T,
)
from wattleflow.concrete import Attribute, AuditLogger
from wattleflow.concrete.strategy import StrategyCreate
from wattleflow.constants import Event


# Generic blackboard with write support to multiple repositories
class GenericBlackboard(IBlackboard, Attribute, AuditLogger, Generic[T]):
    def __init__(
        self,
        expected_type: Type[T],
        strategy_create: StrategyCreate,
        level: int = NOTSET,
        handler: Optional[Handler] = None,
    ):
        IBlackboard.__init__(self)
        AuditLogger.__init__(self, level=level, handler=handler)

        self.evaluate(strategy_create, StrategyCreate)

        self._expected_type = expected_type
        self._strategy_create = strategy_create
        self._storage: Dict[str, T] = {}
        self._repositories: List[IRepository] = []

        self.debug(
            msg=Event.Constructor.value,
            expected_type=expected_type,
            strategy_create=strategy_create,
        )

    def __exit__(self):
        self.debug(msg=Event.Destructor.value)

    @property
    def count(self) -> int:
        return len(self._storage)

    def clean(self):
        self.info(msg="clean")
        self._repositories.clear()
        self._storage.clear()

    def create(self, processor: IProcessor, *args, **kwargs) -> T:
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

    def read(self, identifier: str) -> Optional[T]:
        self.info(msg=Event.Reading.value, identifier=identifier)
        return self._storage.get(identifier, None)

    def register(self, repository: IRepository) -> None:
        self.evaluate(repository, IRepository)
        self.info(msg=Event.Registered.value, repository=repository.name)
        self._repositories.append(repository)

    def write(self, pipeline: IPipeline, item: T, *args, **kwargs) -> str:
        self.evaluate(pipeline, IPipeline)
        self.evaluate(item, self._expected_type)

        self.debug(
            msg=Event.Write.value,
            pipeline=pipeline.name,
            item=item,
            expected_type=self._expected_type,
            **kwargs,
        )

        identifier = getattr(item, "identifier", str(uuid4().hex))
        self._storage[identifier] = item

        self.info(msg=Event.Stored.value, item=item, identifier=identifier, **kwargs)

        for repository in self._repositories:
            self.debug(msg=Event.Writting.value, to=repository.name, **kwargs)
            repository.write(pipeline, item, *args, **kwargs)

        return identifier


# Generic blackboard with only one repository and read and write from it
class GenericBlackboardRW(IBlackboard, Attribute, AuditLogger, Generic[T]):
    def __init__(
        self,
        expected_type: Type[T],
        strategy_create: StrategyCreate,
        level: int = NOTSET,
        handler: Optional[Handler] = None,
    ):
        IBlackboard.__init__(self)
        AuditLogger.__init__(self, level=level, handler=handler)

        self.evaluate(strategy_create, StrategyCreate)

        self._expected_type = expected_type
        self._strategy_create = strategy_create
        self._storage: Dict[str, T] = {}
        self._repository: IRepository = None

        self.debug(
            msg=Event.Constructor.value,
            expected_type=expected_type,
            strategy_create=strategy_create,
        )

    def __exit__(self):
        self.debug(msg=Event.Destructor.value)

    @property
    def count(self) -> int:
        return len(self._storage)

    @property
    def storage(self) -> Dict[str, T]:
        return self._storage

    def clean(self):
        self.info(msg="clean")
        self._repository.clear()
        self._storage.clear()

    def create(self, processor: IProcessor, *args, **kwargs) -> T:
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

    def read(self, identifier: str) -> Optional[T]:
        self.info(msg=Event.Reading.value, identifier=identifier)

        if identifier not in self.storage:
            raise ValueError(f"Item not found: {identifier}")

        if self._repository is None:
            self.warning(msg=Event.Reading.value, error="Repository not assigned!")
            return self.storage[identifier]

        return self._repository.read(
            identifier=identifier, item=self.storage[identifier]
        )

    def register(self, repository: IRepository) -> None:
        self.evaluate(repository, IRepository)
        self.info(msg=Event.Registered.value, repository=repository.name)
        self._repository = repository

    def write(self, pipeline: IPipeline, item: T, *args, **kwargs) -> str:
        self.evaluate(pipeline, IPipeline)
        self.evaluate(item, self._expected_type)

        self.debug(
            msg=Event.Write.value,
            pipeline=pipeline.name,
            item=item,
            expected_type=self._expected_type,
            **kwargs,
        )

        identifier = getattr(item, "identifier", str(uuid4().hex))
        self._storage[identifier] = item

        self.info(msg=Event.Stored.value, item=item, identifier=identifier, **kwargs)
        self.debug(msg=Event.Writting.value, to=self._repository.name, **kwargs)
        self._repository.write(pipeline, item, *args, **kwargs)

        return identifier
