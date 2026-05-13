# Module name: concrete/pipeline.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #

from __future__ import annotations
from abc import ABC, abstractmethod
from logging import Handler, NOTSET
from typing import Any, Optional
from wattleflow.core import IProcessor, IPipeline, ITarget
from wattleflow.concrete import AuditLogger
from wattleflow.concrete.exception import AuditException
from wattleflow.constants import Event
from wattleflow.decorators.preset import PresetDecorator
from wattleflow.helpers import Attribute

# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Exceptions                                                           #
# --------------------------------------------------------------------------- #


class PipelineError(AuditException):
    pass


# --------------------------------------------------------------------------- #
# endregion Exceptions                                                        #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Pipelines                                                            #
# --------------------------------------------------------------------------- #


class GenericPipeline(IPipeline, AuditLogger, ABC):
    def __init__(
        self,
        level: int = NOTSET,
        handler: Optional[Handler] = None,
        **kwargs,
    ):
        IPipeline.__init__(self)
        AuditLogger.__init__(self, level=level, handler=handler)

        self.debug(
            msg=Event.Constructor.value,
            level=level,
            handler=handler,
            **kwargs,
        )

        self._preset: PresetDecorator = PresetDecorator(self, **kwargs)

    # region Private
    def __del__(self):
        if self._preset:
            try:
                del self._preset
            except Exception as e:
                self.error(msg=Event.Delete.name, preset=self._preset, error=str(e))

    # Must be implemented if using PresetDecorator
    def __getattr__(self, name: str) -> Any:
        preset: PresetDecorator = object.__getattribute__(self, "_preset")
        return preset.__getattr__(name)

    def __repr__(self) -> str:
        return f"{self.name}"

    # endregion

    @abstractmethod
    def process(
        self,
        processor: IProcessor,
        facade: ITarget,
        **kwargs,
    ) -> None:
        self.debug(
            msg=Event.Process.value,
            step=Event.Starting.value,
            processor=processor,
            facade=facade,
            **kwargs,
        )

        Attribute.evaluate(caller=self, target=processor, expected_type=IProcessor)
        Attribute.evaluate(caller=self, target=facade, expected_type=ITarget)


# --------------------------------------------------------------------------- #
# endregion Pipelines                                                         #
# --------------------------------------------------------------------------- #
