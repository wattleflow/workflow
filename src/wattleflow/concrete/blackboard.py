# Module Name: core/concrete/blackboard.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence
# Description: This modul contains concrete blackboard classes.

"""
1. Storage Management
    - _storage: Dict[str, T]: Stores objects using a unique identifier.
    - _repositories: List[IRepository]: Keeps track of subscribed repositories.

2. Object Lifecycle
    - create(processor, *args, **kwargs): Uses _strategy_create to create objects.
    - write(pipeline, item, *args, **kwargs): Stores items and forwards them to repositories.
    - delete(identifier): Removes an item from storage.

3. Repository Subscription
    - subscribe(repository): Adds a repository to _repositories.
    - When an item is written, all subscribed repositories receive the item.

4. Access & Cleanup
    - read(identifier): Retrieves an item or raises NotFoundError if missing.
    - clean(): Clears _storage and _repositories.
"""

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
        self._repositories.clear()
        self._storage.clear()

    def create(self, processor: IProcessor, *args, **kwargs) -> T:
        self.evaluate(processor, IProcessor)
        return self._strategy_create.create(processor, *args, **kwargs)

    def delete(self, identifier: str) -> None:
        if identifier in self._storage:
            del self._storage[identifier]
        else:
            print(f"[WARNING] Identifier {identifier} not found in Blackboard.")

    def read(self, identifier: str) -> Optional[T]:
        return self._storage.get(identifier, None)

    def subscribe(self, repository: IRepository) -> None:
        self.evaluate(repository, IRepository)
        self._repositories.append(repository)

    def write(self, pipeline: IPipeline, item: T, *args, **kwargs) -> str:
        self.evaluate(pipeline, IPipeline)
        self.evaluate(item, self._expected_type)

        identifier = getattr(item, "identifier", str(uuid4().hex))
        self._storage[identifier] = item

        valid_repositories = [repo for repo in self._repositories if isinstance(repo, IRepository)]
        for repository in valid_repositories:
            repository.write(pipeline, item, *args, **kwargs)

        return identifier
