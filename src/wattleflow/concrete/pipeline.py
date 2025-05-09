# Module Name: concrete/pipeline.py
# Description: This modul contains pipeline classes.
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence

from abc import ABC, abstractmethod
from logging import Handler, NOTSET
from typing import Optional
from wattleflow.core import IProcessor, IPipeline
from wattleflow.concrete import AuditLogger
from wattleflow.helpers.attributes import Attributes
from wattleflow.helpers.configuration import Preset


class GenericPipeline(IPipeline, Attributes, AuditLogger, ABC):
    _allowed: list

    def __init__(
        self,
        level: int = NOTSET,
        handler: Optional[Handler] = None,
        *args,
        **kwargs,
    ):
        IPipeline.__init__(self)
        Attributes.__init__(self)
        AuditLogger.__init__(self, level=level, handler=handler)
        self.debug(msg="__init__", level=level, args=args, kwargs=kwargs)

    @abstractmethod
    def process(self, processor: IProcessor, item, *args, **kwargs) -> None:
        self.evaluate(processor, IProcessor)
        if item is None:
            msg = f"{self.name}.process: Received None as item!."
            self.error(msg=msg)
            raise ValueError(msg)

        self.debug(
            msg="process",
            processor=processor.name,
            item=item.identifier if hasattr(item, "identifier") else "unknown",
            kwargs=kwargs,
        )


class GenericPipelineWithPreset(GenericPipeline, Preset, ABC):
    def __init__(
        self,
        level: int = NOTSET,
        handler: Optional[Handler] = None,
        *args,
        **kwargs,
    ):
        IPipeline.__init__(self)
        Attributes.__init__(self)
        AuditLogger.__init__(self, level=level, handler=handler)
        self.debug(msg="__init__", level=level, args=args, kwargs=kwargs)
        self.configure(*args, **kwargs)
