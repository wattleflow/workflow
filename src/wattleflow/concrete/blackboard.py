# Module Name: core/concrete/blackboard.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence
# Description: This modul contains concrete blackboard classes.

from uuid import uuid4
from typing import (
    Dict,
    Generic,
    List,
    Optional,
    Type,
    TypeVar,
)
from wattleflow.core import (
    IBlackboard,
    IPipeline,
    IRepository,
    IProcessor,
)
from wattleflow.concrete.attribute import Attribute
from wattleflow.concrete.exception import NotFoundError
from wattleflow.concrete.strategy import StrategyCreate

T = TypeVar("T")


class GenericBlackboard(IBlackboard, Attribute, Generic[T]):
    def __init__(self, expected_type: Type[T], strategy_create: StrategyCreate):
        super().__init__()
        self.evaluate(strategy_create, StrategyCreate)
        self._expected_type = expected_type
        self._strategy_create = strategy_create
        self._storage: Dict[str, T] = {}
        self._repositories: List[IRepository] = []

    @property
    def count(self) -> int:
        return len(self._storage)

    def clean(self):
        if hasattr(self, "_repositories"):
            self._repositories.clear()
        if hasattr(self, "_storage"):
            self._storage.clear()

    def create(self, processor: IProcessor, *args, **kwargs) -> T:
        self.evaluate(processor, IProcessor)
        return self._strategy_create.create(processor, *args, **kwargs)

    def delete(self, identifier: str) -> None:
        if identifier not in self._storage:
            raise NotFoundError(identifier, self._storage)

        del self._storage[identifier]

    def read(self, identifier: str) -> Optional[T]:
        if identifier not in self._storage:
            raise NotFoundError(identifier, self._storage)

        return self._storage.get(identifier, None)

    def subscribe(self, repository: IRepository) -> None:
        self.evaluate(repository, IRepository)
        self._repositories.append(repository)

    def write(self, pipeline: IPipeline, item: T, *args, **kwargs) -> str:
        self.evaluate(pipeline, IPipeline)
        self.evaluate(item, self._expected_type)

        identifier = getattr(item, "identifier", str(uuid4().hex))
        self._storage[identifier] = item

        for repository in self._repositories:
            repository.write(pipeline, item, *args, **kwargs)

        return identifier
