# Module Name: concrete/pipeline.py
# Description: This modul contains pipeline classes.
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2025 WattleFlow
# License: Apache 2 Licence

from abc import ABC, abstractmethod
from logging import Handler, NOTSET
from typing import Any, Optional
from wattleflow.core import IProcessor, IPipeline, ITarget
from wattleflow.concrete import AuditLogger, AttributeException
from wattleflow.constants import Event
from wattleflow.decorators.preset import PresetDecorator
from wattleflow.helpers import Attribute


class GenericPipeline(IPipeline, AuditLogger, ABC):
    def __init__(
        self,
        level: int = NOTSET,
        handler: Optional[Handler] = None,
        *args,
        **kwargs,
    ):
        IPipeline.__init__(self)
        AuditLogger.__init__(self, level=level, handler=handler)

        self.debug(
            msg=Event.Constructor.value,
            level=level,
            handler=handler,
            *args,
            **kwargs,
        )

        self._preset: PresetDecorator = PresetDecorator(self, **kwargs)

    @abstractmethod
    def process(
        self,
        processor: IProcessor,
        document: ITarget,
        *args,
        **kwargs,
    ) -> None:
        self.debug(
            msg=Event.Process.value,
            step=Event.Starting.value,
            processor=processor,
            document=document,
            *args,
            **kwargs,
        )

        Attribute.evaluate(caller=self, target=processor, expected_type=IProcessor)
        Attribute.evaluate(caller=self, target=document, expected_type=ITarget)

    # Must be implemented if using PresetDecorator
    def __getattr__(self, name: str) -> Any:
        preset: PresetDecorator = object.__getattribute__(self, "_preset")
        return preset.__getattr__(name)

    def __repr__(self) -> str:
        return f"{self.name}"
