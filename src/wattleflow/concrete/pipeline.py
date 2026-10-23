# Module name: concrete/pipeline.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #

from __future__ import annotations

__all__ = ["GenericPipeline", "PipelineError"]

from abc import ABC, abstractmethod
from logging import Handler, NOTSET
from typing import Any
from wattleflow.core import IProcessor, IPipeline, ITarget
from wattleflow.concrete.base import Wattleflow
from wattleflow.concrete.exception import PipelineException
from wattleflow.concrete.helper import NameHelper
from wattleflow.enums.event import Event
from wattleflow.decorators.preset import PresetDecorator


# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Exceptions                                                           #
# --------------------------------------------------------------------------- #


class PipelineError(PipelineException):
    """What a pipeline raises; one family with the PipelineException the processor raises."""


# --------------------------------------------------------------------------- #
# endregion Exceptions                                                        #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Pipelines                                                            #
# --------------------------------------------------------------------------- #


class GenericPipeline(Wattleflow, IPipeline, ABC):
    __slots__ = ("_preset",)

    def __init__(
        self,
        level: int = NOTSET,
        handler: Handler | None = None,
        **kwargs,
    ):
        super().__init__(level=level, handler=handler, **kwargs)

        self.debug(
            msg=Event.Constructor,
            level=level,
            handler=handler,
            kwargs=kwargs,
        )

        self._preset: PresetDecorator = PresetDecorator(self, **kwargs)

    # region Private
    def __del__(self):
        try:
            object.__getattribute__(self, "_preset")
        except AttributeError:
            return
        try:
            del self._preset
        except Exception as e:
            reason = "%s.__del__ error: %s" % (self.__class__.__name__, type(e).__name__)
            self.error(
                msg=Event.Delete,
                step=Event.Failed,
                reason=reason,
            )

    def __getattr__(self, name: str) -> Any:
        try:
            preset: PresetDecorator = object.__getattribute__(self, "_preset")
        except AttributeError:
            raise AttributeError(name) from None
        return preset.__getattr__(name)

    def __repr__(self) -> str:
        return f"{self.name}"

    # endregion

    @abstractmethod
    def transform(
        self,
        processor: IProcessor,
        facade: ITarget,
        **kwargs,
    ) -> Any: ...

    def process(
        self,
        processor: IProcessor,
        facade: ITarget,
        **kwargs,
    ) -> None:
        self.debug(
            msg=Event.Transform,
            processor=processor,
            facade=facade,
        )
        try:
            if not isinstance(processor, IProcessor):
                raise PipelineError(
                    caller=self, error="Expected IProcessor. Found %s" % type(processor)
                )
            if not isinstance(facade, ITarget):
                raise PipelineError(
                    caller=self, error="Expected ITarget. Found %s" % type(facade)
                )

            self.debug(
                msg=Event.Transform,
                step=Event.Started,
                source=NameHelper.source_name(facade),
                document=getattr(facade, "identifier", None),
            )

            result = self.transform(processor, facade, **kwargs)

            self.debug(
                msg=Event.Transform,
                step=Event.Completed,
                result=result,
            )
        except PipelineError as e:
            self.debug(msg=Event.Transform, step=Event.Failed, error=type(e).__name__)
            raise
        except Exception as e:
            error = "%s.process error: %s" % (self.__class__.__name__, type(e).__name__)
            self.debug(msg=Event.Transform, step=Event.Failed, error=error)
            raise PipelineError(caller=self, error=error) from None


# --------------------------------------------------------------------------- #
# endregion Pipelines                                                         #
# --------------------------------------------------------------------------- #
