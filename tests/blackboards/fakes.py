# Module name: tests/blackboards/fakes.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

"""What the blackboard tests share: a text document, its facade, a create strategy and
stand-ins for the pipeline, processor and repository the blackboard checks by interface."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from unittest.mock import Mock, patch

from wattleflow.concrete import Document, DocumentFacade, StrategyCreate
from wattleflow.core import IPipeline, IProcessor, IRepository


class Text(Document[str]):
    __slots__ = ()

    @property
    def size(self) -> int:
        return len(self.content or "")


class Create(StrategyCreate):
    def algorithm(self, caller, **kwargs) -> Any:
        return DocumentFacade(Text("created"))


def facade(content: str = "text", **metadata: Any) -> DocumentFacade:
    document = Text(content)
    for key, value in metadata.items():
        document.update_metadata(key, value)
    return DocumentFacade(document)


def pipeline() -> Mock:
    stub = Mock(spec=IPipeline)
    stub.name = "pipeline"
    return stub


def processor() -> Mock:
    stub = Mock(spec=IProcessor)
    stub.name = "processor"
    return stub


def repository(name: str = "repository", confirms: bool = True) -> Mock:
    stub = Mock(spec=IRepository)
    stub.name = name
    stub.write.return_value = confirms
    return stub


def written(repo: Mock) -> list[str]:
    """Identifiers of the facades a repository was given, in order."""
    return [call.kwargs["facade"].identifier for call in repo.write.call_args_list]


@contextmanager
def warnings_of(cls: type, instance: Any) -> Iterator[list]:
    """Warnings the instance logged; a class-wide patch also catches boards collected meanwhile."""
    calls: list = []
    with patch.object(cls, "warning", autospec=True) as warning:
        yield calls
    calls.extend(call for call in warning.call_args_list if call.args and call.args[0] is instance)
