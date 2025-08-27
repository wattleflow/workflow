# Module Name: concrete/pipeline.py
# Description: This modul contains pipeline classes.
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2025 WattleFlow
# License: Apache 2 Licence

from abc import ABC, abstractmethod
from logging import Handler, NOTSET
from typing import Optional
from wattleflow.core import IProcessor, IPipeline, ITarget
from wattleflow.concrete import AuditLogger
from wattleflow.constants import Event
from wattleflow.helpers import Attribute, MissingAttribute


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
        from wattleflow.helpers.preset import Preset

        self._preset: Preset = Preset()
        self._preset.configure(caller=self, raise_errors=False, **kwargs)

    @abstractmethod
    def process(
        self,
        processor: IProcessor,
        document: ITarget,
        *args,
        **kwargs,
    ) -> None:
        self.debug(
            msg=Event.Processing.value,
            processor=processor,
            id=getattr(document, "identifier", "unknown"),
            document=document,
            *args,
            **kwargs,
        )

        Attribute.evaluate(caller=self, target=processor, expected_type=IProcessor)

        if document is None:
            msg = f"{self.name!r}.process: document parameter is not assigned!."
            self.error(msg=msg, document=document, **kwargs)
            raise MissingAttribute(caller=self, error=msg)

    def __repr__(self) -> str:
        return f"{self.name}"
