# Module name: pipeline.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2025 WattleFlow. All rights reserved.
# License: Apache 2 Licence


from __future__ import annotations
from abc import ABC, abstractmethod
from logging import Handler, NOTSET
from typing import Any, Optional
from wattleflow.core import IProcessor, IPipeline, ITarget
from wattleflow.concrete import AuditLogger
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
        facade: ITarget,
        *args,
        **kwargs,
    ) -> None:
        self.debug(
            msg=Event.Process.value,
            step=Event.Starting.value,
            processor=processor,
            facade=facade,
            *args,
            **kwargs,
        )

        Attribute.evaluate(caller=self, target=processor, expected_type=IProcessor)
        Attribute.evaluate(caller=self, target=facade, expected_type=ITarget)

    # Must be implemented if using PresetDecorator
    def __getattr__(self, name: str) -> Any:
        preset: PresetDecorator = object.__getattribute__(self, "_preset")
        return preset.__getattr__(name)

    def __repr__(self) -> str:
        return f"{self.name}"
